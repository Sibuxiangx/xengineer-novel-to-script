import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type AssetTab =
  | 'overview'
  | 'script'
  | 'chapter'
  | 'characters'
  | 'locations'
  | 'events'
  | 'validation'
  | 'versions'

export type ThemeMode = 'light' | 'dark'

const LEGACY_TAB_MAP: Record<string, AssetTab> = {
  yaml: 'script',
  index: 'characters',
  chapters: 'overview',
  harness: 'validation',
}

function normalizeTab(value: unknown): AssetTab {
  if (typeof value !== 'string') return 'overview'
  const allTabs: AssetTab[] = [
    'overview',
    'script',
    'chapter',
    'characters',
    'locations',
    'events',
    'validation',
    'versions',
  ]
  if (allTabs.includes(value as AssetTab)) return value as AssetTab
  return LEGACY_TAB_MAP[value] ?? 'overview'
}

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
      activeAssetTab: 'overview',
      leftRailCollapsed: false,
      rightInspectorWidth: 432,
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
      version: 7,
      migrate: (persisted) => ({
        ...(persisted && typeof persisted === 'object' ? persisted : {}),
        activeAssetTab: normalizeTab(
          persisted && typeof persisted === 'object'
            ? (persisted as Partial<UiPrefsState>).activeAssetTab
            : undefined,
        ),
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
                560,
                Math.max(360, (persisted as Partial<UiPrefsState>).rightInspectorWidth ?? 432),
              )
            : 432,
      }),
    },
  ),
)
