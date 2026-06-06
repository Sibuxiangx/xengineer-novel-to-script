import { Button } from 'antd'
import { CheckCircleOutlined, ExclamationCircleOutlined } from '@ant-design/icons'

type RunSummaryProps = {
  variant: 'completed' | 'completed_with_errors'
  message?: string
  rejectedVersionId?: string | null
  repairAttemptCount?: number
  onOpenRejected?: () => void
}

export function RunSummaryBubble({
  variant,
  message,
  repairAttemptCount,
  onOpenRejected,
}: RunSummaryProps) {
  if (variant === 'completed') {
    return (
      <div className="sw-run-summary is-completed">
        <CheckCircleOutlined aria-hidden className="sw-run-summary-icon" />
        <span className="sw-run-summary-text">
          {message ?? '剧本已生成并通过校验。'}
        </span>
      </div>
    )
  }
  return (
    <div className="sw-run-summary is-errors">
      <ExclamationCircleOutlined aria-hidden className="sw-run-summary-icon" />
      <span className="sw-run-summary-text">
        {message ?? '已保留 rejected 草稿，可在资产栏接管修复。'}
        {repairAttemptCount != null && repairAttemptCount > 0
          ? `（已自动修复 ${repairAttemptCount} 次）`
          : null}
      </span>
      {onOpenRejected && (
        <Button type="link" size="small" onClick={onOpenRejected} style={{ padding: 0 }}>
          查看草稿
        </Button>
      )}
    </div>
  )
}
