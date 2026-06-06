import { useEffect, useMemo, useState } from 'react'
import {
  Button,
  Divider,
  Flex,
  Form,
  Input,
  Modal,
  Space,
  Statistic,
  Steps,
  Tag,
  Typography,
} from 'antd'
import { BulbOutlined } from '@ant-design/icons'
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
  const regexFieldId = `confirm-${confirmation.id}-regex`

  const titlePreview = useMemo(
    () => [...preview.titles.slice(0, 6), ...preview.last_titles.slice(-3)],
    [preview.titles, preview.last_titles],
  )

  const [modalOpen, setModalOpen] = useState(false)
  const [pendingAction, setPendingAction] = useState<LocalPending>(null)

  useEffect(() => {
    if (!isStreaming) {
      const id = window.setTimeout(() => setPendingAction(null), 0)
      return () => window.clearTimeout(id)
    }
    return undefined
  }, [isStreaming])

  const confirmLoading = pendingAction === 'confirm'
  const cancelLoading = pendingAction === 'cancel'
  const buttonsDisabled = isStreaming || pendingAction !== null
  const stepCurrent = confirmLoading ? 3 : 2

  const handleConfirm = () => {
    setPendingAction('confirm')
    setModalOpen(false)
    onConfirm()
  }
  const handleCancel = () => {
    setPendingAction('cancel')
    setModalOpen(false)
    onCancel()
  }

  return (
    <>
      <div className="sw-confirm-callout" role="region" aria-label="分章确认提示">
        <div className="sw-confirm-callout-body">
          <BulbOutlined className="sw-confirm-callout-icon" aria-hidden />
          <Paragraph className="sw-confirm-callout-text">
            已推导出 <strong>{preview.chapter_count}</strong> 章分章规则，共{' '}
            <strong>{formatNumber(confirmation.payload.text_length)}</strong> 字。
            请确认后继续生成剧本。
          </Paragraph>
        </div>
        <Flex gap={8}>
          <Button
            type="primary"
            size="small"
            disabled={buttonsDisabled}
            loading={confirmLoading}
            onClick={() => setModalOpen(true)}
            aria-label="查看分章规则并确认"
          >
            {confirmLoading ? '正在继续…' : '查看分章并确认'}
          </Button>
          <Button
            size="small"
            disabled={buttonsDisabled}
            loading={cancelLoading}
            onClick={handleCancel}
            aria-label="取消这次分章确认"
          >
            取消
          </Button>
        </Flex>
      </div>

      <Modal
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        title="确认分章规则"
        footer={
          <Flex gap={8} justify="end">
            <Button onClick={() => setModalOpen(false)}>先不确认</Button>
            <Button type="primary" loading={confirmLoading} onClick={handleConfirm}>
              确认并继续
            </Button>
          </Flex>
        }
        width={560}
        destroyOnHidden
      >
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Steps
            size="small"
            current={stepCurrent}
            items={[
              { title: '识别项目' },
              { title: '推导分章' },
              { title: '等你确认' },
              { title: '导入章节' },
              { title: '生成剧本' },
            ]}
          />

          <Paragraph type="secondary" style={{ marginBottom: 0 }}>
            {confirmation.prompt}
          </Paragraph>

          <Flex gap={12} wrap>
            <Statistic title="字符数" value={formatNumber(confirmation.payload.text_length)} />
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
              label="标题匹配正则（可选修改）"
              htmlFor={regexFieldId}
              extra={rule.strategy === 'no_chapters' ? '当前为单章模式，无需正则' : rule.reason}
            >
              <Input.TextArea
                id={regexFieldId}
                value={regexValue}
                onChange={(e) => onRuleDraftChange(confirmation.id, e.target.value)}
                autoSize={{ minRows: 2, maxRows: 4 }}
                spellCheck={false}
                disabled={rule.strategy === 'no_chapters'}
              />
              <Text type="secondary" style={{ fontSize: 12 }}>
                修改后点"确认并继续"会按新规则切分章节。
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
        </Space>
      </Modal>
    </>
  )
}
