import { describe, expect, it } from 'vitest'
import {
  deriveRunStatus,
  findLatestProjectId,
  parseAssetUpdated,
  parseConfirmation,
  parseErrorEvent,
  parseModelUsage,
  parseRunCompletedWithErrors,
  parseRunProgress,
  parseToolCallEvent,
  parseValidationCompleted,
  SSE_EVENT_NAMES,
  type LiveEvent,
} from './events'

const makeEvent = (event: string, data: Record<string, unknown>) => ({ event, data })

const makeLiveEvent = (event: string, data: Record<string, unknown>, id = 'x'): LiveEvent => ({
  event,
  data,
  id,
  receivedAt: Date.now(),
})

describe('parseRunProgress', () => {
  it('returns payload for a valid completed stage', () => {
    const payload = parseRunProgress(
      makeEvent('run.progress', {
        run_id: 'r1',
        stage: 'generate_script_yaml',
        status: 'completed',
        duration_ms: 1200,
      }),
    )
    expect(payload).not.toBeNull()
    expect(payload?.status).toBe('completed')
    expect(payload?.duration_ms).toBe(1200)
  })

  it('returns null for unknown status', () => {
    expect(
      parseRunProgress(makeEvent('run.progress', { status: 'weird' })),
    ).toBeNull()
  })
})

describe('parseToolCallEvent', () => {
  it('parses a completed tool call', () => {
    const event = parseToolCallEvent(
      makeEvent('tool.call.completed', {
        id: 't1',
        session_id: 's1',
        run_id: 'r1',
        name: 'split_chapters',
        status: 'completed',
        output: { chapter_count: 3 },
        created_at: '2026-01-01',
        updated_at: '2026-01-01',
      }),
    )
    expect(event?.name).toBe('split_chapters')
    expect(event?.output).toEqual({ chapter_count: 3 })
  })

  it('returns null for invalid status', () => {
    expect(
      parseToolCallEvent(
        makeEvent('tool.call.x', { id: 't1', name: 'foo', status: 'bogus' }),
      ),
    ).toBeNull()
  })
})

describe('parseValidationCompleted', () => {
  it('returns payload when validation_report has accepted bool', () => {
    const payload = parseValidationCompleted(
      makeEvent('validation.completed', {
        project_id: 'p1',
        validation_status: 'rejected',
        repair_attempt_count: 2,
        rejected_version_id: 'v2',
        validation_report: {
          accepted: false,
          severity: 'error',
          errors: [],
          warnings: [],
          metrics: {},
        },
      }),
    )
    expect(payload?.validation_status).toBe('rejected')
    expect(payload?.rejected_version_id).toBe('v2')
  })

  it('returns null when validation_report missing', () => {
    expect(
      parseValidationCompleted(
        makeEvent('validation.completed', { validation_status: 'accepted' }),
      ),
    ).toBeNull()
  })
})

describe('parseModelUsage / parseAssetUpdated / parseConfirmation', () => {
  it('parses model usage and includes string array fields', () => {
    const usage = parseModelUsage(
      makeEvent('model.usage.estimated', {
        id: 'usage:t1',
        tool_call_id: 't1',
        project_id: 'p',
        task: 'generate_yaml',
        provider: 'openai',
        model: 'gpt-4o-mini',
        estimated_input_tokens: 1024,
        context_budget_tokens: 8000,
        included_block_ids: ['a', 'b'],
        omitted_block_ids: ['c'],
      }),
    )
    expect(usage?.id).toBe('usage:t1')
    expect(usage?.tool_call_id).toBe('t1')
    expect(usage?.included_block_ids).toEqual(['a', 'b'])
    expect(usage?.omitted_block_ids).toEqual(['c'])
  })

  it('parses asset.updated as a typed payload', () => {
    const payload = parseAssetUpdated(
      makeEvent('asset.updated', { asset: 'script_yaml', project_id: 'p' }),
    )
    expect(payload?.asset).toBe('script_yaml')
  })

  it('parses confirmation events when id and kind exist', () => {
    const payload = parseConfirmation(
      makeEvent('tool.confirm.required', {
        id: 'c1',
        kind: 'chapter_split',
        session_id: 's1',
        prompt: 'confirm?',
        status: 'pending',
        payload: { rule: {}, preview: {} },
      }),
    )
    expect(payload?.id).toBe('c1')
  })
})

describe('parseRunCompletedWithErrors & error helpers', () => {
  it('extracts rejected_version_id and repair count', () => {
    const payload = parseRunCompletedWithErrors(
      makeEvent('run.completed_with_errors', {
        run_id: 'r1',
        message: 'validation failed',
        rejected_version_id: 'rv-1',
        repair_attempt_count: 3,
      }),
    )
    expect(payload?.rejected_version_id).toBe('rv-1')
    expect(payload?.repair_attempt_count).toBe(3)
  })

  it('falls back to default message in parseErrorEvent', () => {
    const payload = parseErrorEvent(makeEvent('error', {}))
    expect(payload.message).toBe('执行失败')
  })
})

describe('deriveRunStatus', () => {
  it('returns idle when there are no events and not streaming', () => {
    expect(deriveRunStatus([], false, false)).toBe('idle')
  })

  it('returns running when streaming with no terminal event', () => {
    const events: LiveEvent[] = [
      makeLiveEvent(SSE_EVENT_NAMES.runStarted, { run_id: 'r' }),
    ]
    expect(deriveRunStatus(events, false, true)).toBe('running')
  })

  it('returns waiting_confirmation when last lifecycle event is waiting', () => {
    const events: LiveEvent[] = [
      makeLiveEvent(SSE_EVENT_NAMES.runStarted, { run_id: 'r' }),
      makeLiveEvent(SSE_EVENT_NAMES.runWaitingConfirmation, { run_id: 'r' }),
    ]
    expect(deriveRunStatus(events, true, false)).toBe('waiting_confirmation')
  })

  it('returns completed_with_errors when last lifecycle event is error variant', () => {
    const events: LiveEvent[] = [
      makeLiveEvent(SSE_EVENT_NAMES.runStarted, { run_id: 'r' }),
      makeLiveEvent(SSE_EVENT_NAMES.runCompletedWithErrors, { run_id: 'r' }),
    ]
    expect(deriveRunStatus(events, false, false)).toBe('completed_with_errors')
  })
})

describe('findLatestProjectId', () => {
  it('picks the most recent string project_id', () => {
    const events: LiveEvent[] = [
      makeLiveEvent('a', { project_id: 'p1' }),
      makeLiveEvent('b', { project_id: 'p2' }),
      makeLiveEvent('c', { other: 'x' }),
    ]
    expect(findLatestProjectId(events)).toBe('p2')
  })

  it('returns null when no project_id seen', () => {
    expect(findLatestProjectId([])).toBeNull()
  })
})
