# Notes: Iwatsuki (1992) — *Stentor coeruleus* Shows Positive Photokinesis

Source: Iwatsuki, K. (1992). *Stentor coeruleus* shows positive photokinesis.
*Photochemistry and Photobiology*, 55(3), 469–471.
(PDF: [`references/Iwatsuki-1992-Stentor-coeruleus-positive-photokinesis.pdf`](references/Iwatsuki-1992-Stentor-coeruleus-positive-photokinesis.pdf))

## Key findings

- *S. coeruleus* shows **positive photokinesis**: swims faster in light, slower in dark.
  Mean velocity ~0.6 mm/s at 100 lx, up to ~1.0 mm/s at 50000 lx (white light).
- Velocity increases roughly **linearly with log(fluence rate)** — a Weber–Fechner-type
  relationship, not linear in raw light intensity.
- Photokinesis has its own action spectrum, distinct from the photophobic-response/
  phototaxis action spectrum (peak 610 nm). This implies **at least two separate
  photoreceptor systems** in the cell.
- *S. coeruleus* is reported as the first protozoan shown to exhibit all three
  photoresponse types: photophobic response, phototaxis, and photokinesis.

## Figure 3

![](references/iwatsuki-1992-figure3-action-spectrum.png){width=100%}

## How Figure 3 (action spectrum) was built

For each of 9 wavelengths (400–720 nm), the authors measured a full fluence-rate vs.
velocity dose-response curve (like the 680 nm / 440 nm examples in Fig. 2a — velocity
rises ~linearly with log fluence rate). From each curve they read off the **fluence rate
required to reach a fixed criterion velocity: 0.58 mm/s** (the paper calls this the
"half-maximal kinetic response," but see the "Why 0.58 mm/s" section below — the paper
does not describe how this specific number was derived, and it's likely just a common
target velocity within the overlapping range of all 9 curves rather than a computed
dark-floor/light-ceiling midpoint). This lets 9 whole dose-response curves collapse into
9 single comparable numbers (essentially an EC50-per-wavelength), which is what's plotted
as the action spectrum.

### Reading the y-axis: logarithmic AND inverted

- Y-axis label: "Relative response." Y-axis units are actually the **fluence rate (W/m^2)**
  needed to hit 0.58 mm/s — same scale as the x-axis of Fig. 2a (log, ~0.1–1.0+ W/m^2).
- The axis is drawn **inverted** (small numbers near the top, large numbers near the
  bottom). This is a standard action-spectrum convention: the biologically meaningful
  quantity is *sensitivity* = 1/fluence needed, not the fluence itself. Rather than plot
  the reciprocal, the axis is just flipped so "higher on the page" = "less light was
  needed" = "more sensitive" — producing a normal-looking peaked curve even though the
  raw printed numbers are fluence rates, not sensitivity units.

### Specific values discussed

- **680 nm to ~0.08 W/m^2** needed to reach 0.58 mm/s (near the top of the plot — most
  sensitive point tested).
- **400 nm to ~1.1 W/m^2** needed to reach 0.58 mm/s (near the bottom — least sensitive
  point tested).
- Ratio ~= **14x** — Stentor needs roughly 14 times less red (680 nm) light than blue
  (400 nm) light to produce the same swimming-speed increase. This is a genuine, strong
  action-spectrum peak at 680 nm, not just a mild bias.
- Curve shape across the spectrum: steep rise from 400–440 nm, a plateau through
  ~440–600 nm, then a second climb to the true peak at 680 nm, followed by a drop at
  720 nm.

## Why 0.58 mm/s specifically

**Correction / uncertainty flag:** initial notes here speculated that 0.58 mm/s was the
midpoint between a measured "dark floor" velocity and a measured "saturating ceiling"
velocity. That is *not* stated anywhere in the paper's Materials & Methods and is likely
wrong, for two reasons:

1. **A true zero-light data point isn't measurable with their setup.** The same light
   source that provides the photokinetic stimulus also provides the dark-field
   illumination the "Bug-tracker" camera needs to see/track the cell at all ("To generate
   dark-field illumination and to stimulate the organisms, white light... was...
   projected..."). There's no separate viewing-light channel, so they can't record a cell
   swimming in literal darkness.
2. **No plateau is described.** Both Fig. 1a (white light, 100–50000 lx) and Fig. 2a
   (monochromatic, ~0.1–2 W/m^2) are described as "increased almost linearly with a
   logarithmic increase" across the *entire* tested range — no floor/ceiling saturation
   is mentioned, so there's no natural min/max to average.

**More likely explanation:** 0.58 mm/s is a fixed criterion velocity chosen because it
falls *within the overlapping, actually-measured range* of all nine wavelength-specific
fluence-response curves — i.e., a common target every curve crosses somewhere in its
tested data, so a fluence-rate value can be read off (interpolated, not extrapolated) for
each of the 9 wavelengths. This is the standard practical reason for picking one criterion
response when collapsing several dose-response curves into a single action spectrum; it
does not require or imply any dark/saturating-max calibration measurement.
