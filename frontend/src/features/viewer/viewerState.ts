import type { Take } from '@/lib/api'
import type { MotionSource } from '@/features/viewer/MotionViewport'

/** What the viewer shows for one recording's take: a file to play, or a message. */
export interface ViewerState {
  take?: Take
  src?: MotionSource
  message?: string
}
