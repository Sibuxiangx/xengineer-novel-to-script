import { Bubble } from '@ant-design/x'
import type { BubbleItemType } from '@ant-design/x'
import { useLayoutEffect, useMemo, useRef } from 'react'
import type { UIEvent } from 'react'
import { bubbleRoles } from './bubbleRoles'
import './ChatTimeline.css'

type ChatTimelineProps = {
  items: BubbleItemType[]
}

const FOLLOW_BOTTOM_THRESHOLD = 56

function isNearBottom(container: HTMLDivElement): boolean {
  return (
    container.scrollHeight - container.scrollTop - container.clientHeight <=
    FOLLOW_BOTTOM_THRESHOLD
  )
}

export function ChatTimeline({ items }: ChatTimelineProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const shouldFollowRef = useRef(true)
  const lastFirstKeyRef = useRef<string | null>(null)
  const scrollSignal = useMemo(
    () => items.map((item) => String(item.key ?? '')).join('|'),
    [items],
  )

  function handleScroll(event: UIEvent<HTMLDivElement>) {
    shouldFollowRef.current = isNearBottom(event.currentTarget)
  }

  useLayoutEffect(() => {
    const container = scrollRef.current
    if (!container) return

    const firstKey = String(items[0]?.key ?? '')
    if (firstKey && firstKey !== lastFirstKeyRef.current) {
      lastFirstKeyRef.current = firstKey
      shouldFollowRef.current = true
    }

    const scrollToBottom = () => {
      container.scrollTop = container.scrollHeight
    }

    if (!shouldFollowRef.current) return
    scrollToBottom()
    const frame = window.requestAnimationFrame(scrollToBottom)
    return () => window.cancelAnimationFrame(frame)
  }, [items, scrollSignal])

  return (
    <div
      ref={scrollRef}
      className="sw-chat-area"
      aria-live="polite"
      aria-label="对话时间线"
      onScroll={handleScroll}
    >
      <Bubble.List
        className="sw-bubble-list"
        items={items}
        role={bubbleRoles}
      />
    </div>
  )
}
