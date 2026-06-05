import { useEffect, useMemo } from 'react'
import { App as AntdApp, ConfigProvider } from 'antd'
import { XProvider } from '@ant-design/x'
import { getThemeConfig } from './styles/tokens'
import { AppRouter } from './routes/AppRouter'
import { useUiPrefs } from './state/uiPrefs'

export default function App() {
  const themeMode = useUiPrefs((state) => state.themeMode)
  const themeConfig = useMemo(() => getThemeConfig(themeMode), [themeMode])

  useEffect(() => {
    document.documentElement.dataset.theme = themeMode
  }, [themeMode])

  return (
    <ConfigProvider theme={themeConfig}>
      <XProvider theme={themeConfig}>
        <AntdApp>
          <AppRouter />
        </AntdApp>
      </XProvider>
    </ConfigProvider>
  )
}
