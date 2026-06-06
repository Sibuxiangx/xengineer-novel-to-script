import { useEffect, useRef } from 'react'
import { LoadingOutlined } from '@ant-design/icons'
import { useEventLog, type SessionEventState } from '../../state/eventLog'
import type { ToolCallEvent } from '../../types'
import './LiveToolStream.css'

const TOOL_LABEL: Record<string, string> = {
  propose_project_title: '推导项目名',
  propose_chapter_split: '推导分章规则',
  build_book_index: '抽取人物 / 地点 / 事件',
  generate_script_yaml: '生成剧本 YAML',
  edit_script_yaml: '局部修改剧本',
}

const LLM_STREAM_TOOL_NAMES = new Set(Object.keys(TOOL_LABEL))

function pickRunningStreamTool(toolCalls: Record<string, ToolCallEvent>): ToolCallEvent | null {
  for (const tool of Object.values(toolCalls)) {
    if (tool.status !== 'running') continue
    if (!LLM_STREAM_TOOL_NAMES.has(tool.name)) continue
    return tool
  }
  return null
}

function streamTextOf(tool: ToolCallEvent | null): string {
  if (!tool) return ''
  return (tool.deltas ?? [])
    .filter((d) => d.delta.kind === 'llm_stream')
    .map((d) => d.delta.content)
    .filter((c): c is string => typeof c === 'string')
    .join('')
}

const TAIL_CHARS = 600

type LiveToolStreamProps = {
  sessionId: string | null
}

export function LiveToolStream({ sessionId }: LiveToolStreamProps) {
  const tool = useEventLog((state) => {
    if (!sessionId) return null
    const session: SessionEventState | undefined = state.bySession[sessionId]
    if (!session) return null
    return pickRunningStreamTool(session.toolCalls)
  })

  const text = streamTextOf(tool)
  const tail = text.length > TAIL_CHARS ? text.slice(-TAIL_CHARS) : text

  const preRef = useRef<HTMLPreElement | null>(null)
  useEffect(() => {
    if (preRef.current) {
      preRef.current.scrollTop = preRef.current.scrollHeight
    }
  }, [tail])

  if (!tool) return null

  const label = TOOL_LABEL[tool.name] ?? tool.name

  return (
    <aside className="sw-live-stream" aria-label="模型推导实时输出">
      <header className="sw-live-stream-head">
        <LoadingOutlined className="sw-live-stream-icon" aria-hidden />
        <span className="sw-live-stream-title">{label}</span>
        <span className="sw-live-stream-sep" aria-hidden>·</span>
        <span className="sw-live-stream-status">推导中…</span>
        <span className="sw-live-stream-count">{text.length.toLocaleString()} 字</span>
      </header>
      {tail ? (
        <pre ref={preRef} className="sw-live-stream-text">
          {tail}
        </pre>
      ) : (
        <p className="sw-live-stream-placeholder">等待模型开始输出…</p>
      )}
    </aside>
  )
}
