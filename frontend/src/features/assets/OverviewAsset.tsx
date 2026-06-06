import { useMemo } from 'react'
import { Card, Empty, Flex, Skeleton, Space, Statistic, Tag, Typography } from 'antd'
import {
  BookOutlined,
  EnvironmentOutlined,
  ThunderboltOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { parse } from 'yaml'
import type { ValidationCompletedPayload } from '../../lib/events'
import type { BookIndexResponse, Chapter, JsonRecord, ScriptVersion } from '../../types'
import './OverviewAsset.css'

const { Text, Title, Paragraph } = Typography

type OverviewAssetProps = {
  loading: boolean
  yaml: string
  chapters: Chapter[]
  bookIndex: BookIndexResponse | null
  versions: ScriptVersion[]
  validation: ValidationCompletedPayload | null
}

type OverviewMeta = {
  title: string | null
  logline: string | null
  genre: string[]
  format: string | null
  tone: string | null
  audience: string | null
}

function parseMeta(yaml: string): OverviewMeta {
  const empty: OverviewMeta = {
    title: null,
    logline: null,
    genre: [],
    format: null,
    tone: null,
    audience: null,
  }
  if (!yaml) return empty
  try {
    const data = parse(yaml) as JsonRecord | null
    const project = (data?.project ?? {}) as JsonRecord
    return {
      title: typeof project.title === 'string' ? project.title : null,
      logline: typeof project.logline === 'string' ? project.logline : null,
      genre: Array.isArray(project.genre)
        ? (project.genre.filter((v) => typeof v === 'string') as string[])
        : [],
      format: typeof project.format === 'string' ? project.format : null,
      tone: typeof project.tone === 'string' ? project.tone : null,
      audience:
        typeof project.target_audience === 'string' ? project.target_audience : null,
    }
  } catch {
    return empty
  }
}

type IndexShape = {
  characters?: unknown[]
  locations?: unknown[]
  chapters?: { events?: unknown[] }[]
}

function indexShape(record: JsonRecord | undefined): IndexShape {
  return record ? (record as unknown as IndexShape) : {}
}

export function OverviewAsset({
  loading,
  yaml,
  chapters,
  bookIndex,
  versions,
  validation,
}: OverviewAssetProps) {
  const meta = useMemo(() => parseMeta(yaml), [yaml])
  const shape = indexShape(bookIndex?.book_index)
  const characterCount = shape.characters?.length ?? 0
  const locationCount = shape.locations?.length ?? 0
  const eventCount = (shape.chapters ?? []).reduce(
    (sum, c) => sum + (c.events?.length ?? 0),
    0,
  )
  const acceptedCount = versions.filter((v) => v.validation_status === 'accepted').length
  const rejectedCount = versions.length - acceptedCount

  if (loading) {
    return <Skeleton active paragraph={{ rows: 6 }} />
  }

  if (!meta.title && chapters.length === 0 && !bookIndex) {
    return (
      <div className="sw-overview-empty">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="项目还没有信息可展示，先上传小说并完成分章。"
        />
      </div>
    )
  }

  return (
    <div className="sw-overview">
      <Card variant="borderless" className="sw-overview-hero">
        <Space orientation="vertical" size={4} style={{ width: '100%' }}>
          <Text type="secondary" className="sw-overview-kicker">
            项目基础信息
          </Text>
          <Title level={3} className="sw-overview-title">
            {meta.title ?? '尚未命名'}
          </Title>
          <Flex gap={8} wrap>
            {meta.format ? <Tag color="blue">{meta.format}</Tag> : null}
            {meta.audience ? <Tag>{meta.audience}</Tag> : null}
            {meta.tone ? <Tag color="purple">{meta.tone}</Tag> : null}
            {meta.genre.map((g) => (
              <Tag key={g}>{g}</Tag>
            ))}
            {validation ? (
              <Tag color={validation.validation_status === 'accepted' ? 'success' : 'warning'}>
                校验：{validation.validation_status === 'accepted' ? '通过' : '未通过'}
              </Tag>
            ) : null}
          </Flex>
        </Space>
      </Card>

      {meta.logline ? (
        <Card size="small" title="一句话故事" variant="borderless">
          <Paragraph className="sw-overview-logline" style={{ marginBottom: 0 }}>
            {meta.logline}
          </Paragraph>
        </Card>
      ) : null}

      <Card size="small" title="资产总览" variant="borderless">
        <Flex gap={24} wrap>
          <Statistic
            title={
              <span>
                <BookOutlined aria-hidden /> 章节
              </span>
            }
            value={chapters.length}
          />
          <Statistic
            title={
              <span>
                <UserOutlined aria-hidden /> 角色
              </span>
            }
            value={characterCount}
          />
          <Statistic
            title={
              <span>
                <EnvironmentOutlined aria-hidden /> 地点
              </span>
            }
            value={locationCount}
          />
          <Statistic
            title={
              <span>
                <ThunderboltOutlined aria-hidden /> 事件
              </span>
            }
            value={eventCount}
          />
          <Statistic
            title="已接受版本"
            value={acceptedCount}
            valueStyle={{ color: 'var(--sw-color-success)' }}
          />
          <Statistic
            title="待修草稿"
            value={rejectedCount}
            valueStyle={
              rejectedCount > 0 ? { color: 'var(--sw-color-warning)' } : undefined
            }
          />
        </Flex>
      </Card>
    </div>
  )
}
