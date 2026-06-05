import { describe, expect, it } from 'vitest'
import { buildBubbleItems } from './buildBubbleItems'
import type { LiveEvent } from '../../lib/events'
import { SSE_EVENT_NAMES } from '../../lib/events'

let counter = 0
const makeLive = (event: string, data: Record<string, unknown>): LiveEvent => ({
  event,
  data,
  id: `id-${counter++}`,
  receivedAt: Date.now(),
})

const baseArgs = {
  messages: [],
  timeline: [],
  pendingConfirmation: null,
  ruleDraft: undefined,
  isStreaming: false,
  onRuleDraftChange: () => undefined,
  onConfirm: () => undefined,
  onCancel: () => undefined,
  onJumpAssetTab: () => undefined,
  onOpenRejectedVersion: () => undefined,
  onRetryLast: undefined,
}

describe('buildBubbleItems', () => {
  it('returns an empty array when there is no content', () => {
    expect(buildBubbleItems({ ...baseArgs, liveEvents: [] })).toEqual([])
  })

  it('groups validation events into a validation bubble', () => {
    const liveEvents: LiveEvent[] = [
      makeLive(SSE_EVENT_NAMES.runStarted, { run_id: 'r1' }),
      makeLive(SSE_EVENT_NAMES.validationCompleted, {
        project_id: 'p1',
        validation_status: 'rejected',
        rejected_version_id: 'rv1',
        repair_attempt_count: 1,
        validation_report: {
          accepted: false,
          severity: 'error',
          errors: [
            {
              code: 'E001',
              severity: 'error',
              path: 'scenes[0]',
              message: 'missing field',
              repair_hint: null,
              source: 'harness',
            },
          ],
          warnings: [],
          metrics: {},
        },
      }),
      makeLive(SSE_EVENT_NAMES.runCompletedWithErrors, {
        run_id: 'r1',
        message: 'failed harness',
        rejected_version_id: 'rv1',
        repair_attempt_count: 1,
      }),
    ]
    const items = buildBubbleItems({ ...baseArgs, liveEvents })
    const keys = items.map((item) => String(item.key ?? ''))
    expect(keys.some((key) => key.startsWith('validation-'))).toBe(true)
    expect(keys.some((key) => key.startsWith('done-errors-'))).toBe(true)
  })

  it('includes a tool trace bubble when tool events exist', () => {
    const liveEvents: LiveEvent[] = [
      makeLive(SSE_EVENT_NAMES.runStarted, { run_id: 'r2' }),
      makeLive(SSE_EVENT_NAMES.toolCallStarted, {
        id: 't1',
        name: 'identify_project',
        status: 'running',
        run_id: 'r2',
        session_id: 's1',
      }),
      makeLive(SSE_EVENT_NAMES.toolCallCompleted, {
        id: 't1',
        name: 'identify_project',
        status: 'completed',
        output: { title: 'Demo' },
        run_id: 'r2',
        session_id: 's1',
      }),
    ]
    const items = buildBubbleItems({ ...baseArgs, liveEvents })
    expect(
      items.some((item) => String(item.key ?? '').startsWith('tool-')),
    ).toBe(true)
  })

  it('dedupes by tool id keeping the latest status', () => {
    const liveEvents: LiveEvent[] = [
      makeLive(SSE_EVENT_NAMES.runStarted, { run_id: 'r3' }),
      makeLive(SSE_EVENT_NAMES.toolCallStarted, {
        id: 'tx',
        name: 'split_chapters',
        status: 'running',
        run_id: 'r3',
        session_id: 's1',
      }),
      makeLive(SSE_EVENT_NAMES.toolCallFailed, {
        id: 'tx',
        name: 'split_chapters',
        status: 'failed',
        error_message: 'bad regex',
        run_id: 'r3',
        session_id: 's1',
      }),
    ]
    const items = buildBubbleItems({ ...baseArgs, liveEvents })
    expect(
      items.filter((item) => String(item.key ?? '').startsWith('tool-')),
    ).toHaveLength(1)
  })
})
