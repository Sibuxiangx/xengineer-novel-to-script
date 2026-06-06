import { Badge, Empty, Skeleton, Tag, Tree, Typography } from 'antd'
import {
  BookOutlined,
  CodeOutlined,
  EnvironmentOutlined,
  ExclamationCircleOutlined,
  FileTextOutlined,
  HistoryOutlined,
  ReadOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
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
  selectedScriptVersionLabel?: string | null
  selectedScriptVersionTone?: 'accepted' | 'draft' | null
  activeTab: AssetTab
  selectedChapterId: string | null
  highlightedTabs?: Partial<Record<AssetTab, boolean>>
  onSelectTab: (tab: AssetTab, chapterId?: string | null) => void
}

type StructureNode = {
  key: string
  title: ReactNode
  icon?: ReactNode
}

type BookIndexShape = {
  chapters?: { events?: unknown[] }[]
  characters?: unknown[]
  locations?: unknown[]
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
    <span className="sw-structure-title">
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
    </span>
  )
}

type ParsedKey =
  | { kind: 'tab'; tab: AssetTab }
  | { kind: 'chapter'; chapterId: string }

function parseKey(key: string): ParsedKey | null {
  if (key.startsWith('chapter:')) {
    return { kind: 'chapter', chapterId: key.slice('chapter:'.length) }
  }
  if (key.startsWith('tab:')) {
    return { kind: 'tab', tab: key.slice('tab:'.length) as AssetTab }
  }
  return null
}

function selectedKeyFor(activeTab: AssetTab, selectedChapterId: string | null): string {
  if (activeTab === 'chapter' && selectedChapterId) {
    return `chapter:${selectedChapterId}`
  }
  return `tab:${activeTab}`
}

type SectionProps = {
  label: string
  icon: ReactNode
  meta?: ReactNode
  variant?: 'default' | 'tools'
  treeData: StructureNode[]
  selectedKey: string
  onSelect: (key: string) => void
}

function Section({ label, icon, meta, variant, treeData, selectedKey, onSelect }: SectionProps) {
  if (treeData.length === 0) return null
  return (
    <div className={`sw-structure-section${variant === 'tools' ? ' is-tools' : ''}`}>
      <div className="sw-structure-section-header">
        <span className="sw-structure-section-icon" aria-hidden>{icon}</span>
        <Text className="sw-structure-section-label">{label}</Text>
        {meta ? <span className="sw-structure-section-meta">{meta}</span> : null}
      </div>
      <Tree
        blockNode
        showIcon
        selectable
        selectedKeys={[selectedKey]}
        treeData={treeData}
        onSelect={(keys) => {
          const key = String(keys[0] ?? '')
          if (key) onSelect(key)
        }}
      />
    </div>
  )
}

export function ProjectStructurePanel({
  hasProject,
  chapters,
  chaptersLoading,
  bookIndex,
  bookIndexLoading,
  versions,
  selectedScriptVersionLabel,
  selectedScriptVersionTone,
  activeTab,
  selectedChapterId,
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
  const eventTotal = indexedChapters.reduce(
    (sum, chapter) => sum + (chapter.events?.length ?? 0),
    0,
  )
  const acceptedCount = versions.filter(
    (version) => version.validation_status === 'accepted',
  ).length
  const rejectedCount = versions.length - acceptedCount

  // ── 剧本故事 ──
  const storyNodes: StructureNode[] = [
    {
      key: 'tab:overview',
      icon: <FileTextOutlined aria-hidden />,
      title: nodeTitle('项目基础信息', null, { highlighted: highlightedTabs.overview }),
    },
    {
      key: 'tab:script',
      icon: <CodeOutlined aria-hidden />,
      title: nodeTitle(
        '剧本',
        selectedScriptVersionLabel ? (
          <Tag
            color={selectedScriptVersionTone === 'draft' ? 'warning' : 'success'}
            className="sw-structure-version-tag"
          >
            {selectedScriptVersionLabel}
          </Tag>
        ) : rejectedCount > 0 ? (
          <Tag color="warning" className="sw-structure-tag">
            待修
          </Tag>
        ) : null,
        { highlighted: highlightedTabs.script },
      ),
    },
    ...chapters.map((chapter) => ({
      key: `chapter:${chapter.id}`,
      icon: <ReadOutlined aria-hidden />,
      title: nodeTitle(
        `${String(chapter.order_index + 1).padStart(2, '0')} · ${chapter.title}`,
      ),
    })),
  ]

  // ── 故事元素 ──
  const elementNodes: StructureNode[] = [
    {
      key: 'tab:characters',
      icon: <UserOutlined aria-hidden />,
      title: nodeTitle('角色设定', <Tag className="sw-structure-tag">{characters.length}</Tag>, {
        highlighted: highlightedTabs.characters,
      }),
    },
    {
      key: 'tab:locations',
      icon: <EnvironmentOutlined aria-hidden />,
      title: nodeTitle('场景地点', <Tag className="sw-structure-tag">{locations.length}</Tag>, {
        highlighted: highlightedTabs.locations,
      }),
    },
    {
      key: 'tab:events',
      icon: <ThunderboltOutlined aria-hidden />,
      title: nodeTitle('核心事件', <Tag className="sw-structure-tag">{eventTotal}</Tag>, {
        highlighted: highlightedTabs.events,
      }),
    },
  ]

  // ── 项目工具 ──
  const toolNodes: StructureNode[] = [
    {
      key: 'tab:validation',
      icon: <SafetyCertificateOutlined aria-hidden />,
      title: nodeTitle(
        '规则校验',
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
      key: 'tab:versions',
      icon: <HistoryOutlined aria-hidden />,
      title: nodeTitle('历史版本', <Tag className="sw-structure-tag">{versions.length}</Tag>, {
        highlighted: highlightedTabs.versions,
      }),
    },
  ]

  const selectedKey = selectedKeyFor(activeTab, selectedChapterId)
  const handleSelect = (rawKey: string) => {
    const parsed = parseKey(rawKey)
    if (!parsed) return
    if (parsed.kind === 'chapter') {
      onSelectTab('chapter', parsed.chapterId)
    } else {
      onSelectTab(parsed.tab, null)
    }
  }

  return (
    <div className="sw-structure-panel">
      <Section
        label="剧本故事"
        icon={<BookOutlined aria-hidden />}
        meta={
          chapters.length > 0 ? (
            <Tag className="sw-structure-tag">{chapters.length} 章</Tag>
          ) : null
        }
        treeData={storyNodes}
        selectedKey={selectedKey}
        onSelect={handleSelect}
      />
      <Section
        label="故事元素"
        icon={<ThunderboltOutlined aria-hidden />}
        treeData={elementNodes}
        selectedKey={selectedKey}
        onSelect={handleSelect}
      />
      <div className="sw-structure-divider" role="separator" aria-hidden />
      <Section
        label="项目工具"
        icon={<SettingOutlined aria-hidden />}
        variant="tools"
        treeData={toolNodes}
        selectedKey={selectedKey}
        onSelect={handleSelect}
      />
    </div>
  )
}
