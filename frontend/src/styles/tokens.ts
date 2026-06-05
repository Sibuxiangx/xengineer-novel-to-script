import { theme as antdTheme, type ThemeConfig } from 'antd'
import type { ThemeMode } from '../state/uiPrefs'

export const lightColors = {
  primary: '#1677ff',
  primaryActive: '#0958d9',
  success: '#52c41a',
  warning: '#faad14',
  danger: '#ff4d4f',
  surface: '#ffffff',
  layout: '#f5f7fb',
  border: '#edf0f5',
  textPrimary: '#1f2937',
  textSecondary: '#4b5563',
} as const

export const darkColors = {
  primary: '#c9a84c',
  primaryActive: '#e0c56c',
  success: '#4ade80',
  warning: '#fbbf24',
  danger: '#ef4444',
  surface: '#161618',
  layout: '#0c0c0e',
  border: '#2b2926',
  textPrimary: '#f2f0eb',
  textSecondary: '#b8b0a5',
} as const

export const colors = lightColors

const fontFamily =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif'

export function getThemeConfig(mode: ThemeMode): ThemeConfig {
  const palette = mode === 'dark' ? darkColors : lightColors
  return {
    algorithm:
      mode === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
    token: {
      colorPrimary: palette.primary,
      colorSuccess: palette.success,
      colorWarning: palette.warning,
      colorError: palette.danger,
      colorBgLayout: palette.layout,
      colorBgContainer: palette.surface,
      colorBorder: palette.border,
      colorTextBase: palette.textPrimary,
      borderRadius: 12,
      fontFamily,
    },
    components: {
      Layout: {
        bodyBg: palette.layout,
        siderBg: palette.surface,
        headerBg: palette.surface,
      },
      Card: {
        borderRadiusLG: 14,
      },
      Button: {
        controlOutlineWidth: 3,
      },
    },
  }
}

export const themeConfig = getThemeConfig('light')
