import { create } from 'zustand'
import {
  parseAssetUpdated,
  parseConfirmation,
  parseModelUsage,
  parseToolCallDelta,
  parseToolCallEvent,
  parseValidationCompleted,
  SSE_EVENT_NAMES,
  type AssetUpdatedPayload,
  type LiveEvent,
  type ModelUsagePayload,
  type ValidationCompletedPayload,
} from '../lib/events'
import type { ChatConfirmation, SseEvent, ToolCallEvent } from '../types'

type SessionEventState = {
  events: LiveEvent[]
  toolCalls: Record<string, ToolCallEvent>
  pendingConfirmation: ChatConfirmation | null
  latestValidation: ValidationCompletedPayload | null
  latestAssets: Record<string, AssetUpdatedPayload>
  modelUsage: ModelUsagePayload[]
  currentRunId: string | null
  lastErrorMessage: string | null
}

type AssetUpdatedListener = (
  sessionId: string,
  payload: AssetUpdatedPayload,
) => void

type EventLogState = {
  bySession: Record<string, SessionEventState>
  assetUpdatedListeners: Set<AssetUpdatedListener>
  pushEvent: (sessionId: string, sse: SseEvent) => void
  clearSession: (sessionId: string) => void
  clearError: (sessionId: string) => void
  onAssetUpdated: (listener: AssetUpdatedListener) => () => void
}

const EMPTY_SESSION_STATE: SessionEventState = Object.freeze({
  events: [] as never[],
  toolCalls: {} as Record<string, never>,
  pendingConfirmation: null,
  latestValidation: null,
  latestAssets: {} as Record<string, never>,
  modelUsage: [] as never[],
  currentRunId: null,
  lastErrorMessage: null,
}) as unknown as SessionEventState

const emptySessionState = (): SessionEventState => ({
  events: [],
  toolCalls: {},
  pendingConfirmation: null,
  latestValidation: null,
  latestAssets: {},
  modelUsage: [],
  currentRunId: null,
  lastErrorMessage: null,
})

let counter = 0
const nextId = () => {
  counter += 1
  return `${Date.now().toString(36)}-${counter.toString(36)}`
}

function applyEvent(state: SessionEventState, sse: SseEvent): SessionEventState {
  const liveEvent: LiveEvent = {
    ...sse,
    id: nextId(),
    receivedAt: Date.now(),
  }
  const next: SessionEventState = {
    ...state,
    events: [...state.events, liveEvent],
  }

  switch (sse.event) {
    case SSE_EVENT_NAMES.runStarted: {
      const runId = typeof sse.data.run_id === 'string' ? sse.data.run_id : null
      next.currentRunId = runId
      next.lastErrorMessage = null
      if (
        typeof sse.data.confirmation_id === 'string' &&
        typeof sse.data.confirmation_action === 'string'
      ) {
        next.pendingConfirmation = null
      }
      break
    }
    case SSE_EVENT_NAMES.toolCallStarted:
    case SSE_EVENT_NAMES.toolCallCompleted:
    case SSE_EVENT_NAMES.toolCallFailed: {
      const tool = parseToolCallEvent(sse)
      if (tool) {
        next.toolCalls = { ...state.toolCalls, [tool.id]: tool }
      }
      break
    }
    case SSE_EVENT_NAMES.toolCallDelta: {
      const delta = parseToolCallDelta(sse)
      if (delta) {
        const existing = state.toolCalls[delta.id]
        if (existing) {
          next.toolCalls = {
            ...state.toolCalls,
            [delta.id]: {
              ...existing,
              deltas: [...(existing.deltas ?? []), delta],
            },
          }
        }
      }
      break
    }
    case SSE_EVENT_NAMES.toolConfirmRequired: {
      const confirmation = parseConfirmation(sse)
      if (confirmation) {
        next.pendingConfirmation = confirmation
      }
      break
    }
    case SSE_EVENT_NAMES.toolConfirmCancelled: {
      next.pendingConfirmation = null
      break
    }
    case SSE_EVENT_NAMES.runWaitingConfirmation:
      break
    case SSE_EVENT_NAMES.assetUpdated: {
      const asset = parseAssetUpdated(sse)
      if (asset) {
        next.latestAssets = { ...state.latestAssets, [asset.asset]: asset }
      }
      break
    }
    case SSE_EVENT_NAMES.validationCompleted: {
      const validation = parseValidationCompleted(sse)
      if (validation) {
        next.latestValidation = validation
      }
      break
    }
    case SSE_EVENT_NAMES.modelUsage: {
      const usage = parseModelUsage(sse)
      if (usage) {
        next.modelUsage = [...state.modelUsage, usage]
      }
      break
    }
    case SSE_EVENT_NAMES.runCompleted: {
      next.pendingConfirmation = null
      next.currentRunId = null
      break
    }
    case SSE_EVENT_NAMES.runCompletedWithErrors: {
      next.currentRunId = null
      const message = typeof sse.data.message === 'string' ? sse.data.message : null
      next.lastErrorMessage = message
      break
    }
    case SSE_EVENT_NAMES.error: {
      const message = typeof sse.data.message === 'string' ? sse.data.message : '执行失败'
      next.lastErrorMessage = message
      next.currentRunId = null
      break
    }
    default:
      break
  }
  return next
}

export const useEventLog = create<EventLogState>((set, get) => ({
  bySession: {},
  assetUpdatedListeners: new Set(),
  pushEvent: (sessionId, sse) => {
    set((state) => {
      const previous = state.bySession[sessionId] ?? emptySessionState()
      const updated = applyEvent(previous, sse)
      return {
        bySession: {
          ...state.bySession,
          [sessionId]: updated,
        },
      }
    })
    if (sse.event === SSE_EVENT_NAMES.assetUpdated) {
      const payload = parseAssetUpdated(sse)
      if (payload) {
        for (const listener of get().assetUpdatedListeners) {
          listener(sessionId, payload)
        }
      }
    }
  },
  clearSession: (sessionId) =>
    set((state) => {
      if (!(sessionId in state.bySession)) {
        return state
      }
      const next = { ...state.bySession }
      delete next[sessionId]
      return { bySession: next }
    }),
  clearError: (sessionId) =>
    set((state) => {
      const previous = state.bySession[sessionId]
      if (!previous || !previous.lastErrorMessage) {
        return state
      }
      return {
        bySession: {
          ...state.bySession,
          [sessionId]: { ...previous, lastErrorMessage: null },
        },
      }
    }),
  onAssetUpdated: (listener) => {
    const set_ = get().assetUpdatedListeners
    set_.add(listener)
    return () => {
      set_.delete(listener)
    }
  },
}))

export const selectSession =
  (sessionId: string | null) =>
  (state: EventLogState): SessionEventState =>
    sessionId
      ? (state.bySession[sessionId] ?? EMPTY_SESSION_STATE)
      : EMPTY_SESSION_STATE

export const emptySession = emptySessionState
