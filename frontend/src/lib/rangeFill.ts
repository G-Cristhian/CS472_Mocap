import type { CSSProperties } from 'react'

/** Style for a .slider range input: how far along the track the purple fill reaches. */
export function rangeFill(value: number, min: number, max: number): CSSProperties {
  return { '--fill': `${((value - min) / (max - min)) * 100}%` } as CSSProperties
}
