import type { LiveEvent } from '../../lib/events'
import { SSE_EVENT_NAMES } from '../../lib/events'
import type { ChatSessionDetail, ToolCallEvent } from '../../types'

let replayCounter = 0
const nextReplayId = () => {
  replayCounter += 1
  return `replay-${replayCounter.toString(36)}`
}

function eventNameForStatus(status: ToolCallEvent['status']): string {
  if (status === 'failed') return SSE_EVENT_NAMES.toolCallFailed
  if (status === 'completed') return SSE_EVENT_NAMES.toolCallCompleted
  return SSE_EVENT_NAMES.toolCallStarted
}

function toLiveEvent(name: string, data: Record<string, unknown>, ts: number): LiveEvent {
  return {
    event: name,
    data,
    id: nextReplayId(),
    receivedAt: ts,
  }
}

export function buildHistoryEvents(
  detail: ChatSessionDetail | undefined,
): LiveEvent[] {
  if (!detail) return []
  const calls = detail.tool_calls ?? []
  const events: LiveEvent[] = []

  for (const run of detail.runs ?? []) {
    const createdAt = run.created_at ? new Date(run.created_at).getTime() : Date.now()
    events.push(
      toLiveEvent(
        SSE_EVENT_NAMES.runStarted,
        {
          run_id: run.id,
          session_id: run.session_id,
          user_message_id: run.user_message_id,
          assistant_message_id: run.assistant_message_id,
          status: run.status,
        },
        createdAt,
      ),
    )
  }

  const knownRunIds = new Set((detail.runs ?? []).map((run) => run.id))
  for (const call of calls) {
    const createdAt = call.created_at ? new Date(call.created_at).getTime() : Date.now()
    if (call.run_id && !knownRunIds.has(call.run_id)) {
      knownRunIds.add(call.run_id)
      events.push(
        toLiveEvent(
          SSE_EVENT_NAMES.runStarted,
          { run_id: call.run_id, session_id: call.session_id },
          createdAt - 1,
        ),
      )
    }
    events.push(
      toLiveEvent(
        eventNameForStatus(call.status),
        {
          id: call.id,
          session_id: call.session_id,
          run_id: call.run_id,
          name: call.name,
          status: call.status,
          input: call.input,
          output: call.output,
          error_message: call.error_message,
          duration_ms: call.duration_ms,
          created_at: call.created_at,
          updated_at: call.updated_at,
        },
        createdAt,
      ),
    )
  }

  return events
}
