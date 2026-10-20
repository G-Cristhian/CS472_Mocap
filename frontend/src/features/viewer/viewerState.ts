import { takeFileUrl, type Take } from '@/lib/api'
import type { MotionSource } from '@/features/viewer/MotionViewport'

/** What the viewer shows for one recording's take: a file to play, or a message. */
export interface ViewerState {
  take?: Take
  src?: MotionSource
  message?: string
}

export function viewerStateFor(take: Take): ViewerState {
  switch (take.status) {
    case 'queued':
      return { take, message: 'Queued' }
    case 'running':
      return { take, message: take.stage ? `Processing: ${take.stage}…` : 'Processing…' }
    case 'failed':
      return { take, message: take.error ?? 'Processing failed' }
    case 'done': {
      // parseMotion picks the parser from the extension, so the name must end in .bvh
      const name = `${take.name ?? take.id}.bvh`
      // Loads the BVH (17-joint skeleton). Consider out3d.json later: all 33 raw joints, and it shows where tracking dropped out.
      return { take, src: { url: takeFileUrl(take.id, 'out3d.bvh'), name } }
    }
  }
}
