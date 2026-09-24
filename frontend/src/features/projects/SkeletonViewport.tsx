import type { RigPart, Source } from '@/types'

interface Joint {
  id: string
  x: number
  y: number
  r?: number
}

const JOINTS: Joint[] = [
  { id: 'l-shoulder', x: 68, y: 84 },
  { id: 'chest', x: 100, y: 84 },
  { id: 'r-shoulder', x: 132, y: 84 },
  { id: 'l-elbow', x: 58, y: 126 },
  { id: 'r-elbow', x: 142, y: 126 },
  { id: 'l-wrist', x: 50, y: 168 },
  { id: 'r-wrist', x: 150, y: 168 },
  { id: 'pelvis', x: 100, y: 152 },
  { id: 'l-knee', x: 78, y: 204 },
  { id: 'r-knee', x: 122, y: 204 },
  { id: 'l-foot', x: 72, y: 250 },
  { id: 'r-foot', x: 128, y: 250 },
]

const BONES: [string, string][] = [
  ['l-shoulder', 'chest'],
  ['chest', 'r-shoulder'],
  ['chest', 'pelvis'],
  ['l-shoulder', 'l-elbow'],
  ['l-elbow', 'l-wrist'],
  ['r-shoulder', 'r-elbow'],
  ['r-elbow', 'r-wrist'],
  ['pelvis', 'l-knee'],
  ['l-knee', 'l-foot'],
  ['pelvis', 'r-knee'],
  ['r-knee', 'r-foot'],
]

export const SOURCE_COLOR: Record<Source, string> = {
  suit: 'var(--blue)',
  ai: 'var(--purple-soft)',
  review: 'var(--amber)',
}

interface Props {
  parts: RigPart[]
  selectedId: string
  onSelect: (partId: string) => void
  hidden: Source[]
  playing: boolean
}

export function SkeletonViewport({ parts, selectedId, onSelect, hidden, playing }: Props) {
  const jointToPart = new Map<string, RigPart>()
  parts.forEach((part) => part.joints.forEach((j) => jointToPart.set(j, part)))
  const pos = new Map(JOINTS.map((j) => [j.id, j]))

  const dimmed = (part?: RigPart) => (part && hidden.includes(part.status) ? 0.22 : 1)

  return (
    <svg
      viewBox="0 0 200 300"
      width="100%"
      height="100%"
      style={{ maxHeight: 620 }}
      role="img"
      aria-label="Skeleton preview — pick a joint to see where its motion came from"
    >
      <g className={playing ? 'skeleton skeleton--playing' : 'skeleton'}>
        {/* floor grid */}
        <g stroke="rgba(255,255,255,0.14)" strokeWidth="0.6" fill="none">
          <path d="M34 296 L74 262 H126 L166 296 Z" />
          <path d="M54 279 H146" />
          <path d="M90 262 V296 M110 262 V296" />
        </g>

        {BONES.map(([a, b]) => {
          const pa = pos.get(a)!
          const pb = pos.get(b)!
          return (
            <line
              key={`${a}-${b}`}
              x1={pa.x}
              y1={pa.y}
              x2={pb.x}
              y2={pb.y}
              stroke="#4a4a58"
              strokeWidth="7"
              strokeLinecap="round"
              opacity={dimmed(jointToPart.get(b) ?? jointToPart.get(a))}
            />
          )
        })}

        {/* head */}
        <circle
          cx="100"
          cy="42"
          r="22"
          fill="#4a4a58"
          opacity={dimmed(jointToPart.get('head'))}
          style={{ cursor: 'pointer' }}
          onClick={() => onSelect('head')}
        />
        {selectedId === 'head' && (
          <circle cx="100" cy="42" r="28" fill="none" stroke="var(--pink)" strokeWidth="1.6" />
        )}

        {JOINTS.map((joint) => {
          const part = jointToPart.get(joint.id)
          const isSelected = part?.id === selectedId
          return (
            <g key={joint.id} onClick={() => part && onSelect(part.id)} style={{ cursor: 'pointer' }}>
              {isSelected && (
                <>
                  <circle cx={joint.x} cy={joint.y} r="13" fill="none" stroke="var(--pink)" strokeWidth="1.4" />
                  <circle cx={joint.x} cy={joint.y} r="9" fill="none" stroke="var(--pink)" strokeWidth="1.4" />
                </>
              )}
              <circle
                cx={joint.x}
                cy={joint.y}
                r={joint.r ?? 5.6}
                fill={part ? SOURCE_COLOR[part.status] : '#6b6b7b'}
                opacity={dimmed(part)}
              >
                <title>{part ? `${part.name} — ${part.status}` : joint.id}</title>
              </circle>
            </g>
          )
        })}
      </g>

    </svg>
  )
}
