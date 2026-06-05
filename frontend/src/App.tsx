import {
  useEffect,
  useRef,
  useState,
  type ClipboardEvent,
  type ReactNode,
} from 'react'
import Editor from '@monaco-editor/react'
import {
  Attachments,
  Bubble,
  Conversations,
  Prompts,
  Sender,
  ThoughtChain,
  Welcome,
  XProvider,
  type BubbleItemType,
  type ConversationItemType,
  type PromptsItemType,
  type ThoughtChainItemType,
} from '@ant-design/x'
import {
  Alert,
  App as AntdApp,
  Avatar,
  Badge,
  Button,
  Card,
  Collapse,
  Divider,
  Empty,
  Flex,
  Input,
  Layout,
  Space,
  Spin,
  Statistic,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  type UploadFile,
} from 'antd'
import {
  ApiOutlined,
  ApartmentOutlined,
  BookOutlined,
  BranchesOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  CloudUploadOutlined,
  CodeOutlined,
  DatabaseOutlined,
  EditOutlined,
  FileDoneOutlined,
  HistoryOutlined,
  InboxOutlined,
  LoadingOutlined,
  MessageOutlined,
  PaperClipOutlined,
  PlusOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
  SendOutlined,
  ThunderboltOutlined,
  UserOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ApiError,
  api,
  apiBaseUrl,
  streamPost,
  type BookIndexResponse,
  type Chapter,
  type ChapterSplitRule,
  type ChatConfirmation,
  type ChatMessage,
  type ChatRunRequest,
  type ChatSession,
  type ConfirmationActionRequest,
  type JsonRecord,
  type ScriptVersion,
  type SseEvent,
  type ToolCallEvent,
  type ValidationReport,
} from './lib/api'

type AssetTab = 'chapters' | 'index' | 'yaml' | 'harness' | 'versions'

type LiveEvent = SseEvent & {
  id: string
  receivedAt: number
}

type ProjectStatus = 'idle' | 'uploading' | 'awaiting' | 'generating' | 'ready'

const { Header, Sider, Content } = Layout
const { Text, Title, Paragraph } = Typography

const numberFormatter = new Intl.NumberFormat('zh-CN')
const dateFormatter = new Intl.DateTimeFormat('zh-CN', {
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
})

const assetTabs: Array<{
  key: AssetTab
  label: string
  icon: ReactNode
}> = [
  { key: 'chapters', label: '章节', icon: <BookOutlined /> },
  { key: 'index', label: '索引', icon: <DatabaseOutlined /> },
  { key: 'yaml', label: 'YAML', icon: <CodeOutlined /> },
  { key: 'harness', label: '校验', icon: <SafetyCertificateOutlined /> },
  { key: 'versions', label: '版本', icon: <HistoryOutlined /> },
]

const starterPrompts: PromptsItemType[] = [
  {
    key: 'start-short-drama',
    icon: <ThunderboltOutlined />,
    label: '开始短剧改编',
    description: '保留人物关系，增强冲突和场次节奏',
  },
  {
    key: 'split-first',
    icon: <BranchesOutlined />,
    label: '先检查分章',
    description: '让 Agent 推导分章规则并等待确认',
  },
  {
    key: 'tone-suspense',
    icon: <EditOutlined />,
    label: '偏悬疑表达',
    description: '改编时强化伏笔、误导和反转',
  },
]

const starterPromptText: Record<string, string> = {
  'start-short-drama': '请按短剧节奏改编，保留主要人物关系，增强冲突和场次推进。',
  'split-first': '请先识别项目名并推导分章方式，分章确认后再继续生成索引和 YAML。',
  'tone-suspense': '请用偏悬疑的表达处理剧本，强化伏笔、误导和反转。',
}

function App() {
  return (
    <XProvider
      theme={{
        token: {
          colorPrimary: '#1677ff',
          borderRadius: 12,
          colorBgLayout: '#f5f7fb',
          colorTextBase: '#1f2937',
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
        },
        components: {
          Layout: {
            bodyBg: '#f5f7fb',
            siderBg: '#ffffff',
            headerBg: '#ffffff',
          },
        },
      }}
    >
      <AntdApp>
        <Workspace />
      </AntdApp>
    </XProvider>
  )
}

function Workspace() {
  const queryClient = useQueryClient()
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [eventsBySession, setEventsBySession] = useState<Record<string, LiveEvent[]>>({})
  const [message, setMessage] = useState('')
  const [sourceText, setSourceText] = useState('')
  const [sourceFileName, setSourceFileName] = useState('novel.txt')
  const [attachmentOpen, setAttachmentOpen] = useState(true)
  const [isStreaming, setIsStreaming] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [ruleDrafts, setRuleDrafts] = useState<Record<string, string>>({})
  const [assetTab, setAssetTab] = useState<AssetTab>('chapters')
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null)
  const creatingInitialSession = useRef(false)

  const sessionsQuery = useQuery({
    queryKey: ['chat-sessions'],
    queryFn: api.listSessions,
  })

  const sessions = sessionsQuery.data ?? []
  const currentSessionId = activeSessionId ?? sessions[0]?.id ?? null

  useEffect(() => {
    if (sessionsQuery.isLoading || sessions.length > 0 || creatingInitialSession.current) {
      return
    }
    creatingInitialSession.current = true
    void api
      .createSession()
      .then((session) => {
        setActiveSessionId(session.id)
        return queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
      })
      .catch((error: unknown) => setErrorMessage(getErrorMessage(error)))
      .finally(() => {
        creatingInitialSession.current = false
      })
  }, [queryClient, sessions.length, sessionsQuery.isLoading])

  const detailQuery = useQuery({
    queryKey: ['chat-session', currentSessionId],
    queryFn: () => api.getSession(currentSessionId ?? ''),
    enabled: Boolean(currentSessionId),
  })

  const detail = detailQuery.data ?? null
  const currentSession = detail?.session ?? sessions.find((item) => item.id === currentSessionId)
  const liveEvents = currentSessionId ? (eventsBySession[currentSessionId] ?? []) : []
  const liveProjectId = findLatestProjectId(liveEvents)
  const currentProjectId = liveProjectId ?? currentSession?.project_id ?? null
  const pendingConfirmation = detail?.pending_confirmations[0] ?? findLiveConfirmation(liveEvents)
  const validationReport = latestValidationReport(liveEvents)

  const chaptersQuery = useQuery({
    queryKey: ['chapters', currentSessionId],
    queryFn: () => api.listChapters(currentSessionId ?? ''),
    enabled: Boolean(currentSessionId && currentProjectId),
  })

  const bookIndexQuery = useQuery({
    queryKey: ['book-index', currentSessionId],
    queryFn: () => api.getBookIndex(currentSessionId ?? ''),
    enabled: Boolean(currentSessionId && currentProjectId),
  })

  const versionsQuery = useQuery({
    queryKey: ['script-versions', currentSessionId],
    queryFn: () => api.listVersions(currentSessionId ?? ''),
    enabled: Boolean(currentSessionId && currentProjectId),
  })

  const versions = versionsQuery.data?.versions ?? detail?.latest_versions ?? []
  const latestVersionId = selectedVersionId ?? versions.at(-1)?.id ?? null

  const versionDetailQuery = useQuery({
    queryKey: ['script-version-detail', currentSessionId, latestVersionId],
    queryFn: () => api.getVersion(currentSessionId ?? '', latestVersionId ?? ''),
    enabled: Boolean(currentSessionId && currentProjectId && latestVersionId),
  })

  const sessionTitle = currentSession?.title ?? '新的改编对话'
  const timelineMessages = detail?.messages ?? []
  const hasTimelineContent =
    timelineMessages.length > 0 || liveEvents.length > 0 || Boolean(pendingConfirmation)
  const projectStatus = inferProjectStatus(currentSession, liveEvents, isStreaming)
  const sourceAttachment = buildSourceAttachment(sourceText, sourceFileName)

  async function ensureSession(): Promise<ChatSession> {
    if (currentSession) {
      return currentSession
    }
    const created = await api.createSession()
    setActiveSessionId(created.id)
    await queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
    return created
  }

  function pushEvent(sessionId: string, event: SseEvent) {
    setEventsBySession((previous) => ({
      ...previous,
      [sessionId]: [
        ...(previous[sessionId] ?? []),
        {
          ...event,
          id: `${event.event}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
          receivedAt: Date.now(),
        },
      ],
    }))
  }

  async function refreshSessionAssets(sessionId: string, projectIdHint: string | null) {
    await queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
    await queryClient.invalidateQueries({ queryKey: ['chat-session', sessionId] })
    const updated = await api.getSession(sessionId).catch(() => null)
    const refreshedProjectId = updated?.session.project_id ?? projectIdHint
    if (refreshedProjectId) {
      await queryClient.invalidateQueries({ queryKey: ['chapters', sessionId] })
      await queryClient.invalidateQueries({ queryKey: ['book-index', sessionId] })
      await queryClient.invalidateQueries({ queryKey: ['script-versions', sessionId] })
    }
  }

  async function handleSend(submittedMessage?: string) {
    const finalMessage = (submittedMessage ?? message).trim()
    const finalSourceText = sourceText.trim()
    if ((!finalMessage && !finalSourceText) || isStreaming) {
      return
    }

    setErrorMessage(null)
    setIsStreaming(true)
    try {
      const session = await ensureSession()
      const payload: ChatRunRequest = {
        message: finalMessage || '请开始改编这篇小说。',
        source_file_name: finalSourceText ? sourceFileName : null,
        source_text: finalSourceText || null,
        screenplay_format: 'short_drama',
      }
      setMessage('')
      await streamPost(`/chat/sessions/${session.id}/runs/stream`, payload, (sse) => {
        pushEvent(session.id, sse)
      })
      setSourceText('')
      await refreshSessionAssets(session.id, session.project_id)
      setAssetTab('chapters')
    } catch (error) {
      setErrorMessage(getErrorMessage(error))
    } finally {
      setIsStreaming(false)
    }
  }

  async function handleConfirmation(action: 'confirm' | 'cancel') {
    if (!pendingConfirmation || isStreaming) {
      return
    }
    setErrorMessage(null)
    setIsStreaming(true)
    try {
      const editedRegex = ruleDrafts[pendingConfirmation.id] ?? ''
      const payload: ConfirmationActionRequest = {
        action,
        message: action === 'confirm' ? '确认这个分章，继续生成剧本。' : '取消这次分章。',
        chapter_split_rule:
          action === 'confirm' ? buildRulePayload(pendingConfirmation, editedRegex) : null,
      }
      await streamPost(
        `/chat/sessions/${pendingConfirmation.session_id}/confirmations/${pendingConfirmation.id}/stream`,
        payload,
        (sse) => pushEvent(pendingConfirmation.session_id, sse),
      )
      await refreshSessionAssets(pendingConfirmation.session_id, pendingConfirmation.project_id)
      setAssetTab('yaml')
    } catch (error) {
      setErrorMessage(getErrorMessage(error))
    } finally {
      setIsStreaming(false)
    }
  }

  async function handleNewSession() {
    if (isStreaming) {
      return
    }
    setErrorMessage(null)
    try {
      const session = await api.createSession()
      setActiveSessionId(session.id)
      setMessage('')
      setSourceText('')
      setSelectedVersionId(null)
      await queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
    } catch (error) {
      setErrorMessage(getErrorMessage(error))
    }
  }

  function handleSelectSession(sessionId: string) {
    setActiveSessionId(sessionId)
    setMessage('')
    setSourceText('')
    setSelectedVersionId(null)
    setErrorMessage(null)
  }

  async function readSourceFile(file: File) {
    const text = await file.text()
    setSourceFileName(file.name)
    setSourceText(text)
    setAttachmentOpen(true)
    if (!message.trim()) {
      setMessage('请开始改编这篇小说。')
    }
  }

  function handlePaste(event: ClipboardEvent<HTMLElement>) {
    const text = event.clipboardData.getData('text')
    if (text.length > 1200 && !sourceText) {
      event.preventDefault()
      setSourceText(text)
      setSourceFileName('pasted-novel.txt')
      setAttachmentOpen(true)
      setMessage('请开始改编这篇小说。')
    }
  }

  const bubbleItems = buildBubbleItems({
    messages: timelineMessages,
    liveEvents,
    pendingConfirmation,
    ruleDraft: pendingConfirmation ? ruleDrafts[pendingConfirmation.id] : undefined,
    isStreaming,
    onRuleDraftChange: (confirmationId, value) =>
      setRuleDrafts((drafts) => ({ ...drafts, [confirmationId]: value })),
    onConfirm: () => void handleConfirmation('confirm'),
    onCancel: () => void handleConfirmation('cancel'),
  })

  return (
    <Layout className="sw-shell">
      <Sider className="sw-sider" width={304}>
        <ProjectRail
          sessions={sessions}
          activeSessionId={currentSessionId}
          loading={sessionsQuery.isLoading}
          onCreate={() => void handleNewSession()}
          onSelect={handleSelectSession}
        />
      </Sider>

      <Layout className="sw-main">
        <Header className="sw-header">
          <div className="sw-header-title">
            <Space size={12}>
              <Avatar size={40} icon={<RobotOutlined />} className="brand-avatar" />
              <div>
                <Title level={4}>{sessionTitle}</Title>
                <Text type="secondary">AI 小说转剧本工作台</Text>
              </div>
            </Space>
          </div>
          <Space size={8} wrap>
            <StatusTag status={projectStatus} />
            <Tooltip title="后端 API 地址">
              <Tag icon={<ApiOutlined />} className="api-tag">
                {apiBaseUrl}
              </Tag>
            </Tooltip>
          </Space>
        </Header>

        {errorMessage ? (
          <Alert
            className="sw-error"
            type="error"
            showIcon
            message={errorMessage}
            closable
            onClose={() => setErrorMessage(null)}
          />
        ) : null}

        <Content className="sw-chat">
          {!currentSessionId || detailQuery.isLoading ? (
            <div className="center-loading">
              <Spin />
              <Text type="secondary">正在读取会话</Text>
            </div>
          ) : hasTimelineContent ? (
            <Bubble.List
              className="bubble-list"
              items={bubbleItems}
              autoScroll
              role={bubbleRoles}
            />
          ) : (
            <EmptyWorkspace
              onPrompt={(value) => setMessage(value)}
              onUpload={(file) => void readSourceFile(file)}
            />
          )}
        </Content>

        <div className="sender-wrap">
          <Sender
            value={message}
            loading={isStreaming}
            disabled={!currentSessionId}
            placeholder={
              sourceText
                ? '补充改编要求，或直接发送开始处理这篇小说'
                : '上传 TXT，或描述你想如何改编'
            }
            autoSize={{ minRows: 2, maxRows: 6 }}
            submitType="enter"
            onChange={(value) => setMessage(value)}
            onSubmit={(value) => void handleSend(value)}
            onPaste={handlePaste}
            onPasteFile={(files) => {
              const file = files.item(0)
              if (file) {
                void readSourceFile(file)
              }
            }}
            prefix={
              <Tooltip title="上传或粘贴小说 TXT">
                <Button
                  type={sourceText ? 'primary' : 'text'}
                  icon={<PaperClipOutlined />}
                  onClick={() => setAttachmentOpen((open) => !open)}
                />
              </Tooltip>
            }
            suffix={
              <Tooltip title={isStreaming ? 'Agent 正在执行' : '发送'}>
                <Button
                  type="primary"
                  shape="circle"
                  icon={isStreaming ? <LoadingOutlined /> : <SendOutlined />}
                  disabled={isStreaming || (!message.trim() && !sourceText.trim())}
                  onClick={() => void handleSend()}
                />
              </Tooltip>
            }
            header={
              <Sender.Header
                title="小说输入"
                open={attachmentOpen || Boolean(sourceText)}
                onOpenChange={setAttachmentOpen}
              >
                <div className="sender-header-panel">
                  <Attachments
                    accept=".txt,text/plain"
                    maxCount={1}
                    items={sourceAttachment}
                    beforeUpload={(file) => {
                      void readSourceFile(file)
                      return false
                    }}
                    onRemove={() => {
                      setSourceText('')
                      setSourceFileName('novel.txt')
                      return true
                    }}
                    placeholder={{
                      icon: <InboxOutlined />,
                      title: '上传小说 TXT',
                      description: '支持点击选择、拖拽上传，或直接把长文本粘贴到输入框。',
                    }}
                  />
                  {sourceText ? (
                    <Input.TextArea
                      className="source-preview"
                      value={sourceText}
                      onChange={(event) => setSourceText(event.target.value)}
                      autoSize={{ minRows: 4, maxRows: 8 }}
                      spellCheck={false}
                    />
                  ) : null}
                </div>
              </Sender.Header>
            }
          />
        </div>
      </Layout>

      <AssetInspector
        projectId={currentProjectId}
        activeTab={assetTab}
        chapters={chaptersQuery.data?.chapters ?? []}
        chaptersLoading={chaptersQuery.isLoading}
        bookIndex={bookIndexQuery.data ?? null}
        bookIndexLoading={bookIndexQuery.isLoading}
        bookIndexError={bookIndexQuery.isError}
        scriptYaml={versionDetailQuery.data?.script_yaml ?? ''}
        validationReport={validationReport}
        versions={versions}
        selectedVersionId={latestVersionId}
        versionsLoading={versionsQuery.isLoading || versionDetailQuery.isLoading}
        onTabChange={setAssetTab}
        onSelectVersion={setSelectedVersionId}
      />
    </Layout>
  )
}

function ProjectRail({
  sessions,
  activeSessionId,
  loading,
  onCreate,
  onSelect,
}: {
  sessions: ChatSession[]
  activeSessionId: string | null
  loading: boolean
  onCreate: () => void
  onSelect: (sessionId: string) => void
}) {
  const items: ConversationItemType[] = sessions.map((session) => ({
    key: session.id,
    label: (
      <div className="conversation-label">
        <Text ellipsis>{session.title}</Text>
        <Text type="secondary">{formatDate(session.updated_at)}</Text>
      </div>
    ),
    icon:
      session.pending_confirmation_count > 0 ? (
        <Badge dot>
          <MessageOutlined />
        </Badge>
      ) : (
        <MessageOutlined />
      ),
    group: session.pending_confirmation_count > 0 ? '待确认' : '最近会话',
  }))

  return (
    <div className="project-rail">
      <div className="rail-brand">
        <Avatar size={42} icon={<ApartmentOutlined />} className="brand-avatar" />
        <div>
          <Title level={4}>ScriptWeaver</Title>
          <Text type="secondary">Ant Design X Agent</Text>
        </div>
      </div>

      <Button type="primary" icon={<PlusOutlined />} block size="large" onClick={onCreate}>
        新建改编
      </Button>

      <Divider titlePlacement="left" plain>
        Projects
      </Divider>

      {loading ? (
        <div className="rail-loading">
          <Spin size="small" />
          <Text type="secondary">加载会话</Text>
        </div>
      ) : (
        <Conversations
          items={items}
          activeKey={activeSessionId ?? undefined}
          onActiveChange={(key) => onSelect(key)}
          groupable={{
            label: (group) => <Text type="secondary">{group}</Text>,
          }}
        />
      )}
    </div>
  )
}

function EmptyWorkspace({
  onPrompt,
  onUpload,
}: {
  onPrompt: (value: string) => void
  onUpload: (file: File) => void
}) {
  return (
    <div className="empty-workspace">
      <Welcome
        variant="borderless"
        icon={<Avatar size={56} icon={<RobotOutlined />} className="brand-avatar" />}
        title="开始一次小说到剧本的 Agent 改编"
        description="上传或粘贴 TXT 后，Agent 会自动识别项目名、推导分章方式，并在生成剧情索引和 YAML 剧本前让你确认关键步骤。"
      />

      <Attachments
        rootClassName="empty-upload"
        accept=".txt,text/plain"
        maxCount={1}
        beforeUpload={(file) => {
          onUpload(file)
          return false
        }}
        placeholder={{
          icon: <CloudUploadOutlined />,
          title: '上传小说 TXT',
          description: '点击或拖拽文件到这里，短篇无分章也可以继续处理。',
        }}
      />

      <Prompts
        title="你也可以先给 Agent 一个改编方向"
        items={starterPrompts}
        wrap
        fadeIn
        onItemClick={({ data }) => onPrompt(starterPromptText[data.key] ?? data.key)}
      />
    </div>
  )
}

const bubbleRoles = {
  user: {
    placement: 'end',
    variant: 'filled',
    shape: 'round',
    avatar: <Avatar icon={<UserOutlined />} />,
    styles: {
      content: {
        background: '#1677ff',
        color: '#fff',
      },
    },
  },
  ai: {
    placement: 'start',
    variant: 'filled',
    shape: 'round',
    avatar: <Avatar icon={<RobotOutlined />} className="brand-avatar" />,
  },
  tool: {
    placement: 'start',
    variant: 'borderless',
    avatar: <Avatar icon={<BranchesOutlined />} />,
  },
  confirm: {
    placement: 'start',
    variant: 'shadow',
    shape: 'default',
    avatar: <Avatar icon={<SafetyCertificateOutlined />} />,
  },
  system: {
    variant: 'borderless',
  },
} satisfies NonNullable<React.ComponentProps<typeof Bubble.List>['role']>

function buildBubbleItems({
  messages,
  liveEvents,
  pendingConfirmation,
  ruleDraft,
  isStreaming,
  onRuleDraftChange,
  onConfirm,
  onCancel,
}: {
  messages: ChatMessage[]
  liveEvents: LiveEvent[]
  pendingConfirmation: ChatConfirmation | null
  ruleDraft: string | undefined
  isStreaming: boolean
  onRuleDraftChange: (confirmationId: string, value: string) => void
  onConfirm: () => void
  onCancel: () => void
}): BubbleItemType[] {
  const items: BubbleItemType[] = messages
    .filter((message) => message.role !== 'tool' && message.content.trim())
    .map((message) => ({
      key: `message-${message.id}`,
      role: message.role === 'user' ? 'user' : 'ai',
      content: message.content,
      footer: formatDate(message.created_at),
      typing: message.role === 'assistant' ? { effect: 'fade-in', step: 8 } : false,
    }))

  const toolEvents = latestToolEvents(liveEvents)
  if (toolEvents.length > 0) {
    items.push({
      key: `tools-${toolEvents.map((tool) => tool.id).join('-')}`,
      role: 'tool',
      content: <ToolTracePanel tools={toolEvents} />,
    })
  }

  for (const event of liveEvents) {
    if (event.event === 'message.delta') {
      items.push({
        key: event.id,
        role: 'ai',
        content: String(event.data.content ?? ''),
        streaming: isStreaming,
        typing: { effect: 'typing', step: [6, 12], interval: 20 },
      })
    }
    if (event.event === 'asset.updated') {
      items.push({
        key: event.id,
        role: 'system',
        content: <AssetUpdateEvent event={event} />,
      })
    }
    if (event.event === 'run.waiting_confirmation') {
      items.push({
        key: event.id,
        role: 'system',
        content: <Tag color="warning">等待用户确认</Tag>,
      })
    }
    if (event.event === 'run.completed') {
      items.push({
        key: event.id,
        role: 'system',
        content: <Tag color="success">本轮执行完成</Tag>,
      })
    }
    if (event.event === 'error') {
      items.push({
        key: event.id,
        role: 'system',
        content: <Tag color="error">{String(event.data.message ?? '执行失败')}</Tag>,
      })
    }
  }

  if (pendingConfirmation) {
    items.push({
      key: `confirmation-${pendingConfirmation.id}`,
      role: 'confirm',
      content: (
        <ConfirmationPanel
          confirmation={pendingConfirmation}
          ruleDraft={ruleDraft}
          isStreaming={isStreaming}
          onRuleDraftChange={onRuleDraftChange}
          onConfirm={onConfirm}
          onCancel={onCancel}
        />
      ),
    })
  }

  if (isStreaming) {
    items.push({
      key: 'streaming-loading',
      role: 'ai',
      content: 'Agent 正在执行工具调用，请稍候。',
      loading: true,
    })
  }

  return items
}

function ToolTracePanel({ tools }: { tools: ToolCallEvent[] }) {
  const items: ThoughtChainItemType[] = tools.map((tool) => ({
    key: tool.id,
    title: tool.name,
    description: summarizeTool(tool),
    status:
      tool.status === 'failed' ? 'error' : tool.status === 'completed' ? 'success' : 'loading',
    icon:
      tool.status === 'failed' ? (
        <CloseCircleOutlined />
      ) : tool.status === 'completed' ? (
        <CheckCircleOutlined />
      ) : (
        <LoadingOutlined />
      ),
    content: <ToolPayloadPreview tool={tool} />,
    collapsible: Boolean(tool.input || tool.output || tool.error_message),
  }))

  return (
    <Card className="tool-card" size="small" title="Agent 工具调用" variant="borderless">
      <ThoughtChain items={items} defaultExpandedKeys={items.slice(-1).map((item) => item.key ?? '')} />
    </Card>
  )
}

function ToolPayloadPreview({ tool }: { tool: ToolCallEvent }) {
  const payload = tool.error_message
    ? { error: tool.error_message }
    : (tool.output ?? tool.input ?? null)
  if (!payload) {
    return <Text type="secondary">等待工具返回</Text>
  }
  return <pre className="json-preview">{JSON.stringify(payload, null, 2).slice(0, 1200)}</pre>
}

function AssetUpdateEvent({ event }: { event: LiveEvent }) {
  const asset = String(event.data.asset ?? 'asset')
  const color = asset === 'script_yaml' ? 'blue' : asset === 'book_index' ? 'purple' : 'green'
  return (
    <Space size={8}>
      <FileDoneOutlined />
      <Tag color={color}>{asset}</Tag>
      <Text type="secondary">资产已更新</Text>
    </Space>
  )
}

function ConfirmationPanel({
  confirmation,
  ruleDraft,
  isStreaming,
  onRuleDraftChange,
  onConfirm,
  onCancel,
}: {
  confirmation: ChatConfirmation
  ruleDraft: string | undefined
  isStreaming: boolean
  onRuleDraftChange: (confirmationId: string, value: string) => void
  onConfirm: () => void
  onCancel: () => void
}) {
  const rule = confirmation.payload.rule
  const regexValue = ruleDraft ?? rule.heading_regex ?? ''
  const preview = confirmation.payload.preview
  const titlePreview = [...preview.titles.slice(0, 6), ...preview.last_titles.slice(-3)]

  return (
    <Card
      className="confirm-card"
      size="small"
      title={
        <Space>
          <SafetyCertificateOutlined />
          确认分章预览
        </Space>
      }
      extra={<Tag color="warning">待确认</Tag>}
    >
      <Paragraph type="secondary">{confirmation.prompt}</Paragraph>

      <div className="confirm-stats">
        <Statistic title="字符数" value={confirmation.payload.text_length} />
        <Statistic title="章节数" value={preview.chapter_count} />
        <Statistic title="标题候选" value={preview.candidate_heading_count} />
        <Statistic title="疑似漏切" value={preview.unmatched_candidate_count} />
      </div>

      <Input.TextArea
        value={regexValue}
        onChange={(event) => onRuleDraftChange(confirmation.id, event.target.value)}
        autoSize={{ minRows: 2, maxRows: 4 }}
        spellCheck={false}
        placeholder="标题匹配正则"
      />

      <Flex className="chapter-title-preview" gap={8} wrap>
        {titlePreview.map((title, index) => (
          <Tag key={`${title}-${index}`}>{title}</Tag>
        ))}
      </Flex>

      <Flex justify="end" gap={8}>
        <Button disabled={isStreaming} onClick={onCancel}>
          取消
        </Button>
        <Button type="primary" disabled={isStreaming} onClick={onConfirm}>
          确认并继续
        </Button>
      </Flex>
    </Card>
  )
}

function AssetInspector({
  projectId,
  activeTab,
  chapters,
  chaptersLoading,
  bookIndex,
  bookIndexLoading,
  bookIndexError,
  scriptYaml,
  validationReport,
  versions,
  selectedVersionId,
  versionsLoading,
  onTabChange,
  onSelectVersion,
}: {
  projectId: string | null
  activeTab: AssetTab
  chapters: Chapter[]
  chaptersLoading: boolean
  bookIndex: BookIndexResponse | null
  bookIndexLoading: boolean
  bookIndexError: boolean
  scriptYaml: string
  validationReport: ValidationReport | null
  versions: ScriptVersion[]
  selectedVersionId: string | null
  versionsLoading: boolean
  onTabChange: (tab: AssetTab) => void
  onSelectVersion: (versionId: string) => void
}) {
  return (
    <aside className="asset-inspector">
      <div className="asset-head">
        <Space>
          <Avatar icon={<DatabaseOutlined />} />
          <div>
            <Title level={5}>项目资产</Title>
            <Text type="secondary">{projectId ? '已连接本地项目' : '等待上传小说'}</Text>
          </div>
        </Space>
        <Tag color={projectId ? 'success' : 'default'}>{projectId ? 'linked' : 'empty'}</Tag>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={(key) => onTabChange(key as AssetTab)}
        items={assetTabs.map((tab) => ({
          key: tab.key,
          label: (
            <Space size={4}>
              {tab.icon}
              {tab.label}
            </Space>
          ),
          children: !projectId ? (
            <AssetEmpty />
          ) : tab.key === 'chapters' ? (
            <ChaptersAsset chapters={chapters} loading={chaptersLoading} />
          ) : tab.key === 'index' ? (
            <JsonAsset data={bookIndex?.book_index ?? null} loading={bookIndexLoading} error={bookIndexError} />
          ) : tab.key === 'yaml' ? (
            <YamlAsset value={scriptYaml} loading={versionsLoading} />
          ) : tab.key === 'harness' ? (
            <HarnessAsset report={validationReport} />
          ) : (
            <VersionsAsset
              versions={versions}
              selectedVersionId={selectedVersionId}
              loading={versionsLoading}
              onSelectVersion={onSelectVersion}
            />
          ),
        }))}
      />
    </aside>
  )
}

function AssetEmpty() {
  return (
    <Empty
      image={Empty.PRESENTED_IMAGE_SIMPLE}
      description="上传小说后，这里会展示章节、索引、YAML、校验和版本。"
    />
  )
}

function ChaptersAsset({ chapters, loading }: { chapters: Chapter[]; loading: boolean }) {
  if (loading) {
    return <SpinBlock label="加载章节" />
  }
  if (chapters.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚未确认分章" />
  }
  return (
    <Collapse
      className="asset-collapse"
      size="small"
      items={chapters.map((chapter) => ({
        key: chapter.id,
        label: (
          <Flex justify="space-between" align="center" gap={8}>
            <Text ellipsis>
              {String(chapter.order_index + 1).padStart(2, '0')} · {chapter.title}
            </Text>
            <Tag>{formatNumber(chapter.token_estimate ?? chapter.content.length)}</Tag>
          </Flex>
        ),
        children: (
          <Paragraph className="chapter-preview">
            {chapter.content.slice(0, 680)}
          </Paragraph>
        ),
      }))}
    />
  )
}

function JsonAsset({
  data,
  loading,
  error,
}: {
  data: JsonRecord | null
  loading: boolean
  error: boolean
}) {
  if (loading) {
    return <SpinBlock label="读取索引" />
  }
  if (!data || error) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚未生成 book_index.json" />
  }
  return <pre className="asset-code">{JSON.stringify(data, null, 2)}</pre>
}

function YamlAsset({ value, loading }: { value: string; loading: boolean }) {
  if (loading) {
    return <SpinBlock label="读取 YAML" />
  }
  if (!value) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚未生成 script.yaml" />
  }
  return (
    <div className="yaml-editor">
      <Editor
        height="100%"
        defaultLanguage="yaml"
        value={value}
        theme="vs-light"
        options={{
          readOnly: true,
          minimap: { enabled: false },
          fontSize: 13,
          lineHeight: 21,
          scrollBeyondLastLine: false,
          wordWrap: 'on',
        }}
      />
    </div>
  )
}

function HarnessAsset({ report }: { report: ValidationReport | null }) {
  if (!report) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="等待 harness 校验结果" />
  }
  return (
    <Space direction="vertical" size={12} className="full-width">
      <Alert
        type={report.accepted ? 'success' : 'error'}
        showIcon
        message={report.accepted ? 'YAML 已通过校验' : 'YAML 未通过校验'}
        description={`最高严重级别：${report.severity}`}
      />
      <div className="metric-grid">
        {Object.entries(report.metrics).map(([key, value]) => (
          <Card key={key} size="small">
            <Statistic title={key} value={String(value)} />
          </Card>
        ))}
      </div>
      {[...report.errors, ...report.warnings].map((issue) => (
        <Alert
          key={`${issue.path}-${issue.code}-${issue.message}`}
          type={issue.severity === 'warning' ? 'warning' : 'error'}
          showIcon
          message={`${issue.path} · ${issue.code}`}
          description={issue.message}
        />
      ))}
    </Space>
  )
}

function VersionsAsset({
  versions,
  selectedVersionId,
  loading,
  onSelectVersion,
}: {
  versions: ScriptVersion[]
  selectedVersionId: string | null
  loading: boolean
  onSelectVersion: (versionId: string) => void
}) {
  if (loading) {
    return <SpinBlock label="读取版本" />
  }
  if (versions.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可接受版本" />
  }
  return (
    <Space direction="vertical" size={8} className="full-width">
      {versions.map((version) => (
        <Card
          key={version.id}
          size="small"
          className={version.id === selectedVersionId ? 'active-version-card' : undefined}
          onClick={() => onSelectVersion(version.id)}
        >
          <Flex justify="space-between" align="center" gap={12}>
            <div>
              <Text strong>{version.reason}</Text>
              <br />
              <Text type="secondary">{formatDate(version.created_at)}</Text>
            </div>
            <Tag color="success">{version.validation_status}</Tag>
          </Flex>
        </Card>
      ))}
    </Space>
  )
}

function SpinBlock({ label }: { label: string }) {
  return (
    <div className="spin-block">
      <Spin size="small" />
      <Text type="secondary">{label}</Text>
    </div>
  )
}

function StatusTag({ status }: { status: ProjectStatus }) {
  const config: Record<ProjectStatus, { color: string; label: string; icon: ReactNode }> = {
    idle: { color: 'default', label: '空闲', icon: <MessageOutlined /> },
    uploading: { color: 'processing', label: '导入中', icon: <LoadingOutlined /> },
    awaiting: { color: 'warning', label: '待确认', icon: <WarningOutlined /> },
    generating: { color: 'processing', label: '生成中', icon: <LoadingOutlined /> },
    ready: { color: 'success', label: '已就绪', icon: <CheckCircleOutlined /> },
  }
  return (
    <Tag color={config[status].color} icon={config[status].icon}>
      {config[status].label}
    </Tag>
  )
}

function buildSourceAttachment(sourceText: string, sourceFileName: string): UploadFile[] {
  if (!sourceText) {
    return []
  }
  return [
    {
      uid: 'source-text',
      name: sourceFileName,
      status: 'done',
      size: new Blob([sourceText]).size,
      type: 'text/plain',
      percent: 100,
    },
  ]
}

function latestToolEvents(events: LiveEvent[]): ToolCallEvent[] {
  const tools = new Map<string, ToolCallEvent>()
  for (const event of events) {
    if (event.event === 'tool.call.started' || event.event === 'tool.call.completed') {
      const tool = event.data as unknown as ToolCallEvent
      tools.set(tool.id, tool)
    }
  }
  return [...tools.values()]
}

function latestValidationReport(events: LiveEvent[]): ValidationReport | null {
  for (const event of [...events].reverse()) {
    const report = event.data.validation_report
    if (report && typeof report === 'object') {
      return report as ValidationReport
    }
  }
  return null
}

function findLiveConfirmation(events: LiveEvent[]): ChatConfirmation | null {
  for (const event of [...events].reverse()) {
    if (event.event === 'tool.confirm.required') {
      return event.data as unknown as ChatConfirmation
    }
  }
  return null
}

function findLatestProjectId(events: LiveEvent[]): string | null {
  for (const event of [...events].reverse()) {
    const projectId = event.data.project_id
    if (typeof projectId === 'string') {
      return projectId
    }
  }
  return null
}

function inferProjectStatus(
  session: ChatSession | undefined,
  liveEvents: LiveEvent[],
  isRunning: boolean,
): ProjectStatus {
  if (isRunning) {
    return session?.project_id || findLatestProjectId(liveEvents) ? 'generating' : 'uploading'
  }
  if (session?.pending_confirmation_count || findLiveConfirmation(liveEvents)) {
    return 'awaiting'
  }
  if (session?.project_id || findLatestProjectId(liveEvents)) {
    return 'ready'
  }
  return 'idle'
}

function buildRulePayload(
  confirmation: ChatConfirmation,
  editedRegex: string,
): ChapterSplitRule {
  return {
    ...confirmation.payload.rule,
    heading_regex:
      confirmation.payload.rule.strategy === 'line_regex'
        ? editedRegex.trim() || confirmation.payload.rule.heading_regex
        : null,
  }
}

function summarizeTool(tool: ToolCallEvent): string {
  if (tool.error_message) {
    return tool.error_message
  }
  if (tool.status === 'running') {
    return '执行中'
  }
  const output = tool.output ?? {}
  if ('title' in output) {
    return String(output.title)
  }
  if ('chapter_count' in output) {
    return `${String(output.chapter_count)} 个章节`
  }
  if ('accepted' in output) {
    return output.accepted ? '校验通过' : '校验未通过'
  }
  if ('asset' in output) {
    return String(output.asset)
  }
  return '已完成'
}

function formatNumber(value: number) {
  return numberFormatter.format(value)
}

function formatDate(value: string) {
  return dateFormatter.format(new Date(value))
}

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message
  }
  if (error instanceof Error) {
    return error.message
  }
  return '请求失败，请检查后端服务。'
}

export default App
