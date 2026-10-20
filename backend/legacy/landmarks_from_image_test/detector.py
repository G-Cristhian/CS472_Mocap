import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# model to detect the different parts of body using a model
def detector(model_path):
    # grab the task model
    base_options = python.BaseOptions(model_asset_path=model_path)
    options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    output_segmentation_masks=True)

    # return the detector object
    return vision.PoseLandmarker.create_from_options(options)
