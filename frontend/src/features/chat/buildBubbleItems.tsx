import type { BubbleItemType } from '@ant-design/x'
import type {
  ChatConfirmation,
  ChatMessage,
  ChatTimelineItem,
  ToolCallEvent,
} from '../../types'
import {
  parseConfirmation,
  parseErrorEvent,
  parseMessageCreated,
  parseRunCompletedWithErrors,
  parseToolCallDelta,
  parseToolCallEvent,
  parseValidationCompleted,
  SSE_EVENT_NAMES,
  type LiveEvent,
  type ValidationCompletedPayload,
} from '../../lib/events'
import type { AssetTab } from '../../state/uiPrefs'
import { MessageBubbleContent } from './bubbles/MessageBubble'
import { ToolTraceBubble } from './bubbles/ToolTraceBubble'
import { ValidationBubble } from './bubbles/ValidationBubble'
import { ErrorBubble } from './bubbles/ErrorBubble'
import { RunSummaryBubble } from './bubbles/RunSummaryBubble'
import { ConfirmationBubble } from './bubbles/ConfirmationBubble'

export type BuildBubbleItemsArgs = {
  messages: ChatMessage[]
  timeline: ChatTimelineItem[]
  liveEvents: LiveEvent[]
  pendingConfirmation: ChatConfirmation | null
  ruleDraft: string | undefined
  isStreaming: boolean
  onRuleDraftChange: (confirmationId: string, value: string) => void
  onConfirm: () => void
  onCancel: () => void
  onJumpAssetTab: (tab: AssetTab) => void
  onOpenRejectedVersion: (versionId: string) => void
  onRetryLast?: () => void
}

type ParsedToolDelta = NonNullable<ReturnType<typeof parseToolCallDelta>>
type ParsedConfirmation = NonNullable<ReturnType<typeof parseConfirmation>>
type ParsedLiveMessage = ChatMessage & { run_id?: string }

type EventGroup = {
  runId: string
  userMessage?: ParsedLiveMessage
  messages: ParsedLiveMessage[]
  toolCalls: ToolCallEvent[]
  toolDeltas: ParsedToolDelta[]
  validations: ValidationCompletedPayload[]
  confirmations: ParsedConfirmation[]
  status: 'running' | 'completed' | 'completed_with_errors' | 'failed'
  endedMessage?: string
  rejectedVersionId?: string | null
  repairAttemptCount?: number
  errorMessage?: string
  errorCode?: string
}

const HIDDEN_TOOL_NAMES = new Set(['request_chapter_split_confirmation'])

function confirmationIdFromMessage(message: ChatMessage | null | undefined): string | null {
  const metadata = message?.metadata
  if (!metadata) return null
  const confirmationId = metadata.confirmation_id
  return typeof confirmationId === 'string' ? confirmationId : null
}

function emptyGroup(runId: string): EventGroup {
  return {
    runId,
    messages: [],
    toolCalls: [],
    toolDeltas: [],
    validations: [],
    confirmations: [],
    status: 'running',
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object'
}

function parseRunStartedUserMessage(event: LiveEvent): ParsedLiveMessage | null {
  const raw = event.data.user_message
  if (!isRecord(raw)) return null
  const role = raw.role
  if (role !== 'user' && role !== 'assistant' && role !== 'system' && role !== 'tool') {
    return null
  }
  if (typeof raw.id !== 'string' || typeof raw.session_id !== 'string') {
    return null
  }
  return {
    id: raw.id,
    session_id: raw.session_id,
    role,
    content: typeof raw.content === 'string' ? raw.content : '',
    metadata: isRecord(raw.metadata) ? raw.metadata : null,
    created_at: typeof raw.created_at === 'string' ? raw.created_at : '',
    run_id: typeof event.data.run_id === 'string' ? event.data.run_id : undefined,
  }
}

function ensureGroup(
  groups: EventGroup[],
  groupsByRunId: Map<string, EventGroup>,
  runId: string,
): EventGroup {
  let group = groupsByRunId.get(runId)
  if (!group) {
    group = emptyGroup(runId)
    groupsByRunId.set(runId, group)
    groups.push(group)
  }
  return group
}

function partitionByRun(events: LiveEvent[]): EventGroup[] {
  const groups: EventGroup[] = []
  const groupsByRunId = new Map<string, EventGroup>()
  let current: EventGroup | null = null

  for (const event of events) {
    if (event.event === SSE_EVENT_NAMES.runStarted) {
      const runId =
        typeof event.data.run_id === 'string' ? event.data.run_id : `run-${groups.length + 1}`
      current = ensureGroup(groups, groupsByRunId, runId)
      current.userMessage = current.userMessage ?? parseRunStartedUserMessage(event) ?? undefined
      continue
    }

    const eventRunId = typeof event.data.run_id === 'string' ? event.data.run_id : null
    if (eventRunId) {
      current = ensureGroup(groups, groupsByRunId, eventRunId)
    }
    if (!current) {
      current = ensureGroup(groups, groupsByRunId, eventRunId ?? `run-${groups.length + 1}`)
    }

    switch (event.event) {
      case SSE_EVENT_NAMES.messageCreated: {
        const message = parseMessageCreated(event)
        if (message) {
          current.messages.push(message)
          if (message.role === 'user') {
            current.userMessage = current.userMessage ?? message
          }
        }
        break
      }
      case SSE_EVENT_NAMES.toolCallStarted:
      case SSE_EVENT_NAMES.toolCallCompleted:
      case SSE_EVENT_NAMES.toolCallFailed: {
        const tool = parseToolCallEvent(event)
        if (tool) current.toolCalls.push(tool)
        break
      }
      case SSE_EVENT_NAMES.toolCallDelta: {
        const delta = parseToolCallDelta(event)
        if (delta) current.toolDeltas.push(delta)
        break
      }
      case SSE_EVENT_NAMES.toolConfirmRequired: {
        const confirmation = parseConfirmation(event)
        if (confirmation) current.confirmations.push(confirmation)
        break
      }
      case SSE_EVENT_NAMES.validationCompleted: {
        const validation = parseValidationCompleted(event)
        if (validation) current.validations.push(validation)
        break
      }
      case SSE_EVENT_NAMES.runCompleted: {
        current.status = 'completed'
        break
      }
      case SSE_EVENT_NAMES.runCompletedWithErrors: {
        const payload = parseRunCompletedWithErrors(event)
        if (payload) {
          current.status = 'completed_with_errors'
          current.endedMessage = payload.message
          current.rejectedVersionId = payload.rejected_version_id
          current.repairAttemptCount = payload.repair_attempt_count
        }
        break
      }
      case SSE_EVENT_NAMES.error: {
        const payload = parseErrorEvent(event)
        current.status = 'failed'
        current.errorMessage = payload.message
        current.errorCode = payload.code
        break
      }
      default:
        break
    }
  }
  return groups
}

function dedupeToolCalls(
  toolCalls: ToolCallEvent[],
  toolDeltas: ParsedToolDelta[],
): ToolCallEvent[] {
  const map = new Map<string, ToolCallEvent>()
  for (const tool of toolCalls) {
    const existing = map.get(tool.id)
    map.set(tool.id, {
      ...tool,
      deltas: existing?.deltas ?? tool.deltas,
    })
  }
  for (const delta of toolDeltas) {
    const existing = map.get(delta.id)
    if (!existing) continue
    map.set(delta.id, {
      ...existing,
      deltas: [...(existing.deltas ?? []), delta],
    })
  }
  return Array.from(map.values())
}

function mergeToolWithLive(
  persisted: ToolCallEvent,
  live: ToolCallEvent | undefined,
): ToolCallEvent {
  if (!live) return persisted
  const liveIsStaleRunning =
    (persisted.status === 'completed' || persisted.status === 'failed') &&
    live.status === 'running'
  if (liveIsStaleRunning) {
    return {
      ...persisted,
      deltas: [...(persisted.deltas ?? []), ...(live.deltas ?? [])],
    }
  }
  return {
    ...persisted,
    ...live,
    input: live.input ?? persisted.input,
    output: live.output ?? persisted.output,
    error_message: live.error_message ?? persisted.error_message,
    duration_ms: live.duration_ms ?? persisted.duration_ms,
    deltas: [...(persisted.deltas ?? []), ...(live.deltas ?? [])],
  }
}

export function buildBubbleItems(args: BuildBubbleItemsArgs): BubbleItemType[] {
  const {
    messages,
    timeline,
    liveEvents,
    pendingConfirmation,
    ruleDraft,
    isStreaming,
    onRuleDraftChange,
    onConfirm,
    onCancel,
    onJumpAssetTab,
    onOpenRejectedVersion,
    onRetryLast,
  } = args

  const groups = partitionByRun(liveEvents)
  const liveToolsById = new Map<string, ToolCallEvent>()
  const liveMessagesById = new Map<string, ParsedLiveMessage>()
  const timelineRunIds = new Set<string>()

  for (const group of groups) {
    if (group.userMessage) {
      liveMessagesById.set(group.userMessage.id, group.userMessage)
    }
    for (const message of group.messages) {
      liveMessagesById.set(message.id, message)
    }
    for (const tool of dedupeToolCalls(group.toolCalls, group.toolDeltas)) {
      liveToolsById.set(tool.id, tool)
    }
  }
  for (const item of timeline) {
    if (item.run_id) timelineRunIds.add(item.run_id)
  }

  const items: BubbleItemType[] = []
  const renderedMessageIds = new Set<string>()
  const renderedToolIds = new Set<string>()
  const renderedConfirmationIds = new Set<string>()

  function appendMessage(message: ChatMessage | null | undefined, runId?: string | null): void {
    if (!message || message.role === 'tool' || !message.content.trim()) return
    if (renderedMessageIds.has(message.id)) return
    renderedMessageIds.add(message.id)
    items.push({
      key: `message-${message.id}`,
      role: message.role === 'user' ? 'user' : 'ai',
      content: <MessageBubbleContent message={message} />,
    })

    const confirmationId = confirmationIdFromMessage(message)
    if (
      confirmationId &&
      pendingConfirmation?.id === confirmationId &&
      !renderedConfirmationIds.has(confirmationId)
    ) {
      appendConfirmation(pendingConfirmation, runId)
    }
  }

  function appendTool(tool: ToolCallEvent | null | undefined): void {
    if (!tool || renderedToolIds.has(tool.id) || HIDDEN_TOOL_NAMES.has(tool.name)) return
    renderedToolIds.add(tool.id)
    items.push({
      key: `tool-${tool.id}`,
      role: 'tool',
      content: <ToolTraceBubble tool={tool} />,
    })
  }

  function appendConfirmation(
    confirmation: ChatConfirmation | null | undefined,
    runId?: string | null,
  ): void {
    if (!confirmation || confirmation.status !== 'pending') return
    if (!pendingConfirmation || pendingConfirmation.id !== confirmation.id) return
    const effective = pendingConfirmation
    if (renderedConfirmationIds.has(effective.id)) return
    renderedConfirmationIds.add(effective.id)
    items.push({
      key: `confirmation-${effective.id}`,
      role: 'confirm',
      content: (
        <ConfirmationBubble
          confirmation={effective}
          ruleDraft={ruleDraft}
          isStreaming={isStreaming}
          onRuleDraftChange={onRuleDraftChange}
          onConfirm={onConfirm}
          onCancel={onCancel}
        />
      ),
    })
    if (runId) timelineRunIds.add(runId)
  }

  function appendValidation(group: EventGroup): void {
    for (const validation of group.validations) {
      items.push({
        key: `validation-${group.runId}-${validation.rejected_version_id ?? validation.accepted_version_id ?? items.length}`,
        role: 'validation',
        content: (
          <ValidationBubble
            payload={validation}
            onOpenHarness={() => onJumpAssetTab('harness')}
            onOpenYaml={() => {
              onJumpAssetTab('yaml')
              if (validation.rejected_version_id) {
                onOpenRejectedVersion(validation.rejected_version_id)
              } else if (validation.accepted_version_id) {
                onOpenRejectedVersion(validation.accepted_version_id)
              }
            }}
          />
        ),
      })
    }
  }

  function appendRunProblem(group: EventGroup): void {
    if (group.status === 'completed_with_errors') {
      items.push({
        key: `done-errors-${group.runId}`,
        role: 'validation',
        content: (
          <RunSummaryBubble
            variant="completed_with_errors"
            message={group.endedMessage}
            rejectedVersionId={group.rejectedVersionId}
            repairAttemptCount={group.repairAttemptCount}
            onOpenRejected={
              group.rejectedVersionId
                ? () => {
                    onJumpAssetTab('versions')
                    onOpenRejectedVersion(group.rejectedVersionId!)
                  }
                : undefined
            }
          />
        ),
      })
    } else if (group.status === 'failed') {
      items.push({
        key: `error-${group.runId}`,
        role: 'system',
        content: (
          <ErrorBubble
            payload={{
              run_id: group.runId,
              message: group.errorMessage ?? '执行失败',
              code: group.errorCode,
            }}
            onRetry={onRetryLast}
          />
        ),
      })
    }
  }

  for (const item of timeline) {
    if (item.kind === 'message') {
      appendMessage(
        liveMessagesById.get(item.message?.id ?? '') ?? item.message,
        item.run_id,
      )
    } else if (item.kind === 'tool_call') {
      const tool = item.tool_call
      appendTool(tool ? mergeToolWithLive(tool, liveToolsById.get(tool.id)) : null)
    } else if (item.kind === 'confirmation') {
      appendConfirmation(item.confirmation, item.run_id)
    }
  }

  if (timeline.length === 0) {
    for (const message of messages) {
      appendMessage(message, null)
    }
  }

  for (const group of groups) {
    appendMessage(group.userMessage, group.runId)
    for (const tool of dedupeToolCalls(group.toolCalls, group.toolDeltas)) {
      appendTool(tool)
    }
    for (const message of group.messages) {
      appendMessage(message, group.runId)
    }

    const lastConfirmation = group.confirmations[group.confirmations.length - 1]
    appendConfirmation(
      pendingConfirmation?.id === lastConfirmation?.id ? pendingConfirmation : lastConfirmation,
      group.runId,
    )

    appendValidation(group)
    if (!timelineRunIds.has(group.runId) || group.status !== 'completed') {
      appendRunProblem(group)
    }
  }

  if (
    pendingConfirmation &&
    !renderedConfirmationIds.has(pendingConfirmation.id)
  ) {
    appendConfirmation(pendingConfirmation, null)
  }

  return items
}
