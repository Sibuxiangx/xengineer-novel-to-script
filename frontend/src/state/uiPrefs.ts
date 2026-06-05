import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type AssetTab = 'chapters' | 'index' | 'yaml' | 'harness' | 'versions'
export type ThemeMode = 'light' | 'dark'

type UiPrefsState = {
  activeAssetTab: AssetTab
  leftRailCollapsed: boolean
  rightInspectorWidth: number
  attachmentOpen: boolean
  themeMode: ThemeMode
  setActiveAssetTab: (tab: AssetTab) => void
  setLeftRailCollapsed: (collapsed: boolean) => void
  setRightInspectorWidth: (width: number) => void
  setAttachmentOpen: (open: boolean) => void
  setThemeMode: (mode: ThemeMode) => void
}

export const useUiPrefs = create<UiPrefsState>()(
  persist(
    (set) => ({
      activeAssetTab: 'chapters',
      leftRailCollapsed: false,
      rightInspectorWidth: 408,
      attachmentOpen: false,
      themeMode: 'light',
      setActiveAssetTab: (tab) => set({ activeAssetTab: tab }),
      setLeftRailCollapsed: (collapsed) => set({ leftRailCollapsed: collapsed }),
      setRightInspectorWidth: (width) => set({ rightInspectorWidth: width }),
      setAttachmentOpen: (open) => set({ attachmentOpen: open }),
      setThemeMode: (mode) => set({ themeMode: mode }),
    }),
    {
      name: 'scriptweaver-ui-prefs',
      version: 4,
      migrate: (persisted) => ({
        ...(persisted && typeof persisted === 'object' ? persisted : {}),
        attachmentOpen: false,
        themeMode:
          persisted &&
          typeof persisted === 'object' &&
          (persisted as Partial<UiPrefsState>).themeMode === 'dark'
            ? 'dark'
            : 'light',
        rightInspectorWidth:
          persisted &&
          typeof persisted === 'object' &&
          typeof (persisted as Partial<UiPrefsState>).rightInspectorWidth === 'number'
            ? Math.min(
                720,
                Math.max(320, (persisted as Partial<UiPrefsState>).rightInspectorWidth ?? 408),
              )
            : 408,
      }),
    },
  ),
)
