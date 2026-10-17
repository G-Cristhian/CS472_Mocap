# In case accuracy isn't the best, 
#   this is a fallback calibration file that uses a printed ChArUco board.
# Activates in main.py whenever calibrate_person.py fails or not accurate enough.

# To make the printable board
#   python board_calibration.py make-board [chosenName].png
# use one board per camera for calibration
#   film the board moving around, seen by both cameras
#   to start calibration:
#       python board_calibration.py calibrate [video1].mp4 [video2.mp4] --out calibration.toml

# make sure to manually adjust square length when printing
#   since printers often rescale it.

import argparse
import cv2

from aniposelib.boards import CharucoBoard
from aniposelib.cameras import CameraGroup

# measurements for the board! 
#   (make sure printed board matches and vice versa)
SQUARES_X = 7
SQUARES_Y = 5
SQUARE_LENGTH_M = 0.030   # one black/white square (in meters)
MARKER_LENGTH_M = 0.022   # ArUco marker inside square (in meters)
MARKER_BITS = 4
DICT_SIZE = 50


## function to create the board using above measurements!!
def make_board(square_length=SQUARE_LENGTH_M, marker_length=MARKER_LENGTH_M):
    return CharucoBoard(SQUARES_X, SQUARES_Y,
                        square_length=square_length, marker_length=marker_length,
                        marker_bits=MARKER_BITS, dict_size=DICT_SIZE)


# save a board image to print at 300 dpi, 100% scale, landscape on letter/A4
# at that size each square comes out SQUARE_LENGTH_M wide

# function to save the board image to print at:
#   300 dpi, 100% scale, and landscape on letter or A4 format
#   with each square being SQUARE_LENGTH_M wide
def save_board_image(path, dpi=300):
    pixels_per_square = round(SQUARE_LENGTH_M / 0.0254 * dpi)
    margin = pixels_per_square // 4

    board = make_board()
    
    # add the margin to the size so every square is exactly pixels_per_square
    size = (SQUARES_X * pixels_per_square + 2 * margin, SQUARES_Y * pixels_per_square + 2 * margin)
    image = board.board.generateImage(size, marginSize=margin)
    
    cv2.imwrite(str(path), image)
    return path


# function that takes in the motion capture videos, then calibrates cameras using board
def calibrate_from_board(videos, square_length=SQUARE_LENGTH_M, marker_length=MARKER_LENGTH_M):
    # creates board for calibration reference
    board = make_board(square_length, marker_length)

    cam_names = [f"cam{i}" for i in range(len(videos))] ## assigning camera names 0 to i-1 for each video
    cgroup = CameraGroup.from_names(cam_names)          ## assigning camera names to camera group

    # using aniposelib, it calibrates the videos 
    #   then returns reprojection error in pixels plus detected board points
    #   the lower, the better btw
    error, _ = cgroup.calibrate_videos([[str(v)] for v in videos], board, verbose=False)

    info = {
        "method": "charuco",
        "reprojection_error_px": float(error),
    }
    return cgroup, info


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ChArUco board calibration (fallback)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_board = sub.add_parser("make-board", help="save a printable board image")
    p_board.add_argument("out", help="output image path, e.g. board.png")

    p_cal = sub.add_parser("calibrate", help="calibrate cameras from board videos")
    p_cal.add_argument("videos", nargs="+", help="one board video per camera")
    p_cal.add_argument("--out", default="calibration.toml")
    p_cal.add_argument("--square-length", type=float, default=SQUARE_LENGTH_M)
    p_cal.add_argument("--marker-length", type=float, default=MARKER_LENGTH_M)

    args = parser.parse_args()

    if args.command == "make-board":
        save_board_image(args.out)
        print(f"Saved board to {args.out}")
    else:
        cgroup, info = calibrate_from_board(args.videos, args.square_length, args.marker_length)
        cgroup.dump(args.out)
        print(f"Saved calibration to {args.out} (reprojection error {info['reprojection_error_px']:.2f} px)")
