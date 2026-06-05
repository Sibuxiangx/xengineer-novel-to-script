import { describe, expect, it, vi } from 'vitest'
import { parseSseBlock, streamPost } from './sse'

describe('parseSseBlock', () => {
  it('parses a single event with JSON data', () => {
    const block = 'event: run.started\ndata: {"run_id":"abc","session_id":"s1"}'
    const parsed = parseSseBlock(block)
    expect(parsed).toEqual({
      event: 'run.started',
      data: { run_id: 'abc', session_id: 's1' },
    })
  })

  it('returns null when no data line is present', () => {
    expect(parseSseBlock('event: heartbeat')).toBeNull()
  })

  it('returns null on invalid JSON', () => {
    expect(parseSseBlock('event: x\ndata: {not json')).toBeNull()
  })

  it('defaults event to "message" when not specified', () => {
    const parsed = parseSseBlock('data: {"ok":true}')
    expect(parsed?.event).toBe('message')
    expect(parsed?.data).toEqual({ ok: true })
  })

  it('joins multi-line data', () => {
    const block = 'event: chunk\ndata: {"a":\ndata: 1}'
    const parsed = parseSseBlock(block)
    expect(parsed?.data).toEqual({ a: 1 })
  })
})

describe('streamPost', () => {
  it('parses SSE chunks and invokes onEvent for each block', async () => {
    const chunks = [
      'event: run.started\ndata: {"run_id":"r1"}\n\n',
      'event: tool.call.completed\ndata: {"id":"t1","name":"foo","status":"completed"}\n\n',
    ]
    const encoder = new TextEncoder()
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) {
          controller.enqueue(encoder.encode(chunk))
        }
        controller.close()
      },
    })
    const response = new Response(stream, { status: 200 })
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(response)

    const events: unknown[] = []
    await streamPost('/test', { hello: 1 }, { onEvent: (event) => events.push(event) })

    expect(events).toHaveLength(2)
    expect((events[0] as { event: string }).event).toBe('run.started')
    expect((events[1] as { event: string }).event).toBe('tool.call.completed')
    fetchSpy.mockRestore()
  })

  it('throws ApiError on non-2xx', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(
        new Response(JSON.stringify({ detail: 'nope' }), {
          status: 500,
          headers: { 'content-type': 'application/json' },
        }),
      )
    await expect(
      streamPost('/test', {}, { onEvent: () => undefined }),
    ).rejects.toThrow(/nope|HTTP 500/)
    fetchSpy.mockRestore()
  })
})
