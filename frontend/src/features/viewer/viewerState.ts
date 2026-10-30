import type { MotionSource } from '@/features/viewer/MotionViewport'

/** What the viewer shows for one recording's take: a file to play, or a message. */
export interface ViewerState {
  src?: MotionSource
  message?: string
}
