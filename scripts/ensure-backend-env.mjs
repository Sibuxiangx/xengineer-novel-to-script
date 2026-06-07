#!/usr/bin/env node

import { constants } from 'node:fs'
import { access, copyFile, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { createInterface } from 'node:readline/promises'
import { stdin as input, stdout as output } from 'node:process'
import { fileURLToPath } from 'node:url'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const defaultRootDir = path.resolve(scriptDir, '..')
const rootDir = process.env.SCRIPTWEAVER_ENV_ROOT
  ? path.resolve(process.env.SCRIPTWEAVER_ENV_ROOT)
  : defaultRootDir
const backendDir = path.join(rootDir, 'backend')
const envPath = path.join(backendDir, '.env')
const examplePath = path.join(backendDir, '.env.example')
const checkOnly = process.argv.includes('--check-only')

const requiredEnvVars = [
  {
    key: 'DEEPSEEK_API_KEY',
    label: 'DeepSeek API Key',
    description: '用于真实 Agent 调用 DeepSeek 模型，形如 sk-...',
  },
]

function log(message) {
  console.log(`\x1b[1;34m[env]\x1b[0m ${message}`)
}

async function pathExists(targetPath) {
  try {
    await access(targetPath, constants.F_OK)
    return true
  } catch {
    return false
  }
}

function stripQuotes(value) {
  const trimmed = value.trim()
  if (
    (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
    (trimmed.startsWith("'") && trimmed.endsWith("'"))
  ) {
    return trimmed.slice(1, -1)
  }
  return trimmed
}

function parseEnv(content) {
  const values = new Map()
  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim()
    if (!line || line.startsWith('#')) {
      continue
    }
    const match = line.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/)
    if (!match) {
      continue
    }
    values.set(match[1], stripQuotes(match[2] ?? ''))
  }
  return values
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function formatEnvValue(value) {
  if (/^[A-Za-z0-9_./:@+-]+$/.test(value)) {
    return value
  }
  return JSON.stringify(value)
}

function setEnvValue(content, key, value) {
  const line = `${key}=${formatEnvValue(value)}`
  const matcher = new RegExp(`^\\s*${escapeRegExp(key)}\\s*=.*$`, 'm')
  if (matcher.test(content)) {
    return content.replace(matcher, line)
  }
  const separator = content.endsWith('\n') || content.length === 0 ? '' : '\n'
  return `${content}${separator}${line}\n`
}

function renderBox(title, lines) {
  const width = Math.max(title.length + 4, ...lines.map((line) => line.length + 4), 58)
  const border = '─'.repeat(width - 2)
  console.log(`┌${border}┐`)
  console.log(`│ ${title.padEnd(width - 4)} │`)
  console.log(`├${border}┤`)
  for (const line of lines) {
    console.log(`│ ${line.padEnd(width - 4)} │`)
  }
  console.log(`└${border}┘`)
}

async function promptRequiredValues(missingVars) {
  if (!input.isTTY || !output.isTTY) {
    const names = missingVars.map((item) => item.key).join(', ')
    throw new Error(`缺少后端必填环境变量：${names}。请编辑 backend/.env 后重新运行。`)
  }

  renderBox('ScriptWeaver 后端环境变量初始化', [
    '检测到首次运行或必填项为空，需要补齐真实模型调用配置。',
    '输入内容会写入 backend/.env，该文件已被 .gitignore 忽略。',
    '直接 Ctrl+C 可以取消启动。',
  ])

  const rl = createInterface({ input, output })
  const answers = new Map()
  try {
    for (const item of missingVars) {
      console.log(`\n${item.label}`)
      console.log(`  ${item.description}`)
      let answer = ''
      while (!answer.trim()) {
        answer = await rl.question(`请输入 ${item.key}: `)
        if (!answer.trim()) {
          console.log('该项不能为空。')
        }
      }
      answers.set(item.key, answer.trim())
    }
  } finally {
    rl.close()
  }
  return answers
}

async function ensureBackendEnv() {
  const hasEnv = await pathExists(envPath)
  if (!hasEnv) {
    if (!(await pathExists(examplePath))) {
      throw new Error(`找不到 ${path.relative(rootDir, examplePath)}，无法创建后端 .env。`)
    }
    if (checkOnly) {
      throw new Error('缺少 backend/.env。请运行 pnpm run dev 并按提示初始化，或手动复制 .env.example。')
    }
    log('backend/.env not found; copying backend/.env.example')
    await copyFile(examplePath, envPath)
  }

  const content = await readFile(envPath, 'utf8')
  const values = parseEnv(content)
  const missingVars = requiredEnvVars.filter((item) => !values.get(item.key)?.trim())

  if (missingVars.length === 0) {
    log('backend/.env check passed')
    return
  }

  if (checkOnly) {
    const names = missingVars.map((item) => item.key).join(', ')
    throw new Error(`缺少后端必填环境变量：${names}。`)
  }

  const answers = await promptRequiredValues(missingVars)
  let nextContent = content
  for (const [key, value] of answers.entries()) {
    nextContent = setEnvValue(nextContent, key, value)
  }
  if (!nextContent.endsWith('\n')) {
    nextContent += '\n'
  }
  await writeFile(envPath, nextContent, 'utf8')
  log('backend/.env updated')
}

ensureBackendEnv().catch((error) => {
  console.error(`\x1b[1;31m[env]\x1b[0m ${error instanceof Error ? error.message : String(error)}`)
  process.exit(1)
})
