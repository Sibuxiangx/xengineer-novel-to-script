import type { ReactNode } from 'react'
import { Avatar, Tag, Typography } from 'antd'
import { DatabaseOutlined } from '@ant-design/icons'
import './RightInspector.css'

const { Text, Title } = Typography

type RightInspectorProps = {
  projectId: string | null
  children: ReactNode
}

export function RightInspector({ projectId, children }: RightInspectorProps) {
  const shortId = projectId ? `${projectId.slice(0, 8)}…` : null
  return (
    <>
      <header className="sw-inspector-head">
        <div className="sw-inspector-head-left">
          <Avatar icon={<DatabaseOutlined aria-hidden />} />
          <div className="sw-inspector-head-meta">
            <Title level={5} className="sw-inspector-title">
              项目资产
            </Title>
            <Text type="secondary" className="sw-inspector-subtitle">
              {shortId ? `项目 ${shortId}` : '还未启动改编流程'}
            </Text>
          </div>
        </div>
        <Tag
          color={projectId ? 'success' : 'default'}
          aria-live="polite"
          aria-label={projectId ? '项目已链接' : '尚未链接项目'}
        >
          {projectId ? '已就绪' : '待启动'}
        </Tag>
      </header>
      <div className="sw-inspector-body">{children}</div>
    </>
  )
}
