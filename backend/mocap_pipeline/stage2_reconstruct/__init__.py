# Outline file copied from mocap_pipeline, no legacy/multicam_3d code
"""
Stage 2: the maths. 2D joints from several cameras in, 3D joints out.
Run order: sync -> calibrate -> scale_floor -> triangulate -> smooth.
"""
