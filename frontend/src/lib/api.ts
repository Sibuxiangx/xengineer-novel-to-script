const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000'

export const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? DEFAULT_API_BASE_URL

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

export type ChatConfirmation = {
  id: string
  session_id: string
  project_id: string | null
  kind: 'chapter_split'
  status: 'pending' | 'confirmed' | 'cancelled'
  prompt: string
  payload: {
    file_name: string
    source_text_path: string
    text_length: number
    rule: ChapterSplitRule
    preview: ChapterSplitPreview
  }
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
  validation_status: string
  created_at: string
}

export type ValidationIssue = {
  code: string
  severity: 'info' | 'warning' | 'error' | 'blocking'
  path: string
  message: string
  repair_hint: string | null
  source: string
}

export type ValidationReport = {
  accepted: boolean
  severity: 'info' | 'warning' | 'error' | 'blocking'
  errors: ValidationIssue[]
  warnings: ValidationIssue[]
  metrics: Record<string, number | string>
}

export type ChatSessionDetail = {
  session: ChatSession
  messages: ChatMessage[]
  pending_confirmations: ChatConfirmation[]
  latest_versions: ScriptVersion[]
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
  created_at: string
  updated_at: string
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
}

export type ScriptVersionDetail = {
  version: ScriptVersion
  script_yaml: string
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

export type SseEvent = {
  event: string
  data: JsonRecord
}

export class ApiError extends Error {
  status: number
  body: unknown

  constructor(status: number, body: unknown, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

function errorMessage(status: number, body: unknown): string {
  if (typeof body === 'string') {
    return body
  }
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail?: unknown }).detail
    if (typeof detail === 'string') {
      return detail
    }
    if (detail && typeof detail === 'object' && 'detail' in detail) {
      const nested = (detail as { detail?: unknown }).detail
      if (typeof nested === 'string') {
        return nested
      }
    }
  }
  return `请求失败，HTTP ${status}`
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  if (!response.ok) {
    let body: unknown
    try {
      body = await response.json()
    } catch {
      body = await response.text()
    }
    throw new ApiError(response.status, body, errorMessage(response.status, body))
  }

  return (await response.json()) as T
}

function parseSseBlock(block: string): SseEvent | null {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith('event: ')) {
      event = line.slice('event: '.length)
    }
    if (line.startsWith('data: ')) {
      dataLines.push(line.slice('data: '.length))
    }
  }
  if (dataLines.length === 0) {
    return null
  }
  return {
    event,
    data: JSON.parse(dataLines.join('\n')) as JsonRecord,
  }
}

export async function streamPost(
  path: string,
  payload: unknown,
  onEvent: (event: SseEvent) => void,
): Promise<void> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    let body: unknown
    try {
      body = await response.json()
    } catch {
      body = await response.text()
    }
    throw new ApiError(response.status, body, errorMessage(response.status, body))
  }

  if (!response.body) {
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) {
      break
    }
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''
    for (const part of parts) {
      const parsed = parseSseBlock(part.trim())
      if (parsed) {
        onEvent(parsed)
      }
    }
  }

  const tail = parseSseBlock(buffer.trim())
  if (tail) {
    onEvent(tail)
  }
}

export const api = {
  listSessions() {
    return request<ChatSession[]>('/chat/sessions')
  },
  createSession(title?: string) {
    return request<ChatSession>('/chat/sessions', {
      method: 'POST',
      body: JSON.stringify({ title: title ?? null }),
    })
  },
  getSession(sessionId: string) {
    return request<ChatSessionDetail>(`/chat/sessions/${sessionId}`)
  },
  listChapters(sessionId: string) {
    return request<{ chapters: Chapter[] }>(`/chat/sessions/${sessionId}/assets/chapters`)
  },
  getBookIndex(sessionId: string) {
    return request<BookIndexResponse>(`/chat/sessions/${sessionId}/assets/book-index`)
  },
  listVersions(sessionId: string) {
    return request<{ versions: ScriptVersion[] }>(
      `/chat/sessions/${sessionId}/assets/scripts/versions`,
    )
  },
  getVersion(sessionId: string, versionId: string) {
    return request<ScriptVersionDetail>(
      `/chat/sessions/${sessionId}/assets/scripts/versions/${versionId}`,
    )
  },
}
