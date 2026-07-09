# StentorCam

Downstream analysis pipeline for *Stentor* (single-cell ciliate) tracking and
behavior quantification, consuming video recorded by
[RoboCam 3.1](https://github.com/dairyking98/RoboCam3.1) (and its
predecessors). This document describes the repository **as currently
uploaded** — it is a snapshot for orientation, not a design spec. Nothing
here has been reorganized or fixed yet; see the "Known gaps" section below
for what's rough.

There is no `pyproject.toml`, environment file, or test suite in the repo
yet. A `requirements.txt` and `setup.sh`/`run.sh` convenience scripts now
exist (see "Setup" below); the dependency list in them is still inferred
from each script's imports, not pinned to versions known to work.

---

## Setup

```
bash setup.sh          # creates .venv, installs requirements.txt, checks for ffmpeg
source .venv/bin/activate
bash run.sh <script.py> [args...]     # or just: python <script.py> [args...]
```

`setup.sh` does not install Fiji/ImageJ, TrackMate, or `ffmpeg` itself —
`ffmpeg` must already be on `PATH` (`stentTrack.py` and `multiTest.py` both
shell out to it to composite the overlay video; without it they will run
tracking to completion and then fail at the final compositing step). Fiji
is a separate GUI application only needed for `stentor_preprocess.ijm`, see
that workflow below.

There is no single "start" script — this repo is a set of independent CLI
tools, not one long-running app — so `run.sh` is a thin wrapper that
activates `.venv` and forwards its arguments to `python`. See "Usage" below
for the exact invocation each script expects.

---

## Two independent workflows

The repo currently contains **two separate, non-interoperating** tracking
pipelines. Nothing here converts one workflow's output into the other's
input format.

### 1. Fiji / TrackMate workflow (semi-manual)

```
video frames (PNG sequence)
  → stentor_preprocess.ijm   (Fiji macro: median-projection background
                               subtraction, Otsu binarization, manual
                               TrackMate detection/tracking pause)
  → per-track CSV export from TrackMate (one or more CSV files)
  → csv_compiler.py           (merge many CSVs into one, reassigning
                               track ids sequentially)
  → full_data_plot.py / track_plot.py   (population or per-track speed
                               plots)
```

- **`stentor_preprocess.ijm`** — Fiji/ImageJ macro. Loads a PNG frame
  sequence (hardcodes the first frame's name as `frame0001.png`), converts
  to 8-bit, computes a median-intensity projection as background, subtracts
  it, and launches TrackMate. The macro **pauses twice** for a human: once
  to manually tune TrackMate's detector and run tracking (`waitForUser`),
  and once after a *second* background subtraction + Otsu threshold to save
  the resulting binary mask by hand. Not automatable in its current form.
- **`csv_compiler.py`** — merges every CSV in a folder into one, matching
  columns via a small alias table (`track id`/`trackid`/`id`,
  `x`/`position_x`, `y`/`position_y`, `t`/`frame`/`time` — i.e. built for
  TrackMate/Fiji's export headers). Renumbers to a `new_track_id` every time
  the source `track id` changes, to keep tracks from different files or
  different segments distinct. Rows with a non-numeric track id are
  silently dropped.
- **`full_data_plot.py`** — reads a single compiled CSV (`-i`), assuming the
  Fiji export's layout: skips the first **4 lines** unconditionally, then
  reads columns by **fixed position** (`x`=index 1, `y`=index 2, `frame`=
  index 3, `track_id`=index 4), not by header name. Computes per-frame
  speed for every track, plots the population mean ± 1 SD and a
  frame-window sliding average, with a light/laser-color-coded shaded
  region assumed at frames 900–1800 (i.e. a fixed 30/30/30 s pre/on/post
  laser structure at 30 fps → 2700 total frames = 90 s).
- **`track_plot.py`** — same CSV format assumption as above, but plots up to
  5 individually-named tracks (`-s1`..`-s5`, each a comma-separated list of
  track ids to stitch together) side-by-side: raw trail, inverted-axis
  "expanded" trail, and per-track speed, plus the same population-average
  panels as `full_data_plot.py`. Includes a hardcoded reference circle
  (assumed well boundary) and a hardcoded 1 mm scale bar position, both
  tuned to one specific camera/zoom setup.

Both plotting scripts hardcode the same speed conversion:
`dist_px / dt_frames * 30 / 56.25` → mm/s, i.e. **30 fps and 56.25 px/mm
are assumed constants**, not derived from the input data or CLI arguments.
Both also hardcode the 2700-frame (90 s) timeline in axis limits and the
laser on/off shading. Any recording at a different frame rate, duration, or
camera zoom needs these constants hand-edited before the plots are
meaningful.

### 2. Standalone Python/OpenCV workflow (automatic)

```
video (mp4)                                    → CSV + ffmpeg overlay video
  → stentTrack.py   (single cell)
  → multiTest.py    (multiple cells)

  -- or, reading a RoboCam 3.1 experiment directory directly --

RoboCam 3.1 <exp_dir>/raw/*.npy (via robocam_input.py, one invocation
  batches every well found)                    → per-well CSV + overlay video
  → stentTrack.py --exp_dir
  → multiTest.py  --exp_dir
```

- **`stentTrack.py`** — single-stentor tracker. Per video: computes a
  median-frame background, then per frame does background subtraction →
  percentile threshold → largest contour → ellipse-fit to classify pose as
  `CONTRACTED` or `ELONGATED` (contour-to-ellipse fit error above/below a
  threshold) → for elongated cells, fits a minimum enclosing triangle and
  scores its three edges (by length dominance vs. alignment with recent
  motion direction) to pick a head edge / tail point, with a
  low-confidence fallback that re-scores assuming backward motion. Writes
  one CSV row per frame (`frame, x, y, pose, movement, direction_deg,
  contour`) and a debug overlay video (contour, pose box/triangle,
  head/tail markers, motion arrow) composited over the source video via a
  `subprocess` call to `ffmpeg`. Several `#debugging` comments mark
  in-progress tuning code the file's own docstring says not to treat as
  load-bearing.
- **`multiTest.py`** — despite the filename, its own header docstring names
  it `contour_video.py`; this mismatch is real and worth fixing/renaming
  once the file's identity settles. The most substantial file in the repo:
  a multi-cell tracker with a real correction pipeline —
  1. **Pass 1 (detection)**: background subtraction (with an optional
     circular ROI mask), Otsu threshold, distance-transform watershed to
     split touching cells, contour + centroid extraction per frame.
  2. **Pass 1b (identity)**: frame-to-frame track assignment via the
     Hungarian algorithm (`scipy.optimize.linear_sum_assignment`) on
     centroid distance.
  3. **Pass 2 (correction sweep)**: drops tracks shorter than
     `min_track_len` as noise; linearly interpolates (centroid *and*
     resampled contour shape) across gaps up to `max_gap` frames; detects
     suspiciously large blobs (likely two cells merged by the mask) and
     re-splits them with a *seeded* watershed using neighboring tracks'
     predicted centroids as seeds.
  4. **Pass 2b (optional `--n_cells` enforcement)**: if the true cell count
     per frame is known ahead of time, per-frame reconciles detected count
     against it — under-detection tries a finer watershed re-seed first,
     then falls back to splitting a merge partner's blob or, last resort,
     pure interpolation; over-detection scores and drops the least
     track-consistent excess detections.
  5. **Pass 3**: renders an overlay (dashed = gap-filled, thick = merge-
     split, dotted = soft-recovered, cross = fully synthesized/forced,
     solid = real detection) and composites it over the source video via
     `ffmpeg`. Also writes a CSV (`frame, track_id, x, y, correction,
     contour`) exposing the same gap-filled/merge-split/soft-recover/forced
     tag the overlay's line style already encodes visually, as structured
     data instead of only a picture.

Both `stentTrack.py` and `multiTest.py` also accept `--exp_dir <path>`
instead of `--video`, reading a RoboCam 3.1 experiment directory's
`raw/*.npy` well-stacks directly (via the shared `robocam_input.py`
module) and batch-processing every well found, writing per-well CSV +
overlay outputs to `<exp_dir>/tracking/`. See "Usage" below.

`stentTrack.py`'s own CSV schema (`frame, x, y, pose, movement,
direction_deg, contour`) and `multiTest.py`'s (`frame, track_id, x, y,
correction, contour`) both differ from what `full_data_plot.py` /
`track_plot.py` expect (the Fiji/TrackMate fixed-column layout above), so
today there is no script that takes either Python tracker's output straight
into the plotting scripts without a manual reformatting step.

---

## Usage

Concrete, current-state invocations — every flag actually accepted by each
script's `argparse` block, not an aspirational interface. Run `bash setup.sh`
first (see "Setup" above), then either `source .venv/bin/activate` and call
`python <script>.py` directly, or prefix each command below with
`bash run.sh `.

### `stentTrack.py` — single-cell tracker

```
python stentTrack.py --video cell.mp4 --output tracks.csv --overlay overlay.mp4 \
    --thresh 40 --min_area 200

# or, reading a RoboCam 3.1 experiment directory directly (batches every
# well found under <exp_dir>/raw/, writing to <exp_dir>/tracking/):
python stentTrack.py --exp_dir /path/to/robocam_experiment_dir
```

- `--video` / `--exp_dir` (mutually exclusive, one required):
  - `--video` — single input mp4.
  - `--exp_dir` — a RoboCam 3.1 experiment directory. Reads `raw/*.npy`
    well-stacks directly (never `images/`/`videos/`, even if present —
    see `ROBOCAM_COMPATIBILITY.md`) via the shared `robocam_input.py`
    module, and processes every well found. `--output`/`--overlay` are
    not used in this mode; per-well paths are auto-derived as
    `<exp_dir>/tracking/<well>_<exp_ts>_tracks.csv` and
    `..._overlay.mp4`. Only the current stacked-array raw format is
    supported (no legacy pre-2026-07-06 per-frame-file fallback).
- `--output` (required with `--video`) — CSV path; written with columns
  `frame, x, y, pose, movement, direction_deg, contour`.
- `--overlay` (required with `--video`) — output mp4 path for the debug
  overlay (contour, pose box/triangle, head/tail markers, motion arrow),
  composited over the source video via `ffmpeg`.
- `--thresh` (float, default `40`) — percentile threshold cutoff after
  background subtraction.
- `--min_area` (int, default `200`) — minimum contour area in pixels to
  count as a cell.

Assumes exactly one Stentor in frame for the whole video (or per well, in
`--exp_dir` mode).

### `multiTest.py` — multi-cell tracker

```
python multiTest.py --video colony.mp4 --overlay overlay.mp4 --output tracks.csv \
    --n_cells 4 --roi_cx 320 --roi_cy 240 --roi_r 300

# or, reading a RoboCam 3.1 experiment directory directly (same batching
# behavior as stentTrack.py above):
python multiTest.py --exp_dir /path/to/robocam_experiment_dir --n_cells 4
```

- `--video` / `--exp_dir` (mutually exclusive, one required) — same shape
  as `stentTrack.py` above: `--exp_dir` batches every well found, writing
  to `<exp_dir>/tracking/`, and `--output`/`--overlay` are not used in
  that mode.
- `--output` (optional with `--video`) — CSV path; written with columns
  `frame, track_id, x, y, correction, contour`, where `correction` is
  `real`/`gap_fill`/`merge_split`/`soft_recover`/`forced` — the same tag
  `draw_overlay()` already uses to pick the overlay's line style (dashed/
  thick/dotted/cross/solid), now also exposed as data. Always written in
  `--exp_dir` mode.
- `--overlay` (required with `--video`) — output mp4 path.
- `--n_cells`, `--roi_cx`, `--roi_cy`, `--roi_r`, and the other tuning
  flags below apply identically to every well in a batch `--exp_dir` run
  (one shared value, no per-well override).
- `--blur_ksize` (int, default `5`) — Gaussian blur kernel before Otsu.
- `--min_area` (int, default `200`) — minimum contour area in pixels.
- `--peak_min_dist` (int, default `15`) — watershed seed spacing in pixels.
- `--max_dist` (float, default `50`) — max centroid jump (px) allowed for
  frame-to-frame track assignment.
- `--max_gap` (int, default `10`) — max frames to gap-fill per track.
- `--min_track_len` (int, default `3`) — tracks shorter than this are
  dropped as noise.
- `--merge_area_thresh` (float, default `1.8`) — blob-area / median-cell-area
  ratio that flags a merged (touching-cells) blob; lower = more sensitive.
- `--n_cells` (int, optional) — expected cell count per frame; when set,
  each frame is forced to reconcile to exactly this many contours (see the
  "Pass 2b" description above). Omit to skip this enforcement pass entirely.
- `--roi_cx`, `--roi_cy` (float, optional) — centre of a circular ROI mask in
  pixels; default to the frame's horizontal/vertical centre if omitted.
- `--roi_r` (float, optional) — ROI radius in pixels; pixels outside are
  zeroed before detection. Omit for no masking (full frame).

The script's own `--help` description references a `debug_frame1.py` for
tuning detection parameters before a real run — **that file does not exist
anywhere in this repo**; treat that instruction as aspirational/missing
tooling, not a currently-runnable step (see "Known gaps").

#### `multiTest_gui.py` — step-by-step tuning wizard for `multiTest.py`

```
python multiTest_gui.py
```

A PySide6 GUI wrapping `multiTest.py` only (its 5 stages and 8+ parameters
are what actually benefit from step-by-step tuning; `stentTrack.py`'s 2
parameters don't). Walks through the pipeline one stage at a time —
**Input & Clip → ROI → Detection → Track Assignment → Correction Sweep →
n_cells Enforcement → Export** — against a short scrubbable clip (a
user-chosen start frame + length, default 60 frames) from either a
`--video` file or a `--exp_dir` RoboCam experiment directory (with a well
picker). Each stage previews its effect on that clip with a scrub slider;
changing a stage's parameters only invalidates and recomputes that stage
and everything after it, not the whole pipeline. The final **Export** step
runs the finalized parameters against the *entire* source (not just the
clip) through `multiTest.py`'s own unchanged `detect_and_label`/
`run_exp_dir` functions — a GUI-driven export and a CLI-driven run with the
same parameters take the identical code path and produce identical output.

Architecture lives under `gui/` (`pipeline_state.py` for the cache/
invalidation logic, `preview.py` for image-conversion + the scrub widget,
`steps/*.py` for one file per wizard stage, `main_window.py` for
navigation) — it calls `multiTest.py`'s existing functions
(`run_pass1`, `assign_tracks`, `correction_sweep`, `enforce_n_cells`,
`draw_overlay`, etc.) directly rather than reimplementing the tracking
algorithm a second time.

Known limitation: for `--exp_dir` clips, the whole well's frames are
loaded via `robocam_input.load_well_frames` before slicing out the
requested clip range (no partial-range loading exists yet in
`robocam_input.py`), so clip selection is instant for `--video` (which
seeks directly) but not for a very long RoboCam well capture.

### `csv_compiler.py` — merge TrackMate CSV exports

```
python csv_compiler.py -i ./trackmate_csvs/ -o compiled.csv
```

- `-i, --input_folder` (required) — folder containing one or more TrackMate
  CSV exports.
- `-o, --output_file` (required) — path for the single merged CSV.

Expects TrackMate's export column names (or the aliases `track id`/
`trackid`/`id`, `x`/`position_x`, `y`/`position_y`, `t`/`frame`/`time`); rows
with a non-numeric track id are silently dropped.

### `full_data_plot.py` — population-average speed plot

```
python full_data_plot.py -i compiled.csv -o avg_velocity.png -color orange -wave 600
```

- `-i, --input` (required) — a CSV in the Fiji/TrackMate compiled layout
  above (**not** `stentTrack.py`'s or `multiTest.py`'s output — see the
  cross-format gap noted above). The script skips the first 4 lines
  unconditionally and reads columns by fixed position, not header name.
- `-o, --output` (default `avg_velocity.png`).
- `-color, --color` (default `gray`) — laser color, used only for the
  shaded on/off region's fill color in the plot.
- `-wave, --wavelength` (default `no input`) — cosmetic label only (appears
  in a legend/title), not used in any calculation.

Assumes 30 fps, 56.25 px/mm, and a fixed 2700-frame (90 s) recording with
laser on from frame 900–1800 — hand-edit the script's constants for any
other acquisition setup (see "Known gaps").

### `track_plot.py` — per-track trail + speed plot

```
python track_plot.py -i compiled.csv -o track.png -s1 1,2,3 -s2 7 -color orange
```

- `-i, --input` (required), `-o, --output` (default `track.png`) — same CSV
  assumptions as `full_data_plot.py`.
- `-s1` .. `-s5` (optional, comma-separated track ids each) — up to 5 named
  tracks to plot side-by-side; ids listed together under one `-sN` flag are
  stitched into a single continuous track (e.g. `-s1 1,2,3` treats TrackMate
  ids 1, 2, and 3 as one track, useful when TrackMate lost/resumed the same
  cell under a new id).
- `-color, --color` (default `gray`) — same laser-shading purpose as above.

Also plots a hardcoded reference well-boundary circle and a hardcoded 1 mm
scale bar position, both tuned to one specific camera/zoom setup — adjust
in-script for a different rig.

### `stentor_preprocess.ijm` — Fiji/TrackMate preprocessing (manual)

Not a CLI tool: open Fiji, use **File → Import → Image Sequence** on a PNG
frame folder whose first file is literally named `frame0001.png` (hardcoded
in the macro), then **Plugins → Macros → Run...** and select this `.ijm`
file. The macro pauses twice for manual input (tune/run TrackMate detection,
then save a binary mask by hand) — see the workflow description above.
Export each finished TrackMate track set as CSV, then feed that folder to
`csv_compiler.py` above.

---

## Relationship to RoboCam 3.1

The Fiji workflow still only takes a PNG sequence (and is confirmed
**incompatible** with RoboCam's actual PNG naming — see
`ROBOCAM_COMPATIBILITY.md`). The standalone Python/OpenCV workflow
(`stentTrack.py`, `multiTest.py`) now has two entry points: `--video` (an
already-encoded mp4, as before) and `--exp_dir` (a RoboCam 3.1 experiment
directory, reading `raw/*.npy` well-stacks directly via `robocam_input.py`
— no video round-trip, no dependency on RoboCam's own postprocessing step
having been run). This has been manually verified against a synthetic
fixture (a hand-built fake `raw/` directory, not a committed automated
test — see "Known gaps"), **not yet against a real RoboCam capture** —
see `ROBOCAM_COMPATIBILITY.md`'s open questions for what's still
unconfirmed on real hardware.

See [`ROBOCAM_COMPATIBILITY.md`](ROBOCAM_COMPATIBILITY.md) for a detailed,
code-level assessment of what actually lines up and what doesn't between
RoboCam 3.1's real output and StentorCam's real input assumptions.

---

## Dependencies

Listed in `requirements.txt` (installed by `bash setup.sh`); still inferred
from each script's imports rather than pinned to versions verified to work.

- `opencv-python` (`cv2`) — `stentTrack.py`, `multiTest.py`
- `numpy` — `stentTrack.py`, `multiTest.py`, `full_data_plot.py`,
  `track_plot.py`
- `pandas` — `stentTrack.py`, `multiTest.py` (CSV output via `DataFrame.to_csv`)
- `tqdm` — `stentTrack.py`, `multiTest.py`
- `scipy` — `multiTest.py` only (`scipy.optimize.linear_sum_assignment`)
- `matplotlib` — `full_data_plot.py`, `track_plot.py` (both also attempt a
  custom style, `plt.style.use('BME163')`, that isn't bundled here — falls
  back to matplotlib's default style with a printed warning if missing)
- `PySide6` — `multiTest_gui.py` and everything under `gui/`. Matches
  RoboCam 3.1's own GUI stack. Not needed for any CLI script.
- `ffmpeg` — external binary, invoked via `subprocess.run` by
  `stentTrack.py` and `multiTest.py` to composite the PNG overlay sequence
  back onto the source video. Not a Python dependency; must be on `PATH`.
- Fiji/ImageJ with the TrackMate plugin — external GUI application,
  required to run `stentor_preprocess.ijm` and produce its CSV exports.
  Entirely manual, not scriptable from this repo.

## Known gaps

- No automated tests.
- No dependency version pins — `requirements.txt` lists unpinned package
  names only.
- `multiTest.py`'s filename doesn't match its own documented identity
  (`contour_video.py`).
- `multiTest.py`'s own `--help` text and header docstring instruct the user
  to "use `debug_frame1.py` to tune detection parameters first" — that file
  does not exist anywhere in this repo, so that step can't currently be
  followed.
- The two plotting scripts hardcode fps (30), a px/mm calibration (56.25),
  and a fixed 2700-frame/90 s recording length with laser-on window at
  frames 900–1800 — none of this is derived from the input CSV or exposed
  as a CLI argument, so a different frame rate, recording duration, or
  camera zoom silently produces a mislabeled/wrong-scale plot rather than
  an error. RoboCam's own metadata already records the real `fps_average`
  and `laser_events[]` per experiment (see `ROBOCAM_COMPATIBILITY.md`), but
  nothing plumbs that into these two scripts yet.
- No script bridges `stentTrack.py`'s or `multiTest.py`'s CSV output into
  the fixed-column CSV shape `full_data_plot.py`/`track_plot.py` expect —
  three different, mutually-incompatible CSV schemas now exist in this
  repo (`stentTrack.py`'s `frame,x,y,pose,movement,direction_deg,contour`,
  `multiTest.py`'s `frame,track_id,x,y,correction,contour`, and the
  Fiji/TrackMate fixed-column layout the plotting scripts read).
- `robocam_input.py` (new) only supports RoboCam's current stacked-array
  raw format — the legacy pre-2026-07-06 one-`.npy`-file-per-frame format
  is not supported, so an old archived experiment directory in that format
  will raise rather than load.
- `--exp_dir` batch mode has only been exercised against a hand-built
  synthetic fixture, not a real RoboCam capture, and there's no committed
  automated test for it (see "No automated tests" above) — the RoboCam
  compatibility open questions in `ROBOCAM_COMPATIBILITY.md` (real well
  boundary visibility, actual px/mm scale, etc.) are still open.
- `--n_cells`/`--roi_cx`/`--roi_cy`/`--roi_r` apply identically to every
  well in an `--exp_dir` batch run — there's no per-well override if,
  say, different wells have different cell counts.
- `multiTest_gui.py`'s `--exp_dir` clip loading has no partial-range read —
  it loads the whole well via `robocam_input.load_well_frames` before
  slicing out the requested clip, so picking a short clip from a long
  RoboCam well capture is not instant the way it is for `--video` (which
  seeks directly via `cv2.VideoCapture`).
- `multiTest_gui.py` has only been smoke-tested headless
  (`QT_QPA_PLATFORM=offscreen`) against the same synthetic fixture as
  `--exp_dir` — not exercised with a real display/mouse or a real RoboCam
  capture.
