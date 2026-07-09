# RoboCam 3.1 ↔ StentorCam compatibility assessment

This document compares what RoboCam 3.1 actually produces today against
what StentorCam's scripts actually expect, based on reading both repos'
current code (not either repo's aspirational docs). See `README.md` for
StentorCam's own current-state architecture.

Sources: RoboCam 3.1's `robocam/postprocess.py` and `PROJECT_STATE.md`
(§§ 3–5, 8), read 2026-07-08; StentorCam's `stentTrack.py`, `multiTest.py`,
`stentor_preprocess.ijm` as of the same date.

**Update (2026-07-09):** the raw-`.npy` integration described as an open
question below has since been implemented — `robocam_input.py` plus
`--exp_dir` support in both `stentTrack.py` and `multiTest.py` — per the
decisions and design in this repo's git history (branch
`feature/robocam-exp-dir-support`). It reads `raw/*.npy` directly, always
in preference to `images/`/`videos/` even when both exist, and
batch-processes every well found. It has been manually verified against a
synthetic fixture only, **not yet against a real RoboCam capture** — see
the updated Open Questions below for what that leaves unconfirmed. The
rest of this document (written before that work) is left as originally
assessed except where noted, since its analysis is still accurate.

---

## What RoboCam 3.1 actually outputs (post-processing step)

Per well, `robocam/postprocess.py` (`process_well()`) writes, from one
memory-mapped raw `.npy` burst:

```
<exp_dir>/
  images/<well>/<well>_<frame_index:05d>_<t_ms:06d>ms_laser-[on|off].png
  videos/<well>_<exp_ts>_vfr.mkv     (VFR, accurate per-frame timing)
  videos/<well>_<exp_ts>.mp4         (constant fps, libx264 baseline)
```

Key facts confirmed from the code (not just the docs):

- **No software crop to the well.** `images/<well>/` is a *directory* per
  well, not a pixel crop — the raw frame is written at its native
  capture resolution unchanged. The well fills the frame because the
  camera physically moves to and captures only that well; nothing here
  crops a wider shot down to a circular region.
- **Mono passthrough.** The Mars 662M sensor is confirmed monochrome; frames
  go through `cv2.COLOR_GRAY2BGR`, so the PNGs/videos are 3-channel BGR with
  identical R=G=B — grayscale in a color-shaped array, not true multi-channel
  color data.
- **mp4 frame rate is a computed average, not a fixed constant.**
  `display_fps = n_frames / duration_actual_s`, encoded into the container
  as a `Fraction` (e.g. `~29.95` in the 2026-07-01 test dataset), not a
  round `30`. `cv2.VideoCapture(...).get(cv2.CAP_PROP_FPS)` will report
  whatever that actual fraction is.
- **Laser on/off is recorded exactly**, twice over: per-frame in each PNG's
  filename suffix (`laser-on`/`laser-off`), and as precise
  `{time_offset_s, state, frame_index}` transition events in
  `<well>_<ts>_metadata.json`'s `laser_events[]`.
- **fps is itself an open bug upstream**: real achieved capture rate is
  currently stuck at ~30fps against a 90-120fps camera spec (RoboCam
  `PROJECT_STATE.md` § 9, "Investigating"). Today's ~30fps happens to be
  close to StentorCam's hardcoded assumption (see below) — that is
  coincidence, not a guarantee, and will break if/when the fps ceiling bug
  is fixed.

---

## What StentorCam's scripts actually assume

- **`stentTrack.py`, `multiTest.py`** — both take `--video <mp4>` via
  `cv2.VideoCapture`. Detection is **polarity-agnostic**: both compute a
  per-video median-frame background, then `cv2.absdiff(gray, background)`
  (an absolute-value diff, not a signed subtract), so neither script
  actually depends on cells being brighter or darker than the background —
  contrary to RoboCam's own doc note ("darkfield: white=cells, black=bg"),
  StentorCam's own algorithm doesn't require darkfield specifically.
- **`multiTest.py`'s `--roi_cx/--roi_cy/--roi_r`** — an optional circular
  mask, defaulting to the frame's own center when `--roi_cx/--roi_cy` are
  omitted. This lines up well with RoboCam's uncropped, well-centered raw
  frames: the well boundary (if it's visible as a circle inside the frame)
  is exactly the kind of thing this flag was built to mask out.
  Confirmed compatible without needing a code change — RoboCam's frames
  are the same shape/layout multiTest.py's ROI logic already assumes.
- **`stentor_preprocess.ijm`** — hardcodes `open(dir + "frame0001.png")` as
  the very first line of macro logic. RoboCam's PNG naming
  (`A1_00000_000006ms_laser-off.png`) does not match this pattern at all —
  **confirmed incompatible as written**, this macro cannot currently open a
  RoboCam `images/<well>/` folder without either renaming files first or
  editing the macro's hardcoded filename.
- **`full_data_plot.py` / `track_plot.py`** — hardcode fps=30, 56.25 px/mm,
  and a fixed 2700-frame/90s timeline with laser on/off at frames 900–1800,
  none derived from the input CSV. This is the sharpest mismatch:
  - fps: RoboCam's `fps_average` is a measured, slightly-off-30, per-
    experiment value — not read anywhere by these scripts today.
  - laser window: RoboCam's `laser_events[]` records the *actual*
    transition frames per experiment — again, not read anywhere by these
    scripts today, which instead assume every recording is the same fixed
    90s/30-30-30 structure regardless of what actually happened.
  - px/mm: 56.25 is tied to one specific historical camera/zoom
    combination; RoboCam's calibration file (`config/calibrations/*.json`)
    records well *positions* in mm for stage motion, not an optical
    px-per-mm scale for the camera's current lens/resolution/well-crop —
    a different number would need to be established for the current rig,
    it isn't derivable from anything RoboCam already records.

---

## Compatibility matrix

| Input path | Status |
|---|---|
| RoboCam `videos/<well>_<ts>.mp4` → `stentTrack.py --video` / `multiTest.py --video` | **Likely works as-is.** Both scripts only need an OpenCV-readable mp4; RoboCam's is standard H.264 baseline. Not yet run end-to-end against a real RoboCam output file — this is the highest-value next check (see Open Questions). |
| RoboCam `videos/<well>_<ts>_vfr.mkv` → either tracker | **Unverified.** VFR timing may or may not read back as evenly-spaced frames through `cv2.VideoCapture`; the mp4 (constant fps) is the safer bet of the two RoboCam video outputs. |
| RoboCam `images/<well>/*.png` sequence → `stentor_preprocess.ijm` | **Confirmed broken as written** — filename mismatch (see above). Fiji's own "Import → Image Sequence" (used later in the macro) sorts by name and doesn't require the literal `frame0001.png`, but the macro's very first line does an explicit `open()` on that exact name before the sequence import runs. |
| RoboCam raw `.npy` well-stacks (pre-postprocessing) → `stentTrack.py --exp_dir` / `multiTest.py --exp_dir` | **Implemented** (2026-07-09) via `robocam_input.py`. Reads `raw/*.npy` directly — no dependency on `postprocess.py` having run — and batches every well found. Verified against a hand-built synthetic fixture (correct frame-count-ceiling handling, empty-well skip, CSV/overlay output); **not yet verified against a real RoboCam capture** (see Open Questions). Only the current stacked-array raw format is supported, not the legacy pre-2026-07-06 per-frame-file format. |
| RoboCam `laser_events[]` / `fps_average` metadata → `full_data_plot.py` / `track_plot.py` | **Not read.** These scripts have no code path that opens a metadata JSON; the fixed 30fps/2700-frame/frames-900-1800 assumptions are independent of whatever RoboCam actually recorded for a given run. |
| `stentTrack.py` / `multiTest.py` CSV output → `full_data_plot.py` / `track_plot.py` | **Already broken today, independent of RoboCam** — different CSV schemas (see README "Known gaps"). Relevant here because it means even a fully-compatible RoboCam→tracker path still dead-ends before reaching the plotting scripts. |

---

## Open questions (not yet answered — needs a real RoboCam capture to test against)

1. **Highest-value next check**: has a real RoboCam-produced experiment
   directory actually been fed into `stentTrack.py --exp_dir` or
   `multiTest.py --exp_dir` and run to completion? Only a synthetic
   fixture has exercised this path so far — real sensor data may expose
   debayering, bit-depth, or timing assumptions the fixture couldn't.
   (The `--video`/mp4 path is no longer the primary integration target,
   since `--exp_dir` always prefers `raw/*.npy` directly — but the mp4
   path also remains untested against a real RoboCam-produced file.)
2. Is the well boundary actually visible as a circle within the raw frame
   (making `--roi_r` directly useful), or does the camera's field of view
   already tightly match the well with no visible edge/background margin?
3. What is the actual px/mm scale for the current RoboCam camera + lens +
   resolution? Needed before `full_data_plot.py`/`track_plot.py` numbers
   mean anything for RoboCam-sourced data.
4. Now that RoboCam's fps ceiling bug (§9) is under active investigation,
   should StentorCam's plotting scripts be changed to read `fps_average`
   (and `laser_events[]`) from the sidecar metadata instead of hardcoding
   30fps/frame-900-1800, or is a fixed acquisition protocol enough of a
   guarantee that hardcoding is fine? This is a real design decision, not
   answered by this document. (`robocam_input.WellFrames` already carries
   `fps`/`laser_events` through for a well loaded via `--exp_dir` — nothing
   consumes them past that yet, since `full_data_plot.py`/`track_plot.py`
   are out of scope for the `--exp_dir` work.)
5. Multi-cell counts: does RoboCam record or plan to record how many cells
   were loaded per well anywhere in its metadata, which `multiTest.py
   --n_cells` could consume directly? (Currently `--n_cells` is a single
   value applied identically to every well in a batch `--exp_dir` run.)
