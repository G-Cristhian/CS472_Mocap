"""
All tunable constants live here so stages never hard-code numbers.
Values are starting guesses; adjust once real footage is available.
"""

# ---- Stage 1: 2D keypoints -------------------------------------------------
# Path to the MediaPipe model, relative to backend/. The repo ships one in
# backend/models/. MODEL_FILEPATH in .env or --model overrides it.
POSE_MODEL_PATH = "models/pose_landmarker_heavy.task"
# (ours) How many videos are detected at once, each in its own process. 0 is
# automatic: one per video, up to the processor's core count and
# DETECT_MAX_AUTO_JOBS (each process loads its own copy of the pose model,
# roughly 1 to 2 GB of memory). 1 detects the videos one after another in
# this process, as before. --jobs overrides it per run.
DETECT_JOBS = 0
DETECT_MAX_AUTO_JOBS = 4

# ---- Cameras (ours) ----------------------------------------------------------
# At least two cameras in a front arc, iPhones and webcams mixed; no upper
# limit (design decision D-024). Triangulating a joint needs two views, and
# every extra camera adds detection time linearly and refinement time faster.
MIN_CAMERAS = 2

# RTMPose (stage1_keypoints/backends.py, --detector rtmpose). Mode picks rtmlib's
# model pair: "lightweight" (YOLOX-tiny 416 + RTMPose-s 256x192), "balanced"
# (YOLOX-m 640 + RTMPose-m 256x192) or "performance" (YOLOX-x 640 + RTMPose-x
# 384x288). Balanced is rtmlib's default (design decision D-022).
RTMPOSE_MODE = "balanced"
# Run RTMPose's person detector only every this many frames (1 = every frame,
# as before). In between, the performer's box comes from the joints found in
# the previous frame: those scoring at least RTMPOSE_TRACK_MIN_SCORE (rtmlib's
# raw score), at least RTMPOSE_TRACK_MIN_JOINTS of them, their bounding box
# grown RTMPOSE_TRACK_BOX_SCALE times about its centre (rtmlib's PoseTracker
# uses 1.25). Too few good joints and the detector runs on the next frame.
RTMPOSE_DETECT_EVERY = 1
RTMPOSE_TRACK_MIN_SCORE = 0.3
RTMPOSE_TRACK_MIN_JOINTS = 6
RTMPOSE_TRACK_BOX_SCALE = 1.25

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
# Lowered from 8 on 2026-10-19: real takes' claps were rejected as not loud
# enough against the room. The rise-time test below is what keeps speech out,
# so these two mostly decide how much background noise a clap must beat.
# --clap-threshold multiplies both per run (0.5 accepts a clap half as strong).
CLAP_MIN_PROMINENCE = 4.0
# ...and must be at least this many times louder than 30-100 ms before it
# (a clap is sharp; talking and music ramp up slowly). Lowered from 3, same day.
CLAP_MIN_RISE = 2.0
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
# Chirp sync (stage2_reconstruct/chirp.py), the alternative to the clap: a
# known sweep played from a speaker once every camera is recording, found by
# correlating each video's audio with the same sweep (a matched filter). The
# sweep stays inside what phone speakers play well and under the Nyquist
# frequency of CLAP_AUDIO_RATE (8 kHz). Changing any of these four means the
# chirp played on set must be regenerated (python -m mocap_pipeline.stage2_reconstruct.chirp).
CHIRP_F0_HZ = 1500.0
CHIRP_F1_HZ = 6000.0
CHIRP_DURATION_S = 0.5
# The fades are long on purpose: a chirp that reaches full loudness more slowly
# than CLAP_MAX_RISE_S is never taken for a clap, so a take can carry both
# (clap and chirp in one take, to compare the two).
CHIRP_FADE_S = 0.05
# The chirp is accepted where the audio matches it at least this well
# (normalised correlation, 0..1; room noise alone scores about 0.02). Scaled
# by --clap-threshold like the clap thresholds.
CHIRP_MIN_SCORE = 0.2
# A second match at least this fraction as strong as the best, more than
# CHIRP_ECHO_S away from it, makes the detection ambiguous (chirp played
# twice, or two phones playing it); echoes off nearby walls arrive sooner.
CHIRP_MAX_SECOND_PEAK = 0.7
CHIRP_ECHO_S = 0.1

# ---- Stage 2b: calibration -------------------------------------------------
# Our calibration (calibrate.py) starts from the best-matched camera pair, adds
# the others with solvePnP and refines all together. Not Liu et al.'s method.
# Joints stable enough to use as calibration points are joints.CALIBRATION_JOINTS.
# A joint is used as a calibration point only if BOTH cameras in the pair
# report at least this confidence (paper section 3, "data selection").
CALIB_MIN_CONFIDENCE = 0.8
# RANSAC inlier threshold in pixels for the camera pose from the joints.
RANSAC_REPROJ_THRESHOLD_PX = 3.0
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
# (ours) Which smoother cleans the 3D joints: "savgol" (the Savitzky-Golay
# filter above) or "butterworth" (a zero-phase low-pass, the biomechanics
# standard: Winter, Biomechanics and Motor Control of Human Movement, 4th ed.,
# 2009, chapter 3). --smoother picks one per run; both are kept so they can be
# compared on the same take.
SMOOTHER = "savgol"
# Butterworth: cutoff in Hz and the order of one pass. The filter runs forward
# and then backward (scipy sosfiltfilt), so the result has no lag and twice the
# order. Winter's gait work uses 6 Hz; punches are faster, so this starts
# higher. Must be below half the frame rate. Starting guess, not measured.
BUTTER_CUTOFF_HZ = 8.0
BUTTER_ORDER = 2

# ---- Placement tool (Rahimian & Kearney 2015) ------------------------------
# Two cameras can triangulate a point only if their viewing rays meet at an
# angle inside this range (paper section 3.1).
MIN_CONVERGENCE_DEG = 40.0
MAX_CONVERGENCE_DEG = 140.0
# Beyond this distance a camera is treated as not seeing the point. The paper
# used 3.65 m for marker cameras; retune for phones.
CAMERA_EFFECTIVE_RANGE_M = 6.0
# (ours) a target point no camera sees costs 360 plus this (the paper's
# equation 1 penalty, our value): without it the annealer parks every camera
# on one spot, since a point nobody sees costs no more than one everybody
# sees from the same side.
PLACEMENT_UNCOVERED_PENALTY_DEG = 360.0
# (ours) fallback target points when no recording exists: a grid over the
# capture volume, half-width and step in metres on the floor, and the heights.
PLACEMENT_GRID_HALF_WIDTH_M = 1.5
PLACEMENT_GRID_STEP_M = 0.5
PLACEMENT_GRID_HEIGHTS_M = (0.1, 0.9, 1.5)
# (ours) at most this many joint positions are sampled from a recording to
# score a layout; the annealer evaluates the cost thousands of times.
PLACEMENT_MAX_TARGET_POINTS = 300
