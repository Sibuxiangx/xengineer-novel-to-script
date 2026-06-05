import { useEffect, useMemo, useState } from 'react'
import {
  Button,
  Card,
  Divider,
  Flex,
  Form,
  Input,
  Space,
  Statistic,
  Steps,
  Tag,
  Typography,
} from 'antd'
import { SafetyCertificateOutlined } from '@ant-design/icons'
import type { ChatConfirmation } from '../../../types'
import { formatNumber } from '../../../lib/formatting'

const { Paragraph, Text } = Typography

type LocalPending = 'confirm' | 'cancel' | null

type ConfirmationBubbleProps = {
  confirmation: ChatConfirmation
  ruleDraft: string | undefined
  isStreaming: boolean
  onRuleDraftChange: (confirmationId: string, value: string) => void
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmationBubble({
  confirmation,
  ruleDraft,
  isStreaming,
  onRuleDraftChange,
  onConfirm,
  onCancel,
}: ConfirmationBubbleProps) {
  const rule = confirmation.payload.rule
  const preview = confirmation.payload.preview
  const regexValue = ruleDraft ?? rule.heading_regex ?? ''
  const titlePreview = useMemo(
    () => [...preview.titles.slice(0, 6), ...preview.last_titles.slice(-3)],
    [preview.titles, preview.last_titles],
  )

  const regexFieldId = `confirm-${confirmation.id}-regex`

  const [pendingAction, setPendingAction] = useState<LocalPending>(null)
  useEffect(() => {
    if (!isStreaming) {
      const timeoutId = window.setTimeout(() => setPendingAction(null), 0)
      return () => window.clearTimeout(timeoutId)
    }
    return undefined
  }, [isStreaming])

  const handleConfirm = () => {
    setPendingAction('confirm')
    onConfirm()
  }
  const handleCancel = () => {
    setPendingAction('cancel')
    onCancel()
  }
  const confirmLoading = pendingAction === 'confirm'
  const cancelLoading = pendingAction === 'cancel'
  const buttonsDisabled = isStreaming || pendingAction !== null
  const stepCurrent = confirmLoading ? 3 : 2

  return (
    <Card
      size="small"
      className="sw-confirm-card"
      variant="borderless"
      title={
        <Space>
          <SafetyCertificateOutlined aria-hidden />
          <Text strong>分章确认 · 等待你的决定</Text>
          <Tag color="warning">HITL</Tag>
        </Space>
      }
      role="region"
      aria-label="分章确认面板"
    >
      <Space orientation="vertical" size={14} style={{ width: '100%' }}>
        <Steps
          size="small"
          current={stepCurrent}
          items={[
            { title: '识别项目' },
            { title: '推导分章' },
            { title: confirmLoading ? '已确认' : '等你确认' },
            { title: '导入章节' },
            { title: '生成剧本' },
          ]}
        />

        <Paragraph type="secondary" style={{ marginBottom: 0 }}>
          {confirmation.prompt}
        </Paragraph>

        <Flex gap={12} wrap className="sw-confirm-stats">
          <Statistic
            title="字符数"
            value={formatNumber(confirmation.payload.text_length)}
          />
          <Statistic title="章节数" value={preview.chapter_count} />
          <Statistic title="标题候选" value={preview.candidate_heading_count} />
          <Statistic
            title="疑似漏切"
            value={preview.unmatched_candidate_count}
            valueStyle={{
              color:
                preview.unmatched_candidate_count > 0 ? 'var(--sw-color-warning)' : undefined,
            }}
          />
        </Flex>

        <Divider style={{ margin: '4px 0' }} />

        <Form layout="vertical" component="div">
          <Form.Item
            label="标题匹配正则"
            htmlFor={regexFieldId}
            extra={
              rule.strategy === 'no_chapters'
                ? '当前为单章模式，无需正则'
                : rule.reason
            }
          >
            <Input.TextArea
              id={regexFieldId}
              value={regexValue}
              onChange={(event) => onRuleDraftChange(confirmation.id, event.target.value)}
              autoSize={{ minRows: 2, maxRows: 4 }}
              spellCheck={false}
              disabled={rule.strategy === 'no_chapters'}
              aria-describedby={`${regexFieldId}-hint`}
            />
            <Text id={`${regexFieldId}-hint`} type="secondary" style={{ fontSize: 12 }}>
              修改后点"确认并继续"会按新的规则切分章节。
            </Text>
          </Form.Item>
        </Form>

        <div>
          <Text strong>章节标题预览</Text>
          <Flex gap={8} wrap style={{ marginTop: 8 }}>
            {titlePreview.map((title, index) => (
              <Tag key={`${title}-${index}`} className="sw-title-tag">
                {title || '（空标题）'}
              </Tag>
            ))}
          </Flex>
        </div>

        <Flex gap={8} justify="end" wrap>
          <Button
            disabled={buttonsDisabled}
            loading={cancelLoading}
            onClick={handleCancel}
            aria-label="取消这次分章确认"
          >
            取消
          </Button>
          <Button
            type="primary"
            disabled={buttonsDisabled}
            loading={confirmLoading}
            onClick={handleConfirm}
            aria-label="确认分章并继续生成剧本"
          >
            {confirmLoading ? '正在继续…' : '确认并继续'}
          </Button>
        </Flex>
      </Space>
    </Card>
  )
}
