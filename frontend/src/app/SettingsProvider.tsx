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
const STORAGE_VERSION = 1

// The sliders in SettingsPage use these too, so they always match what validation accepts.
export const SETTING_RANGES = {
  cueVolume: { min: 0, max: 100 },
  letterSpacing: { min: 0, max: 0.2 },
  wordSpacing: { min: 0, max: 0.4 },
  lineHeight: { min: 1.2, max: 2.2 },
} as const

type Parser<T> = (value: unknown) => T | undefined

const oneOf =
  <T extends string>(...options: T[]): Parser<T> =>
  (value) =>
    options.find((option) => option === value)

const bool: Parser<boolean> = (value) => {
  if (value === true || value === 'true') return true
  if (value === false || value === 'false') return false
  return undefined
}

const numberIn =
  ({ min, max }: { min: number; max: number }): Parser<number> =>
  (value) => {
    // Plain decimals only: Number() would also turn '' into 0 and '0x10' into 16
    const n = typeof value === 'string' && /^-?\d*\.?\d+$/.test(value) ? Number(value) : value
    return typeof n === 'number' && n >= min && n <= max ? n : undefined
  }

const PARSERS: { [K in keyof AppSettings]: Parser<AppSettings[K]> } = {
  animation: oneOf('full', 'reduced', 'none'),
  freezeViewport: bool,
  toneOnTake: bool,
  soundOnErrors: bool,
  cueVolume: numberIn(SETTING_RANGES.cueVolume),
  textSize: oneOf('small', 'default', 'large', 'xlarge'),
  letterSpacing: numberIn(SETTING_RANGES.letterSpacing),
  wordSpacing: numberIn(SETTING_RANGES.wordSpacing),
  lineHeight: numberIn(SETTING_RANGES.lineHeight),
  underlineLinks: bool,
}

const FIELDS = Object.keys(PARSERS) as (keyof AppSettings)[]

interface Ctx {
  settings: AppSettings
  update: (patch: Partial<AppSettings>) => void
  save: () => void
  reset: () => void
}

const SettingsContext = createContext<Ctx | null>(null)

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** Bad fields fall back to their default. `changed` means the input differs from what comes back. */
function validate(raw: unknown) {
  const input = isObject(raw) ? raw : {}
  const settings = { ...defaultSettings }
  const resetFields: string[] = isObject(raw) ? [] : [...FIELDS]
  let changed =
    !isObject(raw) || Object.keys(input).some((key) => !(FIELDS as string[]).includes(key))

  const applyField = <K extends keyof AppSettings>(key: K) => {
    const value = input[key]
    if (value === undefined) return

    const parsed = PARSERS[key](value)
    if (parsed === undefined) {
      resetFields.push(key)
      changed = true
    } else {
      settings[key] = parsed
      if (parsed !== value) changed = true
    }
  }
  FIELDS.forEach((key) => applyField(key))

  return { settings, resetFields, changed }
}

function write(settings: AppSettings) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: STORAGE_VERSION, settings }))
  } catch {
    /* storage may be unavailable — settings still apply for this session */
  }
}

function load(): AppSettings {
  let raw: string | null
  try {
    raw = localStorage.getItem(STORAGE_KEY)
  } catch {
    return defaultSettings
  }
  if (raw === null) return defaultSettings

  let saved: unknown
  try {
    saved = JSON.parse(raw)
  } catch {
    saved = null
  }

  const version = isObject(saved) ? saved.version : undefined
  // Saved by a newer build: leave its settings alone
  if (typeof version === 'number' && version > STORAGE_VERSION) return defaultSettings

  const current = version === STORAGE_VERSION
  const { settings, resetFields, changed } = validate(
    current && isObject(saved) ? saved.settings : saved,
  )
  if (resetFields.length > 0) {
    console.warn(`Saved settings were invalid, reset to defaults: ${resetFields.join(', ')}`)
  }
  if (changed || !current) write(settings)

  return settings
}

// Once per page load: StrictMode calls useState initializers twice, and load() can warn and write.
const initialSettings = load()

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<AppSettings>(initialSettings)

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
      save: () => write(validate(settings).settings),
      reset: () => {
        setSettings(defaultSettings)
        try {
          localStorage.removeItem(STORAGE_KEY)
        } catch {
          /* storage may be unavailable — defaults still apply for this session */
        }
      },
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
