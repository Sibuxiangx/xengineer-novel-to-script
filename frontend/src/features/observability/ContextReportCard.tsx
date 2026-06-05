import { Card, Progress, Space, Tag, Typography } from 'antd'
import type { ContextPackingReport } from '../../types'
import { formatNumber } from '../../lib/formatting'

const { Text } = Typography

type ContextReportCardProps = {
  report: ContextPackingReport | null
  title?: string
}

export function ContextReportCard({ report, title }: ContextReportCardProps) {
  if (!report) {
    return null
  }
  const ratio =
    report.budget_tokens > 0
      ? Math.min(100, Math.round((report.estimated_tokens / report.budget_tokens) * 100))
      : 0
  return (
    <Card size="small" title={title ?? '上下文打包报告'} className="sw-context-report">
      <Space orientation="vertical" size={8} style={{ width: '100%' }}>
        <Text>
          预算 {formatNumber(report.budget_tokens)} · 估算输入{' '}
          {formatNumber(report.estimated_tokens)}
        </Text>
        <Progress
          percent={ratio}
          status={ratio > 95 ? 'exception' : 'active'}
          aria-label={`上下文使用 ${ratio}%`}
        />
        <Space wrap size={4}>
          <Text type="secondary">包含：</Text>
          {report.included_block_ids.slice(0, 8).map((id) => (
            <Tag key={`in-${id}`} color="blue">
              {id}
            </Tag>
          ))}
          {report.included_block_ids.length > 8 ? (
            <Tag>+{report.included_block_ids.length - 8}</Tag>
          ) : null}
        </Space>
        {report.omitted_block_ids.length > 0 ? (
          <Space wrap size={4}>
            <Text type="secondary">省略：</Text>
            {report.omitted_block_ids.slice(0, 8).map((id) => (
              <Tag key={`out-${id}`}>{id}</Tag>
            ))}
            {report.omitted_block_ids.length > 8 ? (
              <Tag>+{report.omitted_block_ids.length - 8}</Tag>
            ) : null}
          </Space>
        ) : null}
      </Space>
    </Card>
  )
}
