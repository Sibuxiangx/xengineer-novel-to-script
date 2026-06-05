import { useMemo, useState } from 'react'
import { Avatar, Badge, Button, Layout, Popover, Space, Tag, Tooltip, Typography } from 'antd'
import {
  ClockCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  RobotOutlined,
  ThunderboltOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import type { ProjectStatus, RunStatus } from '../types'
import { UsageDigest } from '../features/observability/UsageDigest'
import type { ModelUsagePayload } from '../lib/events'
import './WorkspaceHeader.css'

const { Header } = Layout
const { Text, Title } = Typography

type WorkspaceHeaderProps = {
  title: string
  subtitle: string
  projectStatus: ProjectStatus
  runStatus: RunStatus
  isStreaming: boolean
  modelUsage: ModelUsagePayload[]
}

const statusConfig: Record<
  ProjectStatus,
  { label: string; color: string; icon: React.ReactNode; description: string }
> = {
  idle: {
    label: '等待输入',
    color: 'default',
    icon: <ClockCircleOutlined aria-hidden />,
    description: '等待用户操作',
  },
  uploading: {
    label: '导入中',
    color: 'processing',
    icon: <LoadingOutlined aria-hidden />,
    description: '正在分章并导入章节',
  },
  awaiting: {
    label: '待确认',
    color: 'warning',
    icon: <WarningOutlined aria-hidden />,
    description: '需要用户确认分章',
  },
  generating: {
    label: '生成中',
    color: 'processing',
    icon: <ThunderboltOutlined aria-hidden />,
    description: '正在生成索引或剧本 YAML',
  },
  repairing: {
    label: '修复中',
    color: 'processing',
    icon: <LoadingOutlined aria-hidden />,
    description: 'harness 校验失败，正在自动修复',
  },
  ready: {
    label: '会话待命',
    color: 'blue',
    icon: <ClockCircleOutlined aria-hidden />,
    description: '上一轮已完成，可继续修改或查看资产',
  },
  failed: {
    label: '失败留痕',
    color: 'error',
    icon: <CloseCircleOutlined aria-hidden />,
    description: '生成结果已保留为 rejected draft',
  },
}

export function WorkspaceHeader({
  title,
  subtitle,
  projectStatus,
  runStatus,
  isStreaming,
  modelUsage,
}: WorkspaceHeaderProps) {
  const [usageOpen, setUsageOpen] = useState(false)

  const status = statusConfig[projectStatus]
  const liveLabel = useMemo(() => {
    if (isStreaming) {
      return runStatus === 'waiting_confirmation' ? '等待用户确认' : 'Agent 流式工作中'
    }
    if (runStatus === 'completed') return '待命'
    if (runStatus === 'completed_with_errors') return '上一轮带错误完成'
    if (runStatus === 'failed') return '上一轮失败'
    return '空闲'
  }, [isStreaming, runStatus])

  const totalEstimatedTokens = useMemo(
    () => modelUsage.reduce((sum, item) => sum + item.estimated_input_tokens, 0),
    [modelUsage],
  )

  return (
    <Header className="sw-header" role="banner">
      <div className="sw-header-title">
        <Space size={12} align="center">
          <Avatar size={42} icon={<RobotOutlined aria-hidden />} className="sw-brand-avatar" />
          <div className="sw-header-meta">
            <Title level={4} className="sw-header-name">
              {title}
            </Title>
            <Text type="secondary" className="sw-header-subtitle">
              {subtitle}
            </Text>
          </div>
        </Space>
      </div>

      <div
        className="sw-header-actions"
        role="status"
        aria-live="polite"
        aria-label={`Agent 状态：${liveLabel}`}
      >
        <Space size={8} wrap>
          <Tooltip title={status.description}>
            <Tag color={status.color} icon={status.icon} className="sw-status-tag">
              {status.label}
            </Tag>
          </Tooltip>

          <Badge
            status={isStreaming ? 'processing' : 'default'}
            text={liveLabel}
            className="sw-live-indicator"
          />

          <Popover
            trigger="click"
            open={usageOpen}
            onOpenChange={setUsageOpen}
            placement="bottomRight"
            content={<UsageDigest items={modelUsage} />}
            destroyOnHidden
          >
            <Tooltip title="本会话的模型用量与上下文打包估算">
              <Button
                type="text"
                aria-label="查看用量与上下文估算"
                aria-expanded={usageOpen}
                aria-haspopup="dialog"
              >
                用量 · {totalEstimatedTokens.toLocaleString('zh-CN')}
              </Button>
            </Tooltip>
          </Popover>

        </Space>
      </div>
    </Header>
  )
}
