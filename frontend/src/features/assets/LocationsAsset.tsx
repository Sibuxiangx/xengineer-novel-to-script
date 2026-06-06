import { Avatar, Card, Empty, Flex, Skeleton, Space, Typography } from 'antd'
import { EnvironmentOutlined } from '@ant-design/icons'
import type { BookIndexResponse, JsonRecord } from '../../types'
import './CardGrid.css'

const { Text, Paragraph } = Typography

type LocationsAssetProps = {
  data: BookIndexResponse | null
  loading: boolean
}

type IndexedLocation = {
  id?: string
  name?: string
  description?: string
  atmosphere?: string
}

function asLocations(record: JsonRecord | undefined): IndexedLocation[] {
  if (!record) return []
  const list = (record as { locations?: unknown }).locations
  if (!Array.isArray(list)) return []
  return list.filter((item): item is IndexedLocation => Boolean(item) && typeof item === 'object')
}

export function LocationsAsset({ data, loading }: LocationsAssetProps) {
  if (loading) {
    return <Skeleton active paragraph={{ rows: 5 }} />
  }
  const locations = asLocations(data?.book_index)
  if (locations.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚未抽取地点" />
  }

  return (
    <div className="sw-card-grid">
      {locations.map((location, index) => {
        const name = location.name ?? `地点 ${index + 1}`
        return (
          <Card
            key={location.id ?? `${name}-${index}`}
            size="small"
            className="sw-asset-card"
            title={
              <Flex align="center" gap={10}>
                <Avatar
                  size={32}
                  icon={<EnvironmentOutlined aria-hidden />}
                  className="sw-brand-avatar"
                  style={{ background: 'color-mix(in srgb, #16a34a 12%, transparent)', color: '#16a34a' }}
                />
                <Text strong>{name}</Text>
              </Flex>
            }
          >
            <Space orientation="vertical" size={4} style={{ width: '100%' }}>
              {location.atmosphere ? (
                <div>
                  <Text type="secondary" className="sw-asset-card-meta">氛围</Text>
                  <Paragraph style={{ marginBottom: 0, marginTop: 2 }}>
                    {location.atmosphere}
                  </Paragraph>
                </div>
              ) : null}
              {location.description ? (
                <Paragraph style={{ marginBottom: 0 }} type="secondary">
                  {location.description}
                </Paragraph>
              ) : null}
            </Space>
          </Card>
        )
      })}
    </div>
  )
}
