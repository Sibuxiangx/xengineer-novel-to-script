import { useMemo, useState } from 'react'
import { Badge, Button, Popover, Space, Tag, Tooltip, Typography } from 'antd'
import {
  ClockCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  RobotOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import type { ProjectStatus, RunStatus } from '../types'
import { UsageDigest } from '../features/observability/UsageDigest'
import type { ModelUsagePayload } from '../lib/events'
import './WorkspaceStatusBar.css'

const { Text } = Typography

type WorkspaceStatusBarProps = {
  brand: string
  tip: string
  projectStatus: ProjectStatus
  runStatus: RunStatus
  isStreaming: boolean
  modelUsage: ModelUsagePayload[]
  onOpenSettings?: () => void
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
    description: '本地验证失败，正在自动修复',
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

export function WorkspaceStatusBar({
  brand,
  tip,
  projectStatus,
  runStatus,
  isStreaming,
  modelUsage,
  onOpenSettings,
}: WorkspaceStatusBarProps) {
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
    <footer className="sw-status-bar" role="contentinfo">
      <div className="sw-status-bar-brand" aria-label="软件名">
        <RobotOutlined aria-hidden className="sw-status-bar-brand-icon" />
        <Text className="sw-status-bar-brand-name">{brand}</Text>
      </div>

      <div className="sw-status-bar-tip" aria-label="操作引导">
        <Text type="secondary" className="sw-status-bar-tip-text">
          {tip}
        </Text>
      </div>

      <div
        className="sw-status-bar-actions"
        role="status"
        aria-live="polite"
        aria-label={`Agent 状态：${liveLabel}`}
      >
        <Space size={8} wrap={false}>
          <Tooltip title={status.description}>
            <Tag color={status.color} icon={status.icon} className="sw-status-bar-tag">
              {status.label}
            </Tag>
          </Tooltip>

          <Badge
            status={isStreaming ? 'processing' : 'default'}
            text={liveLabel}
            className="sw-status-bar-live"
          />

          <Popover
            trigger="click"
            open={usageOpen}
            onOpenChange={setUsageOpen}
            placement="topRight"
            content={<UsageDigest items={modelUsage} />}
            destroyOnHidden
          >
            <Tooltip title="本会话的模型用量与上下文打包估算">
              <Button
                type="text"
                size="small"
                aria-label="查看用量与上下文估算"
                aria-expanded={usageOpen}
                aria-haspopup="dialog"
                className="sw-status-bar-usage"
              >
                用量 · {totalEstimatedTokens.toLocaleString('zh-CN')}
              </Button>
            </Tooltip>
          </Popover>

          {onOpenSettings ? (
            <Tooltip title="工作台设置">
              <Button
                type="text"
                size="small"
                icon={<SettingOutlined aria-hidden />}
                onClick={onOpenSettings}
                aria-label="打开工作台设置"
                className="sw-status-bar-settings"
              />
            </Tooltip>
          ) : null}
        </Space>
      </div>
    </footer>
  )
}
