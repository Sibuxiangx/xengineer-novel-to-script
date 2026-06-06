import type { BubbleProps } from '@ant-design/x'

const transparentContent: BubbleProps['styles'] = {
  content: { background: 'none', boxShadow: 'none', border: 'none', padding: 0 },
}

export const bubbleRoles: Record<string, Partial<BubbleProps>> = {
  user: {
    placement: 'end',
    variant: 'filled',
    shape: 'round',
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
  },
  tool: {
    placement: 'start',
    variant: 'borderless',
    rootClassName: 'sw-bubble-tool',
    styles: transparentContent,
  },
  confirm: {
    placement: 'start',
    variant: 'borderless',
    rootClassName: 'sw-bubble-confirm',
    styles: transparentContent,
  },
  validation: {
    placement: 'start',
    variant: 'borderless',
    rootClassName: 'sw-bubble-validation',
    styles: transparentContent,
  },
  progress: {
    placement: 'start',
    variant: 'borderless',
    rootClassName: 'sw-bubble-progress',
    styles: transparentContent,
  },
  system: {
    placement: 'start',
    variant: 'borderless',
    rootClassName: 'sw-bubble-system',
    styles: transparentContent,
  },
}
