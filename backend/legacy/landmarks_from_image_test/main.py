import os
from dotenv import load_dotenv
from get_image import get_image_mp
from detector import detector
from landmarks import LandMarks
import json

load_dotenv()
FILE_PATH = os.path.expanduser(os.getenv('IMAGE_FILEPATH', ''))
MODEL_PATH = os.path.expanduser(os.getenv('MODEL_FILEPATH', ''))

try:
    image = get_image_mp(FILE_PATH)

    # .detect method will detect the image the grab the landmarks into a list
    with detector(MODEL_PATH) as landmarker:
        detection_result = landmarker.detect(image)

    results = detection_result.pose_landmarks

    landmark_dict = {}

    for result in results:
        for i, r in enumerate(result):
            
            landmark_dict[LandMarks(i).name] = {'x': r.x, 'y': r.y, 'z': r.z}
            
            # print(f"{LandMarks(i).name}:")
            # print(f"    x: {r.x}")
            # print(f"    y: {r.y}")
            # print(f"    z: {r.z}")

    json_string = json.dumps(landmark_dict, indent=4)

    with open("out.json", "w") as f:
        json.dump(landmark_dict, f, indent=4)


except Exception as e:
    print(f"Error: {e}")
