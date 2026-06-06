import { Badge, Empty, Flex, Skeleton, Space, Tag, Tree, Typography } from 'antd'
import {
  BookOutlined,
  CodeOutlined,
  DatabaseOutlined,
  EnvironmentOutlined,
  ExclamationCircleOutlined,
  HistoryOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
  UserOutlined,
} from '@ant-design/icons'
import type { ReactNode } from 'react'
import type { AssetTab } from '../../state/uiPrefs'
import type { BookIndexResponse, Chapter, JsonRecord, ScriptVersion } from '../../types'
import './ProjectStructurePanel.css'

const { Text } = Typography

type ProjectStructurePanelProps = {
  hasProject: boolean
  chapters: Chapter[]
  chaptersLoading: boolean
  bookIndex: BookIndexResponse | null
  bookIndexLoading: boolean
  versions: ScriptVersion[]
  activeTab: AssetTab
  highlightedTabs?: Partial<Record<AssetTab, boolean>>
  onSelectTab: (tab: AssetTab) => void
}

type StructureNode = {
  key: string
  title: ReactNode
  icon?: ReactNode
  children?: StructureNode[]
}

type IndexedCharacter = {
  id?: string
  names?: string[]
  name?: string
}

type IndexedLocation = {
  id?: string
  name?: string
}

type IndexedEvent = {
  id?: string
  summary?: string
}

type IndexedChapter = {
  id?: string
  title?: string
  order?: number
  events?: IndexedEvent[]
}

type BookIndexShape = {
  chapters?: IndexedChapter[]
  characters?: IndexedCharacter[]
  locations?: IndexedLocation[]
}

function extractShape(record: JsonRecord | undefined): BookIndexShape {
  return record ? (record as unknown as BookIndexShape) : {}
}

function nodeTitle(
  label: string,
  meta?: ReactNode,
  options: { warning?: boolean; highlighted?: boolean } = {},
) {
  return (
    <Flex align="center" justify="space-between" gap={8} className="sw-structure-title">
      <span className="sw-structure-title-main">
        {options.warning ? (
          <ExclamationCircleOutlined className="sw-structure-warning-icon" aria-hidden />
        ) : null}
        <Text ellipsis className={options.warning ? 'sw-structure-warning-text' : undefined}>
          {label}
        </Text>
      </span>
      <span className="sw-structure-title-meta">
        {options.highlighted ? <Badge dot className="sw-structure-dot" /> : null}
        {meta}
      </span>
    </Flex>
  )
}

function keyToTab(key: string): AssetTab {
  if (key.startsWith('asset:')) return key.slice('asset:'.length) as AssetTab
  if (key.startsWith('chapter:')) return 'chapters'
  if (key.startsWith('version:')) return 'versions'
  if (key.startsWith('validation:')) return 'validation'
  return 'index'
}

export function ProjectStructurePanel({
  hasProject,
  chapters,
  chaptersLoading,
  bookIndex,
  bookIndexLoading,
  versions,
  activeTab,
  highlightedTabs = {},
  onSelectTab,
}: ProjectStructurePanelProps) {
  if (!hasProject) {
    return (
      <div className="sw-structure-empty">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="新建或上传小说后，这里会显示章节、角色和场景结构。"
        />
      </div>
    )
  }

  if (chaptersLoading || bookIndexLoading) {
    return (
      <div className="sw-structure-loading">
        <Skeleton active paragraph={{ rows: 7 }} title={false} />
      </div>
    )
  }

  const shape = extractShape(bookIndex?.book_index)
  const characters = shape.characters ?? []
  const locations = shape.locations ?? []
  const indexedChapters = shape.chapters ?? []
  const acceptedCount = versions.filter((version) => version.validation_status === 'accepted').length
  const rejectedCount = versions.length - acceptedCount

  const treeData: StructureNode[] = [
    {
      key: 'asset:yaml',
      icon: <CodeOutlined aria-hidden />,
      title: nodeTitle(
        '剧本',
        rejectedCount > 0 ? (
          <Tag color="warning" className="sw-structure-tag">
            待修
          </Tag>
        ) : versions.length > 0 ? (
          <Tag color="success" className="sw-structure-tag">
            {versions.length}
          </Tag>
        ) : null,
        { warning: rejectedCount > 0, highlighted: highlightedTabs.yaml },
      ),
    },
    {
      key: 'asset:chapters',
      icon: <BookOutlined aria-hidden />,
      title: nodeTitle('章节', <Tag className="sw-structure-tag">{chapters.length}</Tag>, {
        highlighted: highlightedTabs.chapters,
      }),
      children: chapters.slice(0, 18).map((chapter) => ({
        key: `chapter:${chapter.id}`,
        title: nodeTitle(
          `${String(chapter.order_index + 1).padStart(2, '0')} · ${chapter.title}`,
        ),
      })),
    },
    {
      key: 'asset:index',
      icon: <DatabaseOutlined aria-hidden />,
      title: nodeTitle('剧情索引', null, { highlighted: highlightedTabs.index }),
      children: [
        {
          key: 'index:characters',
          icon: <UserOutlined aria-hidden />,
          title: nodeTitle('角色', <Tag className="sw-structure-tag">{characters.length}</Tag>),
          children: characters.slice(0, 12).map((character, index) => ({
            key: `index:character:${character.id ?? index}`,
            title: nodeTitle(character.names?.join(' / ') ?? character.name ?? `角色 ${index + 1}`),
          })),
        },
        {
          key: 'index:locations',
          icon: <EnvironmentOutlined aria-hidden />,
          title: nodeTitle('地点', <Tag className="sw-structure-tag">{locations.length}</Tag>),
          children: locations.slice(0, 12).map((location, index) => ({
            key: `index:location:${location.id ?? index}`,
            title: nodeTitle(location.name ?? `地点 ${index + 1}`),
          })),
        },
        {
          key: 'index:events',
          icon: <ThunderboltOutlined aria-hidden />,
          title: nodeTitle(
            '事件',
            <Tag className="sw-structure-tag">
              {indexedChapters.reduce((sum, chapter) => sum + (chapter.events?.length ?? 0), 0)}
            </Tag>,
          ),
          children: indexedChapters.slice(0, 8).map((chapter, chapterIndex) => ({
            key: `index:chapter-events:${chapter.id ?? chapterIndex}`,
            title: nodeTitle(chapter.title ?? `章节 ${chapterIndex + 1}`),
            children: (chapter.events ?? []).slice(0, 6).map((event, eventIndex) => ({
              key: `index:event:${event.id ?? `${chapterIndex}-${eventIndex}`}`,
              title: nodeTitle(event.summary ?? `事件 ${eventIndex + 1}`),
            })),
          })),
        },
      ],
    },
    {
      key: rejectedCount > 0 ? 'asset:validation' : 'validation:latest',
      icon: <SafetyCertificateOutlined aria-hidden />,
      title: nodeTitle(
        '校验',
        rejectedCount > 0 ? (
          <Badge count={rejectedCount} size="small" color="var(--sw-color-danger)" />
        ) : (
          <Tag color="success" className="sw-structure-tag">
            正常
          </Tag>
        ),
        { warning: rejectedCount > 0, highlighted: highlightedTabs.validation },
      ),
    },
    {
      key: 'asset:versions',
      icon: <HistoryOutlined aria-hidden />,
      title: nodeTitle('历史版本', <Tag className="sw-structure-tag">{versions.length}</Tag>, {
        highlighted: highlightedTabs.versions,
      }),
    },
  ]

  return (
    <Space orientation="vertical" size={10} className="sw-structure-panel">
      <Flex align="center" justify="space-between" gap={8}>
        <Text type="secondary" className="sw-structure-kicker">
          项目结构
        </Text>
        {rejectedCount > 0 ? (
          <Tag color="warning" className="sw-structure-tag">
            {rejectedCount} 个草稿待修
          </Tag>
        ) : null}
      </Flex>
      <Tree
        blockNode
        showIcon
        selectedKeys={[`asset:${activeTab}`]}
        defaultExpandedKeys={['asset:chapters', 'asset:index']}
        treeData={treeData}
        onSelect={(keys) => {
          const key = String(keys[0] ?? '')
          if (!key) return
          onSelectTab(keyToTab(key))
        }}
      />
    </Space>
  )
}
