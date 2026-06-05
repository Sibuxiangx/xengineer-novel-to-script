import { useMemo, type ClipboardEvent } from 'react'
import { Attachments, Sender, Suggestion } from '@ant-design/x'
import { Button, Tag, Tooltip, Typography, type UploadFile } from 'antd'
import {
  CloseCircleOutlined,
  FileTextOutlined,
  InboxOutlined,
  LoadingOutlined,
  PaperClipOutlined,
  SendOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons'
import { formatNumber } from '../../lib/formatting'
import './ChatComposer.css'

const { Text } = Typography

const SUGGESTIONS = [
  { value: '@加人物 ', label: '@加人物' },
  { value: '@删场景 ', label: '@删场景' },
  { value: '@合并场景 ', label: '@合并场景' },
  { value: '@重排场景 ', label: '@重排场景' },
  { value: '@重新生成本场 ', label: '@重新生成本场' },
  { value: '@修改改编说明 ', label: '@修改改编说明' },
]

type ChatComposerProps = {
  message: string
  onMessageChange: (value: string) => void
  onSubmit: (value: string) => void
  isStreaming: boolean
  disabled?: boolean
  attachmentOpen: boolean
  onToggleAttachment: () => void
  sourceText: string
  sourceFileName: string
  onSourceTextChange: (text: string, fileName?: string) => void
  onSourceClear: () => void
  onLoadDemo?: () => void
}

export function ChatComposer({
  message,
  onMessageChange,
  onSubmit,
  isStreaming,
  disabled,
  attachmentOpen,
  onToggleAttachment,
  sourceText,
  sourceFileName,
  onSourceTextChange,
  onSourceClear,
  onLoadDemo,
}: ChatComposerProps) {
  const hasSource = Boolean(sourceText)
  const placeholder = hasSource
    ? '补充改编要求或直接发送（Enter 发送）'
    : '描述你想如何改编，或先点回形针上传小说 TXT'

  const items: UploadFile[] = useMemo(
    () =>
      hasSource
        ? [
            {
              uid: 'source-text',
              name: sourceFileName,
              status: 'done' as const,
              size: new Blob([sourceText]).size,
              type: 'text/plain',
              percent: 100,
            },
          ]
        : [],
    [hasSource, sourceText, sourceFileName],
  )

  function handlePaste(event: ClipboardEvent<HTMLElement>) {
    const text = event.clipboardData.getData('text')
    if (text.length > 1200 && !hasSource) {
      event.preventDefault()
      onSourceTextChange(text, 'pasted-novel.txt')
    }
  }

  // 已上传时默认折叠 panel，但保留 paperclip 入口可重新展开（更换文件）
  const showPanel = attachmentOpen && !hasSource

  return (
    <div className="sw-composer" role="region" aria-label="消息输入区">
      {hasSource ? (
        <div className="sw-source-chip" role="status" aria-live="polite">
          <Tag
            icon={<FileTextOutlined aria-hidden />}
            color="processing"
            className="sw-source-chip-tag"
          >
            {sourceFileName}
          </Tag>
          <Text type="secondary" className="sw-source-chip-meta">
            {formatNumber(sourceText.length)} 字 · 已附到下一条消息
          </Text>
          <Button
            size="small"
            type="text"
            icon={<CloseCircleOutlined aria-hidden />}
            onClick={onSourceClear}
            aria-label="移除已上传的小说附件"
          >
            移除
          </Button>
        </div>
      ) : null}

      <Suggestion
        items={SUGGESTIONS}
        onSelect={(value) => onMessageChange(`${message}${value}`)}
      >
        {({ onTrigger, onKeyDown }) => (
          <Sender
            value={message}
            loading={isStreaming}
            disabled={disabled}
            placeholder={placeholder}
            autoSize={{ minRows: 2, maxRows: 6 }}
            submitType="enter"
            onChange={(value) => {
              onMessageChange(value)
              if (value.endsWith('@')) {
                onTrigger()
              } else {
                onTrigger(false)
              }
            }}
            onSubmit={onSubmit}
            onPaste={handlePaste}
            onKeyDown={onKeyDown}
            onPasteFile={(files) => {
              const file = files.item(0)
              if (file) {
                file.text().then((text) => onSourceTextChange(text, file.name))
              }
            }}
            prefix={
              <Tooltip title={hasSource ? '更换附件' : '上传或粘贴小说 TXT'}>
                <Button
                  type={hasSource ? 'primary' : 'text'}
                  icon={<PaperClipOutlined aria-hidden />}
                  onClick={onToggleAttachment}
                  aria-label={
                    hasSource
                      ? '更换已上传的小说附件'
                      : showPanel
                        ? '收起上传面板'
                        : '展开上传面板'
                  }
                  aria-expanded={showPanel}
                />
              </Tooltip>
            }
            suffix={
              <Tooltip title={isStreaming ? 'Agent 正在执行' : '发送消息'}>
                <Button
                  type="primary"
                  shape="circle"
                  icon={
                    isStreaming ? (
                      <LoadingOutlined aria-hidden />
                    ) : (
                      <SendOutlined aria-hidden />
                    )
                  }
                  disabled={isStreaming || (!message.trim() && !hasSource)}
                  onClick={() => onSubmit(message)}
                  aria-label="发送消息"
                />
              </Tooltip>
            }
            header={
              showPanel ? (
                <Sender.Header
                  title="上传小说原文"
                  open={true}
                  onOpenChange={onToggleAttachment}
                >
                  <div className="sw-composer-header">
                    <Attachments
                      accept=".txt,text/plain"
                      maxCount={1}
                      items={items}
                      beforeUpload={(file) => {
                        file.text().then((text) => onSourceTextChange(text, file.name))
                        return false
                      }}
                      onRemove={() => {
                        onSourceClear()
                        return true
                      }}
                      placeholder={{
                        icon: <InboxOutlined aria-hidden />,
                        title: '上传小说 TXT',
                        description:
                          '点击或拖拽 TXT 文件，也可以直接把长文粘贴到下面的输入框。',
                      }}
                    />
                    {onLoadDemo ? (
                      <Button
                        icon={<UnorderedListOutlined aria-hidden />}
                        onClick={onLoadDemo}
                        aria-label="载入内置示例小说"
                      >
                        载入示例小说
                      </Button>
                    ) : null}
                  </div>
                </Sender.Header>
              ) : undefined
            }
          />
        )}
      </Suggestion>
    </div>
  )
}
