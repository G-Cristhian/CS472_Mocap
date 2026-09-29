import os
from pathlib import Path
import cv2
import mediapipe as mp

# Suppress Qt platform and theme warnings on Linux
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
os.environ.setdefault("QT_STYLE_OVERRIDE", "Fusion")

# main method of getting the image as an npdarray
def get_image_mp(file_path):
    # STEP 3: Load the input image.
    image = mp.Image.create_from_file(file_path)
    return image

# *******************************************************
#
#       DEBUG FUNCTIONS
#
# *******************************************************


# Fix QFontDatabase missing fonts directory in OpenCV's bundled Qt
_fonts_dir = Path(cv2.__file__).parent / "qt" / "fonts"
if not _fonts_dir.exists():
    for _candidate in [Path("/usr/share/fonts/truetype/dejavu"), Path("/usr/share/fonts")]:
        if _candidate.exists():
            try:
                _fonts_dir.symlink_to(_candidate)
                break
            except OSError:
                pass


def get_image_cv2(file_path):
    img = cv2.imread(file_path)
    if img is None:
        raise FileNotFoundError(f"Image not found at path: {file_path}")

    return img


def show_image(image, window_name="Image Window", max_width=960, max_height=720):
    # Scale window dimensions preserving aspect ratio
    h, w = image.shape[:2]
    scale = min(max_width / w, max_height / h, 1.0)
    display_w = int(w * scale)
    display_h = int(h * scale)

    # WINDOW_NORMAL allows resizing the window
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, display_w, display_h)
    cv2.imshow(window_name, image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()