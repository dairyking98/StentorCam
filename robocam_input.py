"""
robocam_input.py - read RoboCam 3.1 experiment directories directly from
their raw/*_stack.npy bursts, without depending on RoboCam's own
postprocess.py (images/, videos/) ever having been run.

Ported (not imported - StentorCam has no package dependency on RoboCam3.1)
from RoboCam3.1's robocam/postprocess.py: well/experiment-timestamp filename
parsing (parse_meta_name) and the raw Bayer/mono -> BGR conversion
(npy_to_bgr).

Only the current stacked-array raw format is supported (one memory-mapped
(n_frames, H, W) array per well, referenced by metadata["frames_file"]).
The pre-2026-07-06 one-.npy-file-per-frame format is not supported.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, NamedTuple, Optional

import cv2
import numpy as np

# Bayer pattern string -> OpenCV debayer code (-> BGR output).
_BAYER_TO_CV2 = {
    "RGGB": cv2.COLOR_BAYER_RG2BGR,
    "BGGR": cv2.COLOR_BAYER_BG2BGR,
    "GRBG": cv2.COLOR_BAYER_GR2BGR,
    "GBRG": cv2.COLOR_BAYER_GB2BGR,
}


def _npy_to_bgr(arr: np.ndarray, camera_meta: dict) -> np.ndarray:
    """
    Convert one raw sensor frame (a row of a RoboCam raw/*_stack.npy) to
    BGR uint8.

    camera_meta fields used (all optional, default to PlayerOne 8-bit RGGB):
      bayer_pattern : "RGGB" | "BGGR" | "GRBG" | "GBRG" | "mono"
      bit_depth     : int (e.g. 8, 10, 12)
    """
    if arr.ndim == 3:
        arr = arr[:, :, 0]

    bayer = camera_meta.get("bayer_pattern", "RGGB")
    depth = int(camera_meta.get("bit_depth", 8))

    if depth > 8:
        max_val = (1 << depth) - 1
        arr = (arr.astype(np.float32) / max_val * 255).clip(0, 255).astype(np.uint8)
    else:
        arr = arr.astype(np.uint8)

    if bayer == "mono":
        return cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)

    debayer_code = _BAYER_TO_CV2.get(bayer, cv2.COLOR_BAYER_RG2BGR)
    return cv2.cvtColor(arr, debayer_code)


def discover_wells(exp_dir: str) -> list[tuple[str, str, Path]]:
    """
    Find every well in a RoboCam experiment directory by globbing
    raw/*_metadata.json. Returns (well, exp_ts, metadata_path) tuples,
    sorted by well name.

    Raises ValueError if raw/ doesn't exist or has no metadata files - this
    is fatal for the whole invocation (malformed input), not a per-well skip.
    """
    raw_dir = Path(exp_dir) / "raw"
    if not raw_dir.is_dir():
        raise ValueError(f"No raw/ directory found in {exp_dir}")

    meta_paths = sorted(raw_dir.glob("*_metadata.json"))
    if not meta_paths:
        raise ValueError(f"No *_metadata.json files found in {raw_dir}")

    wells = []
    for meta_path in meta_paths:
        parts = meta_path.stem.split("_")
        well = parts[0]
        exp_ts = f"{parts[1]}_{parts[2]}" if len(parts) >= 3 else "unknown"
        wells.append((well, exp_ts, meta_path))
    return wells


class WellFrames(NamedTuple):
    well: str
    exp_ts: str
    frames_gray: np.ndarray                 # (n, H, W) uint8
    height: int
    width: int
    fps: float
    laser_events: list[dict]
    get_bgr: Callable[[int], np.ndarray]    # get_bgr(local_frame_idx) -> BGR frame,
                                             # decoded lazily (only called for frames
                                             # actually needed by overlay compositing)


def load_well_frames(exp_dir: str, well: str, exp_ts: str,
                      metadata_path: Path) -> Optional[WellFrames]:
    """
    Load one well's raw burst directly from raw/*_stack.npy.

    Returns None if the well has zero captured frames (caller should skip
    it and continue the batch, not crash the whole run).
    """
    exp_dir = Path(exp_dir)
    raw_dir = exp_dir / "raw"

    with open(metadata_path, encoding="utf-8") as f:
        meta = json.load(f)

    frames_info = sorted(meta.get("frames", []), key=lambda x: x["frame_index"])
    if not frames_info:
        return None

    frames_file = meta.get("frames_file")
    if not frames_file:
        raise ValueError(
            f"{metadata_path} has no 'frames_file' key - pre-2026-07-06 "
            f"per-frame-file raw format is not supported."
        )

    camera_meta = {}
    cam_meta_path = raw_dir / "camera_meta.json"
    if cam_meta_path.exists():
        with open(cam_meta_path, encoding="utf-8") as f:
            camera_meta = json.load(f)

    # The stack is preallocated to an fps-ceiling estimate, so stack.shape[0]
    # is NOT the real frame count - only frames_info (from frames_captured)
    # is authoritative. Index by each entry's own frame_index, never by bare
    # position, and never read rows beyond what frames_info lists.
    stack = np.load(raw_dir / frames_file, mmap_mode="r")
    frame_indices = [fi["frame_index"] for fi in frames_info]

    frames_gray = []
    for real_idx in frame_indices:
        bgr = _npy_to_bgr(stack[real_idx], camera_meta)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        frames_gray.append(gray.astype(np.uint8))
    frames_gray = np.array(frames_gray)

    height, width = frames_gray.shape[1:3]
    fps = float(meta.get("fps_average", meta.get("fps_actual", 0)) or 30.0)
    laser_events = meta.get("laser_events", [])

    def get_bgr(local_frame_idx: int) -> np.ndarray:
        return _npy_to_bgr(stack[frame_indices[local_frame_idx]], camera_meta)

    return WellFrames(
        well=well, exp_ts=exp_ts, frames_gray=frames_gray,
        height=height, width=width, fps=fps,
        laser_events=laser_events, get_bgr=get_bgr,
    )
