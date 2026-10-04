"""
Camera placement tool. Separate from the capture pipeline; build this last.

Method: Rahimian & Kearney 2015, "Optimal Camera Placement for Motion Capture
Systems in the Presence of Dynamic Occlusion", VRST, DOI 10.1145/2821592.2821596.

Two uses:
  metric.py  score an existing CameraRig (useful straight after calibration:
             "your coverage is poor on the left side").
  anneal.py  search for the best layout for N phones in a given room.
"""
