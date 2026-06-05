import { Alert, Card, Empty, Result, Space, Statistic, Tag, Typography } from 'antd'
import type { ValidationCompletedPayload } from '../../lib/events'
import { formatNumber } from '../../lib/formatting'
import { ContextReportCard } from '../observability/ContextReportCard'

const { Text, Paragraph } = Typography

type ValidationAssetProps = {
  validation: ValidationCompletedPayload | null
}

export function ValidationAsset({ validation }: ValidationAssetProps) {
  if (!validation) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚未运行 harness 校验" />
  }
  const { validation_report: report } = validation
  const accepted = validation.validation_status === 'accepted'

  return (
    <Space orientation="vertical" size={12} style={{ width: '100%' }}>
      <Result
        status={accepted ? 'success' : 'error'}
        title={accepted ? '校验通过' : '校验未通过'}
        subTitle={
          accepted
            ? '剧本已落库为最新可接受版本。'
            : `已自动修复 ${validation.repair_attempt_count} 次后仍未通过。`
        }
      />

      <Card size="small" variant="borderless">
        <Space size={16} wrap>
          <Statistic
            title="错误"
            value={report.errors.length}
            valueStyle={{
              color: report.errors.length > 0 ? 'var(--sw-color-danger)' : undefined,
            }}
          />
          <Statistic
            title="警告"
            value={report.warnings.length}
            valueStyle={{
              color: report.warnings.length > 0 ? 'var(--sw-color-warning)' : undefined,
            }}
          />
          <Statistic title="修复次数" value={validation.repair_attempt_count} />
          {Object.entries(report.metrics).map(([key, value]) => (
            <Statistic key={key} title={key} value={formatNumber(Number(value)) || String(value)} />
          ))}
        </Space>
      </Card>

      {[...report.errors, ...report.warnings].map((issue) => (
        <Alert
          key={`${issue.path}-${issue.code}`}
          type={issue.severity === 'warning' ? 'warning' : 'error'}
          showIcon
          message={
            <Space>
              <Tag color={issue.severity === 'warning' ? 'warning' : 'error'}>
                {issue.severity}
              </Tag>
              <Text strong>{issue.code}</Text>
              <Text type="secondary">{issue.path}</Text>
            </Space>
          }
          description={
            <Paragraph style={{ marginBottom: 0 }}>
              {issue.message}
              {issue.repair_hint ? (
                <Text type="secondary"> · 建议：{issue.repair_hint}</Text>
              ) : null}
            </Paragraph>
          }
        />
      ))}

      <ContextReportCard report={validation.context_report} />
    </Space>
  )
}
