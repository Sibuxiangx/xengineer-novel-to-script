import type {
  BookIndexResponse,
  Chapter,
  ChatSession,
  ChatSessionDetail,
  ScriptVersion,
  ScriptVersionDetail,
} from '../types'

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000'

export const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? DEFAULT_API_BASE_URL

export class ApiError extends Error {
  status: number
  body: unknown
  code: string | null

  constructor(status: number, body: unknown, message: string, code: string | null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
    this.code = code
  }
}

function deriveError(status: number, body: unknown): { message: string; code: string | null } {
  if (typeof body === 'string') {
    return { message: body, code: null }
  }
  if (body && typeof body === 'object') {
    const detail = (body as { detail?: unknown }).detail
    if (typeof detail === 'string') {
      return { message: detail, code: null }
    }
    if (detail && typeof detail === 'object') {
      const innerDetail = (detail as { detail?: unknown }).detail
      const innerCode = (detail as { code?: unknown }).code
      const message = typeof innerDetail === 'string' ? innerDetail : `请求失败，HTTP ${status}`
      const code = typeof innerCode === 'string' ? innerCode : null
      return { message, code }
    }
  }
  return { message: `请求失败，HTTP ${status}`, code: null }
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
  })

  if (!response.ok) {
    let body: unknown
    try {
      body = await response.json()
    } catch {
      body = await response.text()
    }
    const { message, code } = deriveError(response.status, body)
    throw new ApiError(response.status, body, message, code)
  }

  return (await response.json()) as T
}

export const api = {
  health() {
    return request<{ status: string; service: string }>('/health')
  },
  listSessions(options?: { includeArchived?: boolean }) {
    const query = options?.includeArchived ? '?include_archived=true' : ''
    return request<ChatSession[]>(`/chat/sessions${query}`)
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
  archiveSession(sessionId: string) {
    return request<ChatSession>(`/chat/sessions/${sessionId}/archive`, {
      method: 'POST',
    })
  },
  restoreSession(sessionId: string) {
    return request<ChatSession>(`/chat/sessions/${sessionId}/restore`, {
      method: 'POST',
    })
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

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message
  }
  if (error instanceof Error) {
    return error.message
  }
  return '请求失败，请检查后端服务。'
}

export function getErrorCode(error: unknown): string | null {
  if (error instanceof ApiError) {
    return error.code
  }
  return null
}
