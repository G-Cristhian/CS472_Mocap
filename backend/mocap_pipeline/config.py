"""
All tunable constants live here so stages never hard-code numbers.
Values are starting guesses; adjust once real footage is available.
"""

# ---- Stage 1: 2D keypoints -------------------------------------------------
# Path to the MediaPipe model, relative to backend/. The repo already ships one
# in backend/landmarks_from_image_test/models/. MODEL_FILEPATH in .env or
# --model overrides it.
POSE_MODEL_PATH = "landmarks_from_image_test/models/pose_landmarker_heavy.task"

# ---- Cameras (ours) ----------------------------------------------------------
# At least two cameras in a front arc, iPhones and webcams mixed; no upper
# limit (design decision D-024). Triangulating a joint needs two views, and
# every extra camera adds detection time linearly and refinement time faster.
MIN_CAMERAS = 2

# ---- Stage 2a: sync --------------------------------------------------------
# Only search this many seconds from the start of each video for the clap.
CLAP_SEARCH_WINDOW_S = 10.0
# All cameras are resampled to this common frame rate after syncing.
TARGET_FPS = 30.0
# Clap detection on the audio track: audio is decoded to mono at this rate,
# loudness measured every CLAP_WINDOW_S over CLAP_SMOOTH_S, and the clap must stand out from the
# background of the search window by at least CLAP_MIN_PROMINENCE times...
CLAP_AUDIO_RATE = 16000
CLAP_WINDOW_S = 0.002
CLAP_SMOOTH_S = 0.01
CLAP_MIN_PROMINENCE = 8.0
# ...and must be at least this many times louder than 30-100 ms before it
# (a clap is sharp; talking and music ramp up slowly).
CLAP_MIN_RISE = 3.0
# ...and must go from a quarter of its peak loudness to the peak within this
# many seconds.
CLAP_MAX_RISE_S = 0.025
# Cross-check between cameras: refine each camera's clap against camera 0's
# by correlating the audio within this many seconds of the clap. If the
# refinement moves a clap by more than CLAP_MAX_REFINE_S, keep the detection
# and warn instead (the correlation probably locked onto something else).
CLAP_REFINE_WINDOW_S = 0.25
CLAP_MAX_REFINE_S = 0.05
# Resampling never interpolates across a hole longer than this many of the
# camera's own frame intervals (a dropped frame is fine, a stall is a gap).
SYNC_MAX_INTERP_GAP_FRAMES = 2.5

# ---- Stage 2b: calibration -------------------------------------------------
# Our calibration (calibrate.py) starts from the best-matched camera pair, adds
# the others with solvePnP and refines all together. Not Liu et al.'s method.
# Joints stable enough to use as calibration points are joints.CALIBRATION_JOINTS.
# A joint is used as a calibration point only if BOTH cameras in the pair
# report at least this confidence (paper section 3, "data selection").
CALIB_MIN_CONFIDENCE = 0.8
# RANSAC inlier threshold in pixels for the camera pose from the joints.
RANSAC_REPROJ_THRESHOLD_PX = 3.0
# Stop the alternate intrinsic/extrinsic loop when mean reprojection error
# improves by less than this between iterations. (Liu et al. only, not used by ours.)
CALIB_CONVERGENCE_PX = 0.01
CALIB_MAX_ITERATIONS = 50
# Initial guess for a phone main camera's horizontal field of view, used to
# seed the focal length (the paper seeds from factory values we do not have).
# iPhones read their real focal length from the video metadata instead.
DEFAULT_HFOV_DEG = 65.0
# (ours) distinct calibration points two cameras must share; fewer means the
# performer did not move around enough.
CALIB_MIN_CORRESPONDENCES = 200
# (ours) 3D points a further camera must see to be placed (solvePnP).
CALIB_MIN_PNP_POINTS = 50
# (ours) calibration above this mean reprojection error (px) falls back to the
# ChArUco board (stage2_reconstruct/board_calibration.py).
CALIB_MAX_ERROR_PX = 10.0

# ---- Stage 2b: scale and floor ---------------------------------------------
# Height is measured from the heels to the ears, then these are added: the
# top of the skull sits about this far above the ears, and the heel landmark
# about this far above the floor.
HEAD_TOP_ABOVE_EARS_M = 0.12
HEEL_ABOVE_FLOOR_M = 0.03
# A frame counts as standing upright when the hips and shoulders lie within
# this fraction of the heel-to-ear length from the heel-ear line.
UPRIGHT_MAX_DEVIATION = 0.05
# Need at least this many upright frames to trust the height measurement.
MIN_UPRIGHT_FRAMES = 10
# Floor fit: use the lowest this fraction of heel/toe positions (feet on the ground).
FLOOR_LOWEST_FRACTION = 0.2

# ---- Stage 2c: triangulation ----------------------------------------------
# Per-camera observations below this confidence are ignored for that joint.
TRIANGULATION_MIN_CONFIDENCE = 0.5
# A joint needs at least this many cameras in a frame, otherwise it is a gap.
MIN_CAMERAS_PER_JOINT = 2
# Gaps up to this many frames are interpolated; longer gaps stay missing.
MAX_GAP_FILL_FRAMES = 10
# (ours) a camera whose reprojection is further off than this (px) is dropped
# for that joint and the joint is triangulated again from the rest.
MAX_REPROJECTION_ERROR_PX = 15.0
# (ours) Savitzky-Golay smoothing: window in frames (odd) and polynomial order.
# Small window so fast motion such as a punch survives.
SMOOTH_WINDOW_FRAMES = 7
SMOOTH_POLYORDER = 2

# ---- Placement tool (Rahimian & Kearney 2015) ------------------------------
# Two cameras can triangulate a point only if their viewing rays meet at an
# angle inside this range (paper section 3.1).
MIN_CONVERGENCE_DEG = 40.0
MAX_CONVERGENCE_DEG = 140.0
# Beyond this distance a camera is treated as not seeing the point. The paper
# used 3.65 m for marker cameras; retune for phones.
CAMERA_EFFECTIVE_RANGE_M = 6.0
