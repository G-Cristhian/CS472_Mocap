# Live motion capture: someone walks in and the skeleton moves at once

Status: idea noted 2026-10-19, not designed, not scheduled. Written so the
question is not lost; nothing here is a commitment.

## The wish

Today a take is filmed, copied to a laptop, and processed afterwards, minutes
per take. The wish is that a person steps into the capture area and their
skeleton appears on screen within a fraction of a second, continuously.

## What the pipeline already has that helps

- MediaPipe's pose detector has a live-stream mode (`LIVE_STREAM` in its
  running modes, with a callback per frame) built for exactly this. Our
  backend wraps it in video mode; switching the wrapper is small.
- Triangulation works one frame at a time already. Nothing in step 2c needs
  the future.
- The calibration file is reused between runs, so cameras that have not moved
  do not need to be calibrated again.
- The web viewer and the desktop tester both draw a skeleton; a live feed is
  a stream of the same frames.

## What stands in the way, roughly hardest first

1. **Getting live video from several phones into one computer at once.**
   This is the daunting part, not the maths. Phones do not stream video to a
   laptop out of the box. Options: webcams on USB (simplest, lower quality);
   phones running a streaming app (NDI or RTSP over Wi-Fi, latency and drops);
   Apple's Continuity Camera (one phone at a time on a Mac). Every option
   changes the "camera" in step 1 from a file to a live source with its own
   clock.
2. **Synchronisation without a clap.** The clap works because the whole
   recording is there to search. Live, each source needs timestamps on a
   shared clock, which USB webcams give and Wi-Fi phones give badly. Expect
   tens of milliseconds of uncertainty, which matters for fast motion.
3. **Calibration without a walk-around.** Our calibration needs the performer
   to move through the shared view first. Live, either calibrate once at setup
   with a person or a board and keep the cameras still, or calibrate on the
   first seconds and then switch to live.
4. **Scale and floor.** The height measurement needs the performer standing
   still for a moment; the floor needs their feet to have covered some area.
   Live, both can be done once at setup and kept.
5. **Smoothing that cannot see the future.** Both of our smoothers look at
   frames on both sides of the current one. Live needs a one-sided filter: a
   forward-only Butterworth adds lag, the "one euro" filter (Casiez et al.
   2012) is the usual choice for interactive tracking.
6. **Speed.** On a laptop processor the heavy MediaPipe model manages roughly
   10 to 20 frames per second for one stream; three or four streams at once
   need the lighter model, a graphics card, or both. See the hardware section
   of the backend outline: nothing uses a graphics card today.
7. **Delivery.** The skeleton frames go to the viewer over a websocket instead
   of a file; the BVH would be written at the end as a recording of the
   session.

## A staged way in, if it is ever picked up

1. One USB webcam, MediaPipe live mode, 2D skeleton drawn live. Proves the
   streaming wrapper and the viewer path. Days of work.
2. Two webcams, a stored calibration, live triangulation, one-euro smoothing.
   The first 3D result. A week or two.
3. Phones instead of webcams. Open-ended; depends entirely on item 1 above.

## Decisions this would force

Live source abstraction in step 1, a shared clock instead of the clap, a
causal smoother, and a websocket output. Each is a row on the decisions sheet
when it happens.
