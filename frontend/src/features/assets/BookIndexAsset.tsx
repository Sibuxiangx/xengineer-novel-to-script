import { Card, Collapse, Empty, Flex, Skeleton, Space, Statistic, Tabs, Tag, Typography } from 'antd'
import type { BookIndexResponse, JsonRecord } from '../../types'
import { formatNumber } from '../../lib/formatting'

const { Text, Paragraph } = Typography

type BookIndexAssetProps = {
  data: BookIndexResponse | null
  loading: boolean
  error: boolean
}

type IndexedCharacter = {
  id: string
  names: string[]
  role?: string
  description?: string
}

type IndexedLocation = {
  id: string
  name: string
  description?: string
}

type IndexedEvent = {
  id: string
  summary: string
  importance?: string
}

type IndexedChapter = {
  id: string
  title: string
  order: number
  summary: string
  events: IndexedEvent[]
}

type BookIndexShape = {
  title?: string
  chapter_count?: number
  chapters?: IndexedChapter[]
  characters?: IndexedCharacter[]
  locations?: IndexedLocation[]
}

function extractShape(record: JsonRecord | undefined): BookIndexShape {
  if (!record) return {}
  return record as unknown as BookIndexShape
}

export function BookIndexAsset({ data, loading, error }: BookIndexAssetProps) {
  if (loading) {
    return <Skeleton active paragraph={{ rows: 6 }} />
  }
  if (!data || error) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚未生成剧情索引" />
  }

  const shape = extractShape(data.book_index)
  const chapterCount = shape.chapter_count ?? shape.chapters?.length ?? 0
  const characters = shape.characters ?? []
  const locations = shape.locations ?? []

  return (
    <Space orientation="vertical" size={12} style={{ width: '100%' }}>
      <Card size="small" title={shape.title ?? '剧情索引'} variant="borderless">
        <Flex gap={16} wrap>
          <Statistic title="章节数" value={chapterCount} />
          <Statistic title="人物数" value={characters.length} />
          <Statistic title="地点数" value={locations.length} />
        </Flex>
      </Card>

      <Tabs
        size="small"
        items={[
          {
            key: 'summary',
            label: '摘要',
            children: (
              <Space orientation="vertical" size={10} style={{ width: '100%' }}>
                {(shape.chapters ?? []).map((chapter) => (
                  <Card
                    key={chapter.id}
                    size="small"
                    title={
                      <Space>
                        <Tag>{`#${chapter.order}`}</Tag>
                        <Text>{chapter.title}</Text>
                      </Space>
                    }
                  >
                    <Paragraph style={{ marginBottom: 8 }}>{chapter.summary}</Paragraph>
                    {chapter.events.length > 0 ? (
                      <Space orientation="vertical" size={4} style={{ width: '100%' }}>
                        {chapter.events.map((event) => (
                          <Text key={event.id} type="secondary">
                            · {event.summary}
                          </Text>
                        ))}
                      </Space>
                    ) : null}
                  </Card>
                ))}
                {characters.length > 0 ? (
                  <Card size="small" title="人物">
                    <Flex gap={8} wrap>
                      {characters.map((character) => (
                        <Tag key={character.id} color="blue">
                          {character.names.join(' · ')}
                        </Tag>
                      ))}
                    </Flex>
                  </Card>
                ) : null}
                {locations.length > 0 ? (
                  <Card size="small" title="地点">
                    <Flex gap={8} wrap>
                      {locations.map((location) => (
                        <Tag key={location.id} color="green">
                          {location.name}
                        </Tag>
                      ))}
                    </Flex>
                  </Card>
                ) : null}
              </Space>
            ),
          },
          {
            key: 'json',
            label: '原始 JSON',
            children: (
              <Collapse
                size="small"
                ghost
                items={[
                  {
                    key: 'json',
                    label: <Text type="secondary">展开完整剧情索引源码</Text>,
                    children: (
                      <pre className="sw-json-preview">
                        {JSON.stringify(data.book_index, null, 2)}
                      </pre>
                    ),
                  },
                ]}
              />
            ),
          },
        ]}
      />

      {data.context_report ? (
        <Card size="small" title="上下文打包" variant="borderless">
          <Text>
            预算 {formatNumber(data.context_report.budget_tokens)} · 估算输入{' '}
            {formatNumber(data.context_report.estimated_tokens)}
          </Text>
        </Card>
      ) : null}
    </Space>
  )
}
