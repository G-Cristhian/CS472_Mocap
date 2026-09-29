# Landmarking test via single image/frame
This test/demo is to ensure landmarks are being generated on an image

---
# Requirements

1. install uv to run main.py
    - get the lastest here: https://docs.astral.sh/uv/

2. install the Google MediaPipe PyPi package
    ```
    $ python -m pip install mediapipe
    ```

3. Ensure there is a model the detector can pull from in the `/models/` directory

4. Ensure there is a an image file in the `/random_media/` directory. .png/.jpg will work

5. Create a `.env` file and specify the locations of `/models/` and `/random_image/` files 

---
# Getting the landmarks
1. run main:
    ```
    $ uv run main.py
    ```

2. The output will be in `out.json` for x, y, and z coords along with the joint/body part it detected