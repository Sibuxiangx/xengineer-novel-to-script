import type { LiveEvent } from '../../lib/events'
import { findLatestProjectId } from '../../lib/events'
import type { ChatConfirmation, ChatSession, ProjectStatus } from '../../types'

export function inferProjectStatus(
  session: ChatSession | undefined,
  liveEvents: LiveEvent[],
  isStreaming: boolean,
  pendingConfirmation: ChatConfirmation | null,
  hasRejectedDraft: boolean,
): ProjectStatus {
  if (isStreaming) {
    return session?.project_id || findLatestProjectId(liveEvents) ? 'generating' : 'uploading'
  }
  if (pendingConfirmation || (session?.pending_confirmation_count ?? 0) > 0) {
    return 'awaiting'
  }
  if (hasRejectedDraft) {
    return 'failed'
  }
  if (session?.project_id || findLatestProjectId(liveEvents)) {
    return 'ready'
  }
  return 'idle'
}

export function buildRulePayload(
  confirmation: ChatConfirmation,
  editedRegex: string,
) {
  return {
    ...confirmation.payload.rule,
    heading_regex:
      confirmation.payload.rule.strategy === 'line_regex'
        ? editedRegex.trim() || confirmation.payload.rule.heading_regex
        : null,
  }
}
