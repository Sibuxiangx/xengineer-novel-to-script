import { Card, Steps, Typography } from 'antd'
import type { RunProgressPayload } from '../../../lib/events'
import { formatDuration } from '../../../lib/formatting'

const { Text } = Typography

type ProgressBubbleProps = {
  events: RunProgressPayload[]
}

const STAGE_LABELS: Record<string, string> = {
  source_ingestion_agent: '识别项目与分章',
  chat_instruction_agent: '处理用户指令',
  import_chapters: '导入章节',
  build_book_index: '构建剧情索引',
  generate_script_yaml: '生成剧本 YAML',
}

export function ProgressBubble({ events }: ProgressBubbleProps) {
  const stageStates = new Map<string, RunProgressPayload[]>()
  for (const event of events) {
    if (!stageStates.has(event.stage)) {
      stageStates.set(event.stage, [])
    }
    stageStates.get(event.stage)!.push(event)
  }

  type StepStatus = 'finish' | 'error' | 'process' | 'wait'
  const items: Array<{ key: string; title: string; description: string; status: StepStatus }> =
    Array.from(stageStates.entries()).map(([stage, list]) => {
      const last = list[list.length - 1]
      const status: StepStatus =
        last.status === 'completed'
          ? 'finish'
          : last.status === 'failed'
            ? 'error'
            : 'process'
      const description =
        last.status === 'completed' && last.duration_ms != null
          ? `用时 ${formatDuration(last.duration_ms)}`
          : last.status === 'failed'
            ? (last.message ?? '失败')
            : '执行中'
      return {
        key: stage,
        title: STAGE_LABELS[stage] ?? stage,
        description,
        status,
      }
    })

  if (items.length === 0) {
    return null
  }

  return (
    <Card
      size="small"
      variant="borderless"
      className="sw-progress-card"
      title={<Text type="secondary">运行进度</Text>}
    >
      <Steps direction="vertical" size="small" items={items} />
    </Card>
  )
}
