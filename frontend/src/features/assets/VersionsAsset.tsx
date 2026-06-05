import { Card, Empty, Flex, Skeleton, Space, Tag, Typography } from 'antd'
import { CheckCircleOutlined, ExclamationCircleOutlined } from '@ant-design/icons'
import type { ScriptVersion } from '../../types'
import { formatDate } from '../../lib/formatting'
import './VersionsAsset.css'

const { Text } = Typography

type VersionsAssetProps = {
  versions: ScriptVersion[]
  selectedVersionId: string | null
  loading: boolean
  onSelectVersion: (versionId: string) => void
}

export function VersionsAsset({
  versions,
  selectedVersionId,
  loading,
  onSelectVersion,
}: VersionsAssetProps) {
  if (loading) {
    return <Skeleton active paragraph={{ rows: 4 }} />
  }
  if (versions.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无版本记录" />
  }

  const accepted = versions.filter((version) => version.validation_status === 'accepted')
  const rejected = versions.filter((version) => version.validation_status !== 'accepted')

  return (
    <Space orientation="vertical" size={16} style={{ width: '100%' }}>
      {accepted.length > 0 ? (
        <section aria-label="已接受的剧本版本">
          <Flex align="center" gap={6} style={{ marginBottom: 8 }}>
            <CheckCircleOutlined aria-hidden style={{ color: 'var(--sw-color-success)' }} />
            <Text strong>已接受版本</Text>
            <Tag color="success">{accepted.length}</Tag>
          </Flex>
          <Space orientation="vertical" size={8} style={{ width: '100%' }}>
            {accepted.map((version) => (
              <VersionCard
                key={version.id}
                version={version}
                selected={version.id === selectedVersionId}
                tone="accepted"
                onSelect={() => onSelectVersion(version.id)}
              />
            ))}
          </Space>
        </section>
      ) : null}

      {rejected.length > 0 ? (
        <section aria-label="未通过校验的草稿版本">
          <Flex align="center" gap={6} style={{ marginBottom: 8 }}>
            <ExclamationCircleOutlined aria-hidden style={{ color: 'var(--sw-color-warning)' }} />
            <Text strong>Rejected drafts</Text>
            <Tag color="warning">{rejected.length}</Tag>
          </Flex>
          <Space orientation="vertical" size={8} style={{ width: '100%' }}>
            {rejected.map((version) => (
              <VersionCard
                key={version.id}
                version={version}
                selected={version.id === selectedVersionId}
                tone="rejected"
                onSelect={() => onSelectVersion(version.id)}
              />
            ))}
          </Space>
        </section>
      ) : null}
    </Space>
  )
}

type VersionCardProps = {
  version: ScriptVersion
  selected: boolean
  tone: 'accepted' | 'rejected'
  onSelect: () => void
}

function VersionCard({ version, selected, tone, onSelect }: VersionCardProps) {
  return (
    <Card
      size="small"
      hoverable
      className={[
        'sw-version-card',
        `is-${tone}`,
        selected ? 'is-selected' : '',
      ]
        .filter(Boolean)
        .join(' ')}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      aria-pressed={selected}
      aria-label={`版本 ${version.id} · ${version.validation_status}`}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onSelect()
        }
      }}
    >
      <Flex justify="space-between" align="center" gap={12}>
        <Space orientation="vertical" size={2}>
          <Text strong ellipsis>
            {version.reason}
          </Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {formatDate(version.created_at)} · {version.id}
          </Text>
        </Space>
        <Space orientation="vertical" size={2} align="end">
          <Tag color={tone === 'accepted' ? 'success' : 'warning'}>
            {version.validation_status}
          </Tag>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {version.operation_count > 0 ? `${version.operation_count} 步` : ''}
          </Text>
        </Space>
      </Flex>
    </Card>
  )
}
