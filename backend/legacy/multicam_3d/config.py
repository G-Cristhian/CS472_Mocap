# All tunable numbers in one place, so the other files never hard-code them.
# Names match backend/mocap_pipeline/config.py (the team's pipeline outline) where the same setting exists.
# Values are starting guesses; adjust once real footage is available.

# ---- 2D keypoints (extract_2d.py) ----
# MediaPipe model, the repo already ships one; MODEL_FILEPATH in .env or --model overrides it
POSE_MODEL_PATH = "../landmarks_from_image_test/models/pose_landmarker_heavy.task"

# ---- cameras (main.py) ----
MIN_CAMERAS, MAX_CAMERAS = 2, 4
# guess for a camera's horizontal field of view when it isn't an iPhone with focal length metadata
DEFAULT_HFOV_DEG = 65.0

# ---- calibration from the person (calibrate_person.py) ----
# joints stable enough to calibrate from, face and finger landmarks jitter too much
CALIBRATION_JOINTS = [
    "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW", "RIGHT_ELBOW",
    "LEFT_WRIST", "RIGHT_WRIST", "LEFT_HIP", "RIGHT_HIP",
    "LEFT_KNEE", "RIGHT_KNEE", "LEFT_ANKLE", "RIGHT_ANKLE",
]
# a joint is a calibration point only if the camera reports at least this confidence (MediaPipe visibility)
CALIB_MIN_CONFIDENCE = 0.8
# RANSAC inlier threshold in pixels for the camera pose from the landmarks
RANSAC_REPROJ_THRESHOLD_PX = 3.0
# distinct calibration points two cameras must share, fewer means the person didn't move around enough
CALIB_MIN_CORRESPONDENCES = 200
# 3D points a further camera must see to be placed (solvePnP)
CALIB_MIN_PNP_POINTS = 50
# person calibration above this mean reprojection error (px) falls back to the ChArUco board
CALIB_MAX_ERROR_PX = 10.0

# ---- triangulation (triangulate.py) ----
# per-camera observations below this confidence are ignored for that joint
TRIANGULATION_MIN_CONFIDENCE = 0.5
# a joint needs at least this many cameras in a frame, otherwise it is a gap
MIN_CAMERAS_PER_JOINT = 2
# a camera whose reprojection is further off than this (px) is dropped for that joint
MAX_REPROJECTION_ERROR_PX = 15.0

# ---- clean-up (smooth.py) ----
# gaps up to this many frames are interpolated, longer gaps stay missing
MAX_GAP_FILL_FRAMES = 10
# Savitzky-Golay filter: window in frames (odd) and polynomial order
# small window so fast motion such as a punch survives
SMOOTH_WINDOW_FRAMES = 7
SMOOTH_POLYORDER = 2
