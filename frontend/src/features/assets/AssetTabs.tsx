import { Badge, Tabs } from 'antd'
import {
  BookOutlined,
  CodeOutlined,
  DatabaseOutlined,
  HistoryOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons'
import type { ReactNode } from 'react'
import type { AssetTab } from '../../state/uiPrefs'
import './AssetTabs.css'

type AssetTabsProps = {
  activeTab: AssetTab
  onTabChange: (tab: AssetTab) => void
  panels: Record<AssetTab, ReactNode>
  highlightedTabs?: Partial<Record<AssetTab, boolean>>
}

const TAB_DEFS: Array<{ key: AssetTab; label: string; icon: ReactNode }> = [
  { key: 'chapters', label: '章节', icon: <BookOutlined aria-hidden /> },
  { key: 'index', label: '剧情索引', icon: <DatabaseOutlined aria-hidden /> },
  { key: 'yaml', label: '剧本', icon: <CodeOutlined aria-hidden /> },
  { key: 'validation', label: '校验', icon: <SafetyCertificateOutlined aria-hidden /> },
  { key: 'versions', label: '历史版本', icon: <HistoryOutlined aria-hidden /> },
]

export function AssetTabs({
  activeTab,
  onTabChange,
  panels,
  highlightedTabs = {},
}: AssetTabsProps) {
  return (
    <Tabs
      activeKey={activeTab}
      onChange={(key) => onTabChange(key as AssetTab)}
      className="sw-asset-tabs"
      destroyOnHidden={false}
      items={TAB_DEFS.map((tab) => ({
        key: tab.key,
        label: (
          <span className="sw-asset-tab-label">
            {tab.icon}
            <span>{tab.label}</span>
            {highlightedTabs[tab.key] ? <Badge dot className="sw-asset-tab-dot" /> : null}
          </span>
        ),
        children: <div className="sw-asset-panel">{panels[tab.key]}</div>,
      }))}
    />
  )
}
