import { Badge, Dropdown, Empty, Typography, type MenuProps } from 'antd'
import { Conversations, type ConversationItemType } from '@ant-design/x'
import { InboxOutlined, MessageOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useMemo } from 'react'
import type { ChatSession } from '../../types'
import { formatDate } from '../../lib/formatting'

const { Text } = Typography

type ConversationsPanelProps = {
  sessions: ChatSession[]
  activeSessionId: string | null
  onSelect: (sessionId: string) => void
  onArchive?: (sessionId: string) => void
}

function bucketOf(session: ChatSession): string {
  if (session.pending_confirmation_count > 0) return '待你确认'
  if (session.status === 'archived') return '已归档'
  const updatedAt = dayjs(session.updated_at)
  if (updatedAt.isValid() && dayjs().diff(updatedAt, 'minute') <= 30) {
    return '进行中'
  }
  return '最近会话'
}

export function ConversationsPanel({
  sessions,
  activeSessionId,
  onSelect,
  onArchive,
}: ConversationsPanelProps) {
  const sessionById = useMemo(
    () => new Map(sessions.map((session) => [session.id, session])),
    [sessions],
  )

  function buildSessionMenu(session: ChatSession): MenuProps {
    return {
      items: [
        {
          key: 'archive',
          icon: <InboxOutlined aria-hidden />,
          label: '归档会话',
        },
      ],
      onClick: ({ key, domEvent }) => {
        domEvent.stopPropagation()
        if (key === 'archive') {
          onArchive?.(session.id)
        }
      },
    }
  }

  if (sessions.length === 0) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description="还没有会话，点上方按钮新建一个"
      />
    )
  }

  const items: ConversationItemType[] = sessions.map((session) => ({
    key: session.id,
    label: (
      <Dropdown
        menu={buildSessionMenu(session)}
        trigger={onArchive ? ['contextMenu'] : []}
        destroyOnHidden
      >
        <span className="sw-conversation-context">
          <span className="sw-conversation-label">
            <Text ellipsis>{session.title}</Text>
            <Text type="secondary" className="sw-conversation-meta">
              {formatDate(session.updated_at)}
            </Text>
          </span>
        </span>
      </Dropdown>
    ),
    icon:
      session.pending_confirmation_count > 0 ? (
        <Badge dot offset={[-2, 2]}>
          <MessageOutlined aria-hidden />
        </Badge>
      ) : (
        <MessageOutlined aria-hidden />
      ),
    group: bucketOf(session),
  }))

  return (
    <Conversations
      items={items}
      activeKey={activeSessionId ?? undefined}
      onActiveChange={(key) => onSelect(String(key))}
      menu={(conversation) => {
        const session = sessionById.get(String(conversation.key))
        return session && onArchive ? buildSessionMenu(session) : undefined
      }}
      groupable={{
        label: (group: string) => <Text type="secondary">{group}</Text>,
      }}
    />
  )
}
