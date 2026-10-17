# Legacy

Earlier code kept for reference. Nothing here is imported by the live pipeline (`backend/mocap_pipeline`), the API, or the tests, and nothing here is maintained.

| Folder | What it was | Superseded by |
|---|---|---|
| `landmarks_from_image_test/` | the first experiment (2026-09-29): MediaPipe on a single image, output to JSON | `mocap_pipeline/stage1_keypoints/` |
| `multicam_3d/` | the first standalone 2-to-4 camera pipeline (2026-10-04): MediaPipe per video, calibration from the performer, triangulation, smoothing | `mocap_pipeline/` stages 1 and 2, copied from here on 2026-10-04 and reworked since; each live file names the file it came from |

The MediaPipe model that `landmarks_from_image_test` shipped moved to `backend/models/pose_landmarker_heavy.task`, where `config.POSE_MODEL_PATH` points. The `multicam_3d` README describes how its files map onto the pipeline outline.

Delete a folder here when nobody has opened it in a term. History stays in git.
