import { Avatar, Button, Divider, Spin, Tooltip, Typography } from 'antd'
import {
  ApartmentOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  PlusOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import type { ReactNode } from 'react'
import clsx from 'clsx'
import './LeftRail.css'

const { Text, Title } = Typography

type LeftRailProps = {
  loading: boolean
  onCreate: () => void
  children: ReactNode
  collapsed?: boolean
  onToggleCollapsed?: () => void
  onOpenSettings?: () => void
}

export function LeftRail({
  loading,
  onCreate,
  children,
  collapsed,
  onToggleCollapsed,
  onOpenSettings,
}: LeftRailProps) {
  return (
    <nav
      className={clsx('sw-rail', collapsed && 'sw-rail--collapsed')}
      aria-label="改编会话列表"
    >
      <header className="sw-rail-brand">
        <Avatar size={42} icon={<ApartmentOutlined aria-hidden />} className="sw-brand-avatar" />
        {!collapsed ? (
          <div className="sw-rail-brand-meta">
            <Title level={4} className="sw-rail-title">
              ScriptWeaver
            </Title>
            <Text type="secondary" className="sw-rail-subtitle">
              把小说改编成可拍摄短剧
            </Text>
          </div>
        ) : null}
        {onToggleCollapsed ? (
          <Tooltip title={collapsed ? '展开会话栏' : '折叠会话栏'} placement="right">
            <Button
              type="text"
              size="small"
              className="sw-rail-collapse"
              icon={collapsed ? <MenuUnfoldOutlined aria-hidden /> : <MenuFoldOutlined aria-hidden />}
              aria-label={collapsed ? '展开会话栏' : '折叠会话栏'}
              onClick={onToggleCollapsed}
            />
          </Tooltip>
        ) : null}
      </header>

      <Tooltip title={collapsed ? '新建改编' : undefined} placement="right">
        <Button
          type="primary"
          icon={<PlusOutlined aria-hidden />}
          block={!collapsed}
          size="large"
          className="sw-rail-create"
          onClick={onCreate}
          aria-label="新建改编会话"
        >
          {collapsed ? null : '新建改编'}
        </Button>
      </Tooltip>

      {!collapsed ? (
        <Divider plain titlePlacement="start">
          <Text type="secondary">会话</Text>
        </Divider>
      ) : null}

      {!collapsed ? (
        loading ? (
          <div className="sw-rail-loading" role="status" aria-live="polite">
            <Spin size="small" />
            <Text type="secondary">加载会话</Text>
          </div>
        ) : (
          <div className="sw-rail-scroll">{children}</div>
        )
      ) : (
        <div className="sw-rail-collapsed-spacer" aria-hidden />
      )}

      {onOpenSettings ? (
        <Tooltip title={collapsed ? '工作台设置' : undefined} placement="right">
          <Button
            type="text"
            icon={<SettingOutlined aria-hidden />}
            block={!collapsed}
            className="sw-rail-settings"
            aria-label="打开工作台设置"
            onClick={onOpenSettings}
          >
            {collapsed ? null : '设置'}
          </Button>
        </Tooltip>
      ) : null}
    </nav>
  )
}
