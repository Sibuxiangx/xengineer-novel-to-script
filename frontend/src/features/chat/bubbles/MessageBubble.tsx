import { Tag, Typography } from 'antd'
import { FileTextOutlined } from '@ant-design/icons'
import { formatDate, formatNumber } from '../../../lib/formatting'
import type { ChatMessage } from '../../../types'

const { Paragraph, Text } = Typography

type MessageBubbleContentProps = {
  message: ChatMessage
}

function sourceAttachment(message: ChatMessage): { fileName: string; textLength: number } | null {
  const attachment = message.metadata?.source_attachment
  if (!attachment || typeof attachment !== 'object' || Array.isArray(attachment)) {
    return null
  }
  const record = attachment as Record<string, unknown>
  if (typeof record.file_name !== 'string') {
    return null
  }
  return {
    fileName: record.file_name,
    textLength: typeof record.text_length === 'number' ? record.text_length : 0,
  }
}

export function MessageBubbleContent({ message }: MessageBubbleContentProps) {
  const attachment = sourceAttachment(message)
  return (
    <div className="sw-bubble-message">
      <Paragraph className="sw-bubble-text" style={{ whiteSpace: 'pre-wrap', margin: 0 }}>
        {message.content}
      </Paragraph>
      {attachment ? (
        <div className="sw-message-attachment">
          <Tag icon={<FileTextOutlined aria-hidden />} className="sw-message-attachment-tag">
            {attachment.fileName}
          </Tag>
          <Text className="sw-message-attachment-meta">
            {formatNumber(attachment.textLength)} 字
          </Text>
        </div>
      ) : null}
      <Text type="secondary" className="sw-bubble-meta">
        {formatDate(message.created_at)}
      </Text>
    </div>
  )
}
