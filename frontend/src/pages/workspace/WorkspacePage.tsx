import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { App as AntdApp, Alert, Button, Empty, Modal, Space, Tabs } from 'antd'
import { useQueryClient } from '@tanstack/react-query'
import { AppShell } from '../../layout/AppShell'
import { WorkspaceStatusBar } from '../../layout/WorkspaceStatusBar'
import { LeftRail } from '../../layout/LeftRail'
import { WorkspaceSettingsModal } from '../../layout/WorkspaceSettingsModal'
import { ConversationsPanel } from '../../features/sessions/ConversationsPanel'
import { ProjectStructurePanel } from '../../features/workspace/ProjectStructurePanel'
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
  useSaveScriptYaml,
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
import { LiveToolStream } from '../../features/chat/LiveToolStream'
import { buildBubbleItems } from '../../features/chat/buildBubbleItems'
import { buildHistoryEvents } from '../../features/chat/replayHistory'
import { AssetGuide } from '../../features/assets/AssetGuide'
import { OverviewAsset } from '../../features/assets/OverviewAsset'
import { ChapterDetailAsset } from '../../features/assets/ChapterDetailAsset'
import { CharactersAsset } from '../../features/assets/CharactersAsset'
import { LocationsAsset } from '../../features/assets/LocationsAsset'
import { EventsAsset } from '../../features/assets/EventsAsset'
import { ScriptYamlAsset, type ScriptDraftState } from '../../features/assets/ScriptYamlAsset'
import { ValidationAsset } from '../../features/assets/ValidationAsset'
import { VersionsAsset } from '../../features/assets/VersionsAsset'
import {
  buildVersionLabelMap,
  getLatestAcceptedVersion,
} from '../../features/assets/versionLabels'
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

type WorkbenchMeta = { title: string; subtitle: string }

type PendingChatSend = {
  message: string
  sourceText: string
  sourceFileName: string
}

type ScriptVersionCarrier = {
  accepted_version_id?: string | null
  rejected_version_id?: string | null
}

function getUpdatedScriptVersionId(payload: ScriptVersionCarrier): string | null {
  return payload.accepted_version_id ?? payload.rejected_version_id ?? null
}

function getWorkbenchMeta(
  tab: AssetTab,
  options: { selectedChapter?: { order: number; title: string } | null } = {},
): WorkbenchMeta {
  switch (tab) {
    case 'overview':
      return {
        title: '项目基础信息',
        subtitle: '一句话故事、风格设定与资产总览。',
      }
    case 'script':
      return {
        title: '剧本',
        subtitle: '在可视化表单和 YAML 源码之间切换查看剧本草稿。',
      }
    case 'chapter': {
      if (options.selectedChapter) {
        const orderLabel = String(options.selectedChapter.order).padStart(2, '0')
        return {
          title: `第 ${orderLabel} 章 · ${options.selectedChapter.title}`,
          subtitle: '查看本章原文、摘要与抽取出的事件。',
        }
      }
      return {
        title: '章节',
        subtitle: '请在左侧选择具体章节。',
      }
    }
    case 'characters':
      return {
        title: '角色设定',
        subtitle: '抽取出的角色名册与基本设定卡片。',
      }
    case 'locations':
      return {
        title: '场景地点',
        subtitle: '故事发生的地点列表。',
      }
    case 'events':
      return {
        title: '核心事件',
        subtitle: '按章节排列的关键事件时间线。',
      }
    case 'validation':
      return {
        title: '规则校验',
        subtitle: '查看本地验证结果、问题定位和修复建议。',
      }
    case 'versions':
      return {
        title: '历史版本',
        subtitle: '回看已生成的 accepted / rejected 剧本版本。',
      }
  }
}

export default function WorkspacePage() {
  const { sessionId: routeSessionId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { message: notify, modal, notification } = AntdApp.useApp()

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
  const [selectedChapterId, setSelectedChapterId] = useState<string | null>(null)
  const [scriptDraftState, setScriptDraftState] = useState<ScriptDraftState>({
    dirty: false,
    yaml: '',
  })
  const [scriptDiscardKey, setScriptDiscardKey] = useState(0)
  const [pendingDirtySend, setPendingDirtySend] = useState<PendingChatSend | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const lastScriptVersionRefreshKeyRef = useRef<string | null>(null)
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
  const versionLabels = useMemo(() => buildVersionLabelMap(versions), [versions])
  const accepted = useMemo(() => getLatestAcceptedVersion(versions), [versions])
  const effectiveVersionId =
    selectedVersionId ?? accepted?.id ?? versions[0]?.id ?? null
  const selectedVersionLabel = effectiveVersionId
    ? (versionLabels.get(effectiveVersionId) ?? null)
    : null
  const selectedVersionReason = selectedVersionLabel
    ? `${selectedVersionLabel.description}（${effectiveVersionId}）`
    : effectiveVersionId
      ? `版本 ${effectiveVersionId}`
      : '当前版本'
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
  const sessionsCreate = useCreateSession()
  const sessionsArchive = useArchiveSession()
  const sessionsRestore = useRestoreSession()
  const scriptSave = useSaveScriptYaml()

  const handleRuleDraftChange = useCallback(
    (confirmationId: string, value: string) => {
      setRuleDrafts((prev) => ({ ...prev, [confirmationId]: value }))
    },
    [],
  )

  const handleSelectAssetTab = useCallback(
    (tab: AssetTab, chapterId?: string | null) => {
      setActiveAssetTab(tab)
      setAssetHighlights((prev) => ({ ...prev, [tab]: false }))
      if (tab === 'chapter') {
        if (chapterId !== undefined) setSelectedChapterId(chapterId)
      } else if (chapterId === null) {
        setSelectedChapterId(null)
      }
    },
    [setActiveAssetTab],
  )

  const applySelectedScriptVersion = useCallback((versionId: string) => {
    setSelectedVersionId(versionId)
    setActiveAssetTab('script')
    setScriptDraftState({ dirty: false, yaml: '' })
    setScriptDiscardKey((value) => value + 1)
  }, [setActiveAssetTab])

  const handleOpenVersion = useCallback(
    (versionId: string) => {
      applySelectedScriptVersion(versionId)
    },
    [applySelectedScriptVersion],
  )

  const handleSelectScriptVersion = useCallback(
    (versionId: string) => {
      if (versionId === effectiveVersionId) {
        setActiveAssetTab('script')
        return
      }
      if (!scriptDraftState.dirty) {
        applySelectedScriptVersion(versionId)
        return
      }
      modal.confirm({
        title: '切换剧本版本？',
        content:
          '当前可视化编辑器里有未保存改动。切换版本会丢弃这些本地改动，历史版本本身不会被覆盖。',
        okText: '丢弃并切换',
        cancelText: '取消',
        onOk: () => applySelectedScriptVersion(versionId),
      })
    },
    [
      applySelectedScriptVersion,
      effectiveVersionId,
      modal,
      scriptDraftState.dirty,
      setActiveAssetTab,
    ],
  )

  const handleScriptDraftStateChange = useCallback((state: ScriptDraftState) => {
    setScriptDraftState(state)
  }, [])

  const refreshScriptVersionFromEvent = useCallback(
    (versionId: string | null) => {
      if (!activeSessionId || !versionId) return
      const refreshKey = `${activeSessionId}:${versionId}`
      void queryClient.invalidateQueries({
        queryKey: ['script-versions', activeSessionId],
      })
      void queryClient.invalidateQueries({
        queryKey: ['script-version-detail', activeSessionId, versionId],
      })
      if (lastScriptVersionRefreshKeyRef.current === refreshKey) return
      lastScriptVersionRefreshKeyRef.current = refreshKey
      setSelectedVersionId(versionId)
      setScriptDraftState({ dirty: false, yaml: '' })
      setScriptDiscardKey((value) => value + 1)
    },
    [activeSessionId, queryClient],
  )

  const handleSaveScriptYaml = useCallback(
    async (yaml: string) => {
      if (!activeSessionId) {
        void notify.open({
          type: 'warning',
          content: '请先创建或选择一个会话。',
          duration: 3,
        })
        return null
      }
      try {
        const response = await scriptSave.mutateAsync({
          sessionId: activeSessionId,
          payload: {
            script_yaml: yaml,
            reason: `可视化编辑器：从${selectedVersionReason}派生保存手动修改`,
          },
        })
        const nextVersionId = getUpdatedScriptVersionId(response)
        if (nextVersionId) {
          refreshScriptVersionFromEvent(nextVersionId)
        }
        setScriptDraftState({ dirty: false, yaml: response.script_yaml })
        await refreshSessionAssets(queryClient, activeSessionId)
        if (response.validation_status === 'accepted') {
          setActiveAssetTab('script')
          void notify.open({
            type: 'success',
            content: '剧本修改已保存为新版本',
            duration: 2.5,
          })
        } else {
          setActiveAssetTab('validation')
          void notify.open({
            type: 'warning',
            content: '修改已保存为未通过验证的草稿，请先查看校验问题。',
            duration: 4,
          })
        }
        return response
      } catch (error) {
        void notify.open({
          type: 'error',
          content: getErrorMessage(error),
          duration: 4,
        })
        return null
      }
    },
    [
      activeSessionId,
      notify,
      queryClient,
      refreshScriptVersionFromEvent,
      selectedVersionReason,
      scriptSave,
      setActiveAssetTab,
    ],
  )

  async function handleSaveDirtyAndSend() {
    const pending = pendingDirtySend
    if (!pending || isStreaming) return
    const response = await handleSaveScriptYaml(scriptDraftState.yaml)
    if (response?.validation_status !== 'accepted') {
      setPendingDirtySend(null)
      return
    }
    setPendingDirtySend(null)
    await submitChatRun(pending.message, pending.sourceText, pending.sourceFileName)
  }

  async function handleDiscardDirtyAndSend() {
    const pending = pendingDirtySend
    if (!pending || isStreaming) return
    setScriptDiscardKey((value) => value + 1)
    setScriptDraftState({ dirty: false, yaml: '' })
    setPendingDirtySend(null)
    await submitChatRun(pending.message, pending.sourceText, pending.sourceFileName)
  }

  async function ensureSession(): Promise<string> {
    if (activeSessionId) return activeSessionId
    const created = await sessionsCreate.mutateAsync(undefined)
    navigate(`/sessions/${created.id}`, { replace: true })
    return created.id
  }

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

  async function submitChatRun(
    finalMessage: string,
    finalSource: string,
    finalSourceFileName: string,
  ) {
    setErrorMessage(null)
    setIsStreaming(true)
    try {
      const sessionId = await ensureSession()
      const payload: ChatRunRequest = {
        message: finalMessage || '请开始改编这篇小说。',
        source_file_name: finalSource ? finalSourceFileName : null,
        source_text: finalSource || null,
        screenplay_format: 'short_drama',
      }
      lastSendArgsRef.current = { sessionId, payload }
      setMessage('')
      setAttachmentOpen(false)
      await runStream(sessionId, `/chat/sessions/${sessionId}/runs/stream`, payload)
      setSourceText('')
      await refreshSessionAssets(queryClient, sessionId)
      setActiveAssetTab('script')
    } catch (error) {
      if ((error as DOMException)?.name === 'AbortError') return
      setErrorMessage(getErrorMessage(error))
    } finally {
      setIsStreaming(false)
    }
  }

  async function handleSend(submitted?: string) {
    const finalMessage = (submitted ?? message).trim()
    const finalSource = sourceText.trim()
    if ((!finalMessage && !finalSource) || isStreaming) return

    if (scriptDraftState.dirty && scriptDraftState.yaml.trim()) {
      setPendingDirtySend({
        message: finalMessage,
        sourceText: finalSource,
        sourceFileName,
      })
      return
    }

    await submitChatRun(finalMessage, finalSource, sourceFileName)
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
      setActiveAssetTab(action === 'confirm' ? 'script' : 'overview')
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
      setScriptDraftState({ dirty: false, yaml: '' })
      setScriptDiscardKey((value) => value + 1)
      navigate(`/sessions/${created.id}`)
    } catch (error) {
      setErrorMessage(getErrorMessage(error))
    }
  }

  function handleSelectSession(sessionId: string) {
    setMessage('')
    setSourceText('')
    setSelectedVersionId(null)
    setScriptDraftState({ dirty: false, yaml: '' })
    setScriptDiscardKey((value) => value + 1)
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

  useEffect(() => {
    lastScriptVersionRefreshKeyRef.current = null
  }, [activeSessionId])

  const lastValidationKeyRef = useRef<string | null>(null)
  useEffect(() => {
    const validation = sessionEvents.latestValidation
    if (!validation) return
    const key = `${validation.rejected_version_id ?? validation.accepted_version_id ?? ''}-${validation.validation_status}`
    if (lastValidationKeyRef.current === key) return
    lastValidationKeyRef.current = key
    refreshScriptVersionFromEvent(getUpdatedScriptVersionId(validation))
    setActiveAssetTab(
      validation.validation_status === 'accepted' ? 'script' : 'validation',
    )
  }, [refreshScriptVersionFromEvent, sessionEvents.latestValidation, setActiveAssetTab])

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
      let highlightTab: AssetTab | null = null
      let label = '项目资产'
      void queryClient.invalidateQueries({
        queryKey: sessionDetailKey(sessionId),
      })
      if (asset === 'chapters') {
        void queryClient.invalidateQueries({ queryKey: ['chapters', sessionId] })
        highlightTab = 'overview'
        label = '章节'
      } else if (asset === 'book_index') {
        void queryClient.invalidateQueries({ queryKey: ['book-index', sessionId] })
        highlightTab = 'characters'
        label = '剧情索引'
      } else if (asset === 'script_yaml') {
        refreshScriptVersionFromEvent(getUpdatedScriptVersionId(payload))
        void queryClient.invalidateQueries({
          queryKey: ['script-versions', sessionId],
        })
        const nextVersionId = getUpdatedScriptVersionId(payload)
        if (nextVersionId) {
          void queryClient.invalidateQueries({
            queryKey: ['script-version-detail', sessionId, nextVersionId],
          })
        }
        nextTab = payload.validation_status === 'accepted' ? 'script' : 'validation'
        highlightTab = nextTab
        label = payload.validation_status === 'accepted' ? '剧本' : '校验报告'
      } else if (asset === 'project') {
        void queryClient.invalidateQueries({ queryKey: sessionsKey })
      }
      if (highlightTab) {
        setAssetHighlights((prev) => ({ ...prev, [highlightTab]: true }))
      }
      if (nextTab) {
        setActiveAssetTab(nextTab)
      }
      if (highlightTab) {
        notification.success({
          message: `${label}已更新`,
          description: '中间剧本工作区已刷新。',
          placement: 'topRight',
          duration: 2.5,
        })
      }
    })
  }, [
    onAssetUpdated,
    activeSessionId,
    queryClient,
    refreshScriptVersionFromEvent,
    setActiveAssetTab,
    notification,
  ])

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

  const statusBarBrand = 'ScriptWeaver'
  const statusBarTip = (() => {
    switch (projectStatus) {
      case 'uploading':
        return '正在识别项目并切分章节…'
      case 'generating':
        return '正在生成剧情索引与剧本…'
      case 'repairing':
        return '本地验证失败，Agent 正在自动修复…'
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

  const chapterList = chaptersQuery.data?.chapters ?? []
  const selectedChapter =
    selectedChapterId != null
      ? (chapterList.find((c) => c.id === selectedChapterId) ?? null)
      : null

  const panels: Record<AssetTab, ReactNode> = {
    overview: (
      <OverviewAsset
        loading={chaptersQuery.isLoading || bookIndexQuery.isLoading}
        yaml={versionDetailQuery.data?.script_yaml ?? ''}
        chapters={chapterList}
        bookIndex={bookIndexQuery.data ?? null}
        versions={versions}
        validation={sessionEvents.latestValidation}
      />
    ),
    script: (
      <ScriptYamlAsset
        sessionId={activeSessionId}
        yaml={versionDetailQuery.data?.script_yaml ?? ''}
        loading={versionDetailQuery.isLoading}
        version={versionDetailQuery.data?.version ?? null}
        versionLabel={selectedVersionLabel}
        validationReport={
          sessionEvents.latestValidation?.validation_report ?? null
        }
        resetKey={scriptDiscardKey}
        onDraftStateChange={handleScriptDraftStateChange}
        onSaveScriptYaml={handleSaveScriptYaml}
      />
    ),
    chapter: (
      <ChapterDetailAsset
        chapter={selectedChapter}
        loading={chaptersQuery.isLoading}
        bookIndex={bookIndexQuery.data ?? null}
      />
    ),
    characters: (
      <CharactersAsset
        data={bookIndexQuery.data ?? null}
        loading={bookIndexQuery.isLoading}
      />
    ),
    locations: (
      <LocationsAsset
        data={bookIndexQuery.data ?? null}
        loading={bookIndexQuery.isLoading}
      />
    ),
    events: (
      <EventsAsset
        data={bookIndexQuery.data ?? null}
        loading={bookIndexQuery.isLoading}
      />
    ),
    validation: <ValidationAsset validation={sessionEvents.latestValidation} />,
    versions: (
      <VersionsAsset
        versions={versions}
        selectedVersionId={effectiveVersionId}
        loading={versionsQuery.isLoading}
        onSelectVersion={handleSelectScriptVersion}
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
  const workbenchMeta = getWorkbenchMeta(activeAssetTab, {
    selectedChapter: selectedChapter
      ? { order: selectedChapter.order_index + 1, title: selectedChapter.title }
      : null,
  })

  return (
    <>
      <AppShell
      statusBar={
        <>
          <WorkspaceStatusBar
            brand={statusBarBrand}
            tip={statusBarTip}
            projectStatus={projectStatus}
            runStatus={runStatus}
            isStreaming={isStreaming}
            modelUsage={sessionEvents.modelUsage}
            onOpenSettings={() => setSettingsOpen(true)}
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
        >
          <Tabs
            className="sw-rail-tabs"
            size="small"
            items={[
              {
                key: 'structure',
                label: '结构',
                children: (
                  <ProjectStructurePanel
                    hasProject={hasProject}
                    chapters={chaptersQuery.data?.chapters ?? []}
                    chaptersLoading={chaptersQuery.isLoading}
                    bookIndex={bookIndexQuery.data ?? null}
                    bookIndexLoading={bookIndexQuery.isLoading}
                    versions={versions}
                    selectedScriptVersionLabel={selectedVersionLabel?.shortLabel ?? null}
                    selectedScriptVersionTone={selectedVersionLabel?.kind ?? null}
                    activeTab={activeAssetTab}
                    selectedChapterId={selectedChapterId}
                    highlightedTabs={assetHighlights}
                    onSelectTab={handleSelectAssetTab}
                  />
                ),
              },
              {
                key: 'sessions',
                label: '会话',
                children: (
                  <ConversationsPanel
                    sessions={sessions}
                    activeSessionId={activeSessionId}
                    onSelect={handleSelectSession}
                    onArchive={(sessionId) => void handleArchiveSession(sessionId)}
                  />
                ),
              },
            ]}
          />
        </LeftRail>
      }
      rightPaneLabel="AI 对话侧栏"
      rightInspector={
        <section className="sw-chat-panel" aria-label="AI 对话与修改指令">
          <header className="sw-chat-panel-head">
            <div>
              <div className="sw-chat-panel-title">AI 对话</div>
              <div className="sw-chat-panel-subtitle">
                用自然语言继续调整剧本，执行细节默认收起。
              </div>
            </div>
          </header>
          {showEmptyState ? (
            <div className="sw-chat-empty" role="region" aria-label="空对话提示">
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="先上传小说 TXT，或直接描述你想生成怎样的结构化剧本。"
              />
            </div>
          ) : (
            <ChatTimeline items={bubbleItems} />
          )}
          <LiveToolStream sessionId={activeSessionId} />
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
        </section>
      }
      leftRailCollapsed={leftRailCollapsed}
      rightInspectorWidth={rightInspectorWidth}
      onRightInspectorWidthChange={setRightInspectorWidth}
    >
      <div className="sw-workbench-main">
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
        {hasProject ? (
          <section className="sw-script-workbench" aria-label="剧本预览与编辑工作区">
            <header className="sw-workbench-document-head">
              <div>
                <div className="sw-workbench-document-title">{workbenchMeta.title}</div>
                <div className="sw-workbench-document-subtitle">
                  {workbenchMeta.subtitle}
                </div>
              </div>
            </header>
            <div className="sw-workbench-document-body">
              {panels[activeAssetTab]}
            </div>
          </section>
        ) : (
          <section className="sw-script-workbench" aria-label="剧本预览与编辑工作区">
            <AssetGuide projectStatus={projectStatus} />
          </section>
        )}
      </div>
      </AppShell>
      <Modal
        title="你有未保存的剧本修改"
        open={Boolean(pendingDirtySend)}
        onCancel={() => setPendingDirtySend(null)}
        footer={
          <Space>
            <Button onClick={() => setPendingDirtySend(null)}>取消</Button>
            <Button
              disabled={isStreaming}
              onClick={() => void handleDiscardDirtyAndSend()}
            >
              丢弃后发送
            </Button>
            <Button
              type="primary"
              loading={scriptSave.isPending}
              disabled={isStreaming}
              onClick={() => void handleSaveDirtyAndSend()}
            >
              保存并发送
            </Button>
          </Space>
        }
      >
        继续发送会让 Agent 读取当前已保存版本。建议先保存可视化编辑器里的改动，
        再让 AI 基于新剧本继续修改。
      </Modal>
    </>
  )
}
