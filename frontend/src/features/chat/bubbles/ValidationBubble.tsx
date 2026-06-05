import { Alert, Button, Card, Space, Statistic, Tag, Typography } from 'antd'
import {
  CheckCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons'
import type { ValidationCompletedPayload } from '../../../lib/events'
import { formatNumber } from '../../../lib/formatting'

const { Paragraph, Text } = Typography

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
  const visibleErrors = report.errors.slice(0, 3)

  return (
    <Card
      size="small"
      className={`sw-validation-card ${accepted ? 'is-accepted' : 'is-rejected'}`}
      variant="borderless"
      title={
        <Space size={8}>
          {accepted ? (
            <CheckCircleOutlined aria-hidden style={{ color: 'var(--sw-color-success)' }} />
          ) : (
            <ExclamationCircleOutlined aria-hidden style={{ color: 'var(--sw-color-danger)' }} />
          )}
          <Text strong>
            {accepted ? 'YAML 已通过 harness 校验' : 'YAML 未通过 harness 校验'}
          </Text>
          {payload.repair_attempt_count > 0 ? (
            <Tag color="warning">已自动修复 {payload.repair_attempt_count} 次</Tag>
          ) : null}
        </Space>
      }
    >
      <Space orientation="vertical" size={12} style={{ width: '100%' }}>
        <Space size={16} wrap>
          <Statistic
            title="错误"
            value={errorCount}
            valueStyle={{ color: errorCount > 0 ? 'var(--sw-color-danger)' : undefined }}
          />
          <Statistic
            title="警告"
            value={warningCount}
            valueStyle={{ color: warningCount > 0 ? 'var(--sw-color-warning)' : undefined }}
          />
          <Statistic title="严重级" value={report.severity} />
          {Object.entries(report.metrics).map(([key, value]) => (
            <Statistic key={key} title={key} value={formatNumber(Number(value)) || String(value)} />
          ))}
        </Space>

        {!accepted ? (
          <Alert
            type="warning"
            showIcon
            message={
              payload.rejected_version_id
                ? `结果已保存为 rejected draft：${payload.rejected_version_id}`
                : '生成结果未通过校验'
            }
            description="后端没有伪造成功，可在右侧资产栏查看 rejected 草稿与具体错误。"
          />
        ) : null}

        {visibleErrors.length > 0 ? (
          <div className="sw-validation-issues">
            {visibleErrors.map((issue) => (
              <Alert
                key={`${issue.code}-${issue.path}-${issue.message}`}
                type={issue.severity === 'warning' ? 'warning' : 'error'}
                showIcon
                message={`${issue.path} · ${issue.code}`}
                description={
                  <Paragraph style={{ marginBottom: 0 }}>
                    {issue.message}
                    {issue.repair_hint ? (
                      <Text type="secondary"> · 修复建议：{issue.repair_hint}</Text>
                    ) : null}
                  </Paragraph>
                }
              />
            ))}
            {report.errors.length > visibleErrors.length ? (
              <Text type="secondary">
                还有 {report.errors.length - visibleErrors.length} 个错误未列出。
              </Text>
            ) : null}
          </div>
        ) : null}

        <Space size={8} wrap>
          {onOpenHarness ? (
            <Button size="small" onClick={onOpenHarness}>
              查看完整校验
            </Button>
          ) : null}
          {onOpenYaml ? (
            <Button size="small" type="primary" ghost onClick={onOpenYaml}>
              打开 YAML
            </Button>
          ) : null}
        </Space>
      </Space>
    </Card>
  )
}
