import { Empty, Skeleton, Tag, Timeline, Typography } from 'antd'
import type { BookIndexResponse, JsonRecord } from '../../types'
import './EventsAsset.css'

const { Text, Paragraph } = Typography

type EventsAssetProps = {
  data: BookIndexResponse | null
  loading: boolean
}

type IndexedEvent = {
  id?: string
  summary?: string
  importance?: string
}

type IndexedChapter = {
  id?: string
  title?: string
  order?: number
  events?: IndexedEvent[]
}

function asChapters(record: JsonRecord | undefined): IndexedChapter[] {
  if (!record) return []
  const list = (record as { chapters?: unknown }).chapters
  if (!Array.isArray(list)) return []
  return list.filter((item): item is IndexedChapter => Boolean(item) && typeof item === 'object')
}

const importanceColor: Record<string, string> = {
  major: 'red',
  high: 'red',
  medium: 'gold',
  low: 'default',
  minor: 'default',
}

export function EventsAsset({ data, loading }: EventsAssetProps) {
  if (loading) {
    return <Skeleton active paragraph={{ rows: 8 }} />
  }
  const chapters = asChapters(data?.book_index).filter(
    (c) => (c.events?.length ?? 0) > 0,
  )
  if (chapters.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚未抽取事件" />
  }

  return (
    <div className="sw-events-asset">
      {chapters.map((chapter, chapterIndex) => (
        <section key={chapter.id ?? chapterIndex} className="sw-events-chapter">
          <header className="sw-events-chapter-head">
            <Tag>{`#${chapter.order ?? chapterIndex + 1}`}</Tag>
            <Text strong>{chapter.title ?? `第 ${chapterIndex + 1} 章`}</Text>
            <Text type="secondary" className="sw-events-chapter-count">
              {chapter.events?.length ?? 0} 个事件
            </Text>
          </header>
          <Timeline
            className="sw-events-timeline"
            items={(chapter.events ?? []).map((event, eventIndex) => ({
              key: event.id ?? `${chapterIndex}-${eventIndex}`,
              color:
                importanceColor[event.importance ?? 'medium']?.replace(
                  'default',
                  'gray',
                ) ?? 'gray',
              children: (
                <div className="sw-events-item">
                  {event.importance ? (
                    <Tag color={importanceColor[event.importance] ?? 'default'}>
                      {event.importance}
                    </Tag>
                  ) : null}
                  <Paragraph style={{ marginBottom: 0 }}>
                    {event.summary ?? '（缺少摘要）'}
                  </Paragraph>
                </div>
              ),
            }))}
          />
        </section>
      ))}
    </div>
  )
}
