# Comparing pose models

How to decide between the stage 1 detectors on real footage. Today there are two, `mediapipe` (the default) and `rtmpose`; the same steps work for any model added to `backend/mocap_pipeline/stage1_keypoints/backends.py`. The outcome is a row on the design decisions sheet, so the choice is recorded with its evidence.

## 1. Pick the takes

Use at least three takes that passed `check_videos` and processed cleanly with the default detector ([processing-a-take.md](processing-a-take.md)): one calm take (walking, turning), one fast take (punches or kicks), one with partial occlusion (an arm hidden from a camera). A single take tells you about that take.

## 2. Run every detector into its own folder

Each detector gets its own output and calibration folder for every take. The folders must be separate: sync, calibration and the 3D result all depend on the 2D joints, so nothing from one detector's run may be reused by another.

```
cd backend
source .venv/bin/activate
python -m mocap_pipeline.run_pipeline ../session/take03/*.MOV --height-m 1.78 \
    --out output/take03_mediapipe/out3d.json --calibration output/take03_mediapipe/calibration.json
python -m mocap_pipeline.run_pipeline ../session/take03/*.MOV --height-m 1.78 --detector rtmpose \
    --out output/take03_rtmpose/out3d.json --calibration output/take03_rtmpose/calibration.json
```

RTMPose downloads its models on the first run (`~/.cache/rtmlib`), so run it once with internet before the session.

## 3. Compare the numbers

Open each run's `out3d.metrics.json` and put these side by side, per take:

| Key | Comparable across models? | What a better model shows |
|---|---|---|
| `calibrate.reprojection_error_px` | yes | lower: the 2D joints agree better with the geometry |
| `triangulate.mean_reprojection_px` and `_per_joint` | yes | lower, and lower on the joints that matter for the use (wrists, ankles) |
| `triangulate.views_dropped`, `joints_failed` | yes | fewer: fewer mis-detections that the other cameras had to outvote |
| `pose_final.missing_fraction` and `_per_joint` | yes | lower: fewer frames where a joint was seen by under two cameras |
| `rig.bone_lengths.mean_std_m` and `per_bone` | yes | lower: steadier joints over time |
| `timing.detect.<camera>` | yes | faster, if the quality is equal |
| `stage1.<camera>.mean_confidence` | **no** | each model scores on its own scale; RTMPose scores are clipped to 0..1 and are not probabilities. Do not rank models on this. |
| `stage1.<camera>.no_person_fraction` | mostly | a model that loses the person in frames the other keeps is worse, unless those frames had nobody in them |

Reprojection error and bone-length variability are the two measures the literature uses when there is no ground truth (Karashchuk et al. 2021, DOI 10.1016/j.celrep.2021.109730). A model can win on one and lose on the other; say which matters for the use.

## 4. Compare by eye

Open both `out3d.bvh` files in the viewer, same take, and watch the fast moments and the occluded moments. Note what the numbers did not say: a joint that flips left and right, a foot that slides, a head that nods on its own.

## 5. Record the decision

Add a row to `docs/decisions/DECISIONS.md` with Lineage `from D-005` (MediaPipe as the default) and, if the choice is RTMPose, also `from D-007`. The rationale is the table from step 3 for the takes used, plus the step 4 notes. Cite the model's paper (BlazePose, arXiv:2006.10204; RTMPose, arXiv:2303.07399). Status is `cited, pending review` until a second person has looked at the numbers.

If the verdict is "it depends on the take", that is also a decision: record which detector is the default and when to switch, and open an issue for a per-joint fusion of the two: triangulate each detector's joints separately and keep, per frame and joint, the point with the lower reprojection error.

## 6. Keep the evidence

Keep both output folders for the takes used and the side-by-side table, so the comparison can be rerun when a third model arrives or a detector is updated. The `--resume` machinery re-detects when the detector name changes, but not when the same detector's version changes, so note the package versions (`pip show mediapipe rtmlib`) in the session log.
