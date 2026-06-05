import type { BubbleProps } from '@ant-design/x'
import { Avatar } from 'antd'
import {
  BranchesOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
  UserOutlined,
} from '@ant-design/icons'

export const bubbleRoles: Record<string, Partial<BubbleProps>> = {
  user: {
    placement: 'end',
    variant: 'filled',
    shape: 'round',
    avatar: <Avatar icon={<UserOutlined aria-hidden />} />,
    rootClassName: 'sw-user-bubble',
    styles: {
      content: {
        background: 'var(--sw-user-bubble-bg)',
        border: '1px solid var(--sw-user-bubble-border)',
        boxShadow: 'var(--sw-user-bubble-shadow)',
        color: 'var(--sw-user-bubble-text)',
      },
    },
  },
  ai: {
    placement: 'start',
    variant: 'filled',
    shape: 'round',
    avatar: <Avatar icon={<RobotOutlined aria-hidden />} className="sw-brand-avatar" />,
  },
  tool: {
    placement: 'start',
    variant: 'borderless',
    avatar: <Avatar icon={<BranchesOutlined aria-hidden />} />,
  },
  confirm: {
    placement: 'start',
    variant: 'shadow',
    shape: 'default',
    avatar: <Avatar icon={<SafetyCertificateOutlined aria-hidden />} />,
  },
  validation: {
    placement: 'start',
    variant: 'shadow',
    shape: 'default',
    avatar: <Avatar icon={<SafetyCertificateOutlined aria-hidden />} />,
  },
  progress: {
    placement: 'start',
    variant: 'borderless',
    avatar: <Avatar icon={<BranchesOutlined aria-hidden />} />,
  },
  system: {
    placement: 'start',
    variant: 'borderless',
  },
}
