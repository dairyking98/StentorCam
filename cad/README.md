# CAD reference files

Fusion 360 export bundles for StentorCam hardware, kept here for reference.
Each `<name>.f3d/` folder is a raw Fusion export: the source `.f3d`, derived
`.igs`/`.stl`/`.stp` files, and a version-numbered subfolder with per-body
STLs and sketch DXFs.

- **`StentorCam Base.f3d`** — Holds the IR light plate to the printer's
  build plate using two sprung fingers, improving repeatability when
  removing/reattaching the plate between moves.
- **`StentorCam Lens Mount Ender PlayerOne.f3d`** — Mounts in place of the
  extruder on an Ender 5 S1, with an attachment point for a Player One
  camera. Designed so the `T2 male to C female.f3d` adapter fits, allowing a
  small/medium C-mount lens to attach. Further mods may be needed for
  different lens arrangements; may get updated to be parametric. Specific to
  the Ender 5 S1's mounting arrangement — other printers will need a
  redesign.
- **`T2 male to C female.f3d`** — Astrophotography T2-male-to-C-mount
  adapter, with focal plane positioning appropriate for a C-mount lens.
  Print on a Bambu X1C with highest layer precision and random seams.
- **`Darkfield 96 2.0.f3d`** / **`Darkfield 24 3.0.f3d`** — Darkfield masks
  for 96-well and 24-well plates, respectively.

Not yet included: the IR light plate itself — hoping to add a version of
that CAD here soon.
