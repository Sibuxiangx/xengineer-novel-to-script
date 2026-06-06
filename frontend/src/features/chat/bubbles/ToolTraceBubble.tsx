import { Badge, Card, Space, Tag, Typography } from 'antd'
import {
  BranchesOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import type { ToolCallEvent } from '../../../types'
import { formatDuration } from '../../../lib/formatting'
import { ToolPayloadPreview } from './ToolPayloadPreview'

const { Text } = Typography

type ToolTraceBubbleProps = {
  tool: ToolCallEvent
}

function summarize(tool: ToolCallEvent): string {
  if (tool.status === 'failed') return tool.error_message ?? '工具失败'
  if (tool.status === 'running') return '执行中…'
  const output = tool.output ?? {}
  if ('title' in output) return String(output.title)
  if ('chapter_count' in output) return `${String(output.chapter_count)} 个章节`
  if ('accepted' in output) return output.accepted ? '校验通过' : '校验未通过'
  if ('asset' in output) return `资产更新：${String(output.asset)}`
  if ('confirmation_id' in output) return '已创建确认点'
  if ('repair_attempt_count' in output) {
    const count = String(output.repair_attempt_count ?? 0)
    return `修复 ${count} 次`
  }
  return '已完成'
}

function statusIcon(tool: ToolCallEvent) {
  if (tool.status === 'failed') return <CloseCircleOutlined aria-hidden />
  if (tool.status === 'completed') return <CheckCircleOutlined aria-hidden />
  return <LoadingOutlined aria-hidden />
}

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

function statusBadge(tool: ToolCallEvent) {
  if (tool.status === 'failed') return <Badge status="error" text="失败" />
  if (tool.status === 'completed') return <Badge status="success" text="完成" />
  return <Badge status="processing" text="进行中" aria-live="polite" />
}

export function ToolTraceBubble({ tool }: ToolTraceBubbleProps) {
  return (
    <Card
      size="small"
      title={
        <Space size={8}>
          <BranchesOutlined aria-hidden />
          {statusIcon(tool)}
          <Text strong>{TOOL_LABEL[tool.name] ?? tool.name}</Text>
          <Text type="secondary" className="sw-tool-name-raw">
            {tool.name}
          </Text>
          {tool.duration_ms != null && tool.duration_ms > 0 ? (
            <Tag color="default">{formatDuration(tool.duration_ms)}</Tag>
          ) : null}
          {statusBadge(tool)}
        </Space>
      }
      className={`sw-tool-card ${tool.status === 'running' ? 'is-running' : ''}`}
      variant="borderless"
    >
      <Space orientation="vertical" size={10} style={{ width: '100%' }}>
        <Text type="secondary">{summarize(tool)}</Text>
        <ToolPayloadPreview tool={tool} />
      </Space>
    </Card>
  )
}
