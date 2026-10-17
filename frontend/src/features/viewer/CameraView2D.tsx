import { useEffect, useRef, useState } from 'react'

import { ApiUnreachableError, API_URL, getKeypoints, listKeypointCameras } from '@/lib/api'
import type { Keypoints2D } from '@/lib/api'

/**
 * The 2D joints every camera saw, drawn as a stick figure per camera at the
 * transport's time. This is stage 1's output before any 3D work, so it shows
 * which camera lost the performer, where a joint flickers, and how the two
 * detectors compare on the same footage.
 *
 * `time` is on the take's clock (0 at the clap); each camera's frames are
 * indexed by their own video time, so the clap time is added back per camera.
 */

interface Props {
  takeId: string
  time: number
}

/** MediaPipe's pose connections, by joint name so the order the API sends is what counts. */
const BONES: [string, string][] = [
  ['NOSE', 'LEFT_EYE_INNER'], ['LEFT_EYE_INNER', 'LEFT_EYE'], ['LEFT_EYE', 'LEFT_EYE_OUTER'], ['LEFT_EYE_OUTER', 'LEFT_EAR'],
  ['NOSE', 'RIGHT_EYE_INNER'], ['RIGHT_EYE_INNER', 'RIGHT_EYE'], ['RIGHT_EYE', 'RIGHT_EYE_OUTER'], ['RIGHT_EYE_OUTER', 'RIGHT_EAR'],
  ['MOUTH_LEFT', 'MOUTH_RIGHT'],
  ['LEFT_SHOULDER', 'RIGHT_SHOULDER'], ['LEFT_HIP', 'RIGHT_HIP'],
  ['LEFT_SHOULDER', 'LEFT_HIP'], ['RIGHT_SHOULDER', 'RIGHT_HIP'],
  ['LEFT_SHOULDER', 'LEFT_ELBOW'], ['LEFT_ELBOW', 'LEFT_WRIST'],
  ['LEFT_WRIST', 'LEFT_PINKY'], ['LEFT_WRIST', 'LEFT_INDEX'], ['LEFT_WRIST', 'LEFT_THUMB'], ['LEFT_PINKY', 'LEFT_INDEX'],
  ['RIGHT_SHOULDER', 'RIGHT_ELBOW'], ['RIGHT_ELBOW', 'RIGHT_WRIST'],
  ['RIGHT_WRIST', 'RIGHT_PINKY'], ['RIGHT_WRIST', 'RIGHT_INDEX'], ['RIGHT_WRIST', 'RIGHT_THUMB'], ['RIGHT_PINKY', 'RIGHT_INDEX'],
  ['LEFT_HIP', 'LEFT_KNEE'], ['LEFT_KNEE', 'LEFT_ANKLE'], ['LEFT_ANKLE', 'LEFT_HEEL'], ['LEFT_HEEL', 'LEFT_FOOT_INDEX'], ['LEFT_ANKLE', 'LEFT_FOOT_INDEX'],
  ['RIGHT_HIP', 'RIGHT_KNEE'], ['RIGHT_KNEE', 'RIGHT_ANKLE'], ['RIGHT_ANKLE', 'RIGHT_HEEL'], ['RIGHT_HEEL', 'RIGHT_FOOT_INDEX'], ['RIGHT_ANKLE', 'RIGHT_FOOT_INDEX'],
]

/** the same cut-off triangulation uses (config.TRIANGULATION_MIN_CONFIDENCE) */
const CONFIDENT = 0.5

/** Index of the frame whose timestamp is nearest to t (timestamps ascending). */
function frameAt(timestamps: number[], t: number): number {
  let lo = 0
  let hi = timestamps.length - 1
  if (hi < 0) return -1
  if (t <= timestamps[0]) return 0
  if (t >= timestamps[hi]) return hi
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (timestamps[mid] <= t) lo = mid
    else hi = mid
  }
  return t - timestamps[lo] <= timestamps[hi] - t ? lo : hi
}

function cssColor(el: HTMLElement, name: string, fallback: string): string {
  const v = getComputedStyle(el).getPropertyValue(name).trim()
  return v || fallback
}

function draw(canvas: HTMLCanvasElement, kp: Keypoints2D, frame: number) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const w = canvas.width
  const h = canvas.height
  const scale = w / kp.width
  ctx.clearRect(0, 0, w, h)
  ctx.fillStyle = cssColor(canvas, '--panel-2', '#1b1f24')
  ctx.fillRect(0, 0, w, h)
  if (frame < 0) return

  const index = new Map(kp.joints.map((name, i) => [name, i]))
  const points = kp.points[frame]
  const conf = kp.confidence[frame]
  const bone = cssColor(canvas, '--blue', '#5b8def')
  const joint = cssColor(canvas, '--amber', '#f0b429')

  ctx.lineCap = 'round'
  for (const [a, b] of BONES) {
    const i = index.get(a)
    const j = index.get(b)
    if (i === undefined || j === undefined) continue
    const p = points[i]
    const q = points[j]
    if (!p || !q) continue
    const sure = conf[i] >= CONFIDENT && conf[j] >= CONFIDENT
    ctx.strokeStyle = bone
    ctx.globalAlpha = sure ? 0.95 : 0.3
    ctx.lineWidth = sure ? 2 : 1
    ctx.beginPath()
    ctx.moveTo(p[0] * scale, p[1] * scale)
    ctx.lineTo(q[0] * scale, q[1] * scale)
    ctx.stroke()
  }
  ctx.globalAlpha = 1
  ctx.fillStyle = joint
  points.forEach((p, i) => {
    if (!p) return
    ctx.globalAlpha = conf[i] >= CONFIDENT ? 1 : 0.35
    ctx.beginPath()
    ctx.arc(p[0] * scale, p[1] * scale, 2.2, 0, Math.PI * 2)
    ctx.fill()
  })
  ctx.globalAlpha = 1
}

function CameraCanvas({ kp, time }: { kp: Keypoints2D; time: number }) {
  const ref = useRef<HTMLCanvasElement>(null)
  const width = 240
  const height = Math.round((width * kp.height) / kp.width)
  const frame = frameAt(kp.timestamps, time + (kp.clap_time_s ?? 0))
  const seen = frame >= 0 ? kp.points[frame].filter(Boolean).length : 0
  const mean =
    frame >= 0 && seen > 0 ? kp.confidence[frame].reduce((s, c) => s + c, 0) / kp.confidence[frame].length : 0

  useEffect(() => {
    if (ref.current) draw(ref.current, kp, frame)
  }, [kp, frame])

  return (
    <figure style={{ margin: 0, display: 'grid', gap: 6 }}>
      <canvas
        ref={ref}
        width={width}
        height={height}
        style={{ width: '100%', height: 'auto', borderRadius: 6, border: '1px solid var(--line)' }}
        aria-label={`${kp.camera_id}, frame ${frame + 1} of ${kp.timestamps.length}`}
      />
      <figcaption style={{ fontSize: 12, color: 'var(--muted)', display: 'flex', justifyContent: 'space-between' }}>
        <span className="mono">{kp.camera_id}</span>
        <span>
          {frame < 0 ? 'no frames' : seen === 0 ? 'no person' : `${seen}/33 joints, confidence ${mean.toFixed(2)}`}
        </span>
      </figcaption>
    </figure>
  )
}

export function CameraView2D({ takeId, time }: Props) {
  const [cameras, setCameras] = useState<Keypoints2D[] | null>(null)
  const [message, setMessage] = useState<string | null>('Loading the cameras…')

  useEffect(() => {
    const controller = new AbortController()
    setCameras(null)
    setMessage('Loading the cameras…')
    listKeypointCameras(takeId, controller.signal)
      .then((list) => Promise.all(list.map((c) => getKeypoints(takeId, c.camera_id, controller.signal))))
      .then((all) => {
        setCameras(all)
        setMessage(all.length ? null : 'This take has no saved 2D joints.')
      })
      .catch((e) => {
        if (controller.signal.aborted) return
        setMessage(
          e instanceof ApiUnreachableError
            ? `Can't reach the API at ${API_URL}`
            : `Couldn't load the cameras: ${e instanceof Error ? e.message : String(e)}`,
        )
      })
    return () => controller.abort()
  }, [takeId])

  if (message) return <p style={{ color: 'var(--muted-2)', fontSize: 13 }}>{message}</p>
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 14 }}>
      {cameras!.map((kp) => (
        <CameraCanvas key={kp.camera_id} kp={kp} time={time} />
      ))}
    </div>
  )
}
