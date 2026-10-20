# Hybrid Mocap — frontend

A navigable React prototype of every screen in `refs/Hybrid-Mocap-Screens.pdf`. Projects, cameras and
saved devices are mocked in `src/lib/data.ts`. Clips are those mock clips plus any uploaded to Supabase
(`src/lib/clips.ts`). The Footage page uploads raw camera videos to Supabase (`src/lib/footage.ts`) and
sends a set of them to the backend API as one take. Takes, their results and their 2D joints come from the
API (`src/lib/api.ts`), at `VITE_API_URL` or http://localhost:8000. Without `VITE_SUPABASE_URL` and
`VITE_SUPABASE_PUBLISHABLE_KEY` (see `.env.example`), uploads are off and only the mock clips show.

## Run it

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
```

On Windows, in PowerShell, start the API first ([windows-setup.md](../docs/procedures/windows-setup.md) step 5), then:

```
cd $HOME\CS472_Mocap\frontend
npm.cmd install
npm.cmd run dev
```

Other scripts: `npm run build` (production bundle into `dist/`), `npm run preview` (serve the
build), `npm run typecheck`. On Windows, type `npm.cmd` in place of `npm`.

## Screens

| Route | Deck page | What it covers |
| --- | --- | --- |
| `/` | 1–3 | Home. All three concepts from the deck, switchable in the “Home layout” strip: **A — Cards**, **B — Hero**, **C — Minimal**. Shareable as `/?layout=b`. |
| `/record` | 4 | Capture setup, camera monitor grid, connection alert, calibration toast. `Cameras` tab lists the rig. |
| `/projects` | 5 | Project browser with search, “only my projects”, sort, grid/list views. |
| `/projects/:projectId` | 6 | Project workspace: clip list, skeleton viewport, transport bar, and the Rig / Streaming / Export inspector. |
| `/library` | 7 | Motion Library with source filters and grid/list views. |
| `/settings/:section` | 8 | Settings. `accessibility` is the screen in the deck; `devices`, `calibration` and `api` are the other three sections in the sidebar. |

Anything not routed falls through to a friendly not-found page.

## 3D viewer (project workspace)

The viewport on `/projects/:projectId` is a three.js scene (`src/features/viewer/`, via @react-three/fiber and drei):

- Plays the pipeline's skeleton animation (`.bvh`, read with three's BVHLoader) or its raw 3D joints
  (`out3d.json`: MediaPipe's 33 landmarks, then RTMPose's head top, neck, mid-hip and small toes), over a floor grid. Drag to orbit, scroll to zoom.
- Opens `public/samples/sample_take.bvh` by default (made by `backend/mocap_pipeline` from simulated
  cameras). **Open .bvh / .json** (bottom right of the viewport) or drag a file onto it to play another take,
  e.g. `backend/output/out3d.bvh` or `backend/output/out3d.json`. A take processed by the API plays
  from its link, `/projects/:projectId?clip=<take id>`.
- The transport bar plays, pauses and scrubs the file; joints are coloured by rig part, the legend dims a
  source, and clicking a joint selects its rig part.
- The old 2D `SkeletonViewport.tsx` is kept (its colours are still used by the legend).
- Needs WebGL; without it the viewport shows a message instead of the scene.

## What is interactive

- Every nav link, card, breadcrumb and back link routes for real.
- **Record** — start/stop a take (the timer runs), switch Quad / Split / Single layouts, reconnect
  camera 3, dismiss the alert and the toast.
- **Project workspace** — pick a take, click a joint in the viewport or a part in the Rig list (they
  stay in sync), toggle the legend to dim a motion source, scrub and play the transport, add a take,
  switch to the Streaming and Export tabs.
- **Settings → Accessibility** — text size, letter/word spacing, line height, link underlines and
  reduced motion are applied live to every screen and persisted to `localStorage` on *Save changes*.
  “Freeze the 3D viewport” changes how the workspace viewport starts.
- **New project** creates a real (in-memory) project and opens its workspace.

## Layout of the code

```
src/
  app/          router, app shell, settings + studio state providers
  components/   TopNav, shared UI (buttons live in CSS, cards, badges, icons, modal/toast)
  features/     one folder per screen: home, record, projects, library, settings
  lib/data.ts   mock projects, clips, cameras, rig parts, devices
  styles/       tokens.css (colours, radii, accessibility variables) + global.css
  types/        shared types
```

Colours, radii and the accessibility variables all live in `src/styles/tokens.css` — change the
brand there, not in the feature files. The app name in the nav is still the deck’s `[APP NAME]`
placeholder (`src/components/layout/TopNav.tsx`).

## Not built yet

Live video in the camera tiles, a real 3D viewport (the skeleton is SVG), auth, and any backend
wiring.
