# RoboCam Stentor Photobehavior Assay Protocol

Adapted from a design document our PI provided (v1.0, July 2026; kept in a local
reference library, not committed here for copyright reasons). This is our own
restructured summary of that protocol, cross-referenced against
[`WAVELENGTH_SELECTION_GUIDE.md`](WAVELENGTH_SELECTION_GUIDE.md), which it
independently corroborates: primary stimulus 610/620 nm, secondary 480/540 nm, and
**680 nm explicitly as a comparison/control wavelength, not the main stimulus** — the
same conclusion our own literature synthesis reached.

## The three behaviors, one experiment each

| Behavior | Core question | Stimulus geometry | Primary metric | Best RoboCam mode |
|---|---|---|---|---|
| Step-up photophobic response | Does a sudden light increase trigger stop/reversal/turn? | Whole-field temporal pulse, or dark-to-light edge | Response probability, latency, reversal duration, turn angle | High-frame-rate single-well event assay |
| Phototaxis | Does *Stentor* move directionally relative to a light field? | Half-field, side illumination, or smooth gradient along the light axis | Occupancy index and velocity projection | Flat chamber, stable spatial light field |
| Photokinesis | Does light alter swimming speed independent of direction? | Uniform full-field illumination at a defined intensity | Speed ratio, light vs. baseline | 24-well screen with replicated wells |

**Recommended order: photophobic response first, then phototaxis, then photokinesis.**
Phototaxis results are ambiguous on their own — dark-side accumulation in a half-field
assay can be produced by edge-triggered avoidance (photophobic response) rather than
true directional steering, so it needs the photophobic assay validated first as a
baseline to interpret against.

## Design principles

- **Separate stimulus geometry from behavior class.** Temporal steps for photophobia,
  gradients/half-fields for taxis, uniform light for kinesis. Conflating these risks
  mislabeling a photophobic edge artifact as "phototaxis."
- **Synchronize video and LED timing.** Record LED-on timestamps in the same data
  stream as the video frame index (or add a visible timing-indicator LED). Without
  this, latency and event scoring can't be trusted.
- **Use shallow, optically flat chambers.** Flatten the meniscus, constrain depth, keep
  *Stentor* in a single focal layer — losing focus through depth is usually a bigger
  problem than insufficient magnification, since *Stentor* is already large
  (approaching/exceeding 1 mm extended).
- **Calibrate irradiance at the sample plane.** Report wavelength, irradiance, pulse
  duration, duty cycle, and chamber geometry — PWM percentage or supply voltage alone
  isn't comparable across builds.
- **Use non-actinic imaging light.** Dim IR (850/940 nm) or very dim red/far-red for
  tracking, verified with a tracking-light-only control to confirm it doesn't itself
  elicit a response.
- **Block and randomize.** Randomize well order, wavelength order, and intensity
  sequence within culture-day blocks, so time/evaporation/fatigue/culture condition
  doesn't masquerade as a light effect.

## Stimulus wavelengths

| Channel | Purpose | Notes |
|---|---|---|
| 610 or 620 nm | Primary stimulus | Most important channel for photophobic and phototaxis assays |
| 540 or 480 nm | Secondary action-spectrum point | Useful after the main assay works; don't start here |
| 660/680 nm | Long-red comparison | Expected to be less effective than 610/620 nm; used as a control |
| 850/940 nm | Imaging only | Verify with a tracking-light-only control |

Use a constant-current LED driver rather than driving high-power LEDs directly from a
microcontroller; have RoboCam control the driver enable pin or a logic-level MOSFET
gate, and log the actual command waveform (ideally alongside a photodiode signal from
the sample plane during validation).

## Chamber design

- **First assay:** a shallow chamber, not an open 24-well meniscus — glass-bottom or
  optically clear well with a removable spacer/gasket and a top cover film/coverslip.
  Target depth 0.5-1.5 mm (deep enough to avoid compressing cells, shallow enough for
  focus and intensity uniformity); planar area 8-15 mm for single-well tracking.
- **24-well plates** are appropriate for photokinesis screens and replicated
  intensity/wavelength tests, but raw deep-well distributions shouldn't be interpreted
  as taxis unless the light field and depth are characterized — curved meniscus and
  wall effects can dominate the distribution.
- For one-well-at-a-time scanning, randomize well order so plate position and elapsed
  time aren't confounded with condition.

## Assay 1 — Step-up photophobic response (start here)

Recommended as the first RoboCam validation assay: gives a time-locked event with
clear behavioral labels.

- **Pulse durations:** 0.2, 0.5, 1.0, 2.0 s. **Intensity:** log-spaced pilot series at
  the sample plane, to fit dose-response curves and estimate an EC50-like threshold.
  **Inter-trial interval:** at least 5-10 s (longer if repeated stimulation shows
  adaptation). **Frame rate:** 60 fps minimum, 120 fps preferred for latency/reversal
  dynamics.
- **Event definitions:** baseline speed = median speed -2.0 to -0.2 s before LED onset;
  response window = 0.05-1.5 s after onset; stop event = speed drops below 20-30% of
  baseline for >= 2-3 consecutive frames; reversal event = negative displacement relative
  to pre-stimulus heading for >= 100-150 ms; latency = time from LED onset to first
  stop/reversal frame; turn angle = angle between mean heading before stimulus and mean
  heading after recovery.
- **Output metrics:** response probability, median latency/IQR by wavelength and
  irradiance, reversal duration and backward distance, turn-angle distribution,
  dose-response curve (probability vs. log irradiance), adaptation curve across
  repeated pulses.

## Assay 2 — Phototaxis / directional bias (only after Assay 1 works)

- **Half-field chamber:** mask/project half the chamber dark, half bright at 610/620
  nm. Readout: dark-side occupancy over time and edge-crossing response — but this
  conflates true steering with photophobic boundary avoidance.
- **Smooth gradient:** diffuser + neutral-density gradient, wedge mask, or side
  illumination across the chamber. Readout: velocity projection along the gradient
  axis — better isolates steering/taxis, but needs a calibrated light field.
- **Metrics:** occupancy index = (N_dark - N_light)/N_total, reported over time, not
  just at the end; directional bias = mean velocity projected away from the light
  source, divided by speed (near +1 = moving away, near 0 = no bias); edge-crossing
  response probability; dwell time per zone, normalized by zone area.
- **Caution:** don't call a result "true phototaxis" from dark-side accumulation alone
  — pair it with velocity-vector analysis and the photokinesis control. Avoid bubbles,
  curved meniscus, and wall shadows, which generate artificial gradients and trapping
  zones.

## Assay 3 — Photokinesis / speed modulation

The best fit for 24-well RoboCam scans, since uniform full-field illumination is
easier to reproduce across wells than a gradient.

- **Windows:** baseline 30-60 s before light; acute onset 0-2 s after light-on
  (inspect, but don't use as the main metric — photophobic events can contaminate
  speed here); sustained light 10-60 s after light-on (primary photokinesis estimate);
  recovery 30-60 s after light-off (reversibility/fatigue).
- **Photokinesis index** = median speed during sustained light / median baseline
  speed. Use a paired design — each well/cell as its own baseline control. Exclude
  tracks that hit walls, attach to substrate, or leave focus for more than a defined
  fraction of the window.
- **First screen:** 610/620 nm at low/medium/high irradiance, plus a no-light control
  and a 680 nm comparison.

## Controls and confound checks

| Control | Purpose | Pass criterion |
|---|---|---|
| No-actinic sham | Camera/vibration/software-trigger artifacts | No increase in stop/reversal events at sham time |
| Tracking light only | Confirms IR/far-red imaging is behaviorally silent | Baseline speed/event frequency match dark control |
| 680 nm comparison | Separates wavelength-specific sensitivity from generic brightness/heating | Lower or shifted response vs. 610/620 nm at matched irradiance |
| Heat control | Tests whether LED warming changes swimming speed | Temperature rise below a predefined limit; speed not explained by heat alone |
| Spatial mask blank | Tests whether masks create flow/shadow/focusing artifacts | No preferential accumulation without actinic contrast |
| Fixed particle video | Detects stage drift and optical distortion | No apparent movement in fixed particles during LED switching |

## Recommended workflow

**Phase 0 — build and calibration:** measure field uniformity (photodiode/camera
flat-field per mask and LED channel); verify LED timing (film an indicator LED or log
a photodiode signal alongside video); measure sample-plane temperature during the
longest planned exposure; run tracking-light-only controls; record a calibration video
with beads/fixed particles for pixel-to-micron scale.

**Phase 1 — minimum viable experiment:** load 5-20 healthy swimming cells into a
shallow chamber (avoid dense cultures, disturbed cells, debris); 5-10 min
acclimation/dark adaptation; 10 s baseline under non-actinic light; a 610/620 nm pulse
series (0.5 s and 1.0 s at low/medium/high irradiance, 5-10 s between trials); manually
score the first 20-50 events before comparing to automated scoring; repeat with sham
pulses and a 680 nm comparison at matched irradiance.

**Phase 2 — publication-grade assay:** >= 3 independent culture days/batches as
biological replicates; multiple wells/chambers per condition per day as technical
replicates; report analyzable cells/tracks, but treat culture day/well as the primary
replicate level; randomize intensity and well order (avoid monotonic low-to-high
sequences unless specifically studying adaptation); blind manual event scoring to
wavelength/intensity where practical; predefine QC exclusions (stuck cells,
collisions, track loss, fission-stage cells, debris).

## Analysis pipeline

Preprocessing (flat-field correction, background subtraction, timestamp alignment) ->
segmentation (contour/threshold tuned for large *Stentor* bodies, ignoring
sub-threshold particles) -> tracking (nearest-neighbor/Kalman linking with gap-closing)
-> event detection (speed/heading/displacement relative to the pre-stimulus vector) ->
metrics (response probability, latency, reversal duration, speed ratio, occupancy
index, directional bias) -> archiving (raw video, metadata JSON/CSV, processed tracks,
analysis code version — a reproducible experiment folder per run).

## Minimum metadata to record per run

Experiment (id, date, operator, RoboCam build/version, analysis version); biology
(species, culture source/age, feeding status, medium, temperature); chamber (plate
type, depth, gasket material, volume, cover method, well ID); optics (camera model,
lens, magnification, frame rate, resolution, pixel size, imaging light
wavelength/intensity); stimulus (LED wavelength, bandwidth if known, irradiance at
sample plane, pulse duration, duty cycle, mask/gradient geometry); trial (baseline
duration, stimulus onset frame, recovery duration, inter-trial interval, randomized
order index); QC (cells loaded, cells analyzable, exclusions, notes on
bubbles/debris/focus).

## Statistics

- Photophobic response probability: logistic regression / generalized mixed model,
  wavelength/intensity as fixed effects, culture day/well as random/blocking factors.
- Latency and reversal duration: medians or robust models (distributions are often
  skewed and censored by frame rate).
- Photokinesis: paired speed ratios by cell or well, aggregated by well/culture day —
  don't treat every frame as an independent replicate.
- Phototaxis: report both occupancy and directional movement — occupancy alone is
  insufficient, since cells can accumulate in dark zones through photophobic boundary
  rejection rather than true steering.
- Report failed tracking and exclusions transparently; these assays are highly
  sensitive to chamber quality and culture condition.

## Suggested 24-well plate layout for the initial screen

| Wells | Condition | Purpose |
|---|---|---|
| A1-A3 | No-actinic sham, imaging only | Baseline / tracking-light control |
| A4-A6 | 610/620 nm low irradiance | Lower end of dose-response |
| B1-B3 | 610/620 nm medium irradiance | Expected working condition |
| B4-B6 | 610/620 nm high irradiance | Saturation/adaptation check |
| C1-C3 | 680 nm matched irradiance | Long-red wavelength comparison |
| C4-C6 | Uniform 610/620 nm sustained light | Photokinesis window |
| D1-D3 | Half-field 610/620 nm | Phototaxis/edge-avoidance pilot |
| D4-D6 | Recovery/dark after exposure | Carryover and fatigue check |

Don't run the plate in A1-to-D6 order for one-well-at-a-time scanning — generate a
randomized acquisition order instead.
