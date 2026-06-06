import { Card, Steps, Typography } from 'antd'
import {
  BookOutlined,
  CodeOutlined,
  DatabaseOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons'
import type { ProjectStatus } from '../../types'
import './AssetGuide.css'

const { Text, Paragraph } = Typography

type AssetGuideProps = {
  projectStatus: ProjectStatus
}

const STEPS = [
  {
    title: '识别 & 分章',
    description: 'Agent 推导小说标题、章节切分规则',
    icon: <BookOutlined aria-hidden />,
    statesActive: ['uploading'],
  },
  {
    title: '剧情索引',
    description: '抽取人物、地点、事件，便于跨章引用',
    icon: <DatabaseOutlined aria-hidden />,
    statesActive: ['generating'],
  },
  {
    title: '剧本草稿',
    description: '生成可继续打磨的结构化剧本',
    icon: <CodeOutlined aria-hidden />,
    statesActive: ['generating'],
  },
  {
    title: '本地验证',
    description: '失败会自动修复，留痕 rejected draft',
    icon: <SafetyCertificateOutlined aria-hidden />,
    statesActive: ['repairing'],
  },
]

function currentStepIndex(status: ProjectStatus): number {
  switch (status) {
    case 'uploading':
      return 0
    case 'awaiting':
      return 0
    case 'generating':
      return 2
    case 'repairing':
      return 3
    case 'ready':
    case 'failed':
      return 3
    default:
      return -1
  }
}

export function AssetGuide({ projectStatus }: AssetGuideProps) {
  const current = currentStepIndex(projectStatus)
  const isRunning =
    projectStatus === 'uploading' ||
    projectStatus === 'generating' ||
    projectStatus === 'repairing'

  return (
    <div className="sw-asset-guide" role="region" aria-label="项目资产将出现在这里">
      <Card variant="borderless" className="sw-asset-guide-card">
        <Paragraph strong className="sw-asset-guide-title">
          {isRunning ? 'Agent 正在生成项目资产…' : '上传 TXT 后，这里会出现：'}
        </Paragraph>
        <Paragraph type="secondary" style={{ marginBottom: 12 }}>
          {isRunning
            ? '生成完成后会自动切到对应资产标签，无需手动刷新。'
            : '整个流水线通常 1–3 分钟完成，期间可在对话区跟进 Agent 的思考。'}
        </Paragraph>
        <Steps
          direction="vertical"
          size="small"
          current={current}
          items={STEPS.map((step) => ({
            title: <Text strong>{step.title}</Text>,
            description: step.description,
            icon: step.icon,
          }))}
        />
      </Card>
    </div>
  )
}
