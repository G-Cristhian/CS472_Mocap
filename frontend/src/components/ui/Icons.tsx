interface IconProps {
  size?: number
  className?: string
}

const base = (size: number) => ({
  width: size,
  height: size,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.8,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
})

export const SearchIcon = ({ size = 18 }: IconProps) => (
  <svg {...base(size)}>
    <circle cx="11" cy="11" r="7" />
    <path d="M20 20l-3.6-3.6" />
  </svg>
)

export const HelpIcon = ({ size = 22 }: IconProps) => (
  <svg {...base(size)}>
    <circle cx="12" cy="12" r="9" />
    <path d="M9.5 9.2a2.6 2.6 0 015 .9c0 1.7-2.5 2-2.5 3.6" />
    <path d="M12 17.2h.01" />
  </svg>
)

export const GearIcon = ({ size = 22 }: IconProps) => (
  <svg {...base(size)}>
    <circle cx="12" cy="12" r="3.2" />
    <path d="M19.4 14.2a1.6 1.6 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.6 1.6 0 00-1.8-.3 1.6 1.6 0 00-1 1.5v.2a2 2 0 11-4 0v-.1a1.6 1.6 0 00-1-1.5 1.6 1.6 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.6 1.6 0 00.3-1.8 1.6 1.6 0 00-1.5-1H3a2 2 0 110-4h.1a1.6 1.6 0 001.5-1 1.6 1.6 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.6 1.6 0 001.8.3H9a1.6 1.6 0 001-1.5V3a2 2 0 114 0v.1a1.6 1.6 0 001 1.5 1.6 1.6 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.6 1.6 0 00-.3 1.8V9a1.6 1.6 0 001.5 1h.2a2 2 0 110 4h-.1a1.6 1.6 0 00-1.5 1z" />
  </svg>
)

export const PlusIcon = ({ size = 18 }: IconProps) => (
  <svg {...base(size)}>
    <path d="M12 5v14M5 12h14" />
  </svg>
)

export const GridIcon = ({ size = 18 }: IconProps) => (
  <svg {...base(size)} strokeWidth={0} fill="currentColor">
    <rect x="3" y="3" width="8" height="8" rx="2" />
    <rect x="13" y="3" width="8" height="8" rx="2" />
    <rect x="3" y="13" width="8" height="8" rx="2" />
    <rect x="13" y="13" width="8" height="8" rx="2" />
  </svg>
)

export const ListIcon = ({ size = 18 }: IconProps) => (
  <svg {...base(size)} strokeWidth={2.2}>
    <path d="M4 7h16M4 12h16M4 17h16" />
  </svg>
)

export const InfoIcon = ({ size = 18 }: IconProps) => (
  <svg {...base(size)}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5M12 8h.01" />
  </svg>
)

export const AlertIcon = ({ size = 20 }: IconProps) => (
  <svg {...base(size)}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7.5v5M12 16h.01" />
  </svg>
)

export const CheckIcon = ({ size = 18 }: IconProps) => (
  <svg {...base(size)} strokeWidth={2.2}>
    <path d="M4.5 12.5l5 5 10-11" />
  </svg>
)

export const CloseIcon = ({ size = 18 }: IconProps) => (
  <svg {...base(size)} strokeWidth={2}>
    <path d="M6 6l12 12M18 6L6 18" />
  </svg>
)

export const PlayIcon = ({ size = 20 }: IconProps) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M8 5.5l11 6.5-11 6.5z" />
  </svg>
)

export const PauseIcon = ({ size = 20 }: IconProps) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <rect x="7" y="5.5" width="3.6" height="13" rx="1.2" />
    <rect x="13.4" y="5.5" width="3.6" height="13" rx="1.2" />
  </svg>
)

export const DeviceIcon = ({ size = 20 }: IconProps) => (
  <svg {...base(size)}>
    <rect x="6" y="3" width="12" height="18" rx="3" />
    <path d="M10.5 6.5h3" />
  </svg>
)

export const CalibrateIcon = ({ size = 20 }: IconProps) => (
  <svg {...base(size)}>
    <path d="M12 4l8 15H4z" />
  </svg>
)

export const LinkIcon = ({ size = 20 }: IconProps) => (
  <svg {...base(size)}>
    <path d="M10 13.8a4 4 0 006 .5l2.3-2.3a4 4 0 10-5.7-5.7L11.4 7.5" />
    <path d="M14 10.2a4 4 0 00-6-.5L5.7 12a4 4 0 105.7 5.7l1.1-1.1" />
  </svg>
)

export const AccessibilityIcon = ({ size = 20 }: IconProps) => (
  <svg {...base(size)}>
    <circle cx="12" cy="4.6" r="1.8" />
    <path d="M5 8.5h14M12 8.5v6M12 14.5l-3.5 6M12 14.5l3.5 6" />
  </svg>
)

export const LayoutIcon = ({ size = 18 }: IconProps) => (
  <svg {...base(size)} strokeWidth={0} fill="currentColor">
    <rect x="3" y="3" width="8" height="8" rx="1.6" />
    <rect x="13" y="3" width="8" height="8" rx="1.6" />
    <rect x="3" y="13" width="8" height="8" rx="1.6" />
    <rect x="13" y="13" width="8" height="8" rx="1.6" />
  </svg>
)

export const ShareIcon = ({ size = 18 }: IconProps) => (
  <svg {...base(size)}>
    <circle cx="17.5" cy="6" r="2.5" />
    <circle cx="6.5" cy="12" r="2.5" />
    <circle cx="17.5" cy="18" r="2.5" />
    <path d="M8.8 10.8l6.4-3.5M8.8 13.2l6.4 3.5" />
  </svg>
)

export const ExportIcon = ({ size = 18 }: IconProps) => (
  <svg {...base(size)}>
    <path d="M12 15V4M12 4L8.2 7.8M12 4l3.8 3.8" />
    <path d="M4.5 15v3.5a1.5 1.5 0 001.5 1.5h12a1.5 1.5 0 001.5-1.5V15" />
  </svg>
)

// MotionBoxPro mark: a play symbol whose corners are tracked joints, so playback is the motion.
// Hex colours only, so public/logo.svg and public/favicon.svg match it exactly.
export const MoreIcon = ({ size = 18 }: IconProps) => (
  <svg {...base(size)} strokeWidth={0} fill="currentColor">
    <circle cx="5" cy="12" r="2" />
    <circle cx="12" cy="12" r="2" />
    <circle cx="19" cy="12" r="2" />
  </svg>
)

export const LogoMark = ({ size = 26 }: IconProps) => (
  <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
    <defs>
      <linearGradient id="mbp-v5-bg" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
        <stop offset="0" stopColor="#6d4aff" />
        <stop offset="1" stopColor="#e31c79" />
      </linearGradient>
    </defs>
    <rect width="32" height="32" rx="9" fill="url(#mbp-v5-bg)" />
    <path d="M5 13.5H8.5M5 18.5H8.5" stroke="#fff" strokeOpacity="0.45" strokeWidth="1.6" strokeLinecap="round" />
    <path d="M12 9.5L23 16L12 22.5Z" fill="#fff" fillOpacity="0.15" stroke="#fff" strokeWidth="1.8" strokeLinejoin="round" />
    <circle cx="12" cy="9.5" r="2" fill="#fff" />
    <circle cx="23" cy="16" r="2" fill="#fff" />
    <circle cx="12" cy="22.5" r="2" fill="#fff" />
    <circle cx="16.5" cy="16" r="1.2" fill="#fff" fillOpacity="0.8" />
  </svg>
)
