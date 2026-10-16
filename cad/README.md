# CAD reference files

Fusion 360 export bundles for StentorCam hardware, kept here for reference.
Each `<name>.f3d/` folder holds only the Fusion source (`.f3d`, or `.f3z`
where noted) plus `.step` and `.stl` exports — no other files. The version
number in the export filenames is the Fusion design version.

- **`StentorCam Base.f3d`** — Holds the IR light plate to the printer's
  build plate using two sprung fingers, improving repeatability when
  removing/reattaching the plate between moves. Current version: v5.
- **`StentorCam Lens Mount Ender PlayerOne.f3d`** — Mounts in place of the
  extruder on an Ender 5 S1, with an attachment point for a Player One
  camera. Designed so the `T2 male to C female.f3d` adapter fits, allowing a
  small/medium C-mount lens to attach. Further mods may be needed for
  different lens arrangements; may get updated to be parametric. Specific to
  the Ender 5 S1's mounting arrangement — other printers will need a
  redesign. Current version: v20.
  **Use the `.f3z` in this folder, not the `.f3d`.** The design references
  external geometry (linked components), which the standalone `.f3d` doesn't
  carry, so it won't open correctly on its own. The `.f3z` archive bundles
  those references.
- **`StentorCam PlayerOne.f3d`** — StentorCam Player One camera part.
  Current version: v3.
- **`LED Tube.f3d`** — LED tube for StentorCam illumination. Only the
  `.step`/`.stl` exports (v13) are kept; the Fusion source isn't included.
- **`T2 male to C female.f3d`** — Astrophotography T2-male-to-C-mount
  adapter, with focal plane positioning appropriate for a C-mount lens.
  Print on a Bambu X1C with highest layer precision and random seams.
  Current version: v6.
- **`Darkfield 96 2.0.f3d`** / **`Darkfield 24 3.0.f3d`** — Darkfield masks
  for 96-well and 24-well plates, respectively. Current versions: v1 and
  v6. Darkfield 24 note: circle diameter is 21 mm in v6, planned to go to
  22 mm.

Not yet included: the IR light plate itself — hoping to add a version of
that CAD here soon.
