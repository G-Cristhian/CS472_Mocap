# CS472_Mocap — Design Spec
_Last updated: 2026-10-14. Approved by Cristhian before writing._

This is the single source of truth for the app's visual design. It supersedes the original
`frontend/refs/Hybrid-Mocap-Screens.pdf`. Features marked **[planned]** are out of scope for this
semester; Snake must not build them now but may stub them with a visible placeholder.

---

## Colors

| Token | Hex | Job |
|---|---|---|
| `--purple` | `#6D4AFF` | Primary brand; CTA buttons, active nav underline, focus rings |
| `--purple-strong` | `#5B34F0` | Button hover/pressed state |
| `--purple-soft` | `#8B6DFF` | Secondary accent (links in copy, inline badges) |
| `--blue` | `#5B8CFF` | Informational; Processing status badge |
| `--pink` | `#E31C79` | Recording/live indicator dot only |
| `--orange` | `#F26722` | Warnings, Failed status badge |
| `--green` | `#16A34A` | Done/success status badge |
| `--purple-50` | `#EEEBFF` | Project thumbnail background (default) |
| `--blue-50` | `#E8EFFD` | Project thumbnail background (alt) |
| `--pink-50` | `#FDECF3` | Project thumbnail background (alt) |
| `--orange-50` | `#FDEFE2` | Project thumbnail background (alt) |
| `--ink` | `#0B0B12` | All body text, headings |
| `--ink-2` | `#2B2B38` | Secondary text (take names in sidebar, labels) |
| `--muted` | `#6B6B7B` | Supporting text (metadata: clip count, date) |
| `--muted-2` | `#9A9AA8` | Decorative only — never use for text the user must read (fails AA) |
| `--line` | `#E4E4EC` | Borders, dividers |
| `--line-soft` | `#F0F0F5` | Subtle row separators |
| `--surface` | `#FFFFFF` | Page background |
| `--surface-2` | `#F7F7FA` | Sidebar, secondary panels |
| `--viewport` | `#0A0A0C` | 3D viewer background |
| `--viewport-2` | `#15151C` | Viewer side panel background |

**WCAG AA contract** (enforce on every new element):
- Body text (≥16px, normal weight): minimum 4.5:1 contrast against its background.
- Large text (≥24px, or ≥18.67px bold): minimum 3:1.
- `--muted` (#6B6B7B) on white passes at ~4.8:1. Use freely for metadata.
- `--muted-2` (#9A9AA8) on white is ~2.6:1 — **decorative only**, never for readable text.
- White on `--purple` (#6D4AFF) passes at ~9:1. Use for primary button labels.

---

## Fonts

**Family:** Plus Jakarta Sans (Google Fonts, free). Fallback: `ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif`.

| Role | Size | Weight |
|---|---|---|
| Page heading (H1) | 32px | 700 |
| Section heading (H2) | 24px | 700 |
| Sub-heading (H3) | 18px | 600 |
| Body | 16px | 400 |
| Label / small | 14px | 500 |
| Caption | 12px | 400 — decorative only, not for essential info |

Mono font (file names, error codes): JetBrains Mono. Fallback: `ui-monospace, Menlo, monospace`.

---

## Spacing

One scale. Use nothing else.

`4 / 8 / 12 / 16 / 24 / 32 / 48 / 64px`

- **4px** — icon-to-label gap, tight badge padding
- **8px** — inner card padding (top/bottom), row gaps in lists
- **12px** — inner card padding (sides), input padding
- **16px** — section gap, form field gap, nav item spacing
- **24px** — card gap in a grid, panel internal padding
- **32px** — page section spacing
- **48px** — large section breaks, page top padding
- **64px** — page horizontal padding at full width

---

## Components

### Buttons

| Variant | Background | Text | Border | Radius | Min height |
|---|---|---|---|---|---|
| Primary | `--purple` | white | none | pill (999px) | 44px |
| Secondary | `--surface` | `--ink` | 1px `--line` | pill | 44px |
| Destructive | `#DC2626` | white | none | pill | 44px |

- Hover: Primary → `--purple-strong`. Secondary → `--surface-2`. Destructive → `#B91C1C`.
- Disabled: `--surface-2` bg, `--muted-2` text, `cursor: not-allowed`.
- Padding: 16px horizontal minimum. Icon + label: 8px gap.

### Inputs and selects

- Height: 48px. Padding: 12px horizontal.
- Border: 1px `--line`. Radius: `--r-md` (12px).
- Focus: 2px outline `--purple`, offset 2px.
- Error state: border `--orange`, error message in 14px `--orange` below the field.
- File picker: styled as a secondary button with a dashed border (`--line-soft`) and a drop-zone area.

### Cards (project cards)

- Background: white. Radius: `--r-lg` (16px). Shadow: `--shadow-sm`.
- Thumbnail area: colored tint background (rotate through `--purple-50`, `--blue-50`, `--pink-50`, `--orange-50`), stick figure illustration centered.
- Below thumbnail: project name (16px, weight 600), category + take count in `--muted` (14px), last-updated in `--muted` (14px).
- Hover: `--shadow-md`.
- **No AI/Suit badge.** The old color-coded badges are removed.

### Status badges (take processing state)

| State | Background | Text color |
|---|---|---|
| Queued | `--surface-2` | `--muted` |
| Processing | `--blue-50` | `--blue` |
| Done | `#DCFCE7` | `#16A34A` |
| Failed | `--orange-50` | `--orange` |

Radius: pill. Padding: 4px 10px. Font: 13px, weight 600.

### Top nav

- White background, 1px `--line` bottom border. Height: 56px.
- Logo + app name: left.
- Nav links (Home, Upload, Projects, Settings): centered. Active: `--ink` color, 2px `--purple` underline.
- At ≤768px: nav links collapse into a hamburger menu (slide-in drawer). Logo stays visible.

---

## Layout

- **Max content width:** 1280px, centered with auto horizontal margins.
- **Page horizontal padding:** 64px at 1440px, 32px at 768px, 16px at 390px.
- **Project grid:** 4 columns at ≥1024px, 2 columns at 768–1023px, 1 column at <768px. Gap: 24px.
- **Tap targets:** every interactive element at least 44×44px. This applies to buttons, list rows, nav links, and delete icons.
- **Mobile stack order for Project detail:** viewer (full width) → take list → export panel.

---

## Screens

### Home

- Page heading: "Recent projects" (or a welcome line with today's date — match the existing code).
- Two buttons: "New upload" (primary) + "New project" (secondary).
- Recent projects grid (up to 4 cards). "View all projects" link → Projects page.
- **Remove:** suit calibration status bar ("Skeleton calibrated from Suit A · Recalibrate"). The pipeline has no suit.
- Phone: stack buttons above the project list. 1-column grid.

### Upload _(replaces the old Record screen — the nav label is "Upload")_

Two-pane layout at desktop. Single-column stack on phone.

**Left / top pane — form:**
- Take name (text input, required)
- Performer height (number input with unit selector cm/ft, required — the pipeline uses this for scale)
- Video files (file picker, accepts `.mp4 .mov .avi`, 2–4 files required; show a clear "2–4 videos" label and count the selected files)
- "Start processing" button (primary, full-width, disabled until name + height + 2–4 files are chosen)

**Right / bottom pane — processing status** (shown after submit, replaces the form):
- Take name as heading.
- Step indicator, linear:
  1. Queued
  2. Detecting poses
  3. Calibrating cameras
  4. Solving 3D
  5. Done / Failed
- Active step: `--blue` text. Completed: `--green` with check. Failed: `--orange` with ✕.
- On Done: "View take →" link to the take in Projects. On Failed: error message (plain text from the API) and a "Try again" link back to the form.
- Status auto-refreshes every 5 seconds while processing.

### Projects

- Page heading: "Projects". "New project" button (secondary, top right).
- Search input (full-width on phone).
- Project grid (see Layout).
- **No AI/Suit badge on cards.**

### Project detail

Three-panel layout at desktop. Stacked on phone (viewer → take list → export).

**Left sidebar:**
- Takes list. Each row: take name, duration (if done), status badge, delete button (destructive, requires confirmation).
- "New upload" shortcut button at bottom.

**Main panel:**
- 3D skeleton viewer (dark `--viewport` background). Playback bar at bottom: play/pause, scrubber, timestamp.
- "Take not found" empty state when no take is selected.

**Right panel — Take info:**
- Section heading: take name.
- Metadata table (key: value rows):
  - Cameras: number (e.g. "3")
  - Frame rate: fps (e.g. "60 fps")
  - Calibration error: in **pixels** (e.g. "2.4 px")
  - Duration: seconds
  - Status: status badge
- **Export section:** two buttons, stacked:
  - "Download BVH" (primary)
  - "Download JSON" (secondary) — downloads `out3d.json` from the pipeline
- **Remove:** Rig tab, Streaming tab, FBX export, per-joint confidence panel.

### Motion Library _[planned]_

Nav item stays in the top nav but is visually disabled (muted text, no hover effect, `cursor: not-allowed`). Clicking it shows a full-page placeholder: "Motion Library — coming in a future update." No clips, no filter chips.

### Settings

Keep **Accessibility** tab only (it's already built and real):
- Interface animation (full / reduced / none)
- Sound settings (tone at start/end of take, error sounds, volume)
- Text and spacing (size, letter spacing, word spacing, line height, underline links)

**Remove:** Saved devices, Scene calibration, API and integrations. These are suit-specific and don't apply to this pipeline. If the settings sidebar is still visible, show only the Accessibility item.

---

## Do / Don't

**Do:**
- Use the spacing scale. No arbitrary pixel values.
- Keep text/background pairs above 4.5:1. Run a quick contrast check on any new pairing.
- Use status badges on every take row — the user needs to know what's processing vs. done.
- Keep the 3D viewer background `--viewport` (near-black). Light backgrounds wash out the skeleton.
- Show real numbers (cameras, fps, calibration error in px) wherever the API returns them.

**Don't:**
- Add Suit/AI/Review color-coded badges anywhere. The pipeline doesn't produce this data.
- Use `--muted-2` for text the user needs to read.
- Build the Rig tab, Streaming tab, or FBX export — they're out of scope.
- Use arbitrary colors outside this palette. Propose an addition here before using it.
- Break the 44px tap target rule on mobile.
