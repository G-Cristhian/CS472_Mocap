"""
Joint naming shared by every stage.

Stages 1 and 2 use the 33 MediaPipe pose landmarks, in MediaPipe's order.
Stage 3 reduces them to the smaller RIG_JOINTS set that a skeleton needs.
"""

# Index in this list == MediaPipe landmark index. Do not reorder.
MEDIAPIPE_JOINTS = [
    "NOSE", "LEFT_EYE_INNER", "LEFT_EYE", "LEFT_EYE_OUTER",
    "RIGHT_EYE_INNER", "RIGHT_EYE", "RIGHT_EYE_OUTER",
    "LEFT_EAR", "RIGHT_EAR", "MOUTH_LEFT", "MOUTH_RIGHT",
    "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW", "RIGHT_ELBOW",
    "LEFT_WRIST", "RIGHT_WRIST", "LEFT_PINKY", "RIGHT_PINKY",
    "LEFT_INDEX", "RIGHT_INDEX", "LEFT_THUMB", "RIGHT_THUMB",
    "LEFT_HIP", "RIGHT_HIP", "LEFT_KNEE", "RIGHT_KNEE",
    "LEFT_ANKLE", "RIGHT_ANKLE", "LEFT_HEEL", "RIGHT_HEEL",
    "LEFT_FOOT_INDEX", "RIGHT_FOOT_INDEX",
]
NUM_JOINTS = len(MEDIAPIPE_JOINTS)
JOINT_INDEX = {name: i for i, name in enumerate(MEDIAPIPE_JOINTS)}

# Joints stable enough to use as calibration points. Face and finger
# landmarks jitter too much; leave them out.
CALIBRATION_JOINTS = [
    "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW", "RIGHT_ELBOW",
    "LEFT_WRIST", "RIGHT_WRIST", "LEFT_HIP", "RIGHT_HIP",
    "LEFT_KNEE", "RIGHT_KNEE", "LEFT_ANKLE", "RIGHT_ANKLE",
]

# Stage 3 rig: the 17-joint Human3.6M (H36M) skeleton, as used by video2bvh
# (github.com/KevinLTT/video2bvh, bvh_skeleton/h36m_skeleton.py, MIT License).
#
# Rig joint -> how it is computed from the MediaPipe joints: a list is the
# average of those joints, a dict is a weighted sum (weights add up to 1).
# Stage 3 (skeleton.py) uses this to build the rig's joint positions.
# Approximations (MediaPipe has no spine, neck or top-of-head landmarks):
#   Spine = halfway between the hip centre and the shoulder centre (thorax)
#   Neck  = halfway between the thorax and the centre of the ears
#   Head  = top of the head: the centre of the ears, raised along the
#           thorax-to-ears line by 2/3 of that distance (~12 cm on an adult)
RIG_JOINT_SOURCES = {
    "Hip":           ["LEFT_HIP", "RIGHT_HIP"],
    "RightHip":      ["RIGHT_HIP"],
    "RightKnee":     ["RIGHT_KNEE"],
    "RightAnkle":    ["RIGHT_ANKLE"],
    "LeftHip":       ["LEFT_HIP"],
    "LeftKnee":      ["LEFT_KNEE"],
    "LeftAnkle":     ["LEFT_ANKLE"],
    "Spine":         ["LEFT_HIP", "RIGHT_HIP", "LEFT_SHOULDER", "RIGHT_SHOULDER"],
    "Thorax":        ["LEFT_SHOULDER", "RIGHT_SHOULDER"],
    "Neck":          ["LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_EAR", "RIGHT_EAR"],
    "Head":          {"LEFT_EAR": 5 / 6, "RIGHT_EAR": 5 / 6,
                      "LEFT_SHOULDER": -1 / 3, "RIGHT_SHOULDER": -1 / 3},
    "LeftShoulder":  ["LEFT_SHOULDER"],
    "LeftElbow":     ["LEFT_ELBOW"],
    "LeftWrist":     ["LEFT_WRIST"],
    "RightShoulder": ["RIGHT_SHOULDER"],
    "RightElbow":    ["RIGHT_ELBOW"],
    "RightWrist":    ["RIGHT_WRIST"],
}

# Rig joint -> its parent. None marks the root. Order matters: a parent always
# appears before its children, which is the order BVH needs.
RIG_PARENTS = {
    "Hip": None,
    "RightHip": "Hip",
    "RightKnee": "RightHip",
    "RightAnkle": "RightKnee",
    "LeftHip": "Hip",
    "LeftKnee": "LeftHip",
    "LeftAnkle": "LeftKnee",
    "Spine": "Hip",
    "Thorax": "Spine",
    "Neck": "Thorax",
    "Head": "Neck",
    "LeftShoulder": "Thorax",
    "LeftElbow": "LeftShoulder",
    "LeftWrist": "LeftElbow",
    "RightShoulder": "Thorax",
    "RightElbow": "RightShoulder",
    "RightWrist": "RightElbow",
}
RIG_JOINTS = list(RIG_PARENTS)

# Rig joints written as a BVH "End Site" (a position only, no rotation of its
# own), like video2bvh's HeadEndSite. Other leaf joints (ankles, wrists) get an
# End Site added after them, 0.4 x their own bone length long.
RIG_END_SITES = ["Head"]
