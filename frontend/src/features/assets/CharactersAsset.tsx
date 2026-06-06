import { Avatar, Card, Empty, Flex, Skeleton, Space, Tag, Typography } from 'antd'
import { UserOutlined } from '@ant-design/icons'
import type { BookIndexResponse, JsonRecord } from '../../types'
import './CardGrid.css'

const { Text, Paragraph } = Typography

type CharactersAssetProps = {
  data: BookIndexResponse | null
  loading: boolean
}

type IndexedCharacter = {
  id?: string
  names?: string[]
  name?: string
  role?: string
  description?: string
  goals?: string[]
  conflicts?: string[]
}

function asCharacters(record: JsonRecord | undefined): IndexedCharacter[] {
  if (!record) return []
  const list = (record as { characters?: unknown }).characters
  if (!Array.isArray(list)) return []
  return list.filter((item): item is IndexedCharacter => Boolean(item) && typeof item === 'object')
}

export function CharactersAsset({ data, loading }: CharactersAssetProps) {
  if (loading) {
    return <Skeleton active paragraph={{ rows: 6 }} />
  }
  const characters = asCharacters(data?.book_index)
  if (characters.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚未抽取人物" />
  }

  return (
    <div className="sw-card-grid">
      {characters.map((character, index) => {
        const name =
          character.names?.[0] ?? character.name ?? `角色 ${index + 1}`
        const aliases = (character.names ?? []).slice(1)
        return (
          <Card
            key={character.id ?? `${name}-${index}`}
            size="small"
            className="sw-asset-card"
            title={
              <Flex align="center" gap={10}>
                <Avatar size={32} icon={<UserOutlined aria-hidden />} className="sw-brand-avatar" />
                <span>
                  <Text strong>{name}</Text>
                  {character.role ? (
                    <Text type="secondary" className="sw-asset-card-sub">
                      · {character.role}
                    </Text>
                  ) : null}
                </span>
              </Flex>
            }
          >
            <Space orientation="vertical" size={6} style={{ width: '100%' }}>
              {aliases.length > 0 ? (
                <div>
                  <Text type="secondary" className="sw-asset-card-meta">别名</Text>
                  <Flex gap={6} wrap style={{ marginTop: 4 }}>
                    {aliases.map((alias) => (
                      <Tag key={alias}>{alias}</Tag>
                    ))}
                  </Flex>
                </div>
              ) : null}
              {character.description ? (
                <Paragraph style={{ marginBottom: 0 }} type="secondary">
                  {character.description}
                </Paragraph>
              ) : null}
              {character.goals?.length ? (
                <div>
                  <Text type="secondary" className="sw-asset-card-meta">目标</Text>
                  <ul className="sw-asset-card-list">
                    {character.goals.slice(0, 3).map((g, i) => (
                      <li key={i}>{g}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {character.conflicts?.length ? (
                <div>
                  <Text type="secondary" className="sw-asset-card-meta">冲突</Text>
                  <ul className="sw-asset-card-list">
                    {character.conflicts.slice(0, 3).map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </Space>
          </Card>
        )
      })}
    </div>
  )
}
