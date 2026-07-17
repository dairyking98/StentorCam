# Stentor coeruleus Wavelength Selection Guide

Purpose: pool everything we've read across the *S. coeruleus* photoresponse
literature into one decision — which wavelength(s) should StentorCam experiments
prioritize to get a positive result. This is the decision document; for general
background and citation-heavy detail (including a figure-by-figure critique of
Iwatsuki 1992's axis units and 0.58 mm/s criterion) see
[`PHOTOKINESIS_ACTION_SPECTRUM_NOTES.md`](PHOTOKINESIS_ACTION_SPECTRUM_NOTES.md). For
the full experimental protocol once a wavelength is chosen (chamber design, controls,
statistics, plate layout), see
[`ROBOCAM_ASSAY_PROTOCOL.md`](ROBOCAM_ASSAY_PROTOCOL.md), adapted from a design
document our PI provided — it independently reaches the same 610/620 nm
recommendation and treats 680 nm as a control wavelength, corroborating this guide.

## Recommendation

- **Test 610-620 nm first.** Five independent measurements across three labs and
  16 years (1976-1992) converge here — the strongest, most replicated signal in the
  whole literature.
- **Backup/secondary candidates: ~560 nm and ~470-480 nm.** Now corroborated by two
  independent papers (Wood 1976: 568/480 nm; Kim/Prusti/Song/Hader 1984: ~555-560/470
  nm) — the same two-secondary-peak shape shows up twice, which is reassuring, though
  still lower-confidence than the 610-620 nm primary peak. Wood's 568 nm point was
  never directly tested in his own action spectrum (only inferred from absorption
  data); Kim/Prusti/Song/Hader's ~555-560 nm point was directly measured.
- **Deprioritize 680 nm.** This is Iwatsuki's claimed photokinesis peak, and it's an
  outlier by every measure we could check: single source, never independently
  replicated, no known matching pigment, and it's consistent with our own data
  showing little response there. Keep it as an exploratory/comparison arm, not the
  main bet.
- **Novel angle worth pursuing regardless of the above:** none of the five
  610-620 nm measurements were photokinesis experiments — they were phototaxis or
  photophobic (avoidance) response. Testing 610-620 nm specifically for
  *photokinesis* is a measurement nobody has published. A positive result there
  would suggest photokinesis shares stentorin's photoreceptor rather than requiring
  Iwatsuki's proposed second, unidentified 680 nm photoreceptor.

## Cross-paper synthesis

![](references/consensus-action-spectrum.png){width=100%}

| Source | Method | Response type | Reported peak(s) |
|---|---|---|---|
| Wood 1976 | Electrophysiology + ciliary-reversal threshold | Photophobic | 620 nm primary; 480 nm shoulder; 568 nm secondary (absorption data only, not directly tested) |
| Song 1980 | Fluence-response curves, focused-beam orientation | Phototaxis | ~610 nm (broad maximum) |
| Kim/Prusti/Song/Hader 1984 | Ca2+-flux / fluence-response, quantum-efficiency action spectrum vs. absorption spectrum | Phototaxis + photophobic | ~610-615 nm primary; ~555-560 nm secondary; ~470 nm shoulder |
| Stentorin biochemistry (~1990, Song lab) | Absorption / fluorescence-emission spectroscopy of the isolated pigment | Pigment characterization | ~600-620 nm |
| Iwatsuki 1992 | Fluence-response curves (cites the above) | Phototaxis/photophobic | 610 nm |
| **Iwatsuki 1992** | Fluence-response curves, criterion velocity | **Photokinesis** | **680 nm — the outlier** |

Wood 1976, Song 1980, and Kim/Prusti/Song/Hader 1984 values above are confirmed
directly from the primary-source PDFs (now in `references/`) — the ILL request for
Kim/Prusti/Song/Hader came through. Its Fig. 1 plots a proper quantum-efficiency action
spectrum directly against stentorin's measured absorption spectrum (in vivo and at
77 K), and its multi-peak shape (~610-615 nm primary, ~555-560 nm secondary, ~470 nm
shoulder) independently reproduces Wood 1976's pattern (620/568/480 nm) almost exactly
— two separate labs, two different methods (fluence-rate criterion-response vs.
direct quantum-efficiency calculation), converging on the same multi-band shape. That's
a much stronger corroboration of the 610-620 nm cluster than a single-paper result.
Only the stentorin-biochemistry summary is still from a secondary source pending
full-text access.

The photoreceptor behind the 610-620 nm cluster is identified: **stentorin**, a
hypericin-based chromophore with absorption confined to roughly 525-630 nm. It has
essentially no absorption at 680 nm — which is exactly why Iwatsuki had to propose a
second, distinct photoreceptor system to explain the photokinesis result. No
follow-up work in the 30+ years since has identified what that second photoreceptor
might be, and *S. coeruleus* has no plastids/chlorophyll that would otherwise explain
red-region sensitivity out at 680 nm.

## Why 680 nm specifically looks weak (summary)

- **Single source.** Of 24+ papers citing Iwatsuki (1992), none independently
  re-measured the photokinesis action spectrum — all just cite it as background.
- **No replication attempt succeeded.** Kühnel-Kratz & Häder (1994) is the one paper
  that re-examined photokinesis behavior with improved 3D tracking, but they used
  white light only — no monochromatic wavelength sweep — so it neither confirms nor
  refutes 680 nm.
- **No matching pigment.** See above.
- **Thin derivation of the criterion response.** Iwatsuki's action spectrum is built
  by finding the fluence rate needed to hit a fixed criterion velocity (0.58 mm/s) at
  each wavelength; the paper doesn't explain why 0.58 mm/s specifically, beyond it
  being a value within the overlapping range of all nine tested curves. (Full
  breakdown in `PHOTOKINESIS_ACTION_SPECTRUM_NOTES.md`.)

## Other experimental variables to control for

- **Fluence-rate ceiling.** Kühnel-Kratz & Häder (1994) only saw positive photokinesis
  below ~10 W/m^2; above that, no clear kinesis — in tension with Iwatsuki's claim of
  an almost-linear velocity-vs-log-fluence relationship across the *entire* tested
  range. Check where our fluence rates fall relative to this cutoff.
- **Chamber geometry.** Kühnel-Kratz & Häder's dark-swimming baseline velocities
  (1.5-1.8 mm/s) were notably higher than every previously published value
  (0.2-1.2 mm/s, including Iwatsuki's), attributed to their wider 25 mm cuvette
  reducing wall effects. Our own baseline velocities may not be directly comparable
  to the literature unless our chamber width/depth is accounted for.
- **Light-source spectral purity.** Confirm actual output spectrum at whichever
  wavelength setting we test (LED/filter bandwidth can shift or wash out a narrow
  real peak) — relevant whether we're testing 610-620 nm or 680 nm.

## Light sources: what the papers used vs. our apparatus

**What the classic papers actually used** (confirmed from the primary-source PDFs,
now all in `references/`) — none used lasers or LEDs; all were filtered
lamp/projector setups:

| Paper | Light source | Wavelength selection |
|---|---|---|
| Iwatsuki 1992 | Incandescent lamp, IR cut-off filter + water container | Interference filter (<6 nm half-bandwidth) + neutral-density filters; EG&G photometer |
| Wood 1976 | Zircon arc lamp (behavioral test); cool white fluorescent bulbs (electrophysiology test) | Interference filters, 10 nm half-bandwidth, stepped every 20 nm 480-660 nm; ND + heat filters |
| Song 1980 | 40 W incandescent lamp, collimated | ND filters (white light); interference filters (Baird Atomic, ~10 nm half-bandwidth); Kettering Model 65 radiometer |
| Kim/Prusti/Song/Hader 1984 | 300 W slide projector (Gold) | Interference filters, ~10 nm half-bandwidth; Kettering Y.S.I. Model 65A radiant power meter |
| Kuhnel-Kratz & Hader 1994 | 15 W Zeiss microscope lamp (viewing); 150 W halogen (Schott KL 1500 / Osram Xenophot, stimulus) | White light only — no wavelength filtering, consistent with them never testing an action spectrum |

**Our apparatus:** the plotting scripts (`full_data_plot.py`, `track_plot.py`) label
the stimulus "LED On"/"LED Off" in their legends, even though the README's CLI flags
are loosely named after "laser color" — that's historical naming, not a hardware spec,
and no BOM/part number for either an LED or a laser diode exists in this repo
(hardware specifics live in the separate RoboCam repo).

**Current build direction: a laser-based coaxial illuminator with a 50/50
beamsplitter**, sharing the optical axis with the camera. For that specific design, a
laser diode is the better fit optically (small collimated beam couples through a
beamsplitter far more efficiently than an LED, which needs extra collimating optics
and loses more power to etendue mismatch). Recommended source: a **~605-620 nm orange
laser diode module** — this wavelength sits in what's called the semiconductor
"yellow-orange gap" (570-625 nm is hard for direct diode lasers), so it's a specialty
part rather than an off-the-shelf pointer diode, but real products exist (RPMC Lasers'
590-619 nm orange category, Laserland's 600-640 nm modules, Thorlabs' visible laser
diode line). A common 635 nm red diode is the cheap fallback, but Wood 1976's own data
shows "a large decrease... between 620 and 640 nm," so expect a weaker response than a
true 605-620 nm source. For the 480 nm and 680 nm arms, standard blue (~450-473 nm) and
deep-red (~650-685 nm) diodes are cheap and common — no gap issue there.

To get a **consistent, uniform spot covering a well (6-20 mm diameter) over a 0.5-2 ft
throw**: collimate the diode, then pass it through a fixed Galilean beam expander
(e.g. Thorlabs GBE, 5x on a ~3 mm collimated beam gives ~15 mm output) to hold the spot
size steady across that distance range, then an engineered diffuser (e.g. Thorlabs
ED1-C series) to flatten the Gaussian profile into a top-hat so every point in the well
gets the same fluence rate. An iris/aperture after the diffuser can clip to an exact
diameter within the 6-20 mm target if needed. Keep total power modest — Iwatsuki's
tested range was ~0.1-1.1 W/m^2, and Kuhnel-Kratz & Hader saw kinesis disappear above
~10 W/m^2 — a few mW, attenuated by driver current or an ND filter, is plenty.

## Suggested next-experiment design

1. Primary arm: **610 nm and 620 nm**, measuring photokinesis (swimming velocity),
   not just avoidance/phototaxis.
2. Secondary arms: **480 nm and 568 nm** as backup candidates.
3. Comparison arm: **680 nm**, kept in the design specifically to directly test
   Iwatsuki's claim against our own setup, now that we know it's an unreplicated
   outlier rather than settled fact.
4. Keep fluence rates under ~10 W/m^2 per the Kühnel-Kratz ceiling, and record
   chamber width/depth so results are comparable across studies.
5. If 610-620 nm produces a clear photokinesis response, that's a novel result
   (nobody has published a photokinesis measurement at that wavelength) supporting a
   shared photoreceptor with the phototaxis/photophobic response. If it doesn't,
   that keeps the second-photoreceptor question open — but 680 nm still wouldn't be
   confirmed by our data either, so a positive result there would itself be
   noteworthy given the literature gap.

## Source status

| Paper | Status |
|---|---|
| Iwatsuki 1992 | Local reference library (not committed — copyright), values verified |
| Wood 1976 | Local reference library (not committed — copyright), values verified |
| Song 1980 | Local reference library (not committed — copyright), values verified |
| Kuhnel-Kratz & Hader 1994 | Local reference library (not committed — copyright), read — no wavelength data |
| Kim/Prusti/Song/Hader 1984 | Local reference library (not committed — copyright, ILL came through), values verified |

Full-text PDFs for all five papers above are kept outside this repo (in a local
reference library) rather than committed. Wood 1976, Song 1980, Kim/Prusti/Song/Hader
1984, and Kuhnel-Kratz & Hader 1994 came with ILL cover sheets with an explicit "no
further copies, electronic or paper" restriction that doesn't permit redistribution.
Iwatsuki 1992's PDF has no such cover-sheet notice, but it's still a copyrighted
journal article — it was committed to this repo and pushed to the public fork earlier
in this project before this concern came up; that commit has since been removed from
history and force-pushed, and the PDF moved to the same local reference library as the
others. Every value we cite from all five papers has been independently re-verified
against the primary-source PDF text before being written into these docs, even though
the PDFs themselves live outside the repo. The derived Figure 3 crop image
(`references/iwatsuki-1992-figure3-action-spectrum.png`) is still committed, since it's
a small excerpt used for commentary/critique rather than the full paper.
