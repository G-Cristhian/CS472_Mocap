import * as THREE from './lib/three.module.js';
import { OrbitControls } from './lib/OrbitControls.js';

/* ==========================================================================
   State & Configuration
   ========================================================================== */

const WS_PORT = 8000;
const WS_URL = `ws://127.0.0.1:${WS_PORT}/ws`;

let socket = null;
let reconnectTimer = null;
let isConnected = false;

// MediaPipe connections from server or fallback
let poseConnections = [
  // Face
  [0, 1], [1, 2], [2, 3], [3, 7], [0, 4], [4, 5], [5, 6], [6, 8], [9, 10],
  // Torso
  [11, 12], [11, 23], [12, 24], [23, 24],
  // Left arm
  [11, 13], [13, 15], [15, 17], [15, 19], [15, 21], [17, 19],
  // Right arm
  [12, 14], [14, 16], [16, 18], [16, 20], [16, 22], [18, 20],
  // Left leg
  [23, 25], [25, 27], [27, 29], [27, 31], [29, 31],
  // Right leg
  [24, 26], [26, 28], [28, 30], [28, 32], [30, 32]
];

const cameraCards = new Map(); // cam_id -> { element, img, canvas, ctx, showOverlay }
let globalShowOverlays = true;
let availableDevices = [];

// Calibration & T-Pose state
let activeCalibration = null;
let lastTPoseState = 'idle';

// Telemetry
let frameCounter = 0;
let lastFpsTime = performance.now();

/* ==========================================================================
   DOM References
   ========================================================================== */

const brandEngineBadge = document.getElementById('brand-engine-badge');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const activeCamsCount = document.getElementById('active-cams-count');
const poseSourceLabel = document.getElementById('pose-source-label');
const globalFpsLabel = document.getElementById('global-fps');
const viewportSourceBadge = document.getElementById('viewport-source-badge');
const jointCountLabel = document.getElementById('joint-count-label');
const filterStatusLabel = document.getElementById('filter-status-label');

// T-Pose widget
const tposeWidget = document.getElementById('tpose-widget');
const tposeRingFill = document.getElementById('tpose-ring-fill');
const tposeStatusText = document.getElementById('tpose-status-text');
const btnResetTpose = document.getElementById('btn-reset-tpose');

// Quick engine switch buttons
const btnQuickGpu = document.getElementById('btn-quick-gpu');
const btnQuickCpu = document.getElementById('btn-quick-cpu');

// Recenter view button
const btnRecenterView = document.getElementById('btn-recenter-view');

// T-Pose Guidance Overlay Banner
const tposeGuideBanner = document.getElementById('tpose-guide-banner');
const tposeGuideIcon = document.getElementById('tpose-guide-icon');
const tposeGuideTitle = document.getElementById('tpose-guide-title');
const tposeGuideSub = document.getElementById('tpose-guide-sub');
const tposeGuideBar = document.getElementById('tpose-guide-bar');

// Engine Switching Overlay
const engineSwitchingOverlay = document.getElementById('engine-switching-overlay');
const switchingTitle = document.getElementById('switching-title');
const switchingSub = document.getElementById('switching-sub');

const cameraGrid = document.getElementById('camera-grid');
const emptyState = document.getElementById('empty-state');
const detectedQuickList = document.getElementById('detected-quick-list');

// Buttons
const btnAddCamera = document.getElementById('btn-add-camera');
const btnEmptyAdd = document.getElementById('btn-empty-add');
const btnSettings = document.getElementById('btn-settings');
const btnToggleAllOverlays = document.getElementById('btn-toggle-all-overlays');
const btnRescanCameras = document.getElementById('btn-rescan-cameras');

// Recording & Takes Controls
const btnRecord = document.getElementById('btn-record');
const btnRecordText = document.getElementById('btn-record-text');
const recordingPill = document.getElementById('recording-pill');
const recTimer = document.getElementById('rec-timer');
const recFrames = document.getElementById('rec-frames');
const btnTakes = document.getElementById('btn-takes');

const modalTakes = document.getElementById('modal-takes');
const modalCloseTakes = document.getElementById('modal-close-takes');
const btnCloseTakes = document.getElementById('btn-close-takes');
const takesListContainer = document.getElementById('takes-list-container');
const btnOpenRecordingsFolder = document.getElementById('btn-open-recordings-folder');

const modalProcessingResult = document.getElementById('modal-processing-result');
const modalCloseProc = document.getElementById('modal-close-proc');
const btnCloseProc = document.getElementById('btn-close-proc');
const procModalTitle = document.getElementById('proc-modal-title');
const procModalBody = document.getElementById('proc-modal-body');

const settingHeight = document.getElementById('setting-height');
const settingSmoother = document.getElementById('setting-smoother');
const settingAutoProcess = document.getElementById('setting-auto-process');

let isRecording = false;
let currentTakeId = null;
let recordingDuration = 0;

// View presets
const btnViewFront = document.getElementById('btn-view-front');
const btnViewSide = document.getElementById('btn-view-side');
const btnViewTop = document.getElementById('btn-view-top');
const btnViewReset = document.getElementById('btn-view-reset');

// Viewport toggles
const chkGlobalRoot = document.getElementById('chk-global-root');
const chkGrid = document.getElementById('chk-grid');
const chkAxes = document.getElementById('chk-axes');
const chkFilter = document.getElementById('chk-filter');
const selectFilterMode = document.getElementById('select-filter-mode');

// Modals
const modalAddCamera = document.getElementById('modal-add-camera');
const modalCloseAdd = document.getElementById('modal-close-add');
const btnCancelAdd = document.getElementById('btn-cancel-add');
const btnConfirmAdd = document.getElementById('btn-confirm-add');
const localDeviceList = document.getElementById('local-device-list');
const customCamIndex = document.getElementById('custom-cam-index');
const networkUrlInput = document.getElementById('network-url');
const networkNameInput = document.getElementById('network-name');

const modalSettings = document.getElementById('modal-settings');
const modalCloseSettings = document.getElementById('modal-close-settings');
const btnCloseSettings = document.getElementById('btn-close-settings');
const calPathInput = document.getElementById('cal-path-input');
const btnBrowseCal = document.getElementById('btn-browse-cal');
const btnLoadCal = document.getElementById('btn-load-cal');
const calStatusMsg = document.getElementById('cal-status-msg');

const selectModelEngine = document.getElementById('select-model-engine');
const selectEngineDevice = document.getElementById('select-engine-device');
const selectModelVariant = document.getElementById('select-model-variant');
const btnApplyEngine = document.getElementById('btn-apply-engine');
const btnForceTpose = document.getElementById('btn-force-tpose');
const btnResetTposeSettings = document.getElementById('btn-reset-tpose-settings');
const tposeCalInfo = document.getElementById('tpose-cal-info');

/* ==========================================================================
   Audio Synthesizer Chime
   ========================================================================== */

function playCalibrationChime() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
    osc.frequency.exponentialRampToValueAtTime(880.0, ctx.currentTime + 0.15); // A5
    gain.gain.setValueAtTime(0.12, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.35);
  } catch (e) {
    // Audio context may require user interaction
  }
}

/* ==========================================================================
   Three.js 3D Viewport Setup
   ========================================================================== */

const threeContainer = document.getElementById('three-container');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0d14);

const camera = new THREE.PerspectiveCamera(45, 1, 0.05, 100);
camera.position.set(2.0, 1.4, 2.6);

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
threeContainer.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0.9, 0);
controls.enableDamping = true;
controls.dampingFactor = 0.05;
controls.update();

function recenter3DView() {
  controls.target.set(0, 0.9, 0);
  camera.position.set(0, 1.2, 2.5);
  controls.update();
  sendWSCommand('set_root_motion', { mode: chkGlobalRoot && chkGlobalRoot.checked ? 'global' : 'root_locked' });
}

async function requestSwitchEngine(engineType, device = 'auto', variant = null) {
  const chosenVariant = variant || (engineType === 'rtmpose' ? 'balanced' : 'full');
  const chosenDevice = device || (engineType === 'rtmpose' ? 'dml' : 'cpu');

  if (engineSwitchingOverlay && switchingTitle && switchingSub) {
    switchingTitle.textContent = engineType === 'rtmpose'
      ? '⚡ Switching to GPU Tracking (RTMPose)...'
      : '💻 Switching to CPU Tracking (MediaPipe)...';
    switchingSub.textContent = engineType === 'rtmpose'
      ? 'Initializing DirectML execution provider on your GPU...'
      : 'Loading CPU MediaPipe Pose Landmarker...';
    engineSwitchingOverlay.style.display = 'flex';
  }

  if (btnQuickGpu) btnQuickGpu.classList.toggle('active', engineType === 'rtmpose');
  if (btnQuickCpu) btnQuickCpu.classList.toggle('active', engineType === 'mediapipe');
  if (selectModelEngine) selectModelEngine.value = engineType;
  if (selectEngineDevice) selectEngineDevice.value = chosenDevice;

  sendWSCommand('set_model_engine', {
    model_type: engineType,
    device: chosenDevice,
    variant: chosenVariant,
  });

  try {
    const res = await fetch(`http://127.0.0.1:${WS_PORT}/api/model/engine`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model_type: engineType,
        device: chosenDevice,
        model_variant: chosenVariant,
      })
    });
    if (res.ok) {
      setTimeout(() => {
        if (engineSwitchingOverlay) engineSwitchingOverlay.style.display = 'none';
      }, 400);
    }
  } catch (e) {
    console.warn('REST set_model_engine error:', e);
  }
}

// Grid and Lights
const gridHelper = new THREE.GridHelper(5, 10, 0x00d2ff, 0x1e283a);
gridHelper.position.y = 0;
scene.add(gridHelper);

const axesHelper = new THREE.AxesHelper(0.4);
axesHelper.position.set(-1.8, 0.01, -1.8);
scene.add(axesHelper);

const hemiLight = new THREE.HemisphereLight(0xffffff, 0x334155, 1.2);
hemiLight.position.set(0, 10, 0);
scene.add(hemiLight);

const dirLight = new THREE.DirectionalLight(0x00d2ff, 0.8);
dirLight.position.set(3, 8, 4);
scene.add(dirLight);

// Skeleton 3D Objects
const jointMeshes = [];
const boneMeshes = [];
const jointMaterial = new THREE.MeshStandardMaterial({
  color: 0x00d2ff,
  roughness: 0.3,
  metalness: 0.8,
  emissive: 0x004466,
});
const boneMaterial = new THREE.MeshStandardMaterial({
  color: 0x3a82f6,
  roughness: 0.4,
  metalness: 0.5,
});

// Create 33 Joint Spheres
const jointGeo = new THREE.SphereGeometry(0.022, 16, 16);
for (let i = 0; i < 33; i++) {
  const mesh = new THREE.Mesh(jointGeo, jointMaterial);
  mesh.visible = false;
  scene.add(mesh);
  jointMeshes.push(mesh);
}

// Create Bone Cylinders
const boneGeo = new THREE.CylinderGeometry(0.01, 0.01, 1, 12);
boneGeo.translate(0, 0.5, 0);
boneGeo.rotateX(Math.PI / 2);

function ensureBoneMeshes(count) {
  while (boneMeshes.length < count) {
    const mesh = new THREE.Mesh(boneGeo, boneMaterial);
    mesh.visible = false;
    scene.add(mesh);
    boneMeshes.push(mesh);
  }
}
ensureBoneMeshes(poseConnections.length);

function resizeRenderer() {
  const w = threeContainer.clientWidth || 1;
  const h = threeContainer.clientHeight || 1;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}

window.addEventListener('resize', resizeRenderer);
const resizeObserver = new ResizeObserver(() => resizeRenderer());
resizeObserver.observe(threeContainer);
resizeRenderer();

// Render loop
function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
animate();

/* ==========================================================================
   3D Skeleton Update
   ========================================================================== */

function update3DSkeleton(pose3DData) {
  if (!pose3DData || !pose3DData.joints || pose3DData.joints.length === 0) {
    jointMeshes.forEach(m => m.visible = false);
    boneMeshes.forEach(m => m.visible = false);
    viewportSourceBadge.textContent = 'Awaiting Pose';
    jointCountLabel.textContent = '0 Joints Tracked';
    return;
  }

  const joints = pose3DData.joints;
  const source = pose3DData.source || 'Pose Tracker';
  viewportSourceBadge.textContent = source;
  poseSourceLabel.textContent = source.includes('triangulated') ? 'Triangulated' : (source.includes('rtm') ? 'RTMPose' : 'MediaPipe');

  let visibleCount = 0;
  const positions = new Map(); // index -> THREE.Vector3

  const isGlobalMode = chkGlobalRoot ? chkGlobalRoot.checked : true;
  let groundOffset = 0;

  if (source.includes('triangulated')) {
    groundOffset = 0;
  } else if (isGlobalMode && activeCalibration && Number.isFinite(activeCalibration.floor_y)) {
    // Use calibrated static floor height
    groundOffset = -activeCalibration.floor_y;
  } else if (!isGlobalMode) {
    // Center pelvis at origin for in-place rotational inspection
    let hipX = 0, hipZ = 0, hipCount = 0;
    for (const j of joints) {
      if ((j.name === 'LEFT_HIP' || j.name === 'RIGHT_HIP') && j.visibility >= 0.3) {
        hipX += j.x;
        hipZ += j.z;
        hipCount++;
      }
    }
    const centerOffsetX = hipCount > 0 ? -(hipX / hipCount) : 0;
    const centerOffsetZ = hipCount > 0 ? -(hipZ / hipCount) : 0;

    let minY = Infinity;
    for (const j of joints) {
      if (j.visibility >= 0.3) minY = Math.min(minY, j.y);
    }
    groundOffset = Number.isFinite(minY) ? -minY : 0;

    for (let i = 0; i < joints.length && i < jointMeshes.length; i++) {
      const j = joints[i];
      const mesh = jointMeshes[i];

      if (j.visibility >= 0.3) {
        const pos = new THREE.Vector3(j.x + centerOffsetX, j.y + groundOffset, j.z + centerOffsetZ);
        mesh.position.copy(pos);
        mesh.visible = true;
        positions.set(i, pos);
        visibleCount++;
      } else {
        mesh.visible = false;
      }
    }
  } else {
    // Dynamic floor offset before T-pose calibration
    let minY = Infinity;
    for (const j of joints) {
      if (j.visibility >= 0.3) minY = Math.min(minY, j.y);
    }
    groundOffset = Number.isFinite(minY) ? -minY : 0;
  }

  if (isGlobalMode) {
    for (let i = 0; i < joints.length && i < jointMeshes.length; i++) {
      const j = joints[i];
      const mesh = jointMeshes[i];

      if (j.visibility >= 0.3) {
        const pos = new THREE.Vector3(j.x, j.y + groundOffset, j.z);
        mesh.position.copy(pos);
        mesh.visible = true;
        positions.set(i, pos);
        visibleCount++;
      } else {
        mesh.visible = false;
      }
    }
  }

  jointCountLabel.textContent = `${visibleCount} Joints Tracked`;

  // Update Bones
  ensureBoneMeshes(poseConnections.length);
  for (let b = 0; b < poseConnections.length; b++) {
    const [startIdx, endIdx] = poseConnections[b];
    const bone = boneMeshes[b];

    if (positions.has(startIdx) && positions.has(endIdx)) {
      const p1 = positions.get(startIdx);
      const p2 = positions.get(endIdx);
      const dist = p1.distanceTo(p2);

      if (dist > 0.001) {
        bone.position.copy(p1);
        bone.lookAt(p2);
        bone.scale.set(1, 1, dist);
        bone.visible = true;
        continue;
      }
    }
    bone.visible = false;
  }
}

/* ==========================================================================
   T-Pose Auto-Calibration Widget Update
   ========================================================================== */

function updateTPoseWidget(tpose) {
  if (!tpose || !tposeWidget) return;
  const state = tpose.state || 'idle';
  const progress = tpose.progress || 0.0;

  // Circumference of r=8 is 2 * PI * 8 = 50.265
  const strokeOffset = 50.265 * (1.0 - progress);
  if (tposeRingFill) {
    tposeRingFill.style.strokeDashoffset = strokeOffset;
  }

  tposeWidget.classList.remove('holding', 'calibrated');
  if (tposeGuideBanner) {
    tposeGuideBanner.classList.remove('holding', 'calibrated');
  }

  if (state === 'holding') {
    tposeWidget.classList.add('holding');
    tposeStatusText.textContent = `Hold T-Pose (${Math.round(progress * 100)}%)`;

    if (tposeGuideBanner) {
      tposeGuideBanner.classList.add('holding');
      if (tposeGuideIcon) tposeGuideIcon.textContent = '⏱️';
      if (tposeGuideTitle) tposeGuideTitle.textContent = `Holding T-Pose (${Math.round(progress * 100)}%)`;
      if (tposeGuideSub) tposeGuideSub.textContent = 'Hold steady for 1-2s to lock scale & reposition to origin';
      if (tposeGuideBar) tposeGuideBar.style.width = `${Math.round(progress * 100)}%`;
    }
  } else if (state === 'calibrated') {
    tposeWidget.classList.add('calibrated');
    tposeStatusText.textContent = 'Calibrated ✓';

    if (tposeGuideBanner) {
      tposeGuideBanner.classList.add('calibrated');
      if (tposeGuideIcon) tposeGuideIcon.textContent = '✨';
      if (tposeGuideTitle) tposeGuideTitle.textContent = 'T-Pose Calibrated!';
      const floorStr = tpose.calibration ? tpose.calibration.floor_y : 0;
      if (tposeGuideSub) tposeGuideSub.textContent = `Rigid bones locked • Model positioned at origin (Floor Y=${floorStr}m)`;
      if (tposeGuideBar) tposeGuideBar.style.width = '100%';
    }
  } else {
    tposeStatusText.textContent = activeCalibration ? 'Calibrated ✓' : 'T-Pose: Idle';
    if (tposeGuideBanner) {
      if (activeCalibration) {
        if (tposeGuideIcon) tposeGuideIcon.textContent = '✓';
        if (tposeGuideTitle) tposeGuideTitle.textContent = 'T-Pose Calibrated (Ready)';
        if (tposeGuideSub) tposeGuideSub.textContent = 'Floor & rigid bones locked • Hold T-Pose to recalibrate';
        if (tposeGuideBar) tposeGuideBar.style.width = '100%';
      } else {
        if (tposeGuideIcon) tposeGuideIcon.textContent = '🧍';
        if (tposeGuideTitle) tposeGuideTitle.textContent = 'Stand in T-Pose to Calibrate';
        if (tposeGuideSub) tposeGuideSub.textContent = 'Arms horizontal • Hold 1-2s to calibrate';
        if (tposeGuideBar) tposeGuideBar.style.width = '0%';
      }
    }
  }

  if (tpose.just_calibrated) {
    showToast('✨ T-Pose Calibrated! Model repositioned to origin.', 'success');
    playCalibrationChime();
  }

  lastTPoseState = state;

  if (tpose.calibration) {
    activeCalibration = tpose.calibration;
    updateCalibrationDetailsUI(tpose.calibration);
  }
}

function updateCalibrationDetailsUI(cal) {
  if (!tposeCalInfo || !cal) return;
  const bones = cal.bone_lengths ? Object.keys(cal.bone_lengths).length : 0;
  tposeCalInfo.innerHTML = `
    <strong>Status:</strong> Calibrated (${cal.samples_count || 30} samples)<br/>
    <strong>Floor Height:</strong> ${cal.floor_y || 0}m | <strong>Scale:</strong> ${cal.scale_factor || 1.0}x<br/>
    <strong>Wingspan:</strong> ${cal.wingspan_m || 0}m | <strong>Rigid Bones:</strong> ${bones} segments locked
  `;
}

/* ==========================================================================
   2D Canvas Skeleton Rendering
   ========================================================================== */

function draw2DSkeleton(ctx, landmarks2d, width, height) {
  ctx.clearRect(0, 0, width, height);
  if (!landmarks2d || landmarks2d.length === 0) return;

  const points = new Map();
  for (const lm of landmarks2d) {
    if (lm.visibility >= 0.3) {
      const px = lm.x * width;
      const py = lm.y * height;
      points.set(lm.index, { x: px, y: py, vis: lm.visibility });
    }
  }

  // Draw connecting bones
  for (const [startIdx, endIdx] of poseConnections) {
    if (points.has(startIdx) && points.has(endIdx)) {
      const p1 = points.get(startIdx);
      const p2 = points.get(endIdx);

      let strokeStyle = '#00d2ff';
      if ([11, 13, 15, 23, 25, 27].includes(startIdx)) {
        strokeStyle = '#8b5cf6';
      } else if ([12, 14, 16, 24, 26, 28].includes(startIdx)) {
        strokeStyle = '#f59e0b';
      } else if ([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].includes(startIdx)) {
        strokeStyle = '#10b981';
      }

      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.lineWidth = 3;
      ctx.strokeStyle = strokeStyle;
      ctx.lineCap = 'round';
      ctx.shadowColor = strokeStyle;
      ctx.shadowBlur = 4;
      ctx.stroke();
    }
  }
  ctx.shadowBlur = 0;

  // Draw joint dots
  for (const [idx, p] of points.entries()) {
    ctx.beginPath();
    ctx.arc(p.x, p.y, 4.5, 0, Math.PI * 2);
    ctx.fillStyle = '#ffffff';
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#00d2ff';
    ctx.stroke();
  }
}

/* ==========================================================================
   Multi-Camera Card Management
   ========================================================================== */

function getOrCreateCameraCard(camId, cameraData) {
  if (cameraCards.has(camId)) {
    return cameraCards.get(camId);
  }

  emptyState.style.display = 'none';

  const card = document.createElement('div');
  card.className = 'camera-card';
  card.id = `cam-card-${camId}`;

  card.innerHTML = `
    <div class="camera-card-header">
      <div class="camera-meta">
        <span class="camera-title">${cameraData.name || camId}</span>
        <span class="camera-source-tag">${cameraData.source}</span>
      </div>
      <div class="camera-controls">
        <span class="camera-fps-badge" id="fps-${camId}">-- FPS</span>
        <button class="btn-card-action btn-toggle-overlay" title="Toggle 2D skeleton overlay">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
            <circle cx="12" cy="12" r="3"></circle>
          </svg>
        </button>
        <button class="btn-card-action danger btn-remove-cam" title="Remove camera">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
    </div>
    <div class="camera-media-wrap">
      <div class="camera-status-overlay" id="status-overlay-${camId}">
        <div class="loading-spinner" style="color: var(--accent-cyan); font-size: 13px;">Connecting camera...</div>
      </div>
      <img class="camera-media-img" id="img-${camId}" alt="Camera Feed" style="display: none;" />
      <canvas class="camera-overlay-canvas" id="canvas-${camId}"></canvas>
    </div>
    <div class="camera-card-footer">
      <span class="camera-res" id="res-${camId}">--</span>
      <span class="camera-latency" id="lat-${camId}">-- ms</span>
    </div>
  `;

  cameraGrid.appendChild(card);

  const img = card.querySelector(`#img-${camId}`);
  const statusOverlay = card.querySelector(`#status-overlay-${camId}`);
  const canvas = card.querySelector(`#canvas-${camId}`);
  const ctx = canvas.getContext('2d');
  const fpsBadge = card.querySelector(`#fps-${camId}`);
  const resLabel = card.querySelector(`#res-${camId}`);
  const latLabel = card.querySelector(`#lat-${camId}`);
  const btnToggle = card.querySelector('.btn-toggle-overlay');
  const btnRemove = card.querySelector('.btn-remove-cam');

  let showOverlay = true;

  btnToggle.addEventListener('click', () => {
    showOverlay = !showOverlay;
    canvas.style.display = showOverlay ? 'block' : 'none';
    btnToggle.style.opacity = showOverlay ? '1' : '0.4';
  });

  btnRemove.addEventListener('click', () => {
    if (confirm(`Remove camera ${cameraData.name || camId}?`)) {
      sendWSCommand('remove_camera', { cam_id: camId });
    }
  });

  const cardObj = {
    element: card,
    img,
    statusOverlay,
    canvas,
    ctx,
    fpsBadge,
    resLabel,
    latLabel,
    get showOverlay() { return showOverlay && globalShowOverlays; }
  };

  cameraCards.set(camId, cardObj);
  updateActiveCamerasCount();
  return cardObj;
}

function removeCameraCard(camId) {
  if (cameraCards.has(camId)) {
    const cardObj = cameraCards.get(camId);
    cardObj.element.remove();
    cameraCards.delete(camId);
  }
  updateActiveCamerasCount();
  if (cameraCards.size === 0) {
    emptyState.style.display = 'flex';
  }
}

function updateActiveCamerasCount() {
  activeCamsCount.textContent = cameraCards.size;
}

/* ==========================================================================
   WebSocket Connection & Updates
   ========================================================================== */

function connectWebSocket() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }

  statusText.textContent = 'Connecting...';
  statusDot.className = 'status-dot dot-offline';

  socket = new WebSocket(WS_URL);

  socket.onopen = () => {
    isConnected = true;
    statusText.textContent = 'Connected';
    statusDot.className = 'status-dot dot-online';
    showToast('Connected to Live Stream Engine', 'success');
    sendWSCommand('list_devices');
  };

  socket.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      handleServerMessage(msg);
    } catch (e) {
      console.error('Error parsing WS message:', e);
    }
  };

  socket.onclose = () => {
    isConnected = false;
    statusText.textContent = 'Disconnected';
    statusDot.className = 'status-dot dot-offline';
    for (const camId of Array.from(cameraCards.keys())) {
      removeCameraCard(camId);
    }
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connectWebSocket, 2000);
  };

  socket.onerror = (err) => {
    console.warn('WebSocket error:', err);
  };
}

function sendWSCommand(action, payload = {}) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ action, ...payload }));
  } else {
    console.warn('Cannot send command, WS not open:', action);
  }
}

function handleServerMessage(msg) {
  switch (msg.type) {
    case 'init':
      if (msg.connections) poseConnections = msg.connections;
      ensureBoneMeshes(poseConnections.length);
      if (msg.devices) syncVerifiedDevices(msg.devices, false);
      if (msg.model_type && selectModelEngine) selectModelEngine.value = msg.model_type;
      if (msg.device && selectEngineDevice) selectEngineDevice.value = msg.device;
      if (msg.model_variant && selectModelVariant) selectModelVariant.value = msg.model_variant;
      if (msg.root_motion_mode && chkGlobalRoot) chkGlobalRoot.checked = (msg.root_motion_mode === 'global');
      if (msg.tpose) updateTPoseWidget(msg.tpose);
      if (msg.model_type) {
        const isRtm = msg.model_type.toLowerCase().includes('rtm');
        if (btnQuickGpu) btnQuickGpu.classList.toggle('active', isRtm);
        if (btnQuickCpu) btnQuickCpu.classList.toggle('active', !isRtm);
        if (brandEngineBadge) {
          brandEngineBadge.textContent = `${msg.model_type.toUpperCase()} (${msg.device || 'auto'})`;
        }
      }
      break;

    case 'engine_loading':
      if (engineSwitchingOverlay && switchingTitle && switchingSub) {
        switchingTitle.textContent = msg.model_type === 'rtmpose'
          ? '⚡ Switching to GPU Tracking (RTMPose)...'
          : '💻 Switching to CPU Tracking (MediaPipe)...';
        switchingSub.textContent = msg.model_type === 'rtmpose'
          ? 'Initializing DirectML execution provider on your GPU...'
          : 'Loading CPU MediaPipe Pose Landmarker...';
        engineSwitchingOverlay.style.display = 'flex';
      }
      break;

    case 'devices':
      if (msg.devices) syncVerifiedDevices(msg.devices, true);
      break;

    case 'stream_update':
      handleStreamUpdate(msg);
      break;

    case 'camera_added':
      showToast(`Camera added: ${msg.cam_id}`, 'success');
      break;

    case 'camera_removed':
      removeCameraCard(msg.cam_id);
      showToast(`Camera removed: ${msg.cam_id}`, 'info');
      break;

    case 'tpose_reset':
      activeCalibration = null;
      if (tposeCalInfo) tposeCalInfo.innerHTML = '';
      showToast('T-Pose calibration reset', 'info');
      break;

    case 'tpose_calibrated':
      activeCalibration = msg.calibration;
      updateCalibrationDetailsUI(msg.calibration);
      showToast('✨ T-Pose Calibrated! Model repositioned to origin.', 'success');
      playCalibrationChime();
      break;

    case 'origin_recentered':
      showToast('Model origin repositioned', 'info');
      break;

    case 'model_engine_updated':
      if (engineSwitchingOverlay) {
        engineSwitchingOverlay.style.display = 'none';
      }
      if (msg.model_type) {
        const isRtm = msg.model_type.toLowerCase().includes('rtm');
        if (btnQuickGpu) btnQuickGpu.classList.toggle('active', isRtm);
        if (btnQuickCpu) btnQuickCpu.classList.toggle('active', !isRtm);
        if (brandEngineBadge) {
          brandEngineBadge.textContent = `${msg.model_type.toUpperCase()} (${msg.device || 'auto'})`;
        }
      }
      showToast(`Engine updated: ${msg.model_type.toUpperCase()} (${msg.device || 'auto'})`, 'success');
      break;

    case 'root_motion_updated':
      showToast(`Root tracking mode: ${msg.mode}`, 'info');
      break;

    case 'calibration_loaded':
      if (msg.ok) {
        calStatusMsg.textContent = 'Calibration loaded successfully!';
        calStatusMsg.style.color = 'var(--accent-emerald)';
        showToast('Calibration loaded', 'success');
      } else {
        calStatusMsg.textContent = 'Failed to load calibration.';
        calStatusMsg.style.color = 'var(--accent-rose)';
      }
      break;

    case 'recording_started':
      setRecordingState(true, msg.take_id);
      showToast(`Recording started: ${msg.take_id}`, 'info');
      break;

    case 'recording_stopped':
      setRecordingState(false, null);
      showToast(`Recording stopped: ${msg.take_id}`, 'success');
      break;

    case 'processing_started':
      showProcessingModal(msg.take_id);
      break;

    case 'processing_completed':
      showProcessingSuccessModal(msg);
      break;

    case 'processing_error':
      showProcessingErrorModal(msg);
      break;
  }
}

function handleStreamUpdate(msg) {
  frameCounter++;
  const now = performance.now();
  if (now - lastFpsTime >= 1000) {
    globalFpsLabel.textContent = Math.round((frameCounter * 1000) / (now - lastFpsTime));
    frameCounter = 0;
    lastFpsTime = now;
  }

  // Update T-Pose Auto-Calibration Widget
  if (msg.tpose) {
    updateTPoseWidget(msg.tpose);
  }

  // Update filter mode indicator
  if (msg.filter_preset && selectFilterMode && document.activeElement !== selectFilterMode) {
    selectFilterMode.value = msg.filter_preset;
    if (chkFilter && chkFilter.checked) {
      filterStatusLabel.textContent = `1€ Filter: ${msg.filter_preset.toUpperCase()}`;
    }
  }

  // Update Brand Badge and quick switch buttons
  if (msg.model_engine) {
    const isRtm = msg.model_engine.toLowerCase().includes('rtm');
    if (btnQuickGpu) btnQuickGpu.classList.toggle('active', isRtm);
    if (btnQuickCpu) btnQuickCpu.classList.toggle('active', !isRtm);
    if (brandEngineBadge) {
      brandEngineBadge.textContent = `${msg.model_engine.toUpperCase()} (${msg.device || 'auto'})`;
    }
  }

  // Update recording pill
  if (msg.recording) {
    const rec = msg.recording;
    if (rec.is_recording !== isRecording) {
      setRecordingState(rec.is_recording, rec.take_id);
    }
    if (rec.is_recording) {
      const dur = rec.duration_s || 0;
      recTimer.textContent = formatDuration(dur);
      let totalF = 0;
      if (rec.frame_counts) {
        totalF = Object.values(rec.frame_counts).reduce((a, b) => a + b, 0);
      }
      recFrames.textContent = `${totalF} frames`;
    }
  }

  const cameras = msg.cameras || {};
  const activeIds = new Set(Object.keys(cameras));

  // Remove disappeared cameras
  for (const existingId of cameraCards.keys()) {
    if (!activeIds.has(existingId)) {
      removeCameraCard(existingId);
    }
  }

  // Update each camera
  for (const [camId, data] of Object.entries(cameras)) {
    const card = getOrCreateCameraCard(camId, data);

    if (data.status === 'error') {
      card.statusOverlay.style.display = 'flex';
      card.statusOverlay.innerHTML = `
        <div style="display: flex; flex-direction: column; align-items: center; gap: 8px;">
          <span style="color: var(--accent-rose); font-size: 13px; font-weight: 600;">Connection Error</span>
          <span style="color: var(--text-muted); font-size: 11px; max-width: 90%; word-break: break-word;">${data.error || 'Failed to open camera'}</span>
          <button class="btn btn-sm btn-secondary" style="margin-top: 4px;" onclick="window.retryCamera && window.retryCamera('${camId}', '${data.source}', '${(data.name || '').replace(/'/g, "\\'")}')">Retry</button>
        </div>
      `;
      card.img.style.display = 'none';
      card.ctx.clearRect(0, 0, card.canvas.width, card.canvas.height);
    } else if (data.image) {
      card.statusOverlay.style.display = 'none';
      card.img.style.display = 'block';
      card.img.src = `data:image/jpeg;base64,${data.image}`;
    } else {
      card.statusOverlay.style.display = 'flex';
      card.statusOverlay.innerHTML = '<div class="loading-spinner" style="color: var(--accent-cyan); font-size: 13px;">Starting video feed...</div>';
      card.img.style.display = 'none';
      card.ctx.clearRect(0, 0, card.canvas.width, card.canvas.height);
    }

    card.fpsBadge.textContent = `${data.fps || 0} FPS`;
    card.resLabel.textContent = `${data.width || 0}x${data.height || 0}`;
    const eng = data.engine ? ` (${data.engine})` : '';
    card.latLabel.textContent = `${data.latency_ms || 0} ms${eng}`;

    // 2D Skeleton overlay
    if (card.showOverlay && data.landmarks_2d && card.img.clientWidth > 0 && data.image) {
      const rect = card.img.getBoundingClientRect();
      if (card.canvas.width !== rect.width || card.canvas.height !== rect.height) {
        card.canvas.width = rect.width;
        card.canvas.height = rect.height;
      }
      draw2DSkeleton(card.ctx, data.landmarks_2d, rect.width, rect.height);
    } else {
      card.ctx.clearRect(0, 0, card.canvas.width, card.canvas.height);
    }
  }

  // Update 3D skeleton
  update3DSkeleton(msg.pose_3d);
}

/* ==========================================================================
   Camera Hardware Scanning
   ========================================================================== */

let lastBrowserCameras = [];
let isScanningHardware = false;

async function scanHardwareCameras(showToastNotification = false) {
  if (isScanningHardware) return;
  isScanningHardware = true;

  try {
    const res = await fetch(`http://127.0.0.1:${WS_PORT}/api/cameras`);
    if (res.ok) {
      const data = await res.json();
      if (data.devices) {
        syncVerifiedDevices(data.devices, showToastNotification);
        isScanningHardware = false;
        return;
      }
    }
  } catch (e) {
    // WebSocket message fallback
  }

  isScanningHardware = false;
}

function syncVerifiedDevices(serverDevices, showToastNotification = false) {
  if (!serverDevices) return;

  const verified = [];
  for (const sCam of serverDevices) {
    if (sCam.available) {
      verified.push({
        index: sCam.index,
        name: sCam.name,
        available: true,
        in_use: sCam.in_use || false
      });
    }
  }

  updateAvailableDevicesUI(verified);
  if (showToastNotification) {
    showToast(`Found ${verified.length} connected camera(s)`, verified.length > 0 ? 'success' : 'info');
  }
}

let selectedLocalDevice = null;

async function connectCamera(camId, source, name) {
  showToast(`Connecting to ${name}...`, 'info');
  if (socket && socket.readyState === WebSocket.OPEN) {
    sendWSCommand('add_camera', { cam_id: camId, source, name });
  } else {
    try {
      await fetch(`http://127.0.0.1:${WS_PORT}/api/cameras/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cam_id: camId, source, name })
      });
    } catch (e) {
      console.warn('REST add_camera fallback failed:', e);
    }
  }
}
window.retryCamera = (camId, source, name) => connectCamera(camId, source, name);

function updateAvailableDevicesUI(devices) {
  availableDevices = devices || [];
  localDeviceList.innerHTML = '';
  detectedQuickList.innerHTML = '';

  const avail = availableDevices.filter(d => d.available && !d.in_use);

  if (avail.length === 0) {
    localDeviceList.innerHTML = '<p class="muted-note" style="padding: 8px;">No available webcams detected automatically. You can enter an index (e.g. 0, 1) manually below.</p>';
  } else {
    for (const dev of avail) {
      const item = document.createElement('div');
      item.className = 'device-item';
      item.style.cursor = 'pointer';
      item.innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 2px;">
          <strong style="font-size: 13px;">${dev.name}</strong>
          <span style="font-family: var(--font-mono); font-size: 11px; color: var(--accent-cyan);">Device Index: ${dev.index}</span>
        </div>
        <button class="btn btn-sm btn-primary">Connect</button>
      `;

      const doConnect = () => {
        connectCamera(`cam${dev.index}`, dev.index, dev.name);
        modalAddCamera.hidden = true;
      };

      item.querySelector('button').addEventListener('click', (e) => {
        e.stopPropagation();
        doConnect();
      });

      item.addEventListener('dblclick', doConnect);

      item.addEventListener('click', () => {
        selectedLocalDevice = dev;
        customCamIndex.value = dev.index;
        document.querySelectorAll('.device-item').forEach(el => el.style.borderColor = 'var(--border-subtle)');
        item.style.borderColor = 'var(--accent-cyan)';
      });

      localDeviceList.appendChild(item);

      const quickBtn = document.createElement('button');
      quickBtn.className = 'btn btn-secondary btn-sm';
      quickBtn.innerHTML = `+ Connect <strong>${dev.name}</strong>`;
      quickBtn.addEventListener('click', doConnect);
      detectedQuickList.appendChild(quickBtn);
    }

    if (avail.length > 0 && customCamIndex.value === '') {
      selectedLocalDevice = avail[0];
      customCamIndex.value = avail[0].index;
    }
  }
}

/* ==========================================================================
   UI Event Listeners
   ========================================================================== */

function openAddCameraModal() {
  modalAddCamera.hidden = false;
  scanHardwareCameras(false);
}

btnAddCamera.addEventListener('click', openAddCameraModal);
btnEmptyAdd.addEventListener('click', openAddCameraModal);
modalCloseAdd.addEventListener('click', () => modalAddCamera.hidden = true);
btnCancelAdd.addEventListener('click', () => modalAddCamera.hidden = true);

document.querySelectorAll('.modal-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.modal-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    tab.classList.add('active');
    const target = document.getElementById(`tab-${tab.dataset.tab}`);
    if (target) target.classList.add('active');
  });
});

btnConfirmAdd.addEventListener('click', () => {
  const activeTab = document.querySelector('.modal-tab.active')?.dataset.tab || 'local';

  if (activeTab === 'local') {
    const idxVal = customCamIndex.value !== '' ? String(customCamIndex.value).trim() : '';
    if (idxVal !== '') {
      const idx = parseInt(idxVal, 10);
      const name = (selectedLocalDevice && selectedLocalDevice.index === idx) ? selectedLocalDevice.name : `Camera ${idx}`;
      connectCamera(`cam${idx}`, idx, name);
      modalAddCamera.hidden = true;
      customCamIndex.value = '';
      selectedLocalDevice = null;
    } else {
      showToast('Please select a camera or enter an index', 'error');
    }
  } else if (activeTab === 'network') {
    const url = networkUrlInput.value.trim();
    const name = networkNameInput.value.trim() || 'Network Stream';
    if (url) {
      const camId = `net_${Date.now().toString().slice(-4)}`;
      connectCamera(camId, url, name);
      modalAddCamera.hidden = true;
      networkUrlInput.value = '';
      networkNameInput.value = '';
    } else {
      showToast('Please enter a stream URL', 'error');
    }
  }
});

btnSettings.addEventListener('click', () => {
  modalSettings.hidden = false;
});
modalCloseSettings.addEventListener('click', () => modalSettings.hidden = true);
btnCloseSettings.addEventListener('click', () => modalSettings.hidden = true);

// Browse calibration file
btnBrowseCal.addEventListener('click', async () => {
  if (window.electronAPI?.selectCalibrationFile) {
    const filePath = await window.electronAPI.selectCalibrationFile();
    if (filePath) {
      calPathInput.value = filePath;
    }
  } else {
    const manualPath = prompt('Enter absolute path to calibration.json:');
    if (manualPath) calPathInput.value = manualPath;
  }
});

// Browse video file
const btnBrowseVideo = document.getElementById('btn-browse-video');
if (btnBrowseVideo) {
  btnBrowseVideo.addEventListener('click', async () => {
    if (window.electronAPI?.selectVideoFile) {
      const filePath = await window.electronAPI.selectVideoFile();
      if (filePath) {
        networkUrlInput.value = filePath;
        if (!networkNameInput.value) {
          const base = filePath.split(/[/\\]/).pop();
          networkNameInput.value = base ? `File: ${base}` : 'Test Video';
        }
      }
    } else {
      const manualPath = prompt('Enter video file path (e.g. /path/to/video.mp4):');
      if (manualPath) {
        networkUrlInput.value = manualPath;
        if (!networkNameInput.value) {
          const base = manualPath.split(/[/\\]/).pop();
          networkNameInput.value = base ? `File: ${base}` : 'Test Video';
        }
      }
    }
  });
}

btnLoadCal.addEventListener('click', () => {
  const path = calPathInput.value.trim();
  if (path) {
    sendWSCommand('load_calibration', { path });
  } else {
    showToast('Select or enter a calibration file path first', 'error');
  }
});

// Engine & Hardware Acceleration apply button
if (btnApplyEngine) {
  btnApplyEngine.addEventListener('click', () => {
    const engine = selectModelEngine.value;
    const device = selectEngineDevice.value;
    const variant = selectModelVariant.value;
    requestSwitchEngine(engine, device, variant);
  });
}

// Quick Engine Switch buttons
if (btnQuickGpu) {
  btnQuickGpu.addEventListener('click', () => {
    requestSwitchEngine('rtmpose', 'dml', 'balanced');
  });
}
if (btnQuickCpu) {
  btnQuickCpu.addEventListener('click', () => {
    requestSwitchEngine('mediapipe', 'cpu', 'full');
  });
}

// Recenter view button
if (btnRecenterView) {
  btnRecenterView.addEventListener('click', () => {
    recenter3DView();
    sendWSCommand('recenter_origin');
    showToast('3D Viewport & Performer Root Recentered', 'info');
  });
}

// T-Pose calibration buttons
if (btnResetTpose) {
  btnResetTpose.addEventListener('click', () => {
    sendWSCommand('reset_tpose_calibration');
  });
}
if (btnResetTposeSettings) {
  btnResetTposeSettings.addEventListener('click', () => {
    sendWSCommand('reset_tpose_calibration');
  });
}
if (btnForceTpose) {
  btnForceTpose.addEventListener('click', () => {
    sendWSCommand('trigger_tpose_calibration');
  });
}

// Root motion toggle
if (chkGlobalRoot) {
  chkGlobalRoot.addEventListener('change', () => {
    const mode = chkGlobalRoot.checked ? 'global' : 'root_locked';
    sendWSCommand('set_root_motion', { mode });
  });
}

// 2D overlays global toggle
btnToggleAllOverlays.addEventListener('click', () => {
  globalShowOverlays = !globalShowOverlays;
  btnToggleAllOverlays.textContent = globalShowOverlays ? 'Hide 2D Overlays' : 'Show 2D Overlays';
  document.querySelectorAll('.camera-overlay-canvas').forEach(c => {
    c.style.display = globalShowOverlays ? 'block' : 'none';
  });
});

btnRescanCameras.addEventListener('click', () => {
  sendWSCommand('list_devices');
  showToast('Scanning hardware cameras...', 'info');
});

// 3D Viewport presets
btnViewFront.addEventListener('click', () => {
  camera.position.set(0, 1.1, 2.8);
  controls.target.set(0, 0.9, 0);
  controls.update();
});

btnViewSide.addEventListener('click', () => {
  camera.position.set(2.8, 1.1, 0);
  controls.target.set(0, 0.9, 0);
  controls.update();
});

btnViewTop.addEventListener('click', () => {
  camera.position.set(0, 3.8, 0.05);
  controls.target.set(0, 0, 0);
  controls.update();
});

btnViewReset.addEventListener('click', () => {
  camera.position.set(2.0, 1.4, 2.6);
  controls.target.set(0, 0.9, 0);
  controls.update();
});

// Viewport layer toggles
chkGrid.addEventListener('change', () => gridHelper.visible = chkGrid.checked);
chkAxes.addEventListener('change', () => axesHelper.visible = chkAxes.checked);
chkFilter.addEventListener('change', () => {
  const mode = selectFilterMode ? selectFilterMode.value : 'balanced';
  filterStatusLabel.textContent = `1€ Filter: ${chkFilter.checked ? mode.toUpperCase() : 'OFF'}`;
  filterStatusLabel.classList.toggle('pill-active', chkFilter.checked);
  sendWSCommand('set_filter', {
    enabled: chkFilter.checked,
    preset: mode,
  });
});

if (selectFilterMode) {
  selectFilterMode.addEventListener('change', () => {
    sendWSCommand('set_filter', {
      enabled: chkFilter.checked,
      preset: selectFilterMode.value,
    });
    if (chkFilter.checked) {
      filterStatusLabel.textContent = `1€ Filter: ${selectFilterMode.value.toUpperCase()}`;
    }
    showToast(`Anti-jitter mode: ${selectFilterMode.options[selectFilterMode.selectedIndex].text}`, 'info');
  });
}

/* ==========================================================================
   Toast Notification Helper
   ========================================================================== */

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

/* ==========================================================================
   Recording & BVH Export Functions
   ========================================================================== */

function formatDuration(sec) {
  const s = Math.floor(sec || 0);
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${String(m).padStart(2, '0')}:${String(rem).padStart(2, '0')}`;
}

function setRecordingState(recording, takeId) {
  isRecording = recording;
  currentTakeId = takeId;

  if (btnRecord && btnRecordText) {
    if (isRecording) {
      btnRecord.classList.add('recording-active');
      btnRecordText.textContent = 'Stop & Export BVH';
    } else {
      btnRecord.classList.remove('recording-active');
      btnRecordText.textContent = 'Record Footage';
    }
  }

  if (recordingPill) {
    recordingPill.style.display = isRecording ? 'flex' : 'none';
  }
}

function toggleRecording() {
  if (!isRecording) {
    if (cameraCards.size === 0) {
      showToast('Please add at least one camera stream first', 'error');
      openAddCameraModal();
      return;
    }
    sendWSCommand('start_recording');
    setRecordingState(true, null);
  } else {
    const autoProc = settingAutoProcess ? settingAutoProcess.checked : true;
    const height = parseFloat(settingHeight?.value || 1.75);
    const smoother = settingSmoother?.value || 'savgol';

    sendWSCommand('stop_recording', {
      auto_process: autoProc,
      performer_height_m: height,
      smoother: smoother,
    });
    setRecordingState(false, null);
  }
}

if (btnRecord) {
  btnRecord.addEventListener('click', toggleRecording);
}

// Processing Modal Helpers
function showProcessingModal(takeId) {
  if (!modalProcessingResult || !procModalBody) return;
  procModalTitle.textContent = 'Processing Mocap Footage...';
  procModalBody.innerHTML = `
    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 24px 10px; gap: 16px;">
      <div class="loading-spinner" style="font-size: 16px; color: var(--accent-cyan);">
        Running Mocap Pipeline on ${takeId || 'take'}...
      </div>
      <p style="color: var(--text-secondary); font-size: 13px; text-align: center; max-width: 80%;">
        Synchronizing video streams, computing 3D skeleton rotations, fitting bone lengths, and generating BVH animation...
      </p>
    </div>
  `;
  modalProcessingResult.hidden = false;
}

function showProcessingSuccessModal(msg) {
  if (!modalProcessingResult || !procModalBody) return;
  procModalTitle.textContent = 'BVH Export Complete!';
  const bvhName = msg.bvh_path ? msg.bvh_path.split(/[/\\]/).pop() : 'out3d.bvh';
  const sizeKb = msg.file_size_bytes ? Math.round(msg.file_size_bytes / 1024) : 0;
  const takeFolder = msg.bvh_path ? msg.bvh_path.replace(/[/\\][^/\\]+$/, '') : '';

  procModalBody.innerHTML = `
    <div class="proc-card">
      <div class="proc-success-banner">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
        <span>Mocap Pipeline Export Successful!</span>
      </div>
      <p style="color: var(--text-secondary); font-size: 13px; margin-bottom: 12px;">
        Your live footage has been fully reconstructed into a standard H36M hierarchical BVH skeleton motion file.
      </p>
      <div class="proc-detail-row">
        <span style="color: var(--text-muted);">Take ID</span>
        <strong style="color: var(--accent-cyan); font-family: var(--font-mono);">${msg.take_id || 'take'}</strong>
      </div>
      <div class="proc-detail-row">
        <span style="color: var(--text-muted);">BVH Output</span>
        <strong style="font-family: var(--font-mono);">${bvhName} (${sizeKb} KB)</strong>
      </div>
      <div class="proc-detail-row">
        <span style="color: var(--text-muted);">Pipeline Mode</span>
        <span>${msg.method || 'mocap_pipeline'}</span>
      </div>
      <div class="proc-detail-row">
        <span style="color: var(--text-muted);">Location</span>
        <span style="font-size: 11px; word-break: break-all; color: var(--text-secondary);">${msg.bvh_path || ''}</span>
      </div>
      <div style="display: flex; gap: 8px; margin-top: 16px;">
        <button id="btn-modal-open-bvh" class="btn btn-primary" style="flex: 1;">
          Show in File Manager
        </button>
        <button id="btn-modal-open-folder" class="btn btn-secondary">
          Open Folder
        </button>
      </div>
    </div>
  `;
  modalProcessingResult.hidden = false;

  const btnOpenBvh = document.getElementById('btn-modal-open-bvh');
  if (btnOpenBvh) {
    btnOpenBvh.addEventListener('click', () => {
      if (window.electronAPI?.openItem && msg.bvh_path) {
        window.electronAPI.openItem(msg.bvh_path);
      } else {
        alert(`BVH File saved to:\n${msg.bvh_path}`);
      }
    });
  }

  const btnOpenFld = document.getElementById('btn-modal-open-folder');
  if (btnOpenFld) {
    btnOpenFld.addEventListener('click', () => {
      if (window.electronAPI?.openFolder && takeFolder) {
        window.electronAPI.openFolder(takeFolder);
      } else {
        alert(`Folder:\n${takeFolder}`);
      }
    });
  }
}

function showProcessingErrorModal(msg) {
  if (!modalProcessingResult || !procModalBody) return;
  procModalTitle.textContent = 'Processing Error';
  procModalBody.innerHTML = `
    <div class="proc-card" style="border-left: 4px solid var(--accent-rose);">
      <h4 style="color: var(--accent-rose); margin-bottom: 8px;">Failed to process mocap footage</h4>
      <p style="color: var(--text-secondary); font-size: 13px; word-break: break-word;">
        ${msg.error || 'An error occurred during stage reconstruction.'}
      </p>
    </div>
  `;
  modalProcessingResult.hidden = false;
}

if (modalCloseProc) modalCloseProc.addEventListener('click', () => modalProcessingResult.hidden = true);
if (btnCloseProc) btnCloseProc.addEventListener('click', () => modalProcessingResult.hidden = true);

// Takes & Recordings List
async function loadTakesList() {
  if (!takesListContainer) return;
  takesListContainer.innerHTML = '<div class="loading-spinner">Loading recorded takes...</div>';

  try {
    const res = await fetch(`http://127.0.0.1:${WS_PORT}/api/recordings`);
    const data = await res.json();
    const takes = data.takes || [];

    if (takes.length === 0) {
      takesListContainer.innerHTML = `
        <div style="text-align: center; padding: 30px; color: var(--text-muted); font-size: 13px;">
          No recorded takes found yet. Click <strong>Record Footage</strong> in the top navigation to record your first live take!
        </div>
      `;
      return;
    }

    takesListContainer.innerHTML = takes.map(t => {
      const dur = t.info?.duration_s || 0;
      const camCount = t.info?.cameras ? Object.keys(t.info.cameras).length : (t.videos?.length || 0);
      const bvhReady = t.has_bvh;
      const bvhSizeKb = Math.round((t.bvh_size || 0) / 1024);
      const dateStr = t.created_at ? new Date(t.created_at * 1000).toLocaleString() : '';

      return `
        <div class="take-card" data-take="${t.take_id}" data-path="${t.path}">
          <div class="take-info-col">
            <div class="take-title-row">
              <span class="take-name">${t.take_id}</span>
              ${bvhReady
                ? `<span class="badge" style="background: rgba(16, 185, 129, 0.15); color: var(--accent-emerald);">BVH Ready (${bvhSizeKb} KB)</span>`
                : `<span class="badge" style="background: rgba(245, 158, 11, 0.15); color: #f59e0b;">Raw Footage</span>`
              }
            </div>
            <div class="take-meta-row">
              <span>Date: ${dateStr}</span>
              <span>Cameras: ${camCount}</span>
              <span>Duration: ${dur}s</span>
              <span>Videos: ${(t.videos || []).join(', ')}</span>
            </div>
          </div>
          <div class="take-actions">
            ${bvhReady
              ? `<button class="btn btn-sm btn-primary" onclick="window.openTakeItem('${t.path}/out3d.bvh')">Show BVH</button>`
              : `<button class="btn btn-sm btn-primary" onclick="window.triggerProcessTake('${t.take_id}')">Process to BVH</button>`
            }
            <button class="btn btn-sm btn-secondary" onclick="window.openTakeFolder('${t.path}')">Open Folder</button>
            ${bvhReady
              ? `<button class="btn btn-sm btn-ghost" onclick="window.triggerProcessTake('${t.take_id}')" title="Re-process with pipeline">Re-process</button>`
              : ''
            }
          </div>
        </div>
      `;
    }).join('');

  } catch (e) {
    takesListContainer.innerHTML = `<div style="color: var(--accent-rose); padding: 12px;">Failed to load recordings: ${e.message}</div>`;
  }
}

window.openTakeItem = function(itemPath) {
  if (window.electronAPI?.openItem) {
    window.electronAPI.openItem(itemPath);
  } else {
    alert(`File:\n${itemPath}`);
  }
};

window.openTakeFolder = function(folderPath) {
  if (window.electronAPI?.openFolder) {
    window.electronAPI.openFolder(folderPath);
  } else {
    alert(`Folder:\n${folderPath}`);
  }
};

window.triggerProcessTake = function(takeId) {
  modalTakes.hidden = true;
  showProcessingModal(takeId);
  const height = parseFloat(settingHeight?.value || 1.75);
  const smoother = settingSmoother?.value || 'savgol';
  sendWSCommand('process_take', {
    take_id: takeId,
    performer_height_m: height,
    smoother: smoother,
  });
};

if (btnTakes) {
  btnTakes.addEventListener('click', () => {
    modalTakes.hidden = false;
    loadTakesList();
  });
}

if (modalCloseTakes) modalCloseTakes.addEventListener('click', () => modalTakes.hidden = true);
if (btnCloseTakes) btnCloseTakes.addEventListener('click', () => modalTakes.hidden = true);

if (btnOpenRecordingsFolder) {
  btnOpenRecordingsFolder.addEventListener('click', async () => {
    try {
      const res = await fetch(`http://127.0.0.1:${WS_PORT}/api/recording/status`);
      const status = await res.json();
      const folder = status.take_dir ? status.take_dir.replace(/[/\\][^/\\]+$/, '') : '';
      if (window.electronAPI?.openFolder && folder) {
        window.electronAPI.openFolder(folder);
      } else {
        alert('Recordings are located in backend/output/live_recordings');
      }
    } catch (_) {
      alert('Recordings are located in backend/output/live_recordings');
    }
  });
}

// Initial start
connectWebSocket();
scanHardwareCameras(false);

window.scanHardwareCameras = scanHardwareCameras;
window.syncVerifiedDevices = syncVerifiedDevices;
