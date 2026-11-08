/**
 * A BVH preview: the skeleton on a floor grid, drag to rotate, wheel to zoom,
 * with a clock the transport can set and read. The pipeline writes BVH in
 * centimetres, Y up; the loader keeps the file's units, so the whole rig is
 * scaled to metres here.
 *
 * The cameras can be drawn where calibration put them (setCameras, in the same
 * metres, Y up, floor at 0 as the BVH), and every joint can be coloured per
 * frame (jointColour): a ball at the joint and the bone leading to it.
 */
import * as THREE from 'three'
import { BVHLoader } from 'three/examples/jsm/loaders/BVHLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

/** One camera to draw: where it stands, which way it looks and its picture's up, in world metres. */
export interface SceneCamera {
  id: string
  position: number[]
  forward: number[]
  up: number[]
  /** half the picture's width and height over the focal length: the frustum's shape */
  halfWidth: number
  halfHeight: number
  colour: string
  label: string
}

const NEUTRAL = new THREE.Color(0x9aa4b2)

function textSprite(text: string, colour: string): THREE.Sprite {
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')!
  const font = '600 28px system-ui, sans-serif'
  ctx.font = font
  canvas.width = Math.ceil(ctx.measureText(text).width) + 16
  canvas.height = 40
  ctx.font = font
  ctx.fillStyle = 'rgba(14,17,22,0.75)'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.fillStyle = colour
  ctx.textBaseline = 'middle'
  ctx.fillText(text, 8, 21)
  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  // a fixed size on screen, so a label 5 m away stays readable
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, depthTest: false, sizeAttenuation: false }))
  const h = 0.045
  sprite.scale.set((h * canvas.width) / canvas.height, h, 1)
  sprite.renderOrder = 10
  return sprite
}

export class BvhViewer {
  readonly duration: number = 0
  private readonly renderer: THREE.WebGLRenderer
  readonly scene = new THREE.Scene()
  private readonly camera: THREE.PerspectiveCamera
  private readonly controls: OrbitControls
  private readonly clock = new THREE.Clock()
  private mixer: THREE.AnimationMixer | null = null
  rig: THREE.Group | null = null
  private helper: THREE.SkeletonHelper | null = null
  private playing = false
  private time = 0
  private frame = 0
  private readonly observer: ResizeObserver
  private cameras = new THREE.Group()
  private joints: { bone: THREE.Bone; name: string; ball: THREE.Mesh }[] = []
  /** helper segment index -> the joint whose colour that bone takes */
  private segments: string[] = []
  onTime: (t: number) => void = () => {}
  /** the colour of a joint at time t (CSS colour), or null for the plain look */
  jointColour: ((joint: string, t: number) => string | null) | null = null

  constructor(private readonly container: HTMLElement) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true })
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    container.appendChild(this.renderer.domElement)
    this.scene.background = new THREE.Color(0x0e1116)

    this.camera = new THREE.PerspectiveCamera(45, 1, 0.05, 100)
    this.camera.position.set(2.8, 1.7, 3.6)
    this.controls = new OrbitControls(this.camera, this.renderer.domElement)
    this.controls.target.set(0, 0.9, 0)
    this.controls.enableDamping = true
    this.controls.update()

    const grid = new THREE.GridHelper(6, 12, 0x3a4250, 0x242a33)
    this.scene.add(grid)
    this.scene.add(new THREE.AxesHelper(0.5))
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x222233, 1.0))
    this.scene.add(this.cameras)

    this.observer = new ResizeObserver(() => this.resize())
    this.observer.observe(container)
    this.resize()
    this.frame = requestAnimationFrame(this.tick)
  }

  /** Replace the skeleton with the one in this BVH text. */
  load(bvhText: string): void {
    if (this.rig) this.scene.remove(this.rig)
    if (this.helper) this.scene.remove(this.helper)
    for (const j of this.joints) j.ball.removeFromParent()
    this.joints = []
    const { skeleton, clip } = new BVHLoader().parse(bvhText)
    const root = skeleton.bones[0]

    const rig = new THREE.Group()
    rig.add(root)
    // centimetres (the pipeline's BVH) if any bone offset is longer than a few units;
    // bones have no geometry, so a bounding box would be empty
    let longest = 0
    for (const bone of skeleton.bones) longest = Math.max(longest, bone.position.length())
    rig.scale.setScalar(longest > 5 ? 0.01 : 1)
    this.scene.add(rig)
    this.rig = rig

    // The helper's own matrix IS the root bone's world matrix (scale included), so it
    // must sit directly in the scene; as a child of the scaled group it would be
    // scaled twice and draw a centimetre tall.
    const helper = new THREE.SkeletonHelper(root)
    ;(helper.material as THREE.LineBasicMaterial).linewidth = 2
    this.scene.add(helper)
    this.helper = helper
    // the helper draws one segment per bone whose parent is a bone, in this order;
    // the segment takes the colour of the joint it leads to (an end site: its parent's)
    this.segments = []
    for (const bone of helper.bones) {
      if (bone.parent && (bone.parent as THREE.Bone).isBone) {
        this.segments.push(bone.name === 'ENDSITE' ? bone.parent.name : bone.name)
      }
    }
    const ballGeometry = new THREE.SphereGeometry(0.03, 12, 8)
    for (const bone of skeleton.bones) {
      if (bone.name === 'ENDSITE') continue
      const ball = new THREE.Mesh(ballGeometry, new THREE.MeshBasicMaterial({ color: NEUTRAL }))
      this.scene.add(ball)
      this.joints.push({ bone, name: bone.name, ball })
    }

    // tracks are named "<Bone>.position" / "<Bone>.quaternion"; the mixer resolves them from the root bone
    this.mixer = new THREE.AnimationMixer(root)
    this.mixer.clipAction(clip).play()
    ;(this as { duration: number }).duration = clip.duration
    this.setTime(0)
  }

  /** Draw these cameras (replacing any drawn before), and step back far enough to see them all. */
  setCameras(cameras: SceneCamera[], focus: number[] | null): void {
    for (const child of [...this.cameras.children]) child.removeFromParent()
    const v = (a: number[]) => new THREE.Vector3(a[0], a[1], a[2])
    const depth = 0.35
    for (const c of cameras) {
      const origin = v(c.position)
      const forward = v(c.forward).normalize()
      const up = v(c.up).normalize()
      const right = new THREE.Vector3().crossVectors(forward, up).normalize()
      const centre = origin.clone().addScaledVector(forward, depth)
      const corner = (sx: number, sy: number) =>
        centre.clone().addScaledVector(right, sx * c.halfWidth * depth).addScaledVector(up, sy * c.halfHeight * depth)
      const [tl, tr, br, bl] = [corner(-1, 1), corner(1, 1), corner(1, -1), corner(-1, -1)]
      const top = centre.clone().addScaledVector(up, c.halfHeight * depth * 1.5)
      const points = [origin, tl, origin, tr, origin, br, origin, bl, tl, tr, tr, br, br, bl, bl, tl, tl, top, top, tr]
      const lines = new THREE.LineSegments(
        new THREE.BufferGeometry().setFromPoints(points),
        new THREE.LineBasicMaterial({ color: new THREE.Color(c.colour) }),
      )
      this.cameras.add(lines)
      const label = textSprite(c.label, c.colour)
      label.position.copy(origin).addScaledVector(up, c.halfHeight * depth + 0.15)
      this.cameras.add(label)
    }
    if (!cameras.length) return
    const target = focus && focus.every((x) => isFinite(x)) ? v(focus) : new THREE.Vector3(0, 0.9, 0)
    let far = 2
    for (const c of cameras) far = Math.max(far, v(c.position).distanceTo(target))
    // from where the user last looked, but from a bit above, so the cameras around the performer separate
    const direction = this.camera.position.clone().sub(this.controls.target).normalize()
    direction.y = Math.max(direction.y, 0.5)
    direction.normalize()
    this.controls.target.copy(target)
    // step back until every camera is well inside the picture
    this.camera.far = Math.max(100, far * 10)
    this.camera.updateProjectionMatrix()
    const corners = cameras.map((c) => v(c.position))
    for (let d = far * 0.8, i = 0; i < 30; i++, d *= 1.08) {
      this.camera.position.copy(target).addScaledVector(direction, d)
      this.camera.lookAt(target)
      this.camera.updateMatrixWorld()
      const inside = corners.every((p) => {
        const q = p.clone().project(this.camera)
        return Math.abs(q.x) < 0.85 && q.y > -0.8 && q.y < 0.75 && q.z < 1
      })
      if (inside) break
    }
    this.controls.update()
  }

  get currentTime(): number {
    return this.time
  }

  /** Recolour the joints and bones for the current time (called every frame). */
  private paint(): void {
    const colours = new Map<string, THREE.Color>()
    for (const j of this.joints) {
      const css = this.jointColour?.(j.name, this.time) ?? null
      const colour = css ? new THREE.Color(css) : NEUTRAL
      colours.set(j.name, colour)
      j.bone.getWorldPosition(j.ball.position)
      ;(j.ball.material as THREE.MeshBasicMaterial).color.copy(colour)
    }
    const attribute = this.helper?.geometry.getAttribute('color') as THREE.BufferAttribute | undefined
    if (!attribute) return
    this.segments.forEach((name, k) => {
      const c = colours.get(name) ?? NEUTRAL
      attribute.setXYZ(2 * k, c.r, c.g, c.b)
      attribute.setXYZ(2 * k + 1, c.r, c.g, c.b)
    })
    attribute.needsUpdate = true
  }

  setTime(t: number): void {
    this.time = Math.max(0, Math.min(this.duration, t))
    this.mixer?.setTime(this.time)
  }

  play(): void {
    this.playing = true
    this.clock.getDelta()
  }

  pause(): void {
    this.playing = false
  }

  get isPlaying(): boolean {
    return this.playing
  }

  dispose(): void {
    cancelAnimationFrame(this.frame)
    this.observer.disconnect()
    this.controls.dispose()
    this.renderer.dispose()
    this.renderer.domElement.remove()
  }

  private resize(): void {
    const w = this.container.clientWidth || 1
    const h = this.container.clientHeight || 1
    this.renderer.setSize(w, h, false)
    this.renderer.domElement.style.width = '100%'
    this.renderer.domElement.style.height = '100%'
    this.camera.aspect = w / h
    this.camera.updateProjectionMatrix()
  }

  private tick = (): void => {
    const dt = this.clock.getDelta()
    if (this.playing && this.mixer && this.duration > 0) {
      this.time = (this.time + dt) % this.duration
      this.mixer.setTime(this.time)
      this.onTime(this.time)
    }
    this.controls.update()
    this.paint()
    this.renderer.render(this.scene, this.camera)
    this.frame = requestAnimationFrame(this.tick)
  }
}
