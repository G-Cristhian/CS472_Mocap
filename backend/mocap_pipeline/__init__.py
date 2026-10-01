"""
mocap_pipeline: phone videos in, skeleton rig file out.

Data flow (each arrow is a file format defined in schemas.py):

    videos (one per phone, each starting with a clap)
      |  stage1_keypoints.detect
      v
    Keypoints2D            one per camera: 2D joints + confidence per frame
      |  stage2_reconstruct.sync
      v
    SyncResult             time offset of every camera relative to camera 0
      |  stage2_reconstruct.calibrate   (Liu et al. 2022, DOI 10.1049/cvi2.12130)
      |  stage2_reconstruct.scale_floor
      v
    CameraRig              lens model + position/orientation of every camera
      |  stage2_reconstruct.triangulate
      |  stage2_reconstruct.smooth
      v
    Pose3D                 3D joint positions per frame, metres, Y up
      |  stage3_rig.skeleton -> rotations -> bvh_writer
      v
    .bvh file

    placement/             separate tool (Rahimian & Kearney 2015,
                           DOI 10.1145/2821592.2821596). Not part of the main
                           flow; scores a CameraRig and suggests placements.

Rules for anyone filling in a module:
  * A stage only talks to its neighbours through the dataclasses in schemas.py.
    Never import one stage's internals from another stage.
  * Tunable numbers go in config.py, not inline.
  * Every stub raises NotImplementedError and lists its steps as TODOs.
    Replace the raise, keep the signature.

Expected dependencies (not pinned yet): numpy, opencv-python, mediapipe, scipy.
Entry point: python -m mocap_pipeline.run_pipeline --help   (run from backend/)
"""
