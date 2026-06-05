import { Collapse, Empty, Flex, Skeleton, Tag, Typography } from 'antd'
import type { Chapter } from '../../types'
import { formatNumber, truncate } from '../../lib/formatting'

const { Text, Paragraph } = Typography

type ChaptersAssetProps = {
  chapters: Chapter[]
  loading: boolean
}

export function ChaptersAsset({ chapters, loading }: ChaptersAssetProps) {
  if (loading) {
    return <Skeleton active paragraph={{ rows: 5 }} />
  }
  if (chapters.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚未确认分章" />
  }
  return (
    <Collapse
      size="small"
      items={chapters.map((chapter) => ({
        key: chapter.id,
        label: (
          <Flex align="center" justify="space-between" gap={8}>
            <Text ellipsis>
              {String(chapter.order_index + 1).padStart(2, '0')} · {chapter.title}
            </Text>
            <Tag>{formatNumber(chapter.token_estimate ?? chapter.content.length)}</Tag>
          </Flex>
        ),
        children: (
          <Paragraph
            style={{ whiteSpace: 'pre-wrap', color: 'var(--sw-color-text-muted)', margin: 0 }}
          >
            {truncate(chapter.content, 720)}
          </Paragraph>
        ),
      }))}
    />
  )
}
