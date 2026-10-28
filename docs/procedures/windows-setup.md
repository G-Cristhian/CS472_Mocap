# Setting up the pipeline on Windows

For a Windows laptop or desktop. The same steps as [mac-setup.md](mac-setup.md), with the commands Windows needs, in Windows PowerShell, the terminal built into Windows. Steps 1 to 4 and the desktop tester run locally; no server, no account. The web viewer in step 5 needs the Django backend and a login. The Python packages download once, so do this on a good connection.

Before step 1: Git for Windows is installed (`git --version` prints a version), and Node from https://nodejs.org if you will use the web viewer or the desktop tester.

## How Windows commands differ

The other procedures were written on a Mac. In Windows PowerShell five things change, and the pages that give commands now show the Windows form beside the Mac one.[^1]

| On a Mac page | In Windows PowerShell | Why |
|---|---|---|
| `cd backend` | `cd $HOME\CS472_Mocap\backend` | a new PowerShell window starts in your home folder, not in the repository |
| `source .venv/bin/activate`, then `python …` | `.venv\Scripts\python.exe …`, run from `backend` | the venv's own Python needs no activating, and activating runs a script PowerShell blocks by default |
| `npm …` | `npm.cmd …` | PowerShell blocks `npm` itself by default; `npm.cmd` is the same program |
| `a && b`, or a line ending in `\` | one command per line, written out in full | Windows PowerShell has no `&&`, and it continues a line with a backtick, not `\` |
| `take01/*.MOV take01/*.mp4` | `$videos`, listed as in "Giving the pipeline a take's videos" below | PowerShell does not expand `*` for programs, so Python would get a file name with `*` in it |

The paths here assume you clone into your home folder. If you clone somewhere else, use that path wherever these pages say `$HOME\CS472_Mocap`.

## 1. Python 3.12

```
py -3.12 --version
```

It should print `Python 3.12.` and a number. 3.10 to 3.12 work; 3.12 is what the project pins (mac-setup.md, footnote 1). If `py` is not recognised or has no 3.12, install Python 3.12 from https://www.python.org/downloads/windows/ and keep the "py launcher" option ticked.[^2]

## 2. Clone and create the environment

```
cd $HOME
git clone https://github.com/G-Cristhian/CS472_Mocap.git
cd $HOME\CS472_Mocap\backend
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r mocap_pipeline\requirements.txt -r requirements-api.txt pytest
```

The venv lives in `backend\.venv` and is ignored by git. Nothing needs activating: every Python command on these pages starts with `.venv\Scripts\python.exe` and runs from `backend`. Every dependency installs from a ready-made Windows wheel, so nothing is compiled.[^3]

If you would rather type plain `python` and `npm`, allow scripts for your account once with `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. After that `.venv\Scripts\Activate.ps1` activates the venv the way `source` does on a Mac.

## 3. Prove it works, no footage needed

```
cd $HOME\CS472_Mocap\backend
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m tests.evaluate_synthetic --quick
```

Every test should pass, in about a minute.[^4] The benchmark prints the table of errors described in mac-setup.md step 3; the first rows should show a calibration error under 1 px and MPJPE of a few millimetres. If both run, the pipeline is ready.

## 4. The pose model

The MediaPipe model ships in the repository and is the default, so nothing to download. To compare detectors ([comparing-pose-models.md](comparing-pose-models.md)), run RTMPose once while you have internet so it downloads its models into `$HOME\.cache\rtmlib`:[^5]

```
cd $HOME\CS472_Mocap\backend
.venv\Scripts\python.exe -c "from mocap_pipeline.stage1_keypoints.backends import create_backend; create_backend('rtmpose').close(); print('rtmpose ready')"
```

## 5. The web frontend and its backend

The web frontend talks to the Django backend (`backend\motionboxpro`), so start it first and leave its window open. It needs PostgreSQL, a `backend\.env` copied from `backend\.env_`, and the Django packages, set up as in the top-level README (Database Setup, .env, Project Setup); the Windows form of that install is `.venv\Scripts\python.exe -m pip install -r requirements.txt` from `backend`. Then:

```
cd $HOME\CS472_Mocap\backend
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py runserver
```

It answers on http://127.0.0.1:8000. Ctrl+C stops it.

The FastAPI server (`api.py`) is a separate take runner that the web frontend no longer calls. To run it on its own, on another port if Django is up:

```
cd $HOME\CS472_Mocap\backend
.venv\Scripts\python.exe -m uvicorn api:app --reload --port 8001
```

It prints `Application startup complete.` and answers on http://127.0.0.1:8001; http://127.0.0.1:8001/docs lists its routes.[^6] Ctrl+C stops it. Do not stop it, or edit a backend `.py` file (which makes `--reload` restart it), while a take is detecting: the detection processes would keep running on their own.[^7]

Then, in a second PowerShell window:

```
cd $HOME\CS472_Mocap\frontend
npm.cmd install
npm.cmd run dev
```

Open http://localhost:5173 and register an account, or log in. The frontend looks for the Django backend at http://localhost:8000 unless `frontend\.env` sets `VITE_DJANGO_URL` to something else.[^8] After a pull that adds packages to `frontend\package.json`, run `npm.cmd install` again before `npm.cmd run dev`; npm may end it with `npm warn allow-scripts`, and the install still completes.[^10]

## 6. The desktop tester

The desktop app runs the pipeline without the API or the web frontend: [desktop-tester.md](desktop-tester.md), with `npm.cmd` wherever it says `npm` and `cd $HOME\CS472_Mocap\desktop` to get to its folder.

## Giving the pipeline a take's videos

The Mac pages pass a take's videos as `../session/take01/*.MOV ../session/take01/*.mp4`. In PowerShell, list them into a variable, look at the list, then pass the variable:

```
cd $HOME\CS472_Mocap\backend
$videos = (Get-ChildItem ..\session\take01\* -Include *.MOV, *.mp4 | Sort-Object Name).FullName
$videos
.venv\Scripts\python.exe -m mocap_pipeline.check_videos $videos
```

The third line prints the list. Check it is in camera order, camera 0 first, before running anything: the files are sorted by name, and the camera number at the start of each name gives the order ([filming.md](filming.md), section 8). `-Include` matches `.MOV` and `.mov` alike and leaves out anything that is not a video. `$videos` lasts until the window is closed, so later commands in the same window can use it again; in a new window, set it again first.[^9]

## 7. On the day

- Check every take's files at the venue: [filming.md](filming.md), section 9.
- Process the takes afterwards: [processing-a-take.md](processing-a-take.md).

Both show the Windows commands next to the Mac ones.

## If something fails

| What PowerShell says | Why | What to do |
|---|---|---|
| `npm.ps1 cannot be loaded because running scripts is disabled on this system` | PowerShell blocks scripts by default | type `npm.cmd` instead of `npm` |
| `The token '&&' is not a valid statement separator in this version` | a line copied from a Mac page | run each part on its own line |
| `The module '.venv' could not be loaded` | the window is not in `backend`, or step 2 was not done | `cd $HOME\CS472_Mocap\backend`; if it still fails, do step 2 |
| `Could not read package.json` | npm was run outside `frontend` or `desktop` | `cd` to that folder by its full path first |
| `FAIL` and `cannot be opened as a video` for a path containing `*` | the `*` reached Python unexpanded | list the files into `$videos` as above |
| `py` is not recognised, or no Python 3.12 is found | Python is missing, or was installed without the launcher | install Python 3.12 (step 1) |
| `pip` cannot find a wheel | the venv was made with a Python outside 3.10 to 3.12 | delete `backend\.venv` and repeat step 2 with `py -3.12` |

---
## Sources

[^1]: Checked on 2026-10-20 on Windows 11, in a Windows PowerShell 5.1 session with the Restricted execution policy, started in the home folder: `npm --version` failed with the `npm.ps1` error while `npm.cmd --version` worked; `echo a && echo b` was rejected; `.venv\Scripts\python.exe` ran from `backend` without activation; and `check_videos` given `take01\*.MOV` received the name unexpanded and reported it could not be opened. Restricted is the default policy on Windows client editions (Microsoft Learn, about_Execution_Policies), and `&&` arrived in PowerShell 7 (Microsoft Learn, about_Pipeline_Chain_Operators).
[^2]: Python documentation, "Using Python on Windows", the Python install manager and launcher sections (https://docs.python.org/3/using/windows.html). On the machine this page was checked on, `py -3.12 --version` printed Python 3.12.10.
[^3]: Checked on 2026-10-20: in a fresh `py -3.12` venv, `pip install --dry-run` of the same three requirement lists resolved every package for Windows without building any from source. The project's own venv on that machine was installed with the same command.
[^4]: Measured on 2026-10-20 on the Windows laptop, in a Restricted PowerShell session, with exactly these commands: 124 tests passed in 44 s, and the quick benchmark finished in 26 s with 0.00 px and 0.7 mm in its first row.
[^5]: `rtmlib/tools/file.py`, `_get_rtmhub_dir`: the models go under `~/.cache/rtmlib`, which is the home folder on Windows too, unless the `TORCH_HOME` or `XDG_CACHE_HOME` environment variable is set.
[^6]: Checked on 2026-10-20, on port 8000 before the Django backend took it: started with this command, the API printed "Application startup complete." and answered `GET /takes` and `/docs` with HTTP 200.
[^7]: Since stage 1 detects the videos in their own processes (D-048), the API's shutdown stops the take's process but not those detection processes. Seen on 2026-10-19: two detection processes and their manager kept running for minutes after the API's take worker was stopped mid-detection.
[^8]: `frontend/src/lib/django.ts`, `DJANGO_URL`: `VITE_DJANGO_URL` if set, else `http://localhost:8000`. `frontend/src/lib/api.ts` reads `VITE_API_URL` the same way for the FastAPI server, but no routed page uses it.
[^9]: Checked on 2026-10-20 with a `.MOV`, an `.mp4` and a `.txt` file in one folder: `$videos` held the two videos in name order, and `check_videos $videos` read both.
[^10]: Checked on 2026-10-20, after the merge that added `@supabase/supabase-js` to the frontend: the package was missing from `frontend\node_modules` until `npm.cmd install` ran from a Restricted PowerShell. That install exited 0, printed the `allow-scripts` warning for esbuild and changed no tracked file, and the dev server then served the home page with no console errors.
