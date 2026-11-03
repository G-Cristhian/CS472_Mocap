import cv2
from django.core.files.base import ContentFile


def read_video(recording):
    """
    Fills in the size, frame rate and length from the uploaded video, and stores a preview
    image taken one second in (or the first frame, for very short videos). Raises ValueError
    if the file cannot be read as a video.
    """
    capture = cv2.VideoCapture(recording.video.path)
    try:
        if not capture.isOpened():
            raise ValueError("Could not read this video.")

        fps = capture.get(cv2.CAP_PROP_FPS) or 0.0
        frames = capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if fps > 0:
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(fps))
        ok, frame = capture.read()
        if not ok:
            capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = capture.read()
        if not ok:
            raise ValueError("Could not read this video.")

        ok, jpeg = cv2.imencode(".jpg", frame)
        if not ok:
            raise ValueError("Could not make a preview image from this video.")
    finally:
        capture.release()

    recording.width = width or None
    recording.height = height or None
    recording.fps = fps or None
    recording.duration_s = frames / fps if fps else None
    recording.thumbnail.save("thumbnail.jpg", ContentFile(jpeg.tobytes()), save=False)
    recording.save(update_fields=["width", "height", "fps", "duration_s", "thumbnail"])
