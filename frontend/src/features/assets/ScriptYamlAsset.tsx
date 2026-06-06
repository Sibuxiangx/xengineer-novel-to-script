import { useEffect, useRef } from 'react'
import Editor, { type Monaco } from '@monaco-editor/react'
import { Alert, Button, Empty, Skeleton, Space, Tag, Typography } from 'antd'
import { useUiPrefs } from '../../state/uiPrefs'

type MonacoStandaloneEditor = {
  deltaDecorations: (oldIds: string[], newDecorations: MonacoDecoration[]) => string[]
  updateOptions: (options: Record<string, unknown>) => void
}

type MonacoDecoration = {
  range: {
    startLineNumber: number
    startColumn: number
    endLineNumber: number
    endColumn: number
  }
  options: {
    isWholeLine?: boolean
    className?: string
    glyphMarginClassName?: string
    hoverMessage?: { value: string }
  }
}
import { CopyOutlined, DownloadOutlined } from '@ant-design/icons'
import type { ScriptVersion, ValidationReport } from '../../types'
import './ScriptYamlAsset.css'

const { Text, Title, Paragraph } = Typography

type ScriptYamlAssetProps = {
  yaml: string
  loading: boolean
  version: ScriptVersion | null
  validationReport: ValidationReport | null
}

function extractLineFromPath(yaml: string, path: string): number | null {
  if (!path) return null
  const segments = path.split('.').filter(Boolean)
  if (segments.length === 0) return null
  const lines = yaml.split('\n')
  let cursor = 0
  for (const segment of segments) {
    const match = segment.match(/^[a-zA-Z_]+$/)
    if (!match) continue
    const search = `${segment}:`
    while (cursor < lines.length) {
      if (lines[cursor].trimStart().startsWith(search)) {
        break
      }
      cursor += 1
    }
    if (cursor >= lines.length) {
      return null
    }
  }
  return cursor + 1
}

export function ScriptYamlAsset({
  yaml,
  loading,
  version,
  validationReport,
}: ScriptYamlAssetProps) {
  const themeMode = useUiPrefs((state) => state.themeMode)
  const editorRef = useRef<MonacoStandaloneEditor | null>(null)
  const decorationsRef = useRef<string[]>([])

  useEffect(() => {
    const editor = editorRef.current
    if (!editor) return
    const issues = validationReport
      ? [...validationReport.errors, ...validationReport.warnings]
      : []
    const decorations: MonacoDecoration[] = []
    for (const issue of issues) {
      const line = extractLineFromPath(yaml, issue.path)
      if (line == null) continue
      decorations.push({
        range: {
          startLineNumber: line,
          startColumn: 1,
          endLineNumber: line,
          endColumn: 1,
        },
        options: {
          isWholeLine: true,
          className:
            issue.severity === 'warning'
              ? 'sw-monaco-warning-line'
              : 'sw-monaco-error-line',
          glyphMarginClassName:
            issue.severity === 'warning'
              ? 'sw-monaco-warning-glyph'
              : 'sw-monaco-error-glyph',
          hoverMessage: { value: `${issue.code}: ${issue.message}` },
        },
      })
    }
    decorationsRef.current = editor.deltaDecorations(decorationsRef.current, decorations)
    return () => {
      if (editorRef.current && decorationsRef.current.length > 0) {
        editorRef.current.deltaDecorations(decorationsRef.current, [])
        decorationsRef.current = []
      }
    }
  }, [yaml, validationReport])

  if (loading) {
    return <Skeleton active paragraph={{ rows: 8 }} />
  }
  if (!yaml) {
    return (
      <div className="sw-yaml-empty">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <Space orientation="vertical" size={4}>
              <Title level={4} className="sw-yaml-empty-title">
                剧本还没有生成
              </Title>
              <Paragraph type="secondary" className="sw-yaml-empty-copy">
                在右侧对话里上传小说 TXT，并确认分章后，生成的剧本会出现在这里。
              </Paragraph>
            </Space>
          }
        />
      </div>
    )
  }

  function copyYaml() {
    void navigator.clipboard.writeText(yaml)
  }

  function downloadYaml() {
    const blob = new Blob([yaml], { type: 'application/x-yaml' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${version?.id ?? 'script'}.yaml`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  function handleEditorMount(editor: unknown) {
    editorRef.current = editor as MonacoStandaloneEditor
  }

  function handleEditorBeforeMount(monaco: Monaco) {
    monaco.editor.defineTheme('scriptweaver-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [
        { token: '', foreground: 'f2f0eb', background: '0c0c0e' },
        { token: 'string.yaml', foreground: 'e0c56c' },
        { token: 'type.yaml', foreground: 'c9a84c' },
        { token: 'keyword.yaml', foreground: 'f2f0eb' },
        { token: 'number.yaml', foreground: 'd7b45b' },
      ],
      colors: {
        'editor.background': '#0c0c0e',
        'editor.foreground': '#f2f0eb',
        'editorLineNumber.foreground': '#7e776f',
        'editorLineNumber.activeForeground': '#c9a84c',
        'editorCursor.foreground': '#c9a84c',
        'editor.selectionBackground': '#5c4a2288',
        'editor.lineHighlightBackground': '#c9a84c12',
        'editorIndentGuide.background1': '#2b2926',
        'editorIndentGuide.activeBackground1': '#c9a84c66',
        'scrollbarSlider.background': '#f2f0eb22',
        'scrollbarSlider.hoverBackground': '#f2f0eb33',
        'scrollbarSlider.activeBackground': '#c9a84c55',
      },
    })
  }

  return (
    <div className="sw-yaml-wrap">
      <div className="sw-yaml-toolbar">
        <Space size={8} wrap>
          {version ? (
            <>
              <Tag color={version.validation_status === 'accepted' ? 'success' : 'warning'}>
                {version.validation_status}
              </Tag>
              <Text type="secondary">{version.reason}</Text>
            </>
          ) : (
            <Text type="secondary">未选择版本</Text>
          )}
        </Space>
        <Space size={8}>
          <Button
            size="small"
            icon={<CopyOutlined aria-hidden />}
            onClick={copyYaml}
            aria-label="复制 YAML"
          >
            复制
          </Button>
          <Button
            size="small"
            icon={<DownloadOutlined aria-hidden />}
            onClick={downloadYaml}
            aria-label="下载 YAML"
          >
            下载
          </Button>
        </Space>
      </div>
      {version?.validation_status === 'rejected' ? (
        <Alert
          type="warning"
          showIcon
          message="这是 rejected draft，未通过本地验证"
          description="后端没有伪造成功，可在校验 Tab 看错误详情，再让 Agent 修复或自行接管。"
        />
      ) : null}
      <div className="sw-yaml-editor">
        <Editor
          height="100%"
          defaultLanguage="yaml"
          value={yaml}
          theme={themeMode === 'dark' ? 'scriptweaver-dark' : 'vs-light'}
          beforeMount={handleEditorBeforeMount}
          onMount={handleEditorMount}
          options={{
            readOnly: true,
            minimap: { enabled: false },
            fontSize: 13,
            lineHeight: 21,
            scrollBeyondLastLine: false,
            wordWrap: 'on',
            glyphMargin: true,
          }}
        />
      </div>
    </div>
  )
}
