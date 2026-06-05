import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { App as AntdApp, Alert, Empty } from 'antd'
import { useQueryClient } from '@tanstack/react-query'
import { AppShell } from '../../layout/AppShell'
import { WorkspaceHeader } from '../../layout/WorkspaceHeader'
import { LeftRail } from '../../layout/LeftRail'
import { RightInspector } from '../../layout/RightInspector'
import { WorkspaceSettingsModal } from '../../layout/WorkspaceSettingsModal'
import { ConversationsPanel } from '../../features/sessions/ConversationsPanel'
import {
  refreshSessionAssets,
  sessionDetailKey,
  sessionsKey,
  useArchivedSessions,
  useArchiveSession,
  useBookIndex,
  useChapters,
  useCreateSession,
  useRestoreSession,
  useScriptVersionDetail,
  useScriptVersions,
  useSessionDetail,
  useSessions,
} from '../../features/sessions/hooks'
import {
  buildRulePayload,
  inferProjectStatus,
} from '../../features/sessions/inferProjectStatus'
import { ChatTimeline } from '../../features/chat/ChatTimeline'
import { ChatComposer } from '../../features/chat/ChatComposer'
import { buildBubbleItems } from '../../features/chat/buildBubbleItems'
import { buildHistoryEvents } from '../../features/chat/replayHistory'
import { AssetTabs } from '../../features/assets/AssetTabs'
import { AssetGuide } from '../../features/assets/AssetGuide'
import { ChaptersAsset } from '../../features/assets/ChaptersAsset'
import { BookIndexAsset } from '../../features/assets/BookIndexAsset'
import { ScriptYamlAsset } from '../../features/assets/ScriptYamlAsset'
import { ValidationAsset } from '../../features/assets/ValidationAsset'
import { VersionsAsset } from '../../features/assets/VersionsAsset'
import { selectSession, useEventLog } from '../../state/eventLog'
import { useUiPrefs, type AssetTab } from '../../state/uiPrefs'
import { streamPost } from '../../lib/sse'
import { deriveRunStatus, findLatestProjectId } from '../../lib/events'
import { getErrorMessage } from '../../lib/api'
import type {
  ChatRunRequest,
  ConfirmationActionRequest,
} from '../../types'
import './WorkspacePage.css'

export default function WorkspacePage() {
  const { sessionId: routeSessionId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { message: notify, notification } = AntdApp.useApp()

  const [message, setMessage] = useState('')
  const [sourceText, setSourceText] = useState('')
  const [sourceFileName, setSourceFileName] = useState('小说原文.txt')
  const [ruleDrafts, setRuleDrafts] = useState<Record<string, string>>({})
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [restoringSessionId, setRestoringSessionId] = useState<string | null>(null)
  const [assetHighlights, setAssetHighlights] = useState<Partial<Record<AssetTab, boolean>>>({})
  const abortRef = useRef<AbortController | null>(null)
  const lastSendArgsRef = useRef<{
    sessionId: string
    payload: ChatRunRequest
  } | null>(null)

  const {
    activeAssetTab,
    attachmentOpen,
    leftRailCollapsed,
    rightInspectorWidth,
    themeMode,
    setActiveAssetTab,
    setAttachmentOpen,
    setLeftRailCollapsed,
    setRightInspectorWidth,
    setThemeMode,
  } = useUiPrefs()

  const sessionsQuery = useSessions()
  const archivedSessionsQuery = useArchivedSessions(settingsOpen)
  const sessions = useMemo(() => sessionsQuery.data ?? [], [sessionsQuery.data])
  const archivedSessions = useMemo(
    () => archivedSessionsQuery.data ?? [],
    [archivedSessionsQuery.data],
  )

  const activeSessionId = routeSessionId ?? sessions[0]?.id ?? null

  useEffect(() => {
    if (!routeSessionId && sessions.length > 0) {
      navigate(`/sessions/${sessions[0].id}`, { replace: true })
    }
  }, [routeSessionId, sessions, navigate])

  const sessionDetailQuery = useSessionDetail(activeSessionId)
  const sessionDetail = sessionDetailQuery.data

  const sessionEvents = useEventLog(selectSession(activeSessionId))
  const pushEvent = useEventLog((state) => state.pushEvent)
  const clearError = useEventLog((state) => state.clearError)
  const onAssetUpdated = useEventLog((state) => state.onAssetUpdated)

  const historyEvents = useMemo(
    () => buildHistoryEvents(sessionDetail),
    [sessionDetail],
  )
  const mergedEvents = useMemo(
    () =>
      sessionEvents.events.length > 0
        ? [...historyEvents, ...sessionEvents.events]
        : historyEvents,
    [historyEvents, sessionEvents.events],
  )

  const pendingConfirmation =
    sessionEvents.events.length > 0
      ? sessionEvents.pendingConfirmation
      : (sessionDetail?.pending_confirmations?.[0] ?? null)

  const projectId = useMemo(() => {
    return (
      sessionDetail?.session.project_id ??
      findLatestProjectId(mergedEvents) ??
      null
    )
  }, [sessionDetail, mergedEvents])

  const hasProject = Boolean(projectId)

  const chaptersQuery = useChapters(activeSessionId, hasProject)
  const bookIndexQuery = useBookIndex(activeSessionId, hasProject)
  const versionsQuery = useScriptVersions(activeSessionId, hasProject)

  const versions = useMemo(
    () => versionsQuery.data?.versions ?? [],
    [versionsQuery.data],
  )
  const accepted = versions.find((v) => v.validation_status === 'accepted')
  const effectiveVersionId =
    selectedVersionId ?? accepted?.id ?? versions[0]?.id ?? null
  const versionDetailQuery = useScriptVersionDetail(
    activeSessionId,
    effectiveVersionId,
    hasProject,
  )

  const hasRejectedDraft = useMemo(
    () => versions.some((v) => v.validation_status !== 'accepted'),
    [versions],
  )

  const projectStatus = inferProjectStatus(
    sessionDetail?.session,
    mergedEvents,
    isStreaming,
    pendingConfirmation,
    hasRejectedDraft,
  )
  const runStatus = deriveRunStatus(
    mergedEvents,
    Boolean(pendingConfirmation),
    isStreaming,
  )

  const messages = sessionDetail?.messages ?? []

  const handleRuleDraftChange = useCallback(
    (confirmationId: string, value: string) => {
      setRuleDrafts((prev) => ({ ...prev, [confirmationId]: value }))
    },
    [],
  )

  const handleSelectAssetTab = useCallback(
    (tab: AssetTab) => {
      setActiveAssetTab(tab)
      setAssetHighlights((prev) => ({ ...prev, [tab]: false }))
    },
    [setActiveAssetTab],
  )

  const handleOpenVersion = useCallback((versionId: string) => {
    setSelectedVersionId(versionId)
  }, [])

  async function ensureSession(): Promise<string> {
    if (activeSessionId) return activeSessionId
    const created = await sessionsCreate.mutateAsync(undefined)
    navigate(`/sessions/${created.id}`, { replace: true })
    return created.id
  }

  const sessionsCreate = useCreateSession()
  const sessionsArchive = useArchiveSession()
  const sessionsRestore = useRestoreSession()

  async function runStream(
    sessionId: string,
    path: string,
    payload: unknown,
  ) {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    try {
      await streamPost(path, payload, {
        signal: controller.signal,
        onEvent: (event) => pushEvent(sessionId, event),
      })
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null
      }
    }
  }

  async function handleSend(submitted?: string) {
    const finalMessage = (submitted ?? message).trim()
    const finalSource = sourceText.trim()
    if ((!finalMessage && !finalSource) || isStreaming) return

    setErrorMessage(null)
    setIsStreaming(true)
    try {
      const sessionId = await ensureSession()
      const payload: ChatRunRequest = {
        message: finalMessage || '请开始改编这篇小说。',
        source_file_name: finalSource ? sourceFileName : null,
        source_text: finalSource || null,
        screenplay_format: 'short_drama',
      }
      lastSendArgsRef.current = { sessionId, payload }
      setMessage('')
      setAttachmentOpen(false)
      await runStream(sessionId, `/chat/sessions/${sessionId}/runs/stream`, payload)
      setSourceText('')
      await refreshSessionAssets(queryClient, sessionId)
      setActiveAssetTab('chapters')
    } catch (error) {
      if ((error as DOMException)?.name === 'AbortError') return
      setErrorMessage(getErrorMessage(error))
    } finally {
      setIsStreaming(false)
    }
  }

  async function handleRetryLast() {
    const last = lastSendArgsRef.current
    if (!last || isStreaming) return
    setErrorMessage(null)
    setIsStreaming(true)
    try {
      await runStream(
        last.sessionId,
        `/chat/sessions/${last.sessionId}/runs/stream`,
        last.payload,
      )
      await refreshSessionAssets(queryClient, last.sessionId)
    } catch (error) {
      if ((error as DOMException)?.name === 'AbortError') return
      setErrorMessage(getErrorMessage(error))
    } finally {
      setIsStreaming(false)
    }
  }

  async function handleConfirmation(action: 'confirm' | 'cancel') {
    if (!pendingConfirmation || isStreaming) return
    setErrorMessage(null)
    setIsStreaming(true)
    try {
      const editedRegex = ruleDrafts[pendingConfirmation.id] ?? ''
      const payload: ConfirmationActionRequest = {
        action,
        message:
          action === 'confirm'
            ? '确认这个分章，继续生成剧本。'
            : '取消这次分章。',
        chapter_split_rule:
          action === 'confirm'
            ? buildRulePayload(pendingConfirmation, editedRegex)
            : null,
      }
      await runStream(
        pendingConfirmation.session_id,
        `/chat/sessions/${pendingConfirmation.session_id}/confirmations/${pendingConfirmation.id}/stream`,
        payload,
      )
      await refreshSessionAssets(queryClient, pendingConfirmation.session_id)
      setActiveAssetTab(action === 'confirm' ? 'yaml' : 'chapters')
    } catch (error) {
      if ((error as DOMException)?.name === 'AbortError') return
      setErrorMessage(getErrorMessage(error))
    } finally {
      setIsStreaming(false)
    }
  }

  async function handleNewSession() {
    if (isStreaming) return
    setErrorMessage(null)
    try {
      const created = await sessionsCreate.mutateAsync(undefined)
      setMessage('')
      setSourceText('')
      setSelectedVersionId(null)
      navigate(`/sessions/${created.id}`)
    } catch (error) {
      setErrorMessage(getErrorMessage(error))
    }
  }

  function handleSelectSession(sessionId: string) {
    setMessage('')
    setSourceText('')
    setSelectedVersionId(null)
    setErrorMessage(null)
    navigate(`/sessions/${sessionId}`)
  }

  async function handleArchiveSession(sessionId: string) {
    if (isStreaming && sessionId === activeSessionId) {
      void notify.open({
        type: 'warning',
        content: '当前会话正在运行，完成后再归档会更稳。',
        duration: 3,
      })
      return
    }

    const nextSessionId = sessions.find((session) => session.id !== sessionId)?.id ?? null
    try {
      await sessionsArchive.mutateAsync(sessionId)
      void notify.open({
        type: 'success',
        content: '会话已归档',
        duration: 2,
      })
      if (activeSessionId === sessionId) {
        setMessage('')
        setSourceText('')
        setSelectedVersionId(null)
        navigate(nextSessionId ? `/sessions/${nextSessionId}` : '/', { replace: true })
      }
    } catch (error) {
      setErrorMessage(getErrorMessage(error))
    }
  }

  async function handleRestoreSession(sessionId: string) {
    setRestoringSessionId(sessionId)
    try {
      const restored = await sessionsRestore.mutateAsync(sessionId)
      void notify.open({
        type: 'success',
        content: '会话已还原',
        duration: 2,
      })
      setSettingsOpen(false)
      navigate(`/sessions/${restored.id}`)
    } catch (error) {
      setErrorMessage(getErrorMessage(error))
    } finally {
      setRestoringSessionId(null)
    }
  }

  function handleSourceTextChange(text: string, fileName?: string) {
    setSourceText(text)
    if (fileName) setSourceFileName(fileName)
    setAttachmentOpen(true)
    if (!message.trim()) {
      setMessage('请开始改编这篇小说。')
    }
  }

  function handleSourceClear() {
    setSourceText('')
    setSourceFileName('小说原文.txt')
  }

  const lastValidationKeyRef = useRef<string | null>(null)
  useEffect(() => {
    const validation = sessionEvents.latestValidation
    if (!validation) return
    const key = `${validation.rejected_version_id ?? validation.accepted_version_id ?? ''}-${validation.validation_status}`
    if (lastValidationKeyRef.current === key) return
    lastValidationKeyRef.current = key
    setActiveAssetTab(
      validation.validation_status === 'accepted' ? 'yaml' : 'harness',
    )
  }, [sessionEvents.latestValidation, setActiveAssetTab])

  useEffect(() => {
    if (errorMessage) {
      void notify.open({
        type: 'error',
        content: errorMessage,
        duration: 4,
        key: 'workspace-error',
      })
    }
  }, [errorMessage, notify])

  const reportedErrorRef = useRef<string | null>(null)
  useEffect(() => {
    if (!activeSessionId) return
    const storeError = sessionEvents.lastErrorMessage
    if (!storeError) return
    if (reportedErrorRef.current === storeError) return
    reportedErrorRef.current = storeError
    void notify.open({
      type: 'error',
      content: storeError,
      duration: 4,
      key: `workspace-store-error-${activeSessionId}`,
    })
    clearError(activeSessionId)
  }, [activeSessionId, sessionEvents.lastErrorMessage, notify, clearError])

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  useEffect(() => {
    return onAssetUpdated((sessionId, payload) => {
      if (sessionId !== activeSessionId) return
      const asset = payload.asset
      let nextTab: AssetTab | null = null
      let label = '项目资产'
      void queryClient.invalidateQueries({
        queryKey: sessionDetailKey(sessionId),
      })
      if (asset === 'chapters') {
        void queryClient.invalidateQueries({ queryKey: ['chapters', sessionId] })
        nextTab = 'chapters'
        label = '章节'
      } else if (asset === 'book_index') {
        void queryClient.invalidateQueries({ queryKey: ['book-index', sessionId] })
        nextTab = 'index'
        label = '剧情索引'
      } else if (asset === 'script_yaml') {
        void queryClient.invalidateQueries({
          queryKey: ['script-versions', sessionId],
        })
        nextTab = payload.validation_status === 'accepted' ? 'yaml' : 'harness'
        label = payload.validation_status === 'accepted' ? '剧本' : '校验报告'
      } else if (asset === 'project') {
        void queryClient.invalidateQueries({ queryKey: sessionsKey })
      }
      if (nextTab) {
        setAssetHighlights((prev) => ({ ...prev, [nextTab]: true }))
        setActiveAssetTab(nextTab)
        notification.success({
          message: `${label}已更新`,
          description: '右侧项目资产已刷新。',
          placement: 'topRight',
          duration: 2.5,
        })
      }
    })
  }, [onAssetUpdated, activeSessionId, queryClient, setActiveAssetTab, notification])

  const bubbleItems = useMemo(
    () =>
      // eslint-disable-next-line react-hooks/refs
      buildBubbleItems({
        messages,
        timeline: sessionDetail?.timeline ?? [],
        liveEvents: mergedEvents,
        pendingConfirmation,
        ruleDraft: pendingConfirmation
          ? ruleDrafts[pendingConfirmation.id]
          : undefined,
        isStreaming,
        onRuleDraftChange: handleRuleDraftChange,
        onConfirm: () => void handleConfirmation('confirm'),
        onCancel: () => void handleConfirmation('cancel'),
        onJumpAssetTab: handleSelectAssetTab,
        onOpenRejectedVersion: handleOpenVersion,
        onRetryLast: handleRetryLast,
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      messages,
      sessionDetail?.timeline,
      mergedEvents,
      pendingConfirmation,
      ruleDrafts,
      isStreaming,
    ],
  )

  const headerTitle = sessionDetail?.session.title ?? 'ScriptWeaver'
  const headerSubtitle = (() => {
    switch (projectStatus) {
      case 'uploading':
        return '正在识别项目并切分章节…'
      case 'generating':
        return '正在生成剧情索引与剧本…'
      case 'repairing':
        return 'harness 校验失败，Agent 正在自动修复…'
      case 'awaiting':
        return '已生成分章预案，等待你的确认'
      case 'failed':
        return projectId
          ? `项目 ${projectId.slice(0, 8)}… · 已保留 rejected 草稿`
          : '上一轮失败，已保留留痕'
      case 'ready':
        return projectId
          ? `项目 ${projectId.slice(0, 8)}… · 会话待命，可继续修改`
          : '会话待命，可继续修改'
      case 'idle':
      default:
        return projectId
          ? `项目 ${projectId.slice(0, 8)}…`
          : '上传小说 TXT 或描述需求，开始改编'
    }
  })()

  const panels = {
    chapters: (
      <ChaptersAsset
        chapters={chaptersQuery.data?.chapters ?? []}
        loading={chaptersQuery.isLoading}
      />
    ),
    index: (
      <BookIndexAsset
        data={bookIndexQuery.data ?? null}
        loading={bookIndexQuery.isLoading}
        error={Boolean(bookIndexQuery.error)}
      />
    ),
    yaml: (
      <ScriptYamlAsset
        yaml={versionDetailQuery.data?.script_yaml ?? ''}
        loading={versionDetailQuery.isLoading}
        version={versionDetailQuery.data?.version ?? null}
        validationReport={
          sessionEvents.latestValidation?.validation_report ?? null
        }
      />
    ),
    harness: <ValidationAsset validation={sessionEvents.latestValidation} />,
    versions: (
      <VersionsAsset
        versions={versions}
        selectedVersionId={effectiveVersionId}
        loading={versionsQuery.isLoading}
        onSelectVersion={(id) => {
          setSelectedVersionId(id)
          setActiveAssetTab('yaml')
        }}
      />
    ),
  }

  const showEmptyState = bubbleItems.length === 0 && !isStreaming
  const debugInfo = {
    activeSessionId,
    projectId,
    activeAssetTab,
    runStatus,
    isStreaming,
    sessionCount: sessions.length,
    archivedCount: archivedSessions.length,
  }

  return (
    <AppShell
      header={
        <>
          <WorkspaceHeader
            title={headerTitle}
            subtitle={headerSubtitle}
            projectStatus={projectStatus}
            runStatus={runStatus}
            isStreaming={isStreaming}
            modelUsage={sessionEvents.modelUsage}
          />
          <WorkspaceSettingsModal
            open={settingsOpen}
            themeMode={themeMode}
            archivedSessions={archivedSessions}
            archivedLoading={archivedSessionsQuery.isLoading}
            restoringSessionId={restoringSessionId}
            debugInfo={debugInfo}
            onClose={() => setSettingsOpen(false)}
            onThemeModeChange={setThemeMode}
            onRestoreSession={(sessionId) => void handleRestoreSession(sessionId)}
          />
        </>
      }
      leftRail={
        <LeftRail
          loading={sessionsQuery.isLoading}
          onCreate={() => void handleNewSession()}
          collapsed={leftRailCollapsed}
          onToggleCollapsed={() => setLeftRailCollapsed(!leftRailCollapsed)}
          onOpenSettings={() => setSettingsOpen(true)}
        >
          <ConversationsPanel
            sessions={sessions}
            activeSessionId={activeSessionId}
            onSelect={handleSelectSession}
            onArchive={(sessionId) => void handleArchiveSession(sessionId)}
          />
        </LeftRail>
      }
      rightInspector={
        <RightInspector projectId={projectId}>
          {hasProject ? (
            <AssetTabs
              activeTab={activeAssetTab}
              onTabChange={handleSelectAssetTab}
              panels={panels}
              highlightedTabs={assetHighlights}
            />
          ) : (
            <AssetGuide projectStatus={projectStatus} />
          )}
        </RightInspector>
      }
      leftRailCollapsed={leftRailCollapsed}
      rightInspectorWidth={rightInspectorWidth}
      onRightInspectorWidthChange={setRightInspectorWidth}
    >
      <div className="sw-workspace-main">
        {errorMessage ? (
          <Alert
            type="error"
            showIcon
            closable
            message={errorMessage}
            onClose={() => setErrorMessage(null)}
            className="sw-workspace-error"
          />
        ) : null}
        {showEmptyState ? (
          <div className="sw-workspace-empty" role="region" aria-label="空状态欢迎区">
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <span>
                  上传一段小说 TXT，或者直接发一条消息，让 Agent 开始改编为短剧。
                </span>
              }
            />
          </div>
        ) : (
          <ChatTimeline items={bubbleItems} />
        )}
        <ChatComposer
          message={message}
          onMessageChange={setMessage}
          onSubmit={(value) => void handleSend(value)}
          isStreaming={isStreaming}
          disabled={false}
          attachmentOpen={attachmentOpen}
          onToggleAttachment={() => setAttachmentOpen(!attachmentOpen)}
          sourceText={sourceText}
          sourceFileName={sourceFileName}
          onSourceTextChange={handleSourceTextChange}
          onSourceClear={handleSourceClear}
        />
      </div>
    </AppShell>
  )
}
