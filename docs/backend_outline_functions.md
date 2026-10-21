# LIST OF ALL BACKEND FUNCTIONS TO FINISH
(in reference to Giancarlo's MoCap Pipeline Outline -- subject to change)

*[Link to Google Doc version](https://docs.google.com/document/d/1THdnqQ59qjq3xB7Tj74TM-uyVGOQFSp10eTlkLnjBkQ/edit?tab=t.0#heading=h.d30smwye3rro)*

###  ~/CS472_Mocap/backend/mocap_pipeline/placement
**=> [anneal.py](/backend/mocap_pipeline/placement/anneal.py)**
:: Search for a good layout with simulated annealing (paper section 3.5).
* def random_layout(num_cameras: int, constraints) -> CameraRig:
* def optimise_layout(num_cameras: int, constraints, target_points, iterations: int = 20000) -> CameraRig:

**=> [metric.py](/backend/mocap_pipeline/placement/metric.py)** 
:: Quality metric for a camera layout (paper sections 3.1 to 3.4).
* def camera_sees(camera, point) -> bool:
* def is_triangulable(camera_a, camera_b, point) -> bool:
* def point_error(rig: CameraRig, point) -> float:
* def layout_cost(rig: CameraRig, target_points) -> float:
* def target_points_from_pose(pose) -> list:

### ~/CS472_Mocap/backend/mocap_pipeline/stage1_keypoints
**=> [detect.py](/backend/mocap_pipeline/stage1_keypoints/detect.py)** 
:: Stage 1: run the pose model on every frame of one video.
* def create_landmarker(model_path: str):
* def detect_video(video_path: str, model_path: str) -> Keypoints2D:

### ~/CS472_Mocap/backend/mocap_pipeline/stage2_reconstruct
**=> [calibrate.py](/backend/mocap_pipeline/stage2_reconstruct/calibrate.py)** 
:: Stage 2b: checkerboard-free calibration from the performer's own joints.
* def initial_intrinsics(width: int, height: int, hfov_deg: float = config.DEFAULT_HFOV_DEG) -> "np.ndarray":
* ```def select_correspondences(a: Keypoints2D, b: Keypoints2D) -> tuple["np.ndarray", "np.ndarray"]:```
* def estimate_relative_pose(pts_a, pts_b, K_a, K_b):
* def refine_intrinsics(pts_a, pts_b, K_a, K_b, R, t):
* def reprojection_error(pts_2d, pts_3d, K, R, t) -> float:
* ```def calibrate_pair(a: Keypoints2D, b: Keypoints2D, K_a_fixed: "np.ndarray | None" = None, K_b_fixed: "np.ndarray | None" = None) -> tuple[Camera, Camera]:```
* def _place_camera(placed_group, flat_placed, flat_new, K_new, name):
* ```def calibrate_rig(keypoints: list[Keypoints2D], intrinsics: "list[np.ndarray] | None" = None) -> CameraRig:```
* ```def add_camera(rig: CameraRig, existing: list[Keypoints2D], new: Keypoints2D, K_new: "np.ndarray | None" = None) -> CameraRig:```

**=> [scale_floor.py](/backend/mocap_pipeline/stage2_reconstruct/scale_floor.py)** 
:: Stage 2b, second half: things the calibration does not provide.
* def _mid(points, *names):
* def _body_axis(points):
* def scale_factor_from_height(pose: Pose3D, performer_height_m: float) -> float:
* def estimate_floor(pose: Pose3D):
* def make_metric(rig: CameraRig, pose: Pose3D, performer_height_m: float, rescale: bool = True) -> CameraRig:

**=> [smooth.py](/backend/mocap_pipeline/stage2_reconstruct/smooth.py)** 
:: Stage 2c, clean-up: fill short gaps and remove jitter.
* def _runs(mask):
* def fill_gaps(pose: Pose3D) -> Pose3D:
* def smooth(pose: Pose3D) -> Pose3D:

**=> [sync.py](/backend/mocap_pipeline/stage2_reconstruct/sync.py)** 
:: Stage 2a: put every camera on one clock using the clap.
* def _read_audio(video_path: str, max_seconds: float) -> np.ndarray:
* def _loudness(audio: np.ndarray) -> np.ndarray:
* def _peak_and_rise_time(rms, before, i, far, win_s):
* def _clap_from_loudness(rms: np.ndarray, name: str, threshold: float = 1.0) -> float:
* def find_clap_time(video_path: str, threshold: float = 1.0) -> float:
* def _refine_against_reference(rms_ref, clap_ref, rms, clap, name):
* ```def detect_claps(video_paths: list[str], threshold: float = 1.0) -> list[float]:```
* def _resample(kp: Keypoints2D, times: np.ndarray, common: np.ndarray):
* ```def synchronise(video_paths: list[str], keypoints: list[Keypoints2D], clap_times: list[float] | None = None, clap_threshold: float = 1.0) -> tuple[SyncResult, list[Keypoints2D]]:```

**=> [triangulate.py](/backend/mocap_pipeline/stage2_reconstruct/triangulate.py)** 
:: Stage 2c: combine every camera's 2D joints into one 3D point per joint.
* def triangulate_point(points_2d, confidences, projection_matrices):
* ```def triangulate_sequence(keypoints: list[Keypoints2D], rig: CameraRig) -> Pose3D:```

### ~/CS472_Mocap/backend/mocap_pipeline/stage3_rig
**=> [bvh_writer.py](/backend/mocap_pipeline/stage3_rig/bvh_writer.py)** 
:: Stage 3c: write the .bvh text file.
* def _children(name):
* def channel_order():
* ```def write_hierarchy(lines: list[str], rest_offsets) -> None:```
* def write_bvh(path: str, rest_offsets, root_positions, euler_degrees, fps: float) -> None:

**=> [rotations.py](/backend/mocap_pipeline/stage3_rig/rotations.py)** 
:: Stage 3b: positions -> joint rotations.
* def _normalize(v):
* def _frame_from_axes(primary_axis, primary, secondary_axis, secondary, fallback):
* def bone_rotation(rest_direction, current_direction):
* def solve_rotations(rig_positions, rest_offsets):
* def to_euler_degrees(local_rotations, order: str = "ZXY"):

**=> [skeleton.py](/backend/mocap_pipeline/stage3_rig/skeleton.py)** 
:: Stage 3a: turn 33 loose points into a skeleton with fixed bone lengths.
* def _fill_missing(positions):
* def rig_joint_positions(pose: Pose3D):
* def bone_lengths(rig_positions):
* def rest_pose_offsets(lengths):
