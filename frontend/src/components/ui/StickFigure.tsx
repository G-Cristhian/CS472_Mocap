import type { Pose } from '@/types'

const POSES: Record<Pose, { head: [number, number]; paths: string[] }> = {
  stand: { head: [50, 17], paths: ['M50 26 V66', 'M30 52 L50 34 L70 52', 'M34 100 L50 66 L66 100'] },
  walk: { head: [48, 17], paths: ['M48 26 L50 64', 'M32 42 L48 34 L62 50', 'M32 100 L50 64 L68 94'] },
  run: { head: [53, 16], paths: ['M52 25 L48 62', 'M34 36 L52 33 L66 46', 'M30 98 L48 62 L66 84'] },
  lunge: { head: [50, 17], paths: ['M50 26 V62', 'M26 44 L50 36 L74 44', 'M26 100 L50 62 L74 100'] },
  serve: { head: [50, 17], paths: ['M50 26 V64', 'M66 24 L50 34 L34 48', 'M34 100 L50 64 L66 100'] },
  'arms-up': { head: [50, 17], paths: ['M50 26 V64', 'M30 24 L50 36 L70 24', 'M34 100 L50 64 L66 100'] },
}

interface Props {
  pose?: Pose
  color?: string
  headColor?: string
  size?: number
  strokeWidth?: number
  className?: string
}

/** The stick figure used as the project / recording thumbnail throughout the screens. */
export function StickFigure({
  pose = 'stand',
  color = 'currentColor',
  headColor,
  size = 96,
  strokeWidth = 5.5,
  className,
}: Props) {
  const { head, paths } = POSES[pose]
  return (
    <svg
      className={className}
      width={size}
      height={size * 1.15}
      viewBox="0 0 100 115"
      fill="none"
      aria-hidden="true"
    >
      <circle cx={head[0]} cy={head[1]} r={8} fill={headColor ?? color} />
      {paths.map((d) => (
        <path
          key={d}
          d={d}
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ))}
    </svg>
  )
}
