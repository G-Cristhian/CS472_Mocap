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

# Rig joint -> the MediaPipe joints it is computed from (average of the list).
# Stage 3 (skeleton.py) uses this to build the rig's joint positions.
RIG_JOINT_SOURCES = {
    "Hips":          ["LEFT_HIP", "RIGHT_HIP"],
    "Chest":         ["LEFT_SHOULDER", "RIGHT_SHOULDER"],
    "Head":          ["LEFT_EAR", "RIGHT_EAR"],
    "LeftShoulder":  ["LEFT_SHOULDER"],
    "LeftElbow":     ["LEFT_ELBOW"],
    "LeftWrist":     ["LEFT_WRIST"],
    "RightShoulder": ["RIGHT_SHOULDER"],
    "RightElbow":    ["RIGHT_ELBOW"],
    "RightWrist":    ["RIGHT_WRIST"],
    "LeftHip":       ["LEFT_HIP"],
    "LeftKnee":      ["LEFT_KNEE"],
    "LeftAnkle":     ["LEFT_ANKLE"],
    "LeftToe":       ["LEFT_FOOT_INDEX"],
    "RightHip":      ["RIGHT_HIP"],
    "RightKnee":     ["RIGHT_KNEE"],
    "RightAnkle":    ["RIGHT_ANKLE"],
    "RightToe":      ["RIGHT_FOOT_INDEX"],
}

# Rig joint -> its parent. None marks the root. Order matters: a parent always
# appears before its children, which is the order BVH needs.
RIG_PARENTS = {
    "Hips": None,
    "Chest": "Hips",
    "Head": "Chest",
    "LeftShoulder": "Chest",
    "LeftElbow": "LeftShoulder",
    "LeftWrist": "LeftElbow",
    "RightShoulder": "Chest",
    "RightElbow": "RightShoulder",
    "RightWrist": "RightElbow",
    "LeftHip": "Hips",
    "LeftKnee": "LeftHip",
    "LeftAnkle": "LeftKnee",
    "LeftToe": "LeftAnkle",
    "RightHip": "Hips",
    "RightKnee": "RightHip",
    "RightAnkle": "RightKnee",
    "RightToe": "RightAnkle",
}
RIG_JOINTS = list(RIG_PARENTS)
