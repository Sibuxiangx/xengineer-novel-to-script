import { Alert, Button, Space, Typography } from 'antd'
import type { ErrorEventPayload } from '../../../lib/events'

const { Text } = Typography

type ErrorBubbleProps = {
  payload: ErrorEventPayload
  onRetry?: () => void
}

export function ErrorBubble({ payload, onRetry }: ErrorBubbleProps) {
  return (
    <Alert
      type="error"
      showIcon
      role="alert"
      message={
        <Space>
          <Text strong>执行失败</Text>
          {payload.code ? <Text type="secondary">[{payload.code}]</Text> : null}
        </Space>
      }
      description={
        <Space orientation="vertical" size={4} style={{ width: '100%' }}>
          <Text>{payload.message}</Text>
          {onRetry ? (
            <Button size="small" type="link" onClick={onRetry}>
              重试上一条消息
            </Button>
          ) : null}
        </Space>
      }
    />
  )
}
