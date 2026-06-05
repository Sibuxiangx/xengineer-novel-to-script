import type { JsonRecord, SseEvent } from '../types'
import { ApiError, apiBaseUrl } from './api'

export function parseSseBlock(block: string): SseEvent | null {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith('event: ')) {
      event = line.slice('event: '.length)
    } else if (line.startsWith('data: ')) {
      dataLines.push(line.slice('data: '.length))
    }
  }
  if (dataLines.length === 0) {
    return null
  }
  try {
    return {
      event,
      data: JSON.parse(dataLines.join('\n')) as JsonRecord,
    }
  } catch {
    return null
  }
}

export type StreamPostOptions = {
  signal?: AbortSignal
  onEvent: (event: SseEvent) => void
}

export async function streamPost(
  path: string,
  payload: unknown,
  options: StreamPostOptions,
): Promise<void> {
  const { signal, onEvent } = options
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  })

  if (!response.ok) {
    let body: unknown
    try {
      body = await response.json()
    } catch {
      body = await response.text()
    }
    const message =
      typeof body === 'object' && body !== null && 'detail' in body
        ? String((body as { detail?: unknown }).detail ?? '')
        : `请求失败，HTTP ${response.status}`
    throw new ApiError(response.status, body, message || `请求失败，HTTP ${response.status}`, null)
  }

  if (!response.body) {
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
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
  } finally {
    reader.releaseLock?.()
  }

  const tail = parseSseBlock(buffer.trim())
  if (tail) {
    onEvent(tail)
  }
}
