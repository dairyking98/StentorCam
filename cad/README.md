# CAD reference files

Fusion 360 export bundles for StentorCam hardware, kept here for reference.
Each `<name>/` folder holds only the Fusion source (`.f3d`, or `.f3z` where
noted) plus `.step` and `.stl` exports — no other files. The version number
in the export filenames is the Fusion design version. Spaces in Fusion's
original names are replaced with underscores.

Some parts have no Fusion source here: their `.f3d` relied on external
geometry (linked components) that a standalone `.f3d` doesn't carry, so it
wouldn't open correctly on its own. For those, use the `.f3z` (which bundles
the references) if there is one, otherwise just the `.step`/`.stl`.

- **`StentorCam_Base/`** — Holds the IR light plate to the printer's
  build plate using two sprung fingers, improving repeatability when
  removing/reattaching the plate between moves. Current version: v5.
- **`StentorCam_Lens_Mount_Ender_PlayerOne/`** — Mounts in place of the
  extruder on an Ender 5 S1, with an attachment point for a Player One
  camera. Designed so the `T2_male_to_C_female` adapter fits, allowing a
  small/medium C-mount lens to attach. Further mods may be needed for
  different lens arrangements; may get updated to be parametric. Specific to
  the Ender 5 S1's mounting arrangement — other printers will need a
  redesign. Current version: v20. Fusion source is the `.f3z` only (the
  `.f3d` relied on external geometry).
- **`StentorCam_PlayerOne/`** — StentorCam Player One camera part.
  Current version: v3.
- **`LED_Tube/`** — LED tube for StentorCam illumination. The design
  has two separate bodies: the tube and an aperture that threads into the
  tube. Print them as separate parts. Current version: v13. `.step`/`.stl`
  only (the `.f3d` relied on external geometry).
- **`T2_male_to_C_female/`** — Astrophotography T2-male-to-C-mount
  adapter, with focal plane positioning appropriate for a C-mount lens.
  Print on a Bambu X1C with highest layer precision and random seams.
  Current version: v6.
- **`Darkfield_96_2.0/`** / **`Darkfield_24_3.0/`** — Darkfield masks
  for 96-well and 24-well plates, respectively. Current versions: v1 and
  v6. Darkfield 24 note: circle diameter is 21 mm in v6, planned to go to
  22 mm.

Not yet included: the IR light plate itself — hoping to add a version of
that CAD here soon.
