import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type PointerEvent,
  type ReactNode,
} from 'react'
import clsx from 'clsx'
import './AppShell.css'

const INSPECTOR_MIN_WIDTH = 320
const INSPECTOR_MAX_WIDTH = 720
const MAIN_MIN_WIDTH = 560
const LEFT_RAIL_EXPANDED_WIDTH = 304
const LEFT_RAIL_COLLAPSED_WIDTH = 72

type AppShellProps = {
  header: ReactNode
  leftRail: ReactNode
  rightInspector: ReactNode
  children: ReactNode
  leftRailCollapsed?: boolean
  rightInspectorWidth: number
  onRightInspectorWidthChange: (width: number) => void
}

type ResizeState = {
  startX: number
  startWidth: number
}

function clampInspectorWidth(width: number, leftRailCollapsed?: boolean): number {
  const leftWidth = leftRailCollapsed ? LEFT_RAIL_COLLAPSED_WIDTH : LEFT_RAIL_EXPANDED_WIDTH
  const viewportWidth = typeof window === 'undefined' ? 1440 : window.innerWidth
  const responsiveMax = Math.max(
    INSPECTOR_MIN_WIDTH,
    Math.min(INSPECTOR_MAX_WIDTH, viewportWidth - leftWidth - MAIN_MIN_WIDTH),
  )
  return Math.min(responsiveMax, Math.max(INSPECTOR_MIN_WIDTH, Math.round(width)))
}

export function AppShell({
  header,
  leftRail,
  rightInspector,
  children,
  leftRailCollapsed,
  rightInspectorWidth,
  onRightInspectorWidthChange,
}: AppShellProps) {
  const [isResizingInspector, setIsResizingInspector] = useState(false)
  const resizeStateRef = useRef<ResizeState | null>(null)

  const clampedInspectorWidth = clampInspectorWidth(
    rightInspectorWidth,
    leftRailCollapsed,
  )

  useEffect(() => {
    if (clampedInspectorWidth !== rightInspectorWidth) {
      onRightInspectorWidthChange(clampedInspectorWidth)
    }
  }, [clampedInspectorWidth, onRightInspectorWidthChange, rightInspectorWidth])

  useEffect(() => {
    if (!isResizingInspector) return undefined

    const handlePointerMove = (event: globalThis.PointerEvent) => {
      const state = resizeStateRef.current
      if (!state) return
      const nextWidth = state.startWidth - (event.clientX - state.startX)
      onRightInspectorWidthChange(
        clampInspectorWidth(nextWidth, leftRailCollapsed),
      )
    }

    const stopResize = () => {
      resizeStateRef.current = null
      setIsResizingInspector(false)
      document.body.classList.remove('sw-shell--resizing-inspector')
    }

    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', stopResize, { once: true })
    window.addEventListener('pointercancel', stopResize, { once: true })
    return () => {
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerup', stopResize)
      window.removeEventListener('pointercancel', stopResize)
      document.body.classList.remove('sw-shell--resizing-inspector')
    }
  }, [isResizingInspector, leftRailCollapsed, onRightInspectorWidthChange])

  function handleInspectorResizeStart(event: PointerEvent<HTMLDivElement>) {
    if (event.pointerType === 'mouse' && event.button !== 0) return
    event.preventDefault()
    resizeStateRef.current = {
      startX: event.clientX,
      startWidth: clampedInspectorWidth,
    }
    setIsResizingInspector(true)
    document.body.classList.add('sw-shell--resizing-inspector')
  }

  function handleInspectorResizeKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const step = event.shiftKey ? 48 : 24
    if (event.key === 'ArrowLeft') {
      event.preventDefault()
      onRightInspectorWidthChange(
        clampInspectorWidth(clampedInspectorWidth + step, leftRailCollapsed),
      )
    } else if (event.key === 'ArrowRight') {
      event.preventDefault()
      onRightInspectorWidthChange(
        clampInspectorWidth(clampedInspectorWidth - step, leftRailCollapsed),
      )
    } else if (event.key === 'Home') {
      event.preventDefault()
      onRightInspectorWidthChange(INSPECTOR_MIN_WIDTH)
    } else if (event.key === 'End') {
      event.preventDefault()
      onRightInspectorWidthChange(
        clampInspectorWidth(INSPECTOR_MAX_WIDTH, leftRailCollapsed),
      )
    }
  }

  const shellStyle = {
    '--sw-left-rail-width': `${
      leftRailCollapsed ? LEFT_RAIL_COLLAPSED_WIDTH : LEFT_RAIL_EXPANDED_WIDTH
    }px`,
    '--sw-right-inspector-width': `${clampedInspectorWidth}px`,
  } as CSSProperties

  return (
    <>
      <a className="sw-skip-link" href="#sw-main-content">
        跳到主对话区
      </a>
      <div
        className={clsx(
          'sw-shell',
          leftRailCollapsed && 'sw-shell--rail-collapsed',
          isResizingInspector && 'sw-shell--inspector-resizing',
        )}
        style={shellStyle}
      >
        <nav className="sw-sider" aria-label="项目会话栏">
          {leftRail}
        </nav>
        <div className="sw-main">
          {header}
          <main
            id="sw-main-content"
            className="sw-content"
            tabIndex={-1}
            aria-label="Agent 对话主区域"
          >
            {children}
          </main>
        </div>
        <aside className="sw-inspector" aria-label="项目资产巡视器">
          <div
            className="sw-inspector-resizer"
            role="separator"
            aria-orientation="vertical"
            aria-label="拖动调整项目资产面板宽度"
            tabIndex={0}
            onPointerDown={handleInspectorResizeStart}
            onKeyDown={handleInspectorResizeKeyDown}
          />
          {rightInspector}
        </aside>
      </div>
    </>
  )
}
