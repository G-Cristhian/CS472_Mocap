# Comparing pose models

How to decide between the stage 1 detectors on real footage. Today there are two, `mediapipe` (the default) and `rtmpose`; the same steps work for any model added to `backend/mocap_pipeline/stage1_keypoints/backends.py`[^1]. The outcome is a row on the design decisions sheet, so the choice is recorded with its evidence.

## 1. Pick the takes

Use at least three takes[^2] that passed `check_videos` and processed cleanly with the default detector ([processing-a-take.md](processing-a-take.md)): one calm take (walking, turning), one fast take (punches or kicks), one with partial occlusion (an arm hidden from a camera). A single take tells you about that take.

## 2. Run every detector into its own folder

Each detector gets its own output and calibration folder for every take. The folders must be separate: sync, calibration and the 3D result all depend on the 2D joints, so nothing from one detector's run may be reused by another[^3].

```
cd backend
source .venv/bin/activate
python -m mocap_pipeline.run_pipeline ../session/take03/*.MOV --height-m 1.78 \
    --out output/take03_mediapipe/out3d.json --calibration output/take03_mediapipe/calibration.json
python -m mocap_pipeline.run_pipeline ../session/take03/*.MOV --height-m 1.78 --detector rtmpose \
    --out output/take03_rtmpose/out3d.json --calibration output/take03_rtmpose/calibration.json
```

On Windows, in PowerShell ([windows-setup.md](windows-setup.md)):

```
cd $HOME\CS472_Mocap\backend
$videos = (Get-ChildItem ..\session\take03\* -Include *.MOV | Sort-Object Name).FullName
.venv\Scripts\python.exe -m mocap_pipeline.run_pipeline $videos --height-m 1.78 --out output\take03_mediapipe\out3d.json --calibration output\take03_mediapipe\calibration.json
.venv\Scripts\python.exe -m mocap_pipeline.run_pipeline $videos --height-m 1.78 --detector rtmpose --out output\take03_rtmpose\out3d.json --calibration output\take03_rtmpose\calibration.json
```

RTMPose downloads its models on the first run (`~/.cache/rtmlib`, which is `$HOME\.cache\rtmlib` on Windows)[^4], so run it once with internet before the session.

## 3. Compare the numbers

Open each run's `out3d.metrics.json` and put these side by side, per take:

| Key | Comparable across models? | What a better model shows |
|---|---|---|
| `calibrate.reprojection_error_px` | yes | lower: the 2D joints agree better with the geometry |
| `triangulate.mean_reprojection_px` and `_per_joint` | yes | lower, and lower on the joints that matter for the use (wrists, ankles) |
| `triangulate.views_dropped`, `joints_failed` | yes | fewer: fewer mis-detections that the other cameras had to outvote |
| `pose_final.missing_fraction` and `_per_joint` | yes, over the joints each model has (joints a model never gives are null, not missing) | lower: fewer frames where a joint was seen by under two cameras |
| `rig.bone_lengths.mean_std_m` and `per_bone` | yes, except the Head bone: RTMPose's comes from its detected top of the head, MediaPipe's from the ears | lower: steadier joints over time |
| `timing.detect.<camera>` | yes | faster, if the quality is equal |
| `stage1.<camera>.mean_confidence` | **no** | each model scores on its own scale; RTMPose scores are clipped to 0..1 and are not probabilities[^5]. Do not rank models on this. |
| `stage1.<camera>.no_person_fraction` | mostly | a model that loses the person in frames the other keeps is worse, unless those frames had nobody in them |

Reprojection error and bone-length variability are the two measures the literature uses when there is no ground truth[^6] (Karashchuk et al. 2021, DOI 10.1016/j.celrep.2021.109730). A model can win on one and lose on the other; say which matters for the use.

## 4. Compare by eye

Open both `out3d.bvh` files in the viewer, same take, and watch the fast moments and the occluded moments. Note what the numbers did not say: a joint that flips left and right, a foot that slides, a head that nods on its own.

## 5. Record the decision

Add a row to `docs/decisions/DECISIONS.md` with Lineage `from D-005`[^7] (MediaPipe as the default) and, if the choice is RTMPose, also `from D-007`. The rationale is the table from step 3 for the takes used, plus the step 4 notes. Cite the model's paper (BlazePose, arXiv:2006.10204; RTMPose, arXiv:2303.07399).[^8] Status is `cited, pending review` until a second person has looked at the numbers.

If the verdict is "it depends on the take", that is also a decision: record which detector is the default and when to switch, and open an issue for a per-joint fusion of the two: triangulate each detector's joints separately and keep, per frame and joint, the point with the lower reprojection error.

## 6. Keep the evidence

Keep both output folders for the takes used and the side-by-side table, so the comparison can be rerun when a third model arrives or a detector is updated. The `--resume` machinery re-detects when the detector name changes, but not when the same detector's version changes[^9], so note the package versions (`pip show mediapipe rtmlib`) in the session log.

---
## Sources

[^1]: `PoseBackend` and the `BACKENDS` registry in `backends.py` (pull request #27, Lucas, 2026-10-14). MediaPipe as the default is D-005; RTMPose is D-007.
[^2]: Three takes with different motion is team judgement; one take measures that take. Team judgement, no source. A candidate row for `docs/decisions/DECISIONS.md`.
[^3]: `backend/mocap_pipeline/README.md`, "Choosing the pose model": give each detector its own `--out` and `--calibration`, otherwise the first detector's calibration is reused. Keypoint files record the detector that made them (D-023).
[^4]: `RTMPoseBackend` docstring in `backends.py`; rtmlib fetches ONNX weights on first use (https://github.com/Tau-J/rtmlib).
[^5]: `halpe26_to_joints` docstring in `backends.py`: RTMPose scores are clipped to 0..1 so the config thresholds can be applied, but those thresholds were tuned on MediaPipe's visibility (D-007, D-014).
[^6]: Karashchuk et al., "Anipose: A toolkit for robust markerless 3D pose estimation", *Cell Reports* 36(13), 2021, DOI 10.1016/j.celrep.2021.109730, which evaluates its filters by reprojection error and limb-length variation. Reprojection error as a geometric quality measure: Zhang 2000, DOI 10.1109/34.888718.
[^7]: Lineage rules in `docs/decisions/README.md`: a decision that replaces another names it with `from`, one layer deep.
[^8]: Bazarevsky et al., "BlazePose: On-device Real-time Body Pose tracking", arXiv:2006.10204, 2020. Jiang et al., "RTMPose: Real-Time Multi-Person Pose Estimation based on MMPose", arXiv:2303.07399, 2023. Both unverified DOIs: arXiv preprints.
[^9]: The keypoints fingerprint stores the video size and modification time and the detector name only (`run_pipeline.py`, `io.save_keypoints`); D-023 notes the missing mode and version.
