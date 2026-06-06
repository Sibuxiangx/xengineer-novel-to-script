import type { ScriptVersion } from '../../types'

export type ScriptVersionLabel = {
  label: string
  shortLabel: string
  description: string
  kind: 'accepted' | 'draft'
  ordinal: number
}

function byCreatedAtAsc(left: ScriptVersion, right: ScriptVersion): number {
  const leftTime = Date.parse(left.created_at)
  const rightTime = Date.parse(right.created_at)
  if (Number.isFinite(leftTime) && Number.isFinite(rightTime) && leftTime !== rightTime) {
    return leftTime - rightTime
  }
  return left.id.localeCompare(right.id)
}

export function buildVersionLabelMap(versions: ScriptVersion[]): Map<string, ScriptVersionLabel> {
  const labels = new Map<string, ScriptVersionLabel>()
  const accepted = versions
    .filter((version) => version.validation_status === 'accepted')
    .sort(byCreatedAtAsc)
  const drafts = versions
    .filter((version) => version.validation_status !== 'accepted')
    .sort(byCreatedAtAsc)

  accepted.forEach((version, index) => {
    const ordinal = index + 1
    labels.set(version.id, {
      label: `v${ordinal}`,
      shortLabel: `v${ordinal}`,
      description: `正式剧本 v${ordinal}`,
      kind: 'accepted',
      ordinal,
    })
  })

  drafts.forEach((version, index) => {
    const ordinal = index + 1
    labels.set(version.id, {
      label: `草稿 ${ordinal}`,
      shortLabel: `D${ordinal}`,
      description: `未通过验证草稿 ${ordinal}`,
      kind: 'draft',
      ordinal,
    })
  })

  return labels
}

export function getLatestAcceptedVersion(versions: ScriptVersion[]): ScriptVersion | null {
  const accepted = versions
    .filter((version) => version.validation_status === 'accepted')
    .sort(byCreatedAtAsc)
  return accepted[accepted.length - 1] ?? null
}
