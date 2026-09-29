from enum import IntEnum


class LandMarks(IntEnum):
    # 0 - nose
    NOSE = 0
    # 1 - left eye (inner)
    LEFT_EYE_INNER = 1
    # 2 - left eye
    LEFT_EYE = 2
    # 3 - left eye (outer)
    LEFT_EYE_OUTER = 3
    # 4 - right eye (inner)
    RIGHT_EYE_INNER = 4
    # 5 - right eye
    RIGHT_EYE = 5
    # 6 - right eye (outer)
    RIGHT_EYE_OUTER = 6
    RIGHT_EYE_OUT = 6  # alias for convenience
    # 7 - left ear
    LEFT_EAR = 7
    # 8 - right ear
    RIGHT_EAR = 8
    # 9 - mouth (left)
    MOUTH_LEFT = 9
    # 10 - mouth (right)
    MOUTH_RIGHT = 10
    # 11 - left shoulder
    LEFT_SHOULDER = 11
    # 12 - right shoulder
    RIGHT_SHOULDER = 12
    # 13 - left elbow
    LEFT_ELBOW = 13
    # 14 - right elbow
    RIGHT_ELBOW = 14
    # 15 - left wrist
    LEFT_WRIST = 15
    # 16 - right wrist
    RIGHT_WRIST = 16
    # 17 - left pinky
    LEFT_PINKY = 17
    # 18 - right pinky
    RIGHT_PINKY = 18
    # 19 - left index
    LEFT_INDEX = 19
    # 20 - right index
    RIGHT_INDEX = 20
    # 21 - left thumb
    LEFT_THUMB = 21
    # 22 - right thumb
    RIGHT_THUMB = 22
    # 23 - left hip
    LEFT_HIP = 23
    # 24 - right hip
    RIGHT_HIP = 24
    # 25 - left knee
    LEFT_KNEE = 25
    # 26 - right knee
    RIGHT_KNEE = 26
    # 27 - left ankle
    LEFT_ANKLE = 27
    # 28 - right ankle
    RIGHT_ANKLE = 28
    # 29 - left heel
    LEFT_HEEL = 29
    # 30 - right heel
    RIGHT_HEEL = 30
    # 31 - left foot index
    LEFT_FOOT_INDEX = 31
    # 32 - right foot index
    RIGHT_FOOT_INDEX = 32