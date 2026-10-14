import { Component, useEffect, useMemo, useRef, useState } from 'react'
import type { ChangeEvent, DragEvent, ReactNode } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Grid, OrbitControls } from '@react-three/drei'
import { Color, Mesh, MeshStandardMaterial, PerspectiveCamera, Quaternion, Vector3 } from 'three'
import type { RigPart, Source } from '@/types'
import { motionBounds, parseMotion, samplePositions } from './motion'
import type { Motion } from './motion'
import './viewer.css'

export interface MotionInfo {
  name: string
  duration: number
  fps: number
  frames: number
}

interface Props {
  parts: RigPart[]
  selectedId: string
  onSelect: (partId: string) => void
  hidden: Source[]
  playing: boolean
  /** playhead in seconds; changing it from outside (scrubbing) seeks */
  time: number
  onTimeChange: (seconds: number) => void
  onMotionLoaded?: (info: MotionInfo | null) => void
  /** a take to fetch and play; changing it replaces whatever is shown */
  src?: MotionSource
  /** shown in the middle of the viewport while no motion is loaded */
  message?: string
}

export interface MotionSource {
  url: string
  /** display name; its extension (.bvh / .json) picks the parser */
  name: string
}

const SOURCE_VAR: Record<Source, string> = { suit: '--blue', ai: '--purple-soft', review: '--amber' }

/** Read a colour from the design tokens (tokens.css) so the 3D view matches the page. */
function tokenColor(name: string, fallback: string) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return new Color(value || fallback)
}

/** True if the browser can draw 3D (WebGL); some locked-down or remote browsers can't. */
function hasWebGL() {
  try {
    const canvas = document.createElement('canvas')
    return Boolean(canvas.getContext('webgl2') ?? canvas.getContext('webgl'))
  } catch {
    return false
  }
}

/** Keeps a 3D failure inside the viewport instead of taking the whole page down. */
class ViewerErrorBoundary extends Component<{ children: ReactNode }, { error: string | null }> {
  state = { error: null as string | null }
  static getDerivedStateFromError(error: unknown) {
    return { error: error instanceof Error ? error.message : String(error) }
  }
  render() {
    if (this.state.error) {
      return <div className="motionview__error" role="alert">The 3D view stopped: {this.state.error}</div>
    }
    return this.props.children
  }
}

/**
 * 3D viewport for a take: plays a .bvh (three's BVHLoader) or the pipeline's
 * out3d.json as a skeleton over a floor grid, with orbit controls. It fetches
 * `src` when given; a file opened with the button or dropped on the viewport
 * replaces whatever is shown (public/samples/sample_take.bvh is a test file).
 */
export function MotionViewport(props: Props) {
  const { onMotionLoaded, src, message } = props
  const [motion, setMotion] = useState<Motion | null>(null)
  const [error, setError] = useState<string | null>(null)
  // why `src` couldn't be shown, in plain words (shown in the middle, where it can't be missed)
  const [srcError, setSrcError] = useState<string | null>(null)
  const [loading, setLoading] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const fetching = useRef<AbortController | null>(null)

  const show = (m: Motion) => {
    setMotion(m)
    setError(null)
    setSrcError(null)
    onMotionLoaded?.({ name: m.name, duration: m.duration, fps: m.fps, frames: m.times.length })
  }

  const load = (text: string, name: string) => {
    try {
      show(parseMotion(text, name))
    } catch (e) {
      setError(`${name}: ${e instanceof Error ? e.message : String(e)}`)
    }
  }

  const stopFetching = () => {
    fetching.current?.abort()
    fetching.current = null
    setLoading(null)
  }

  // a new src (or a new message, i.e. the page picked something else) clears
  // the old motion; src is then fetched, cancelling any earlier fetch
  const srcUrl = src?.url
  const srcName = src?.name
  useEffect(() => {
    stopFetching()
    setMotion(null)
    setError(null)
    setSrcError(null)
    onMotionLoaded?.(null)
    if (!srcUrl || !srcName) return

    const controller = new AbortController()
    fetching.current = controller
    setLoading(srcName)
    fetch(srcUrl, { signal: controller.signal })
      .then(
        (r) => {
          if (r.ok) return r.text()
          throw new Error(
            r.status === 404
              ? 'The animation file is missing.'
              : `The animation file couldn't be downloaded (the server answered ${r.status}).`,
          )
        },
        () => {
          throw new Error("The animation file couldn't be downloaded (can't reach the server).")
        },
      )
      .then((text) => {
        if (controller.signal.aborted) return
        let m: Motion
        try {
          m = parseMotion(text, srcName)
        } catch (e) {
          console.error(`${srcName}:`, e)
          throw new Error("The animation file couldn't be read.")
        }
        show(m)
      })
      .catch((e) => {
        if (controller.signal.aborted) return
        setSrcError(e instanceof Error ? e.message : String(e))
      })
      .finally(() => {
        if (fetching.current === controller) {
          fetching.current = null
          setLoading(null)
        }
      })
    return () => controller.abort()
  }, [srcUrl, srcName, message])

  const openFile = (file: File | undefined) => {
    if (!file) return
    // a file picked by hand wins over a take still downloading
    stopFetching()
    file.text().then((text) => load(text, file.name))
  }

  const webgl = useMemo(hasWebGL, [])

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    openFile(e.dataTransfer.files[0])
  }

  return (
    <div
      className="motionview"
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      {webgl ? (
        <ViewerErrorBoundary>
          <Canvas
            className="motionview__canvas"
            camera={{ position: [0, 1.4, 4.5], fov: 45, near: 0.05, far: 200 }}
            aria-label="3D skeleton preview: drag to orbit, scroll to zoom, pick a joint to see where its motion came from"
          >
            <ambientLight intensity={0.7} />
            <directionalLight position={[3, 6, 4]} intensity={1.4} />
            <Grid
              infiniteGrid
              cellSize={0.25}
              sectionSize={1}
              cellColor="#2a2a35"
              sectionColor="#4a4a58"
              fadeDistance={30}
              position={[0, 0, 0]}
            />
            <OrbitControls makeDefault enableDamping />
            {motion && <Skeleton3D motion={motion} {...props} />}
          </Canvas>
        </ViewerErrorBoundary>
      ) : (
        <div className="motionview__error" role="alert">
          This browser can&apos;t show the 3D view (WebGL is turned off or not supported). Try Chrome,
          Edge or Firefox with hardware acceleration on.
        </div>
      )}

      <div className="motionview__bar">
        <span className="motionview__file">
          {motion
            ? `${motion.name} · ${motion.kind === 'bvh' ? 'BVH skeleton' : '3D joints'} · ${Math.round(motion.fps)} fps · ${motion.times.length} frames`
            : loading
              ? `Loading ${loading}…`
              : 'No motion loaded'}
        </span>
        <label className="btn btn--white btn--sm motionview__open">
          Open .bvh / .json
          <input
            type="file"
            accept=".bvh,.json"
            onChange={(e: ChangeEvent<HTMLInputElement>) => {
              openFile(e.target.files?.[0])
              e.target.value = ''
            }}
          />
        </label>
      </div>

      {!motion && !loading && srcError && (
        <div className="motionview__message" role="alert">
          {srcError}
        </div>
      )}
      {!motion && !loading && !srcError && message && <div className="motionview__message">{message}</div>}
      {error && (
        <div className="motionview__error" role="alert">
          {error}
        </div>
      )}
      {dragging && <div className="motionview__drop">Drop a .bvh or out3d.json to play it</div>}
    </div>
  )
}

const UP = new Vector3(0, 1, 0)

function Skeleton3D({ motion, parts, selectedId, onSelect, hidden, playing, time, onTimeChange }: Props & { motion: Motion }) {
  const jointRefs = useRef<(Mesh | null)[]>([])
  const boneRefs = useRef<(Mesh | null)[]>([])
  const frame = useMemo(() => new Float32Array(motion.joints.length * 3), [motion])
  const clock = useRef(0)
  const lastEmitted = useRef(0)
  const sinceEmit = useRef(0)

  // which rig part (if any) each joint belongs to
  const jointPart = useMemo(() => {
    const byJoint = new Map<string, RigPart>()
    parts.forEach((part) => part.joints.forEach((j) => byJoint.set(j, part)))
    return motion.partJoints.map((j) => (j ? byJoint.get(j) : undefined))
  }, [motion, parts])

  const colors = useMemo(
    () => ({
      suit: tokenColor(SOURCE_VAR.suit, '#5b8cff'),
      ai: tokenColor(SOURCE_VAR.ai, '#8b6dff'),
      review: tokenColor(SOURCE_VAR.review, '#f5a623'),
      selected: tokenColor('--pink', '#e31c79'),
      neutral: new Color('#8a8a99'),
      bone: new Color('#4a4a58'),
    }),
    [],
  )

  const jointMaterials = useMemo(
    () =>
      jointPart.map((part) => {
        const isSelected = part?.id === selectedId
        const material = new MeshStandardMaterial({
          color: isSelected ? colors.selected : part ? colors[part.status] : colors.neutral,
          emissive: isSelected ? colors.selected : new Color(0x000000),
          emissiveIntensity: isSelected ? 0.5 : 0,
          roughness: 0.5,
          transparent: true,
          opacity: part && hidden.includes(part.status) ? 0.22 : 1,
        })
        return material
      }),
    [jointPart, selectedId, hidden, colors],
  )
  const boneMaterial = useMemo(
    () => new MeshStandardMaterial({ color: colors.bone, roughness: 0.7 }),
    [colors],
  )
  useEffect(() => () => jointMaterials.forEach((m) => m.dispose()), [jointMaterials])
  useEffect(() => () => boneMaterial.dispose(), [boneMaterial])

  // frame the camera on the take when a new one loads
  const camera = useThree((s) => s.camera) as PerspectiveCamera
  const controls = useThree((s) => s.controls) as unknown as { target: Vector3; update: () => void } | null
  useEffect(() => {
    const { min, max } = motionBounds(motion)
    const centre = new Vector3((min[0] + max[0]) / 2, (min[1] + max[1]) / 2, (min[2] + max[2]) / 2)
    const size = Math.max(max[0] - min[0], max[1] - min[1], max[2] - min[2], 1)
    const distance = (size / 2 / Math.tan((camera.fov * Math.PI) / 360)) * 1.3
    camera.position.set(centre.x, centre.y + size * 0.15, centre.z + distance)
    camera.lookAt(centre)
    if (controls) {
      controls.target.copy(centre)
      controls.update()
    }
    clock.current = 0
  }, [motion, camera, controls])

  // outside changes to the playhead (scrubbing, switching takes) seek
  useEffect(() => {
    if (Math.abs(time - lastEmitted.current) > 1e-6) clock.current = Math.min(Math.max(time, 0), motion.duration)
  }, [time, motion])

  const a = useMemo(() => new Vector3(), [])
  const b = useMemo(() => new Vector3(), [])
  const dir = useMemo(() => new Vector3(), [])
  const quat = useMemo(() => new Quaternion(), [])

  useFrame((_, delta) => {
    if (playing && motion.duration > 0) {
      clock.current = (clock.current + delta) % motion.duration
      sinceEmit.current += delta
      // tell the page about the playhead ~10 times a second, not every frame
      if (sinceEmit.current > 0.1) {
        sinceEmit.current = 0
        lastEmitted.current = clock.current
        onTimeChange(clock.current)
      }
    }

    samplePositions(motion, clock.current, frame)
    jointRefs.current.forEach((mesh, j) => {
      if (!mesh) return
      const x = frame[j * 3]
      mesh.visible = Number.isFinite(x)
      if (mesh.visible) mesh.position.set(x, frame[j * 3 + 1], frame[j * 3 + 2])
    })
    boneRefs.current.forEach((mesh, k) => {
      if (!mesh) return
      const [i, j] = motion.bones[k]
      a.set(frame[i * 3], frame[i * 3 + 1], frame[i * 3 + 2])
      b.set(frame[j * 3], frame[j * 3 + 1], frame[j * 3 + 2])
      const length = a.distanceTo(b)
      mesh.visible = Number.isFinite(length) && length > 1e-4
      if (!mesh.visible) return
      dir.subVectors(b, a).divideScalar(length)
      mesh.position.addVectors(a, b).multiplyScalar(0.5)
      mesh.quaternion.copy(quat.setFromUnitVectors(UP, dir))
      mesh.scale.set(1, length, 1)
    })
  })

  const jointRadius = motion.kind === 'bvh' ? 0.035 : 0.025

  return (
    <group>
      {motion.bones.map((_, k) => (
        <mesh
          key={`bone-${k}`}
          ref={(m) => {
            boneRefs.current[k] = m
          }}
          material={boneMaterial}
        >
          <cylinderGeometry args={[0.018, 0.018, 1, 10]} />
        </mesh>
      ))}
      {motion.joints.map((name, j) => {
        const part = jointPart[j]
        return (
          <mesh
            key={`joint-${j}`}
            ref={(m) => {
              jointRefs.current[j] = m
            }}
            material={jointMaterials[j]}
            scale={part?.id === selectedId ? 1.6 : 1}
            onClick={(e) => {
              e.stopPropagation()
              if (part) onSelect(part.id)
            }}
            onPointerOver={(e) => {
              if (part) {
                e.stopPropagation()
                document.body.style.cursor = 'pointer'
              }
            }}
            onPointerOut={() => {
              document.body.style.cursor = ''
            }}
            name={name}
          >
            <sphereGeometry args={[jointRadius, 16, 12]} />
          </mesh>
        )
      })}
    </group>
  )
}
