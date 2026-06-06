import { CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined } from '@ant-design/icons'
import type { ToolCallEvent } from '../../../types'
import { formatDuration } from '../../../lib/formatting'

const TOOL_LABEL: Record<string, string> = {
  propose_project_title: '推导项目名',
  create_project: '创建项目',
  propose_chapter_split: '推导分章规则',
  identify_project: '识别项目',
  infer_chapter_split: '推导分章规则',
  request_chapter_split_confirmation: '请求分章确认',
  confirm_chapter_split: '导入章节',
  import_chapters_from_source: '导入章节',
  build_book_index: '抽取人物 / 地点 / 事件',
  generate_script_yaml: '生成剧本 YAML',
  edit_script_yaml: '局部修改剧本',
  validate_script_yaml: '本地验证',
}

function summarize(tool: ToolCallEvent): string {
  if (tool.status === 'running') return '执行中…'
  if (tool.status === 'failed') return '失败'
  const out = tool.output ?? {}
  if ('title' in out) return String(out.title)
  if ('chapter_count' in out && 'character_count' in out)
    return `${String(out.chapter_count)} 章 · ${String(out.character_count)} 人`
  if ('chapter_count' in out) return `${String(out.chapter_count)} 个章节`
  if ('character_count' in out && 'location_count' in out)
    return `${String(out.character_count)} 人 · ${String(out.location_count)} 地点`
  if ('accepted' in out) return out.accepted ? '校验通过' : '校验未通过'
  if ('asset' in out) return '资产已更新'
  if ('confirmation_id' in out) return '已创建分章确认点'
  if ('operation_count' in out) return `${String(out.operation_count)} 项操作`
  return '完成'
}

type ToolStepLineProps = {
  tool: ToolCallEvent
}

export function ToolStepLine({ tool }: ToolStepLineProps) {
  const isRunning = tool.status === 'running'
  const isFailed = tool.status === 'failed'
  const label = TOOL_LABEL[tool.name] ?? tool.name
  const summary = summarize(tool)

  return (
    <div
      className={`sw-tool-step${isRunning ? ' is-running' : ''}${isFailed ? ' is-failed' : ''}`}
      aria-live={isRunning ? 'polite' : undefined}
    >
      <div className="sw-tool-step-header">
        <span className="sw-tool-step-icon" aria-hidden>
          {isRunning && <LoadingOutlined />}
          {!isRunning && !isFailed && <CheckCircleOutlined />}
          {isFailed && <CloseCircleOutlined />}
        </span>
        <span className="sw-tool-step-label">{label}</span>
        <span className="sw-tool-step-sep" aria-hidden>·</span>
        <span className="sw-tool-step-summary">{summary}</span>
        {!isRunning && tool.duration_ms != null && tool.duration_ms > 0 && (
          <span className="sw-tool-step-duration">{formatDuration(tool.duration_ms)}</span>
        )}
      </div>

      {isFailed && tool.error_message && (
        <details className="sw-tool-step-details">
          <summary>错误详情</summary>
          <pre className="sw-tool-step-error">{tool.error_message}</pre>
        </details>
      )}
    </div>
  )
}
