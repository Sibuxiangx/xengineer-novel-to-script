export type JsonRecord = Record<string, unknown>

export type ChatSession = {
  id: string
  project_id: string | null
  title: string
  status: 'active' | 'archived'
  pending_confirmation_count: number
  created_at: string
  updated_at: string
}

export type ChatMessage = {
  id: string
  session_id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  metadata: JsonRecord | null
  created_at: string
}

export type HeadingCandidate = {
  line_number: number
  start_char: number
  text: string
}

export type ChapterSplitRule = {
  strategy: 'line_regex' | 'no_chapters'
  heading_regex: string | null
  title_source: 'full_line'
  confidence: number
  reason: string
  examples: string[]
}

export type ChapterSplitPreview = {
  chapter_count: number
  titles: string[]
  last_titles: string[]
  candidate_heading_count: number
  unmatched_candidate_count: number
  unmatched_candidates: HeadingCandidate[]
}

export type ChapterSplitConfirmationPayload = {
  file_name: string
  source_text_path: string
  text_length: number
  rule: ChapterSplitRule
  preview: ChapterSplitPreview
}

export type ChatConfirmation = {
  id: string
  session_id: string
  project_id: string | null
  kind: 'chapter_split'
  status: 'pending' | 'confirmed' | 'cancelled'
  prompt: string
  payload: ChapterSplitConfirmationPayload
  created_at: string
  resolved_at: string | null
}

export type ScriptVersion = {
  id: string
  project_id: string
  file_path: string
  created_by: string
  reason: string
  operation_count: number
  validation_status: 'accepted' | 'rejected' | string
  created_at: string
}

export type ValidationIssueSeverity = 'info' | 'warning' | 'error' | 'blocking'

export type ValidationIssue = {
  code: string
  severity: ValidationIssueSeverity
  path: string
  message: string
  repair_hint: string | null
  source: string
}

export type ValidationReport = {
  accepted: boolean
  severity: ValidationIssueSeverity
  errors: ValidationIssue[]
  warnings: ValidationIssue[]
  metrics: Record<string, number | string>
}

export type ChatSessionDetail = {
  session: ChatSession
  messages: ChatMessage[]
  pending_confirmations: ChatConfirmation[]
  runs: ChatRun[]
  tool_calls: ToolCallEvent[]
  timeline: ChatTimelineItem[]
  latest_versions: ScriptVersion[]
  model_usage: ModelUsage[]
}

export type ChatTimelineItem = {
  id: string
  kind: 'message' | 'tool_call' | 'confirmation'
  session_id: string
  run_id: string | null
  message: ChatMessage | null
  tool_call: ToolCallEvent | null
  confirmation: ChatConfirmation | null
  created_at: string
}

export type ChatRun = {
  id: string
  session_id: string
  status:
    | 'running'
    | 'waiting_confirmation'
    | 'completed'
    | 'completed_with_errors'
    | 'failed'
  user_message_id: string | null
  assistant_message_id: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export type ToolCallDelta = {
  id: string
  session_id: string
  run_id: string
  name: string
  status: 'running' | 'completed' | 'failed' | string
  delta: JsonRecord
  created_at: string
}

export type ToolCallEvent = {
  id: string
  session_id: string
  run_id: string
  name: string
  status: 'running' | 'completed' | 'failed'
  input: JsonRecord | null
  output: JsonRecord | null
  error_message: string | null
  duration_ms?: number | null
  created_at: string
  updated_at: string
  deltas?: ToolCallDelta[]
}

export type Chapter = {
  id: string
  project_id: string
  title: string
  order_index: number
  content: string
  file_path: string
  token_estimate: number | null
  created_at: string
}

export type BookIndexResponse = {
  project_id: string
  book_index: JsonRecord
  file_path: string
  context_report?: ContextPackingReport | null
}

export type ScriptVersionDetail = {
  version: ScriptVersion
  script_yaml: string
}

export type ScriptUserEditRequest = {
  script_yaml: string
  reason?: string | null
}

export type ScriptUserEditResponse = {
  project_id: string
  script_yaml: string
  validation_report: ValidationReport
  accepted_version_id: string | null
  rejected_version_id: string | null
  validation_status: 'accepted' | 'rejected'
}

export type ChatRunRequest = {
  message: string
  source_file_name?: string | null
  source_text?: string | null
  screenplay_format?: string
}

export type ConfirmationActionRequest = {
  action: 'confirm' | 'cancel'
  message?: string | null
  chapter_split_rule?: ChapterSplitRule | null
}

export type ContextPackingReport = {
  included_block_ids: string[]
  omitted_block_ids: string[]
  estimated_tokens: number
  budget_tokens: number
}

export type ModelUsage = {
  id?: string
  tool_call_id?: string
  project_id: string
  task: string
  provider: string
  model: string
  estimated_input_tokens: number
  context_budget_tokens: number
  included_block_ids: string[]
  omitted_block_ids: string[]
  created_at?: string
}

export type RunStatus =
  | 'idle'
  | 'running'
  | 'waiting_confirmation'
  | 'completed'
  | 'completed_with_errors'
  | 'failed'

export type ProjectStatus =
  | 'idle'
  | 'uploading'
  | 'awaiting'
  | 'generating'
  | 'repairing'
  | 'ready'
  | 'failed'

export type SseEvent = {
  event: string
  data: JsonRecord
}
