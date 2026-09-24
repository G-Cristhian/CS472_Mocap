import type { Source } from '@/types'
import { sourceLabel } from '@/lib/data'

export function Badge({ source, title }: { source: Source; title?: string }) {
  return (
    <span className={`badge badge--${source}`} title={title}>
      {sourceLabel[source]}
    </span>
  )
}
