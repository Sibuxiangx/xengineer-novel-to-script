import { Alert, Button, Space, Tag, Typography } from 'antd'
import {
  CheckCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons'

const { Text } = Typography

type RunSummaryProps = {
  variant: 'completed' | 'completed_with_errors'
  message?: string
  rejectedVersionId?: string | null
  repairAttemptCount?: number
  onOpenRejected?: () => void
}

export function RunSummaryBubble({
  variant,
  message,
  rejectedVersionId,
  repairAttemptCount,
  onOpenRejected,
}: RunSummaryProps) {
  if (variant === 'completed') {
    return (
      <Alert
        type="success"
        showIcon
        icon={<CheckCircleOutlined aria-hidden />}
        message={
          <Space>
            <Text strong>本轮已完成</Text>
            <Tag color="success">accepted</Tag>
          </Space>
        }
        description={message ?? '剧本已落库为最新可接受版本。'}
      />
    )
  }
  return (
    <Alert
      type="warning"
      showIcon
      icon={<ExclamationCircleOutlined aria-hidden />}
      message={
        <Space wrap>
          <Text strong>本轮带错误完成</Text>
          <Tag color="warning">rejected draft</Tag>
          {repairAttemptCount != null ? (
            <Tag>修复 {repairAttemptCount} 次</Tag>
          ) : null}
        </Space>
      }
      description={
        <Space orientation="vertical" size={4} style={{ width: '100%' }}>
          <Text>{message ?? '已保留 rejected 草稿，可在右侧资产栏接管修复。'}</Text>
          {rejectedVersionId && onOpenRejected ? (
            <Button size="small" type="link" onClick={onOpenRejected}>
              打开 rejected draft {rejectedVersionId}
            </Button>
          ) : null}
        </Space>
      }
    />
  )
}
