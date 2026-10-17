"""
Camera placement tool. Separate from the capture pipeline.

Method: Rahimian & Kearney 2015, "Optimal Camera Placement for Motion Capture
Systems in the Presence of Dynamic Occlusion", VRST, DOI 10.1145/2821592.2821596.

Two uses:
  metric.py  score an existing CameraRig (useful straight after calibration:
             "your coverage is poor on the left side").
  anneal.py  search for the best layout for N phones in a given room.

Quick use, from backend/ (a few seconds):

    from mocap_pipeline.placement import anneal, metric
    targets = metric.target_points_from_pose()            # grid; or pass a Pose3D from io.load_pose3d
    rig = anneal.optimise_layout(3, anneal.Constraints(), targets, iterations=500)
    print(metric.layout_cost(rig, targets), [metric.camera_centre(c) for c in rig.cameras])
"""
