# Hybrid Mocap — frontend

A navigable React prototype of every screen in `refs/Hybrid-Mocap-Screens.pdf`. Cameras, rig parts,
saved devices and seed recordings are mocked in `src/lib/data.ts`. Login, projects, motions, their versions
and uploaded recordings come from the Django API (`src/lib/auth.ts`, `projects.ts`, `motions.ts`,
`recordings.ts`), at `VITE_DJANGO_URL` or http://localhost:8000. The Supabase upload code
(`src/lib/clips.ts`, `src/lib/footage.ts`) and the Footage page are still in the tree but no route opens them.

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
| `/` | 1–3 | Landing page for visitors; a logged-in user skips it. |
| `/login`, `/register`, `/forgot-password`, `/reset-password/:uid/:token` | — | Auth pages, against the Django accounts API. |
| `/streaming` | 4 | Capture setup, camera monitor grid, connection alert. `Cameras` tab lists the rig. |
| `/projects` | 5 | Project cards and a New project dialog. |
| `/projects/:projectId` | 6 | One project's motions and a New motion dialog. |
| `/motions/:motionId` | 6 | Motion workspace: its recordings and performers, the processing panel, versions, skeleton viewport, transport bar, and the Rig / Cameras / Streaming / Export inspector. |
| `/motions` | 7 | Every motion across all projects. |
| `/recordings` | — | The user's recordings, with upload. `/recordings/new` records from one camera; `/recordings/:recordingId` plays one. `/record` redirects to `/recordings/new`. |
| `/settings/:section` | 8 | Settings. `accessibility` is the screen in the deck; `devices`, `calibration` and `api` are the other three sections in the sidebar. |

Every route except `/` and the auth pages needs a logged-in user. Anything not routed falls through to a friendly not-found page.

## 3D viewer (motion workspace)

The viewport on `/motions/:motionId` is a three.js scene (`src/features/viewer/`, via @react-three/fiber and drei):

- Plays the pipeline's skeleton animation (`.bvh`, read with three's BVHLoader) or its raw 3D joints
  (`out3d.json`, 33 MediaPipe landmarks), over a floor grid. Drag to orbit, scroll to zoom.
- Shows the chosen version's `.bvh` once that version has rendered, and its status until then.
  **Open .bvh / .json** (bottom right of the viewport) or drag a file onto it to play another take,
  e.g. `backend/output/out3d.bvh`, `backend/output/out3d.json`, or the test file
  `public/samples/sample_take.bvh` (made by `backend/mocap_pipeline` from simulated cameras).
- The transport bar plays, pauses and scrubs the file; joints are coloured by rig part, the legend dims a
  source, and clicking a joint selects its rig part.
- The old 2D `SkeletonViewport.tsx` is kept (its colours are still used by the legend).
- Needs WebGL; without it the viewport shows a message instead of the scene.

## What is interactive

- Every nav link, card, breadcrumb and back link routes for real.
- **Streaming** — start/stop a take (the timer runs), switch Quad / Split / Single layouts, reconnect
  camera 3, dismiss the alert.
- **Motion workspace** — pick a version, click a joint in the viewport or a part in the Rig list (they
  stay in sync), toggle the legend to dim a motion source, scrub and play the transport, add a recording,
  switch to the Cameras, Streaming and Export tabs.
- **Settings → Accessibility** — text size, letter/word spacing, line height, link underlines and
  reduced motion are applied live to every screen and persisted to `localStorage` on *Save changes*.
  “Freeze the 3D viewport” changes how the workspace viewport starts.
- **New project** creates a project through the Django API and opens it.

## Layout of the code

```
src/
  app/          router, app shell, settings + studio state providers
  components/   TopNav, shared UI (buttons live in CSS, cards, icons, modal)
  features/     one folder per screen: landing, auth, projects, motions, library (recordings list),
                recordings, streaming, settings, footage (not routed); home holds the not-found page
  lib/          API clients: Django (auth, projects, motions, recordings, performers), api.ts, Supabase
  lib/data.ts   mock cameras, rig parts, devices, seed recordings
  styles/       tokens.css (colours, radii, accessibility variables) + global.css
  types/        shared types
```

Colours, radii and the accessibility variables all live in `src/styles/tokens.css` — change the
brand there, not in the feature files. The app name is MotionBoxPro. It appears in the nav
(`src/components/layout/TopNav.tsx`), the auth pages, and the page title in `index.html`. The logo
mark is `LogoMark` in `src/components/ui/Icons.tsx`. The same design is saved as `public/logo.svg`
and `public/favicon.svg`.

## Not built yet

Live video in the camera tiles.
