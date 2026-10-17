/**
 * A BVH preview: the skeleton on a floor grid, drag to rotate, wheel to zoom,
 * with a clock the transport can set and read. The pipeline writes BVH in
 * centimetres, Y up; the loader keeps the file's units, so the whole rig is
 * scaled to metres here.
 */
import * as THREE from 'three'
import { BVHLoader } from 'three/examples/jsm/loaders/BVHLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

export class BvhViewer {
  readonly duration: number = 0
  private readonly renderer: THREE.WebGLRenderer
  readonly scene = new THREE.Scene()
  private readonly camera: THREE.PerspectiveCamera
  private readonly controls: OrbitControls
  private readonly clock = new THREE.Clock()
  private mixer: THREE.AnimationMixer | null = null
  private action: THREE.AnimationAction | null = null
  rig: THREE.Group | null = null
  private helper: THREE.SkeletonHelper | null = null
  private playing = false
  private time = 0
  private frame = 0
  private readonly observer: ResizeObserver
  onTime: (t: number) => void = () => {}

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

    this.observer = new ResizeObserver(() => this.resize())
    this.observer.observe(container)
    this.resize()
    this.frame = requestAnimationFrame(this.tick)
  }

  /** Replace the skeleton with the one in this BVH text. */
  load(bvhText: string): void {
    if (this.rig) this.scene.remove(this.rig)
    if (this.helper) this.scene.remove(this.helper)
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

    // tracks are named "<Bone>.position" / "<Bone>.quaternion"; the mixer resolves them from the root bone
    this.mixer = new THREE.AnimationMixer(root)
    this.action = this.mixer.clipAction(clip)
    this.action.play()
    ;(this as { duration: number }).duration = clip.duration
    this.setTime(0)
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
    this.renderer.render(this.scene, this.camera)
    this.frame = requestAnimationFrame(this.tick)
  }
}
