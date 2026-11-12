import type { MotionSource } from '@/features/viewer/MotionViewport'

/** What the viewer shows for one recording's take: a file to play, or a message. */
export interface ViewerState {
  src?: MotionSource
  message?: string
}

/**
 * Joint marker fill colors for the 3D viewer, shared with the motion page's legend swatches.
 * Each marker has a dark rim (MARKER_RIM, 14:1 on white), which is what meets WCAG 1.4.11's 3:1,
 * so the fills can stay bright.
 */
export const JOINT_COLORS = {
  suit: '#38bdf8',
  ai: '#a78bfa',
  review: '#fbbf24',
  selected: '#f472b6',
  neutral: '#4ade80',
} as const

/** Dark rim around every joint marker and legend swatch. */
export const MARKER_RIM = '#2b2b33'
