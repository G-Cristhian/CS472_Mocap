"""
All tunable constants live here so stages never hard-code numbers.
Values are starting guesses; adjust once real footage is available.
"""

# ---- Stage 1: 2D keypoints -------------------------------------------------
# Path to the MediaPipe model. The repo already ships one in
# backend/landmarks_from_image_test/models/. Decide whether to move it or
# point at it; do not commit a second 30 MB copy.
POSE_MODEL_PATH = "landmarks_from_image_test/models/pose_landmarker_heavy.task"

# ---- Stage 2a: sync --------------------------------------------------------
# Only search this many seconds from the start of each video for the clap.
CLAP_SEARCH_WINDOW_S = 10.0
# All cameras are resampled to this common frame rate after syncing.
TARGET_FPS = 30.0

# ---- Stage 2b: calibration (Liu et al. 2022) -------------------------------
# A joint is used as a calibration point only if BOTH cameras in the pair
# report at least this confidence (paper section 3, "data selection").
CALIB_MIN_CONFIDENCE = 0.8
# RANSAC inlier threshold in pixels for the fundamental matrix.
RANSAC_REPROJ_THRESHOLD_PX = 3.0
# Stop the alternate intrinsic/extrinsic loop when mean reprojection error
# improves by less than this between iterations.
CALIB_CONVERGENCE_PX = 0.01
CALIB_MAX_ITERATIONS = 50
# Initial guess for a phone main camera's horizontal field of view, used to
# seed the focal length (the paper seeds from factory values we do not have).
DEFAULT_HFOV_DEG = 65.0

# ---- Stage 2c: triangulation ----------------------------------------------
# Per-camera observations below this confidence are ignored for that joint.
TRIANGULATION_MIN_CONFIDENCE = 0.5
# A joint needs at least this many cameras in a frame, otherwise it is a gap.
MIN_CAMERAS_PER_JOINT = 2
# Gaps up to this many frames are interpolated; longer gaps stay missing.
MAX_GAP_FILL_FRAMES = 10

# ---- Placement tool (Rahimian & Kearney 2015) ------------------------------
# Two cameras can triangulate a point only if their viewing rays meet at an
# angle inside this range (paper section 3.1).
MIN_CONVERGENCE_DEG = 40.0
MAX_CONVERGENCE_DEG = 140.0
# Beyond this distance a camera is treated as not seeing the point. The paper
# used 3.65 m for marker cameras; retune for phones.
CAMERA_EFFECTIVE_RANGE_M = 6.0
