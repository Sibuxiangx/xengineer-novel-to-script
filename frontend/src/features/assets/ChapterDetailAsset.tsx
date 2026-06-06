import { Card, Empty, Flex, Skeleton, Space, Statistic, Tag, Typography } from 'antd'
import { useMemo } from 'react'
import type { Chapter, BookIndexResponse } from '../../types'
import { formatNumber } from '../../lib/formatting'
import './ChapterDetailAsset.css'

const { Text, Paragraph, Title } = Typography

type ChapterDetailAssetProps = {
  chapter: Chapter | null
  loading: boolean
  bookIndex: BookIndexResponse | null
}

type IndexedEvent = {
  id?: string
  summary?: string
  importance?: string
}

type IndexedChapter = {
  id?: string
  order?: number
  title?: string
  summary?: string
  events?: IndexedEvent[]
  hooks?: string[]
}

function findIndexedChapter(
  bookIndex: BookIndexResponse | null,
  chapter: Chapter | null,
): IndexedChapter | null {
  if (!bookIndex || !chapter) return null
  const list = (bookIndex.book_index as { chapters?: unknown }).chapters
  if (!Array.isArray(list)) return null
  for (const item of list) {
    if (!item || typeof item !== 'object') continue
    const ic = item as IndexedChapter
    if (ic.id === chapter.id) return ic
    if (typeof ic.order === 'number' && ic.order === chapter.order_index + 1) return ic
  }
  return null
}

export function ChapterDetailAsset({
  chapter,
  loading,
  bookIndex,
}: ChapterDetailAssetProps) {
  const indexed = useMemo(
    () => findIndexedChapter(bookIndex, chapter),
    [bookIndex, chapter],
  )

  if (loading) {
    return <Skeleton active paragraph={{ rows: 8 }} />
  }
  if (!chapter) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description="请在左侧目录中选择一个章节"
      />
    )
  }

  return (
    <div className="sw-chapter-detail">
      <Card variant="borderless" className="sw-chapter-hero">
        <Space orientation="vertical" size={4} style={{ width: '100%' }}>
          <Text type="secondary" className="sw-chapter-kicker">
            第 {String(chapter.order_index + 1).padStart(2, '0')} 章
          </Text>
          <Title level={3} className="sw-chapter-title">
            {chapter.title}
          </Title>
          <Flex gap={16} wrap>
            <Statistic
              title="字数"
              value={chapter.content.length}
              formatter={(value) => formatNumber(Number(value))}
            />
            {chapter.token_estimate ? (
              <Statistic
                title="估算 Token"
                value={chapter.token_estimate}
                formatter={(value) => formatNumber(Number(value))}
              />
            ) : null}
            {indexed?.events?.length ? (
              <Statistic title="事件" value={indexed.events.length} />
            ) : null}
          </Flex>
        </Space>
      </Card>

      {indexed?.summary ? (
        <Card size="small" title="本章摘要" variant="borderless">
          <Paragraph style={{ marginBottom: 0 }}>{indexed.summary}</Paragraph>
        </Card>
      ) : null}

      {indexed?.events?.length ? (
        <Card size="small" title="本章事件" variant="borderless">
          <ul className="sw-chapter-event-list">
            {indexed.events.map((event, i) => (
              <li key={event.id ?? i}>
                {event.importance ? (
                  <Tag
                    color={
                      event.importance === 'major' || event.importance === 'high'
                        ? 'red'
                        : event.importance === 'low' || event.importance === 'minor'
                          ? 'default'
                          : 'gold'
                    }
                  >
                    {event.importance}
                  </Tag>
                ) : null}
                <span>{event.summary ?? '（缺少摘要）'}</span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <Card size="small" title="原文" variant="borderless">
        <Paragraph
          className="sw-chapter-content"
          style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}
        >
          {chapter.content}
        </Paragraph>
      </Card>
    </div>
  )
}
