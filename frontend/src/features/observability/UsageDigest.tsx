import { Empty, List, Space, Statistic, Tag, Typography } from 'antd'
import { useMemo } from 'react'
import type { ModelUsagePayload } from '../../lib/events'
import { formatNumber } from '../../lib/formatting'

const { Text } = Typography

type UsageDigestProps = {
  items: ModelUsagePayload[]
}

export function UsageDigest({ items }: UsageDigestProps) {
  const totals = useMemo(() => {
    return {
      tokens: items.reduce((sum, item) => sum + item.estimated_input_tokens, 0),
      tasks: items.length,
      omittedBlocks: items.reduce((sum, item) => sum + item.omitted_block_ids.length, 0),
    }
  }, [items])

  if (items.length === 0) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description="还没有模型用量记录"
        style={{ width: 280 }}
      />
    )
  }

  return (
    <div className="sw-usage-digest" style={{ width: 320, maxHeight: 420, overflow: 'auto' }}>
      <Space size={16} style={{ width: '100%', marginBottom: 12 }}>
        <Statistic title="估算输入 token" value={formatNumber(totals.tokens)} />
        <Statistic title="任务数" value={totals.tasks} />
        <Statistic title="省略块" value={totals.omittedBlocks} />
      </Space>
      <List
        size="small"
        dataSource={items.slice().reverse()}
        renderItem={(item) => (
          <List.Item>
            <Space orientation="vertical" size={4} style={{ width: '100%' }}>
              <Space size={6} wrap>
                <Tag color="blue">{item.task || '未知任务'}</Tag>
                <Text type="secondary">{item.model}</Text>
              </Space>
              <Text>
                输入 {formatNumber(item.estimated_input_tokens)} / 预算{' '}
                {formatNumber(item.context_budget_tokens)}
              </Text>
              {item.omitted_block_ids.length > 0 ? (
                <Text type="secondary">
                  省略：{item.omitted_block_ids.slice(0, 4).join(', ')}
                  {item.omitted_block_ids.length > 4 ? '…' : ''}
                </Text>
              ) : null}
            </Space>
          </List.Item>
        )}
      />
    </div>
  )
}
