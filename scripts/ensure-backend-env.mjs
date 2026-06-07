#!/usr/bin/env node

import { constants } from 'node:fs'
import { access, copyFile, readFile } from 'node:fs/promises'
import path from 'node:path'
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

async function ensureBackendEnv() {
  const hasEnv = await pathExists(envPath)
  if (!hasEnv) {
    if (!(await pathExists(examplePath))) {
      throw new Error(`找不到 ${path.relative(rootDir, examplePath)}，无法创建后端 .env。`)
    }
    if (checkOnly) {
      throw new Error('缺少 backend/.env。请运行 pnpm run dev 后在 Web 设置面板中完成环境配置。')
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

  renderBox('ScriptWeaver 环境配置待完成', [
    '开发服务会继续启动，方便你在 Web 产品里完成初始化。',
    '打开工作台后进入「设置 -> 环境配置」填写 DeepSeek API Key。',
    '生产路径不会静态兜底；未配置前 Agent 调用会返回明确错误。',
  ])
}

ensureBackendEnv().catch((error) => {
  console.error(`\x1b[1;31m[env]\x1b[0m ${error instanceof Error ? error.message : String(error)}`)
  process.exit(1)
})
