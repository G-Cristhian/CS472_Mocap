import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export type TextSize = 'small' | 'default' | 'large' | 'xlarge'
export type Animation = 'full' | 'reduced' | 'none'

export interface AppSettings {
  animation: Animation
  freezeViewport: boolean
  toneOnTake: boolean
  soundOnErrors: boolean
  cueVolume: number
  textSize: TextSize
  letterSpacing: number
  wordSpacing: number
  lineHeight: number
  underlineLinks: boolean
}

export const defaultSettings: AppSettings = {
  animation: 'full',
  freezeViewport: false,
  toneOnTake: false,
  soundOnErrors: false,
  cueVolume: 70,
  textSize: 'default',
  letterSpacing: 0,
  wordSpacing: 0.05,
  lineHeight: 1.6,
  underlineLinks: false,
}

const FONT_SCALE: Record<TextSize, number> = {
  small: 0.9,
  default: 1,
  large: 1.14,
  xlarge: 1.3,
}

const STORAGE_KEY = 'hybrid-mocap.settings'

interface Ctx {
  settings: AppSettings
  update: (patch: Partial<AppSettings>) => void
  save: () => void
  reset: () => void
}

const SettingsContext = createContext<Ctx | null>(null)

function load(): AppSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? { ...defaultSettings, ...JSON.parse(raw) } : defaultSettings
  } catch {
    return defaultSettings
  }
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<AppSettings>(load)

  // Accessibility choices apply to every screen, not just the settings page.
  useEffect(() => {
    const root = document.documentElement
    root.style.setProperty('--font-scale', String(FONT_SCALE[settings.textSize]))
    root.style.setProperty('--letter-spacing', `${settings.letterSpacing}em`)
    root.style.setProperty('--word-spacing', `${settings.wordSpacing}em`)
    root.style.setProperty('--line-height', String(settings.lineHeight))
    root.dataset.motion = settings.animation
    root.dataset.underlineLinks = String(settings.underlineLinks)
  }, [settings])

  const value = useMemo<Ctx>(
    () => ({
      settings,
      update: (patch) => setSettings((s) => ({ ...s, ...patch })),
      save: () => {
        try {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
        } catch {
          /* storage may be unavailable — settings still apply for this session */
        }
      },
      reset: () => setSettings(defaultSettings),
    }),
    [settings],
  )

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>
}

export function useSettings() {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error('useSettings must be used inside <SettingsProvider>')
  return ctx
}
