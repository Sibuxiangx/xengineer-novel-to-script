import { lazy, Suspense } from 'react'
import { Navigate, Route, BrowserRouter, Routes } from 'react-router-dom'
import { Spin } from 'antd'
import { RuntimeConfigGate } from '../features/config/RuntimeConfigGate'

const WorkspacePage = lazy(() => import('../pages/workspace/WorkspacePage'))

function LoadingFallback() {
  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        height: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Spin size="large">
        <div style={{ padding: 32 }}>加载工作台…</div>
      </Spin>
    </div>
  )
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <RuntimeConfigGate>
        <Suspense fallback={<LoadingFallback />}>
          <Routes>
            <Route path="/" element={<WorkspacePage />} />
            <Route path="/sessions/:sessionId" element={<WorkspacePage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </RuntimeConfigGate>
    </BrowserRouter>
  )
}
