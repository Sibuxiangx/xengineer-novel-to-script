import {
  Button,
  Empty,
  List,
  Modal,
  Space,
  Switch,
  Tag,
  Typography,
} from 'antd'
import {
  ApiOutlined,
  BugOutlined,
  MoonOutlined,
  ReloadOutlined,
  SunOutlined,
} from '@ant-design/icons'
import { apiBaseUrl } from '../lib/api'
import { formatDate } from '../lib/formatting'
import type { ChatSession, RunStatus } from '../types'
import type { AssetTab, ThemeMode } from '../state/uiPrefs'
import './WorkspaceSettingsModal.css'

const { Paragraph, Text, Title } = Typography

type DebugInfo = {
  activeSessionId: string | null
  projectId: string | null
  activeAssetTab: AssetTab
  runStatus: RunStatus
  isStreaming: boolean
  sessionCount: number
  archivedCount: number
}

type WorkspaceSettingsModalProps = {
  open: boolean
  themeMode: ThemeMode
  archivedSessions: ChatSession[]
  archivedLoading: boolean
  restoringSessionId: string | null
  debugInfo: DebugInfo
  onClose: () => void
  onThemeModeChange: (mode: ThemeMode) => void
  onRestoreSession: (sessionId: string) => void
}

function DebugRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="sw-settings-debug-row">
      <Text type="secondary">{label}</Text>
      <Text code copyable={value.length > 0}>
        {value || '无'}
      </Text>
    </div>
  )
}

export function WorkspaceSettingsModal({
  open,
  themeMode,
  archivedSessions,
  archivedLoading,
  restoringSessionId,
  debugInfo,
  onClose,
  onThemeModeChange,
  onRestoreSession,
}: WorkspaceSettingsModalProps) {
  const isDark = themeMode === 'dark'

  return (
    <Modal
      title="工作台设置"
      open={open}
      onCancel={onClose}
      footer={null}
      width={680}
      destroyOnHidden
    >
      <Space direction="vertical" size={20} className="sw-settings">
        <section className="sw-settings-section">
          <div className="sw-settings-section-head">
            <div>
              <Title level={5}>外观</Title>
              <Text type="secondary">按你的测试环境切换浅色或深色界面。</Text>
            </div>
            <Switch
              checked={isDark}
              checkedChildren={<MoonOutlined aria-hidden />}
              unCheckedChildren={<SunOutlined aria-hidden />}
              aria-label="切换深色模式"
              onChange={(checked) => onThemeModeChange(checked ? 'dark' : 'light')}
            />
          </div>
          <Tag color={isDark ? 'gold' : 'default'}>
            当前：{isDark ? '深色模式' : '浅色模式'}
          </Tag>
        </section>

        <section className="sw-settings-section">
          <div className="sw-settings-section-head">
            <div>
              <Title level={5}>归档会话</Title>
              <Text type="secondary">归档只隐藏会话，不删除消息、工具调用和资产。</Text>
            </div>
            <Tag>{archivedSessions.length}</Tag>
          </div>

          <List
            loading={archivedLoading}
            dataSource={archivedSessions}
            locale={{
              emptyText: (
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description="暂无归档会话"
                />
              ),
            }}
            renderItem={(session) => (
              <List.Item
                actions={[
                  <Button
                    key="restore"
                    size="small"
                    icon={<ReloadOutlined aria-hidden />}
                    loading={restoringSessionId === session.id}
                    onClick={() => onRestoreSession(session.id)}
                  >
                    还原
                  </Button>,
                ]}
              >
                <List.Item.Meta
                  title={session.title}
                  description={`更新于 ${formatDate(session.updated_at)}`}
                />
              </List.Item>
            )}
          />
        </section>

        <section className="sw-settings-section">
          <div className="sw-settings-section-head">
            <div>
              <Title level={5}>
                <BugOutlined aria-hidden /> 调试信息
              </Title>
              <Text type="secondary">只展示定位问题常用的少量上下文。</Text>
            </div>
            <Tag icon={<ApiOutlined aria-hidden />}>local</Tag>
          </div>
          <div className="sw-settings-debug-grid">
            <DebugRow label="API 基址" value={apiBaseUrl} />
            <DebugRow label="运行模式" value={import.meta.env.MODE} />
            <DebugRow label="当前会话" value={debugInfo.activeSessionId ?? ''} />
            <DebugRow label="项目 ID" value={debugInfo.projectId ?? ''} />
            <DebugRow label="资产页签" value={debugInfo.activeAssetTab} />
            <DebugRow label="运行状态" value={debugInfo.runStatus} />
            <DebugRow label="SSE 流式" value={debugInfo.isStreaming ? 'running' : 'idle'} />
            <DebugRow label="会话数量" value={String(debugInfo.sessionCount)} />
            <DebugRow label="归档数量" value={String(debugInfo.archivedCount)} />
          </div>
          <Paragraph type="secondary" className="sw-settings-debug-note">
            更详细的请求、模型用量和工具调用信息仍保留在会话时间线与右侧资产面板中。
          </Paragraph>
        </section>
      </Space>
    </Modal>
  )
}
