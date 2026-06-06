import type {
  ChatConfirmation,
  ChatMessage,
  ContextPackingReport,
  JsonRecord,
  ModelUsage,
  RunStatus,
  SseEvent,
  ToolCallDelta,
  ToolCallEvent,
  ValidationReport,
} from '../types'

export type LiveEvent = SseEvent & {
  id: string
  receivedAt: number
}

export type RunStartedPayload = {
  run_id: string
  session_id: string
  user_message_id?: string
  user_message?: ChatMessage
}

export type RunProgressPayload = {
  run_id: string
  stage: string
  status: 'started' | 'completed' | 'failed'
  duration_ms?: number
  message?: string
  started_at?: string
}

export type HeartbeatPayload = {
  run_id: string
  stage: string
  created_at: string
}

export type ValidationCompletedPayload = {
  project_id: string
  validation_status: 'accepted' | 'rejected'
  accepted_version_id: string | null
  rejected_version_id: string | null
  repair_attempt_count: number
  validation_report: ValidationReport
  context_report: ContextPackingReport | null
}

export type ModelUsagePayload = ModelUsage

export type AssetUpdatedPayload = {
  asset: 'project' | 'chapters' | 'book_index' | 'script_yaml' | string
  project_id: string
  accepted_version_id?: string | null
  rejected_version_id?: string | null
  validation_status?: string
  repair_attempt_count?: number
  validation_report?: ValidationReport | null
  context_report?: ContextPackingReport | null
  [key: string]: unknown
}

export type RunCompletedPayload = {
  run_id: string
}

export type RunCompletedWithErrorsPayload = {
  run_id: string
  message: string
  rejected_version_id: string | null
  repair_attempt_count: number
}

export type ErrorEventPayload = {
  run_id?: string
  message: string
  code?: string
}

export const SSE_EVENT_NAMES = {
  runStarted: 'run.started',
  runProgress: 'run.progress',
  heartbeat: 'heartbeat',
  messageCreated: 'message.created',
  messageDelta: 'message.delta',
  toolCallStarted: 'tool.call.started',
  toolCallDelta: 'tool.call.delta',
  toolCallCompleted: 'tool.call.completed',
  toolCallFailed: 'tool.call.failed',
  toolConfirmRequired: 'tool.confirm.required',
  toolConfirmCancelled: 'tool.confirm.cancelled',
  runWaitingConfirmation: 'run.waiting_confirmation',
  assetUpdated: 'asset.updated',
  validationCompleted: 'validation.completed',
  modelUsage: 'model.usage.estimated',
  runCompleted: 'run.completed',
  runCompletedWithErrors: 'run.completed_with_errors',
  error: 'error',
} as const

export type SseEventName = (typeof SSE_EVENT_NAMES)[keyof typeof SSE_EVENT_NAMES]

function asString(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function asRecord(value: unknown): JsonRecord | null {
  return value && typeof value === 'object' ? (value as JsonRecord) : null
}

function asNumber(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function asNullableString(value: unknown): string | null {
  return typeof value === 'string' ? value : null
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter((item): item is string => typeof item === 'string')
}

function asValidationReport(value: unknown): ValidationReport | null {
  const record = asRecord(value)
  if (!record) {
    return null
  }
  if (typeof record.accepted !== 'boolean') {
    return null
  }
  return record as unknown as ValidationReport
}

export function parseRunProgress(event: SseEvent): RunProgressPayload | null {
  const data = event.data
  const status = asString(data.status)
  if (status !== 'started' && status !== 'completed' && status !== 'failed') {
    return null
  }
  return {
    run_id: asString(data.run_id),
    stage: asString(data.stage),
    status,
    duration_ms: typeof data.duration_ms === 'number' ? data.duration_ms : undefined,
    message: typeof data.message === 'string' ? data.message : undefined,
    started_at: typeof data.started_at === 'string' ? data.started_at : undefined,
  }
}

export function parseMessageCreated(event: SseEvent): (ChatMessage & { run_id?: string }) | null {
  const data = event.data
  const role = asString(data.role)
  if (role !== 'user' && role !== 'assistant' && role !== 'system' && role !== 'tool') {
    return null
  }
  if (typeof data.id !== 'string' || typeof data.session_id !== 'string') {
    return null
  }
  return {
    id: data.id,
    session_id: data.session_id,
    role,
    content: asString(data.content),
    metadata: asRecord(data.metadata),
    created_at: asString(data.created_at),
    run_id: typeof data.run_id === 'string' ? data.run_id : undefined,
  }
}

export function parseHeartbeat(event: SseEvent): HeartbeatPayload | null {
  const data = event.data
  if (typeof data.run_id !== 'string' || typeof data.stage !== 'string') {
    return null
  }
  return {
    run_id: data.run_id,
    stage: data.stage,
    created_at: asString(data.created_at),
  }
}

export function parseToolCallEvent(event: SseEvent): ToolCallEvent | null {
  const data = event.data
  if (typeof data.id !== 'string' || typeof data.name !== 'string') {
    return null
  }
  const status = asString(data.status)
  if (status !== 'running' && status !== 'completed' && status !== 'failed') {
    return null
  }
  return {
    id: data.id,
    session_id: asString(data.session_id),
    run_id: asString(data.run_id),
    name: data.name,
    status,
    input: asRecord(data.input),
    output: asRecord(data.output),
    error_message: asNullableString(data.error_message),
    duration_ms: typeof data.duration_ms === 'number' ? data.duration_ms : null,
    created_at: asString(data.created_at),
    updated_at: asString(data.updated_at),
  }
}

export function parseToolCallDelta(event: SseEvent): ToolCallDelta | null {
  const data = event.data
  if (typeof data.id !== 'string' || typeof data.name !== 'string') {
    return null
  }
  const delta = asRecord(data.delta)
  if (!delta) {
    return null
  }
  return {
    id: data.id,
    session_id: asString(data.session_id),
    run_id: asString(data.run_id),
    name: data.name,
    status: asString(data.status),
    delta,
    created_at: asString(data.created_at),
  }
}

export function parseValidationCompleted(event: SseEvent): ValidationCompletedPayload | null {
  const data = event.data
  const status = asString(data.validation_status)
  if (status !== 'accepted' && status !== 'rejected') {
    return null
  }
  const report = asValidationReport(data.validation_report)
  if (!report) {
    return null
  }
  return {
    project_id: asString(data.project_id),
    validation_status: status,
    accepted_version_id: asNullableString(data.accepted_version_id),
    rejected_version_id: asNullableString(data.rejected_version_id),
    repair_attempt_count: asNumber(data.repair_attempt_count),
    validation_report: report,
    context_report: (asRecord(data.context_report) as ContextPackingReport | null) ?? null,
  }
}

export function parseModelUsage(event: SseEvent): ModelUsagePayload | null {
  const data = event.data
  if (typeof data.project_id !== 'string' || typeof data.model !== 'string') {
    return null
  }
  return {
    id: asString(data.id) || undefined,
    tool_call_id: asString(data.tool_call_id) || undefined,
    project_id: data.project_id,
    task: asString(data.task),
    provider: asString(data.provider),
    model: data.model,
    estimated_input_tokens: asNumber(data.estimated_input_tokens),
    context_budget_tokens: asNumber(data.context_budget_tokens),
    included_block_ids: asStringArray(data.included_block_ids),
    omitted_block_ids: asStringArray(data.omitted_block_ids),
    created_at: asString(data.created_at) || undefined,
  }
}

export function parseAssetUpdated(event: SseEvent): AssetUpdatedPayload | null {
  const data = event.data
  if (typeof data.asset !== 'string') {
    return null
  }
  return data as unknown as AssetUpdatedPayload
}

export function parseConfirmation(event: SseEvent): ChatConfirmation | null {
  const data = event.data
  if (typeof data.id !== 'string' || typeof data.kind !== 'string') {
    return null
  }
  return data as unknown as ChatConfirmation
}

export function parseRunCompleted(event: SseEvent): RunCompletedPayload | null {
  const runId = event.data.run_id
  if (typeof runId !== 'string') {
    return null
  }
  return { run_id: runId }
}

export function parseRunCompletedWithErrors(event: SseEvent): RunCompletedWithErrorsPayload | null {
  const data = event.data
  if (typeof data.run_id !== 'string') {
    return null
  }
  return {
    run_id: data.run_id,
    message: asString(data.message),
    rejected_version_id: asNullableString(data.rejected_version_id),
    repair_attempt_count: asNumber(data.repair_attempt_count),
  }
}

export function parseErrorEvent(event: SseEvent): ErrorEventPayload {
  const data = event.data
  return {
    run_id: typeof data.run_id === 'string' ? data.run_id : undefined,
    message: typeof data.message === 'string' ? data.message : '执行失败',
    code: typeof data.code === 'string' ? data.code : undefined,
  }
}

export function deriveRunStatus(
  events: LiveEvent[],
  hasPendingConfirmation: boolean,
  isStreaming: boolean,
): RunStatus {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const name = events[i].event
    if (name === SSE_EVENT_NAMES.runCompleted) {
      return 'completed'
    }
    if (name === SSE_EVENT_NAMES.runCompletedWithErrors) {
      return 'completed_with_errors'
    }
    if (name === SSE_EVENT_NAMES.error) {
      return 'failed'
    }
    if (name === SSE_EVENT_NAMES.runWaitingConfirmation) {
      return 'waiting_confirmation'
    }
    if (name === SSE_EVENT_NAMES.runStarted) {
      break
    }
  }
  if (hasPendingConfirmation) {
    return 'waiting_confirmation'
  }
  return isStreaming ? 'running' : 'idle'
}

export function findLatestProjectId(events: LiveEvent[]): string | null {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const projectId = events[i].data.project_id
    if (typeof projectId === 'string' && projectId) {
      return projectId
    }
  }
  return null
}
