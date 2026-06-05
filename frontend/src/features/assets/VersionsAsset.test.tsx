import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { VersionsAsset } from './VersionsAsset'
import type { ScriptVersion } from '../../types'

const versions: ScriptVersion[] = [
  {
    id: 'v-acc',
    project_id: 'p',
    file_path: 'script.yaml',
    created_by: 'agent',
    reason: 'first accepted',
    operation_count: 12,
    validation_status: 'accepted',
    created_at: '2026-06-04T12:00:00Z',
  },
  {
    id: 'v-rej',
    project_id: 'p',
    file_path: 'script.yaml',
    created_by: 'agent',
    reason: 'rejected draft',
    operation_count: 5,
    validation_status: 'rejected',
    created_at: '2026-06-04T12:30:00Z',
  },
]

describe('VersionsAsset', () => {
  it('renders empty state with no versions', () => {
    render(
      <VersionsAsset
        versions={[]}
        selectedVersionId={null}
        loading={false}
        onSelectVersion={() => undefined}
      />,
    )
    expect(screen.getByText('暂无版本记录')).toBeInTheDocument()
  })

  it('renders both accepted and rejected sections', () => {
    render(
      <VersionsAsset
        versions={versions}
        selectedVersionId="v-acc"
        loading={false}
        onSelectVersion={() => undefined}
      />,
    )
    expect(screen.getByText('已接受版本')).toBeInTheDocument()
    expect(screen.getByText('Rejected drafts')).toBeInTheDocument()
    expect(screen.getByText('first accepted')).toBeInTheDocument()
    expect(screen.getByText('rejected draft')).toBeInTheDocument()
  })

  it('calls onSelectVersion when a card is activated', () => {
    const onSelect = vi.fn()
    render(
      <VersionsAsset
        versions={versions}
        selectedVersionId={null}
        loading={false}
        onSelectVersion={onSelect}
      />,
    )
    const buttons = screen.getAllByRole('button', { name: /版本 v-/ })
    expect(buttons.length).toBeGreaterThan(0)
    buttons[0].click()
    expect(onSelect).toHaveBeenCalled()
  })
})
