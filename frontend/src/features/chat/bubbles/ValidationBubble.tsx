import { Button, Space, Tag } from 'antd'
import {
  CheckCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons'
import type { ValidationCompletedPayload } from '../../../lib/events'

type ValidationBubbleProps = {
  payload: ValidationCompletedPayload
  onOpenHarness?: () => void
  onOpenYaml?: () => void
}

export function ValidationBubble({
  payload,
  onOpenHarness,
  onOpenYaml,
}: ValidationBubbleProps) {
  const accepted = payload.validation_status === 'accepted'
  const report = payload.validation_report
  const errorCount = report.errors.length
  const warningCount = report.warnings.length
  const sceneCount = report.metrics.scene_count

  return (
    <div className={`sw-validation-line ${accepted ? 'is-accepted' : 'is-rejected'}`}>
      <span
        className={`sw-validation-line-icon ${accepted ? 'is-accepted' : 'is-rejected'}`}
        aria-hidden
      >
        {accepted ? <CheckCircleOutlined /> : <ExclamationCircleOutlined />}
      </span>
      <span className="sw-validation-line-status">
        {accepted ? 'YAML 校验通过' : 'YAML 校验未通过'}
      </span>
      {sceneCount != null && (
        <span className="sw-validation-line-meta">{String(sceneCount)} 场景</span>
      )}
      {errorCount > 0 && (
        <span className="sw-validation-line-errors">{errorCount} 错误</span>
      )}
      {warningCount > 0 && (
        <span className="sw-validation-line-warnings">{warningCount} 警告</span>
      )}
      {payload.repair_attempt_count > 0 && (
        <Tag color="warning" style={{ margin: 0 }}>
          修复 {payload.repair_attempt_count} 次
        </Tag>
      )}
      <Space size={4} style={{ marginLeft: 'auto' }}>
        {onOpenHarness && (
          <Button type="link" size="small" onClick={onOpenHarness} style={{ padding: 0 }}>
            校验报告
          </Button>
        )}
        {onOpenYaml && (
          <Button type="link" size="small" onClick={onOpenYaml} style={{ padding: 0 }}>
            打开 YAML
          </Button>
        )}
      </Space>
    </div>
  )
}
