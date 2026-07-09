#!/usr/bin/env python3

'''
contour_video.py - multi-cell contour detection with correction sweep
                   (background subtraction + Otsu + distance transform +
                    watershed + bidirectional track correction)

Overview:
    Two-pass pipeline:

    PASS 1 — Detection
        For every frame: background subtraction → Otsu mask → distance
        transform → watershed → extract raw contours and centroids.
        All raw detections are stored in a per-frame list.

    PASS 1b — Identity assignment (proximity-based)
        Walk forward through frames assigning each detection to the nearest
        track from the previous frame (greedy nearest-neighbour within
        max_dist). Unmatched detections start new tracks. This gives every
        contour a persistent track_id so the correction sweep can reason
        about each cell across time.

    PASS 2 — Bidirectional correction sweep
        For each track, look at its full detection history and apply three
        corrections:

        (a) Noise removal
            Isolated detections that appear for fewer than min_track_len
            frames with no surrounding history are dropped entirely.

        (b) Gap filling
            If a track is missing for up to max_gap frames between two
            known detections, linearly interpolate centroid position and
            linearly blend (lerp) contour point positions between the
            surrounding frames to synthesise the missing contours.

        (c) Merge splitting
            If the foreground mask for a frame contains a blob whose area
            is significantly larger than the expected single-cell area (
            area > merge_area_thresh × median track area), and two or more
            track centroids from the previous frame fall inside that blob,
            a seeded watershed is re-run using those prior centroids as
            forced seeds to split the merged blob back into individual cells.

    PASS 3 — Overlay rendering
        Draw corrected contours on RGBA frames and composite onto the
        original video with ffmpeg (same approach as stentTrack2.py).

Parameters to tune (use debug_frame1.py first):
    --blur_ksize        Otsu mask quality. Start at 5.
    --min_area          Drop regions smaller than this. Start at 200.
    --peak_min_dist     Watershed seed spacing. Start at 15.
    --max_dist          Max centroid jump (px) for proximity assignment.
    --max_gap           Max frames a track may be missing before gap-fill stops.
    --min_track_len     Tracks shorter than this are treated as noise and removed.
    --merge_area_thresh Blob area / median cell area ratio above which a merge
                        is suspected. Default 1.8.

Inputs (--video and --exp_dir are mutually exclusive):
    --video             Single input video file
    --exp_dir           RoboCam 3.1 experiment directory — reads raw/*.npy
                        directly (via robocam_input.py) and batches every
                        well found under <exp_dir>/raw/, writing outputs to
                        <exp_dir>/tracking/. --output/--overlay are not used
                        in this mode (per-well paths are auto-derived).
    --output            Output CSV path (--video mode only). Columns:
                        frame, track_id, x, y, correction, contour — where
                        "correction" is real/gap_fill/merge_split/
                        soft_recover/forced (same tag the overlay's line
                        style already encodes visually).
    --overlay           Output overlay video path (--video mode only)
    --blur_ksize        Gaussian blur kernel size before Otsu (default: 5)
    --min_area          Minimum contour area in pixels (default: 200)
    --peak_min_dist     Minimum pixel distance between watershed seeds (default: 15)
    --max_dist          Max centroid distance (px) for track assignment (default: 50)
    --max_gap           Max frames to gap-fill per track (default: 10)
    --min_track_len     Min frames a track must exist to be kept (default: 3)
    --merge_area_thresh Merge detection threshold as a multiple of median cell
                        area (default: 1.8)

Outputs:
    --output / <exp_dir>/tracking/*_tracks.csv   Per-cell, per-frame CSV
    --overlay / <exp_dir>/tracking/*_overlay.mp4 Video with corrected
                        per-cell contours and labels

Example usage:
    python multiTest.py \
        --video input.mp4 \
        --overlay output_overlay.mp4 \
        --output output_tracks.csv \
        --blur_ksize 5 \
        --min_area 200 \
        --peak_min_dist 15 \
        --max_gap 10

    python multiTest.py --exp_dir /path/to/robocam_experiment_dir
'''

import cv2
import numpy as np
import pandas as pd
import os
import shutil
import subprocess
import argparse
from tqdm import tqdm
from scipy.optimize import linear_sum_assignment

import robocam_input as ri


# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

_PALETTE = [
    (255,  80,  80), (80,  255,  80), (80,   80, 255), (255, 255,  80),
    (255,  80, 255), (80,  255, 255), (255, 160,  80), (160, 255,  80),
    (80,  160, 255), (255,  80, 160), (160,  80, 255), (80,  255, 160),
    (200, 200,  80), (200,  80, 200), (80,  200, 200), (255, 140,  40),
    (40,  255, 140), (140,  40, 255), (255,  40, 140), (40,  140, 255),
]

def cell_color(track_id):
    return _PALETTE[track_id % len(_PALETTE)]


def make_circle_mask(height, width, cx, cy, radius):
    """
    Build a uint8 mask that is 255 inside the circle and 0 outside.
    Applied to the foreground difference image before thresholding so
    detections outside the well boundary are suppressed.
    """
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.circle(mask, (int(cx), int(cy)), int(radius), 255, thickness=-1)
    return mask


# ---------------------------------------------------------------------------
# Watershed segmentation
# ---------------------------------------------------------------------------

def watershed_segment(mask, peak_min_dist=15):
    """
    Standard distance-transform watershed with auto-detected seeds.
    Returns (markers int32, n_seeds int).
    """
    dist      = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    dist_norm = cv2.normalize(dist, None, 0, 1.0, cv2.NORM_MINMAX)

    ksize        = 2 * peak_min_dist + 1
    kernel_peak  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksize, ksize))
    dist_dilated = cv2.dilate(dist_norm, kernel_peak)
    local_max    = ((dist_norm == dist_dilated) & (dist_norm > 0)).astype(np.uint8)

    n_seeds, seed_labels = cv2.connectedComponents(local_max)

    if n_seeds <= 1:
        return np.zeros_like(mask, dtype=np.int32), 0

    dist_u8          = (dist_norm * 255).astype(np.uint8)
    dist_bgr         = cv2.cvtColor(dist_u8, cv2.COLOR_GRAY2BGR)
    markers          = seed_labels.astype(np.int32)
    background_label = n_seeds
    markers[mask == 0] = background_label
    cv2.watershed(dist_bgr, markers)

    return markers, n_seeds - 1


def watershed_seeded(mask, seed_xys, height, width):
    """
    Watershed seeded from explicit (x, y) positions — used for merge splitting.

    Each seed_xy gets a unique label. The watershed floods outward from those
    exact points, splitting a merged blob back into one region per seed.

    Args:
        mask      : uint8 binary mask of the merged blob (255 = foreground)
        seed_xys  : list of (x, y) centroid positions to use as seeds
        height, width : frame dimensions

    Returns:
        markers   : int32 label map (1..n_seeds = cell regions)
        n_seeds   : number of seeds used
    """
    dist      = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    dist_norm = cv2.normalize(dist, None, 0, 1.0, cv2.NORM_MINMAX)

    markers          = np.zeros((height, width), dtype=np.int32)
    background_label = len(seed_xys) + 1

    for i, (sx, sy) in enumerate(seed_xys):
        sx = int(np.clip(sx, 0, width  - 1))
        sy = int(np.clip(sy, 0, height - 1))
        markers[sy, sx] = i + 1          # label 1-indexed

    markers[mask == 0] = background_label

    dist_u8  = (dist_norm * 255).astype(np.uint8)
    dist_bgr = cv2.cvtColor(dist_u8, cv2.COLOR_GRAY2BGR)
    cv2.watershed(dist_bgr, markers)

    return markers, len(seed_xys)


# ---------------------------------------------------------------------------
# Contour helpers
# ---------------------------------------------------------------------------

def contour_centroid(contour):
    M = cv2.moments(contour)
    if M["m00"] == 0:
        return None
    return (M["m10"] / M["m00"], M["m01"] / M["m00"])


def interp_contour(c0, c1, t):
    """
    Linearly interpolate between two contours at parameter t in [0, 1].

    Both contours are resampled to the same number of points before
    interpolation so the blend is point-wise.

    Args:
        c0, c1 : contour arrays of shape (N, 1, 2)
        t      : interpolation parameter (0 = c0, 1 = c1)

    Returns:
        contour array of shape (N, 1, 2) as int32
    """
    n = max(len(c0), len(c1))

    def resample(c, n):
        pts  = c.reshape(-1, 2).astype(np.float32)
        # Parametrise by cumulative arc length, resample uniformly
        diffs  = np.diff(pts, axis=0)
        dists  = np.concatenate([[0], np.linalg.norm(diffs, axis=1).cumsum()])
        total  = dists[-1]
        if total == 0:
            return np.tile(pts[0], (n, 1))
        new_d  = np.linspace(0, total, n)
        xs     = np.interp(new_d, dists, pts[:, 0])
        ys     = np.interp(new_d, dists, pts[:, 1])
        return np.stack([xs, ys], axis=1)

    p0 = resample(c0, n)
    p1 = resample(c1, n)
    blended = ((1 - t) * p0 + t * p1).astype(np.int32)
    return blended.reshape(-1, 1, 2)


# ---------------------------------------------------------------------------
# Pass 1b — proximity-based track assignment
# ---------------------------------------------------------------------------

def assign_tracks(all_detections, max_dist=50):
    """
    Walk forward through per-frame detection lists and assign each detection
    to the nearest active track using the Hungarian algorithm.

    Args:
        all_detections : list of lists — all_detections[f] is a list of dicts,
                         each with keys "centroid" (x,y) and "contour".
        max_dist       : maximum centroid distance (px) for a valid match.

    Returns:
        tracks : dict mapping track_id → list of
                 {"frame": int, "centroid": (x,y), "contour": ndarray}
                 Entries are present only for frames where the track was detected.
        frame_tracks : list of lists — frame_tracks[f] is a list of
                       {"track_id": int, "centroid": (x,y), "contour": ndarray}
                       for every detection in frame f after assignment.
    """
    next_id      = 0
    active       = {}    # track_id → last centroid
    tracks       = {}    # track_id → list of frame dicts
    frame_tracks = [[] for _ in all_detections]

    for f, detections in enumerate(all_detections):
        if not detections:
            continue

        det_xys = np.array([d["centroid"] for d in detections], dtype=float)

        if not active:
            # First frame with detections — birth all as new tracks
            for d in detections:
                tid = next_id; next_id += 1
                active[tid] = np.array(d["centroid"])
                tracks[tid] = []
                tracks[tid].append({"frame": f, "centroid": d["centroid"],
                                    "contour": d["contour"]})
                frame_tracks[f].append({"track_id": tid,
                                        "centroid": d["centroid"],
                                        "contour": d["contour"]})
            continue

        # Build cost matrix between active tracks and current detections
        track_ids  = list(active.keys())
        track_xys  = np.array([active[tid] for tid in track_ids], dtype=float)

        diff  = track_xys[:, None, :] - det_xys[None, :, :]
        costs = np.linalg.norm(diff, axis=2)

        rows, cols = linear_sum_assignment(costs)

        matched_tracks = set()
        matched_dets   = set()

        for r, c in zip(rows, cols):
            if costs[r, c] <= max_dist:
                tid = track_ids[r]
                active[tid] = det_xys[c]
                tracks[tid].append({"frame": f,
                                    "centroid": detections[c]["centroid"],
                                    "contour":  detections[c]["contour"]})
                frame_tracks[f].append({"track_id": tid,
                                        "centroid": detections[c]["centroid"],
                                        "contour":  detections[c]["contour"]})
                matched_tracks.add(r)
                matched_dets.add(c)

        # Birth new tracks for unmatched detections
        for c, d in enumerate(detections):
            if c not in matched_dets:
                tid = next_id; next_id += 1
                active[tid] = np.array(d["centroid"])
                tracks[tid] = [{"frame": f, "centroid": d["centroid"],
                                "contour": d["contour"]}]
                frame_tracks[f].append({"track_id": tid,
                                        "centroid": d["centroid"],
                                        "contour":  d["contour"]})

        # Remove tracks that went unmatched (they may re-appear — gap fill handles that)
        unmatched_track_ids = {track_ids[r] for r in range(len(track_ids))
                               if r not in matched_tracks}
        for tid in unmatched_track_ids:
            del active[tid]

    return tracks, frame_tracks


# ---------------------------------------------------------------------------
# Pass 2 — bidirectional correction sweep
# ---------------------------------------------------------------------------

def correction_sweep(tracks, frame_tracks, all_masks, n_frames,
                     height, width,
                     max_gap=10, min_track_len=3,
                     merge_area_thresh=1.8):
    """
    Bidirectional correction sweep over the full track history.

    Applies three corrections per track:

    (a) Noise removal
        Tracks with fewer than min_track_len detections are discarded.

    (b) Gap filling
        Missing frames between two known detections are filled by linearly
        interpolating centroid position and blending contour point positions
        between the surrounding frames.

    (c) Merge splitting
        A frame where the foreground blob is suspiciously large (area >
        merge_area_thresh × median track area) and contains multiple prior
        track centroids is re-segmented using seeded watershed with those
        centroids as seeds.

    Args:
        tracks           : dict from assign_tracks
        frame_tracks     : list of lists from assign_tracks (mutated in place)
        all_masks        : list of uint8 binary foreground masks, one per frame
        n_frames         : total frame count
        height, width    : frame dimensions
        max_gap          : maximum gap length to fill
        min_track_len    : minimum track length to keep
        merge_area_thresh: area ratio threshold for merge detection

    Returns:
        corrected_frame_tracks : list of lists with same structure as
                                 frame_tracks but with corrections applied.
    """

    # Build a corrected copy — indexed as [frame][track_id] = entry dict
    # Start by indexing frame_tracks for fast lookup
    corrected = [dict() for _ in range(n_frames)]
    for f, entries in enumerate(frame_tracks):
        for e in entries:
            corrected[f][e["track_id"]] = e

    # ------------------------------------------------------------------
    # (a) Noise removal — drop tracks shorter than min_track_len
    # ------------------------------------------------------------------
    short_ids = {tid for tid, hist in tracks.items() if len(hist) < min_track_len}
    for f in range(n_frames):
        for tid in short_ids:
            corrected[f].pop(tid, None)
    for tid in short_ids:
        del tracks[tid]

    print(f"  Noise removal: dropped {len(short_ids)} short tracks.")

    # ------------------------------------------------------------------
    # Compute median cell area per track (used for merge detection)
    # ------------------------------------------------------------------
    def track_median_area(hist):
        areas = []
        for e in hist:
            c = e["contour"]
            if c is not None:
                areas.append(cv2.contourArea(c))
        return float(np.median(areas)) if areas else 0.0

    track_areas = {tid: track_median_area(hist) for tid, hist in tracks.items()}
    all_areas   = [a for a in track_areas.values() if a > 0]
    global_median_area = float(np.median(all_areas)) if all_areas else 1.0

    # ------------------------------------------------------------------
    # (b) Gap filling + (c) Merge splitting — per track
    # ------------------------------------------------------------------
    gaps_filled  = 0
    merges_fixed = 0

    for tid, hist in tqdm(tracks.items(), desc="Correction sweep"):
        # Sort history by frame
        hist_sorted = sorted(hist, key=lambda e: e["frame"])
        frames_seen = {e["frame"] for e in hist_sorted}
        med_area    = track_areas.get(tid, global_median_area) or global_median_area

        first_f = hist_sorted[0]["frame"]
        last_f  = hist_sorted[-1]["frame"]

        # Walk through every consecutive pair of known detections
        for i in range(len(hist_sorted) - 1):
            e0 = hist_sorted[i]
            e1 = hist_sorted[i + 1]
            f0 = e0["frame"]
            f1 = e1["frame"]
            gap = f1 - f0 - 1

            if gap == 0:
                continue   # consecutive frames, nothing to fill

            if gap > max_gap:
                continue   # gap too large to interpolate reliably

            xy0 = np.array(e0["centroid"], dtype=float)
            xy1 = np.array(e1["centroid"], dtype=float)
            c0  = e0["contour"]
            c1  = e1["contour"]

            for step in range(1, gap + 1):
                f_fill = f0 + step
                t      = step / (gap + 1)

                # Interpolated centroid
                cx_f = float(xy0[0] * (1 - t) + xy1[0] * t)
                cy_f = float(xy0[1] * (1 - t) + xy1[1] * t)

                # Check if this frame's mask has a merge candidate at this location
                mask_f    = all_masks[f_fill]
                blob_area = 0
                if mask_f is not None:
                    ix = int(np.clip(cx_f, 0, width  - 1))
                    iy = int(np.clip(cy_f, 0, height - 1))
                    if mask_f[iy, ix] > 0:
                        # Find which blob this centroid falls in
                        n_labels, label_map = cv2.connectedComponents(mask_f)
                        blob_id   = label_map[iy, ix]
                        blob_area = int((label_map == blob_id).sum())

                is_merge = (blob_area > merge_area_thresh * med_area
                            and blob_area > merge_area_thresh * global_median_area)

                if is_merge:
                    # -------------------------------------------------
                    # (c) Merge splitting
                    # Collect all track centroids that predict they should
                    # be inside this blob at f_fill, then re-run seeded
                    # watershed on the blob using those centroids.
                    # -------------------------------------------------
                    blob_mask = np.zeros((height, width), dtype=np.uint8)
                    blob_mask[label_map == blob_id] = 255

                    # Gather seed centroids: interpolate every track that
                    # has detections on both sides of f_fill
                    seed_xys  = []
                    seed_tids = []
                    for other_tid, other_hist in tracks.items():
                        other_sorted = sorted(other_hist, key=lambda e: e["frame"])
                        other_frames = [e["frame"] for e in other_sorted]
                        # Find surrounding frames
                        before = [e for e in other_sorted if e["frame"] <= f_fill]
                        after  = [e for e in other_sorted if e["frame"] >= f_fill]
                        if not before or not after:
                            continue
                        eb = before[-1]; ea = after[0]
                        if ea["frame"] == eb["frame"]:
                            pred_xy = np.array(eb["centroid"])
                        else:
                            tt = (f_fill - eb["frame"]) / (ea["frame"] - eb["frame"])
                            pred_xy = (np.array(eb["centroid"]) * (1 - tt) +
                                       np.array(ea["centroid"]) * tt)
                        # Only add if predicted centroid falls inside the blob
                        px = int(np.clip(pred_xy[0], 0, width  - 1))
                        py = int(np.clip(pred_xy[1], 0, height - 1))
                        if blob_mask[py, px] > 0:
                            seed_xys.append(pred_xy)
                            seed_tids.append(other_tid)

                    if len(seed_xys) >= 2:
                        ws_markers, n_ws = watershed_seeded(
                            blob_mask, seed_xys, height, width
                        )
                        for s_idx, s_tid in enumerate(seed_tids):
                            region = np.zeros((height, width), dtype=np.uint8)
                            region[ws_markers == s_idx + 1] = 255
                            sub_contours, _ = cv2.findContours(
                                region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                            )
                            if not sub_contours:
                                continue
                            sub_c = max(sub_contours, key=cv2.contourArea)
                            sub_M = cv2.moments(sub_c)
                            if sub_M["m00"] == 0:
                                continue
                            scx = sub_M["m10"] / sub_M["m00"]
                            scy = sub_M["m01"] / sub_M["m00"]
                            entry = {"track_id": s_tid,
                                     "centroid": (scx, scy),
                                     "contour":  sub_c,
                                     "corrected": "merge_split"}
                            corrected[f_fill][s_tid] = entry
                        merges_fixed += 1
                        continue   # skip the interpolation below for this frame

                # ---------------------------------------------------------
                # (b) Gap fill — interpolate contour and centroid
                # ---------------------------------------------------------
                interp_c = interp_contour(c0, c1, t)
                entry = {"track_id": tid,
                         "centroid": (cx_f, cy_f),
                         "contour":  interp_c,
                         "corrected": "gap_fill"}
                corrected[f_fill][tid] = entry
                gaps_filled += 1

    print(f"  Gap filling:    {gaps_filled} frames filled.")
    print(f"  Merge splits:   {merges_fixed} merge events corrected.")

    return corrected, global_median_area



# ---------------------------------------------------------------------------
# Pass 2b — n_cells enforcement
# ---------------------------------------------------------------------------

def interp_centroid_for_track(tid, f_target, tracks):
    """
    Interpolate the expected centroid of track tid at frame f_target
    using the nearest known detections before and after.
    Returns (x, y) float tuple or None if track has no surrounding data.
    """
    hist = sorted(tracks[tid], key=lambda e: e["frame"])
    before = [e for e in hist if e["frame"] <= f_target]
    after  = [e for e in hist if e["frame"] >= f_target]
    if not before and not after:
        return None
    if not before:
        return after[0]["centroid"]
    if not after:
        return before[-1]["centroid"]
    eb = before[-1]
    ea = after[0]
    if eb["frame"] == ea["frame"]:
        return eb["centroid"]
    t = (f_target - eb["frame"]) / (ea["frame"] - eb["frame"])
    x = eb["centroid"][0] * (1 - t) + ea["centroid"][0] * t
    y = eb["centroid"][1] * (1 - t) + ea["centroid"][1] * t
    return (x, y)


def interp_contour_for_track(tid, f_target, tracks):
    """
    Interpolate the expected contour of track tid at frame f_target
    using the nearest known contours before and after.
    Returns interpolated contour array or None.
    """
    hist = sorted(tracks[tid], key=lambda e: e["frame"])
    before = [e for e in hist if e["frame"] <= f_target and e["contour"] is not None]
    after  = [e for e in hist if e["frame"] >= f_target and e["contour"] is not None]
    if not before and not after:
        return None
    if not before:
        return after[0]["contour"]
    if not after:
        return before[-1]["contour"]
    eb = before[-1]
    ea = after[0]
    if eb["frame"] == ea["frame"]:
        return eb["contour"]
    t = (f_target - eb["frame"]) / (ea["frame"] - eb["frame"])
    return interp_contour(eb["contour"], ea["contour"], t)


def enforce_n_cells(corrected, tracks, all_masks, n_frames,
                    height, width, n_cells,
                    global_median_area, peak_min_dist=15):
    """
    Per-frame enforcement of a known cell count.

    For each frame, after the main correction sweep:

    UNDER-DETECTION  (present < n_cells)
        Step 1 — soft: re-run watershed on the foreground mask with a
                 lower peak_min_dist to try to find missed seeds.
                 Accept new detections only if their centroid matches a
                 missing track's predicted position within max_dist px.
        Step 2 — hard fallback: if a missing track still has no detection,
                 interpolate its centroid and contour from surrounding frames
                 and insert it as a 'forced' entry.

    OVER-DETECTION   (present > n_cells)
        Score each detection by consistency with its track history:
            score = displacement from predicted position (lower = better)
                  + |area - track median area| / track median area
        Remove the excess detections with the highest (worst) scores,
        preferring to keep detections from long, established tracks.

    Args:
        corrected        : list of dicts [frame][track_id] = entry (mutated)
        tracks           : track history dict (read-only in this function)
        all_masks        : list of uint8 binary foreground masks per frame
        n_frames         : total frame count
        height, width    : frame dimensions
        n_cells          : target cell count per frame
        global_median_area: median cell area across all tracks
        peak_min_dist    : watershed seed spacing for soft re-detection

    Returns:
        under_soft  : count of frames fixed by soft re-detection
        under_hard  : count of frames fixed by forced interpolation
        over_removed: count of excess detections removed
    """
    under_soft   = 0
    under_hard   = 0
    over_removed = 0

    # Pre-compute track lengths for scoring (longer = more trustworthy)
    track_lengths = {tid: len(hist) for tid, hist in tracks.items()}

    # Pre-compute per-track median area
    track_areas = {}
    for tid, hist in tracks.items():
        areas = [cv2.contourArea(e["contour"])
                 for e in hist if e["contour"] is not None]
        track_areas[tid] = float(np.median(areas)) if areas else global_median_area

    for f in tqdm(range(n_frames), desc="Pass 2b: n_cells enforcement"):
        present_ids = set(corrected[f].keys())
        count       = len(present_ids)

        if count == n_cells:
            continue

        # All known track IDs after noise removal
        all_tids    = set(tracks.keys())
        missing_ids = all_tids - present_ids

        # ----------------------------------------------------------
        # UNDER-DETECTION
        # ----------------------------------------------------------
        if count < n_cells and missing_ids:
            mask_f = all_masks[f]

            # Step 1 — soft: re-run watershed with finer seed spacing
            soft_peak = max(5, peak_min_dist // 2)
            ws_markers, n_ws = watershed_segment(mask_f, soft_peak)

            # Build list of new candidate detections from finer watershed
            candidates = []
            for cell_id in range(1, n_ws + 1):
                region = np.zeros((height, width), dtype=np.uint8)
                region[ws_markers == cell_id] = 255
                if region.sum() / 255 < global_median_area * 0.3:
                    continue
                ctrs, _ = cv2.findContours(
                    region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )
                if not ctrs:
                    continue
                ctr = max(ctrs, key=cv2.contourArea)
                cen = contour_centroid(ctr)
                if cen is None:
                    continue
                # Only accept if not already covered by a present track
                already_covered = False
                for pid in present_ids:
                    pred = interp_centroid_for_track(pid, f, tracks)
                    if pred and np.linalg.norm(
                            np.array(pred) - np.array(cen)) < 20:
                        already_covered = True
                        break
                if not already_covered:
                    candidates.append({"centroid": cen, "contour": ctr})

            # Match candidates to missing tracks by proximity
            for mid in list(missing_ids):
                if count >= n_cells:
                    break
                pred_xy = interp_centroid_for_track(mid, f, tracks)
                if pred_xy is None:
                    continue
                best_cand = None
                best_dist = float("inf")
                for cand in candidates:
                    d = np.linalg.norm(
                        np.array(pred_xy) - np.array(cand["centroid"]))
                    if d < best_dist:
                        best_dist = d
                        best_cand = cand
                if best_cand is not None and best_dist < 40:
                    corrected[f][mid] = {
                        "track_id" : mid,
                        "centroid" : best_cand["centroid"],
                        "contour"  : best_cand["contour"],
                        "corrected": "soft_recover",
                    }
                    candidates.remove(best_cand)
                    missing_ids.discard(mid)
                    count += 1
                    under_soft += 1

            # Step 2 — hard fallback for still-missing tracks.
            #
            # A missing track is usually missing because it's overlapping
            # another cell and the two got merged into a single blob/contour
            # by Pass 1 (the greedy assignment keeps that blob under whichever
            # track it matched, leaving the other track "missing"). Rather
            # than dropping a plain interpolated point at the merge location,
            # look for that merged blob in the mask and split it with a
            # 2-seed watershed (seeded by the missing track's predicted
            # centroid and the present partner's centroid) to recover real
            # contours for both cells. Only fall back to interpolation if no
            # overlap partner / blob can be found.
            n_labels_f  = None
            label_map_f = None
            if mask_f is not None:
                n_labels_f, label_map_f = cv2.connectedComponents(mask_f)

            for mid in list(missing_ids):
                if count >= n_cells:
                    break
                pred_xy = interp_centroid_for_track(mid, f, tracks)
                if pred_xy is None:
                    continue

                split_done = False

                if label_map_f is not None:
                    ix = int(np.clip(pred_xy[0], 0, width  - 1))
                    iy = int(np.clip(pred_xy[1], 0, height - 1))
                    blob_id = label_map_f[iy, ix]

                    if blob_id > 0:
                        blob_area = int((label_map_f == blob_id).sum())
                        expected_area = track_areas.get(mid, global_median_area) \
                            or global_median_area

                        # Only treat this as a merge if the blob is
                        # meaningfully bigger than a single cell.
                        if blob_area > 1.4 * expected_area:
                            # Find a currently-present track sharing this
                            # blob — the merge partner that absorbed mid.
                            partner_tid = None
                            for pid, p_entry in corrected[f].items():
                                if pid == mid:
                                    continue
                                pcx, pcy = p_entry["centroid"]
                                pix = int(np.clip(pcx, 0, width  - 1))
                                piy = int(np.clip(pcy, 0, height - 1))
                                if label_map_f[piy, pix] == blob_id:
                                    partner_tid = pid
                                    break

                            if partner_tid is not None:
                                blob_mask = np.zeros((height, width), dtype=np.uint8)
                                blob_mask[label_map_f == blob_id] = 255

                                partner_xy = corrected[f][partner_tid]["centroid"]
                                seed_xys   = [pred_xy, partner_xy]
                                seed_tids  = [mid, partner_tid]

                                ws_markers, n_ws = watershed_seeded(
                                    blob_mask, seed_xys, height, width
                                )

                                split_entries = {}
                                for s_idx, s_tid in enumerate(seed_tids):
                                    region = np.zeros((height, width), dtype=np.uint8)
                                    region[ws_markers == s_idx + 1] = 255
                                    sub_contours, _ = cv2.findContours(
                                        region, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE
                                    )
                                    if not sub_contours:
                                        continue
                                    sub_c = max(sub_contours, key=cv2.contourArea)
                                    sub_M = cv2.moments(sub_c)
                                    if sub_M["m00"] == 0:
                                        continue
                                    scx = sub_M["m10"] / sub_M["m00"]
                                    scy = sub_M["m01"] / sub_M["m00"]
                                    split_entries[s_tid] = {
                                        "track_id" : s_tid,
                                        "centroid" : (scx, scy),
                                        "contour"  : sub_c,
                                        "corrected": "merge_split",
                                    }

                                # Only commit if both halves recovered —
                                # otherwise fall through to interpolation.
                                if mid in split_entries and partner_tid in split_entries:
                                    corrected[f][mid]         = split_entries[mid]
                                    corrected[f][partner_tid] = split_entries[partner_tid]
                                    count += 1
                                    under_hard += 1
                                    split_done = True

                if split_done:
                    continue

                # Fallback — no overlap partner found or split failed:
                # plain centroid/contour interpolation (drawn as a cross).
                pred_ctr = interp_contour_for_track(mid, f, tracks)
                corrected[f][mid] = {
                    "track_id" : mid,
                    "centroid" : pred_xy,
                    "contour"  : pred_ctr,
                    "corrected": "forced",
                }
                count += 1
                under_hard += 1

        # ----------------------------------------------------------
        # OVER-DETECTION — remove least-consistent excess detections
        # ----------------------------------------------------------
        elif count > n_cells:
            excess = count - n_cells

            # Score each present detection
            scores = []
            for tid in present_ids:
                entry    = corrected[f][tid]
                pred_xy  = interp_centroid_for_track(tid, f, tracks)
                det_xy   = np.array(entry["centroid"])

                # Displacement from predicted position
                disp = (np.linalg.norm(np.array(pred_xy) - det_xy)
                        if pred_xy else 999.0)

                # Area consistency
                med_area = track_areas.get(tid, global_median_area)
                area     = (cv2.contourArea(entry["contour"])
                            if entry["contour"] is not None else 0)
                area_err = abs(area - med_area) / max(med_area, 1)

                # Track length — longer tracks are more trustworthy
                tlen = track_lengths.get(tid, 1)

                score = disp + 20.0 * area_err - 0.1 * tlen
                scores.append((score, tid))

            # Remove the worst-scoring excess detections
            scores.sort(reverse=True)   # highest score = worst
            for _, tid in scores[:excess]:
                corrected[f].pop(tid, None)
                over_removed += 1

    return under_soft, under_hard, over_removed

# ---------------------------------------------------------------------------
# Overlay drawing
# ---------------------------------------------------------------------------

def draw_overlay(frame_entries, height, width):
    """
    Draw contours, centroid dots, and labels onto a transparent RGBA frame.
    Gap-filled detections are drawn with a dashed style (dotted contour).
    Merge-split detections are drawn with a thicker contour.

    Returns uint8 RGBA array.
    """
    overlay = np.zeros((height, width, 4), dtype=np.uint8)

    for entry in frame_entries:
        tid     = entry["track_id"]
        cx, cy  = entry["centroid"]
        contour = entry["contour"]
        kind    = entry.get("corrected", None)

        if contour is None:
            continue

        color = cell_color(tid) + (255,)
        pts   = contour.reshape(-1, 2)

        if kind == "gap_fill":
            # Dashed contour — draw every other segment
            for i in range(0, len(pts), 2):
                p1 = tuple(pts[i].astype(int))
                p2 = tuple(pts[(i + 1) % len(pts)].astype(int))
                cv2.line(overlay, p1, p2, color, 1)
        elif kind == "merge_split":
            # Thicker contour to flag corrected merges
            for i in range(len(pts)):
                p1 = tuple(pts[i].astype(int))
                p2 = tuple(pts[(i + 1) % len(pts)].astype(int))
                cv2.line(overlay, p1, p2, color, 3)
        elif kind == "soft_recover":
            # Dotted thin contour — recovered from image data
            for i in range(0, len(pts), 3):
                p1 = tuple(pts[i].astype(int))
                cv2.circle(overlay, p1, 1, color, -1)
        elif kind == "forced":
            # Cross marker only — fully synthesised, no image evidence
            cx_i, cy_i = int(cx), int(cy)
            cv2.drawMarker(overlay, (cx_i, cy_i), color,
                           cv2.MARKER_CROSS, 12, 2)
        else:
            for i in range(len(pts)):
                p1 = tuple(pts[i].astype(int))
                p2 = tuple(pts[(i + 1) % len(pts)].astype(int))
                cv2.line(overlay, p1, p2, color, 2)

        cv2.circle(overlay, (int(cx), int(cy)), 4, color, -1)
        cv2.putText(overlay, str(tid),
                    (int(cx) + 6, int(cy) - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    color, 1, cv2.LINE_AA)

    return overlay


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def _build_roi(height, width, roi_cx, roi_cy, roi_r):
    """Resolve circular-ROI parameters and build the mask once (reused
    every frame). Returns (circle_mask_or_None, roi_cx, roi_cy)."""
    _roi_cx = roi_cx if roi_cx is not None else width  / 2.0
    _roi_cy = roi_cy if roi_cy is not None else height / 2.0

    if roi_r is not None:
        circle_mask = make_circle_mask(height, width, _roi_cx, _roi_cy, roi_r)
        print(f"Circular ROI: centre=({_roi_cx:.1f}, {_roi_cy:.1f}), radius={roi_r} px")
    else:
        circle_mask = None
        print("No circular ROI — using full frame.")

    return circle_mask, _roi_cx, _roi_cy


def _process_frames(frames_gray, height, width, circle_mask,
                    blur_ksize=5, min_area=200, peak_min_dist=15,
                    max_dist=50, max_gap=10, min_track_len=3,
                    merge_area_thresh=1.8, n_cells=None):
    """
    Core Pass 1 / 1b / 2 / 2b tracking pipeline over an already-loaded
    (n, H, W) uint8 grayscale frame stack — source-agnostic: a decoded
    video and a RoboCam raw burst both land here in the same shape.

    Returns corrected_frame_tracks: list of lists, one per frame, each a
    list of {"track_id", "centroid", "contour", "corrected"} entries.
    """
    background = np.median(frames_gray, axis=0).astype(np.uint8)
    print("Median background computed.")

    # ------------------------------------------------------------------
    # Pass 1 — per-frame detection
    # ------------------------------------------------------------------
    morph_kernel   = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    ksize          = blur_ksize if blur_ksize % 2 == 1 else blur_ksize + 1
    all_detections = []   # list of lists of detection dicts
    all_masks      = []   # binary foreground masks per frame (for merge splitting)

    for frame_idx in tqdm(range(len(frames_gray)), desc="Pass 1: detecting"):
        gray = frames_gray[frame_idx]

        fg      = cv2.absdiff(gray, background)
        if circle_mask is not None:
            fg = cv2.bitwise_and(fg, fg, mask=circle_mask)
        fg_blur = cv2.GaussianBlur(fg, (ksize, ksize), 0)
        _, mask = cv2.threshold(fg_blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        mask    = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  morph_kernel)
        mask    = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, morph_kernel)
        all_masks.append(mask)

        contours_all, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        detections = []
        for contour in contours_all:
            if cv2.contourArea(contour) < min_area:
                continue
            cen = contour_centroid(contour)
            if cen is None:
                continue
            detections.append({"centroid": cen, "contour": contour})

        all_detections.append(detections)

    # ------------------------------------------------------------------
    # Pass 1b — proximity-based track assignment
    # ------------------------------------------------------------------
    print("Pass 1b: assigning track identities...")
    tracks, frame_tracks = assign_tracks(all_detections, max_dist=max_dist)
    print(f"  {len(tracks)} raw tracks found.")

    # ------------------------------------------------------------------
    # Pass 2 — bidirectional correction sweep
    # ------------------------------------------------------------------
    print("Pass 2: correction sweep...")
    corrected, global_median_area = correction_sweep(
        tracks, frame_tracks, all_masks,
        n_frames         = len(frames_gray),
        height           = height,
        width            = width,
        max_gap          = max_gap,
        min_track_len    = min_track_len,
        merge_area_thresh= merge_area_thresh,
    )

    # ------------------------------------------------------------------
    # Pass 2b — n_cells enforcement
    # ------------------------------------------------------------------
    if n_cells is not None:
        print(f"Pass 2b: enforcing n_cells={n_cells} per frame...")
        u_soft, u_hard, o_rm = enforce_n_cells(
            corrected, tracks, all_masks,
            n_frames           = len(frames_gray),
            height             = height,
            width              = width,
            n_cells            = n_cells,
            global_median_area = global_median_area,
            peak_min_dist      = peak_min_dist,
        )
        print(f"  Soft recoveries : {u_soft}")
        print(f"  Forced inserts  : {u_hard}")
        print(f"  Excess removed  : {o_rm}")
    else:
        print("n_cells not set — skipping cell-count enforcement.")

    return [list(corrected[f].values()) for f in range(len(frames_gray))]


def _contour_to_string(contour):
    """Serialize a contour to 'x1,y1;x2,y2;...' (same format as
    stentTrack.py's contour_to_string)."""
    return ";".join([f"{int(p[0][0])},{int(p[0][1])}" for p in contour])


def write_tracks_csv(corrected_frame_tracks, output_csv):
    """
    Write one row per (frame, track) to output_csv:
        frame, track_id, x, y, correction, contour
    "correction" is the same tag draw_overlay() already uses to choose
    line style: a real detection (None) becomes "real"; otherwise one of
    gap_fill / merge_split / soft_recover / forced.
    """
    rows = []
    for frame_idx, entries in enumerate(corrected_frame_tracks):
        for entry in entries:
            contour = entry.get("contour")
            rows.append({
                "frame": frame_idx,
                "track_id": entry["track_id"],
                "x": entry["centroid"][0],
                "y": entry["centroid"][1],
                "correction": entry.get("corrected") or "real",
                "contour": _contour_to_string(contour) if contour is not None else "",
            })
    pd.DataFrame(rows).to_csv(output_csv, index=False)
    print(f"Saved CSV → {output_csv}")


def render_overlay_frames(corrected_frame_tracks, height, width, temp_dir,
                          circle_mask=None, roi_cx=None, roi_cy=None, roi_r=None):
    """Pass 3: draw each frame's corrected tracks onto a transparent RGBA
    canvas and write it to temp_dir as frame_%05d.png."""
    os.makedirs(temp_dir, exist_ok=True)

    for frame_idx, entries in enumerate(
            tqdm(corrected_frame_tracks, desc="Pass 3: rendering")):
        overlay_frame = draw_overlay(entries, height, width)
        if circle_mask is not None:
            cv2.circle(overlay_frame,
                       (int(roi_cx), int(roi_cy)), int(roi_r),
                       (200, 200, 200, 120), 2)
        cv2.imwrite(
            os.path.join(temp_dir, f"frame_{frame_idx:05d}.png"),
            overlay_frame
        )


def detect_and_label(video_path, overlay_video, output_csv=None,
                     blur_ksize=5, min_area=200, peak_min_dist=15,
                     max_dist=50, max_gap=10, min_track_len=3,
                     merge_area_thresh=1.8, n_cells=None,
                     roi_cx=None, roi_cy=None, roi_r=None):
    """
    --video entry point: decode a single mp4 with OpenCV, run the
    tracking pipeline, optionally write a CSV (frame, track_id, x, y,
    correction, contour), then composite the overlay onto the original
    video with ffmpeg — unchanged from before the shared pipeline was
    split into _process_frames/render_overlay_frames.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")

    width       = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height      = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps         = cap.get(cv2.CAP_PROP_FPS) or 30.0

    print(f"Video: {width}x{height}, {frame_count} frames @ {fps:.1f} fps")

    frames_gray = []
    for _ in tqdm(range(frame_count), desc="Reading frames"):
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        frames_gray.append(gray.astype(np.uint8))
    cap.release()
    frames_gray = np.array(frames_gray)

    circle_mask, _roi_cx, _roi_cy = _build_roi(height, width, roi_cx, roi_cy, roi_r)

    corrected_frame_tracks = _process_frames(
        frames_gray, height, width, circle_mask,
        blur_ksize=blur_ksize, min_area=min_area, peak_min_dist=peak_min_dist,
        max_dist=max_dist, max_gap=max_gap, min_track_len=min_track_len,
        merge_area_thresh=merge_area_thresh, n_cells=n_cells,
    )

    if output_csv:
        write_tracks_csv(corrected_frame_tracks, output_csv)

    temp_dir = "overlay_frames_temp"
    render_overlay_frames(corrected_frame_tracks, height, width, temp_dir,
                          circle_mask, _roi_cx, _roi_cy, roi_r)

    overlay_pattern = os.path.join(temp_dir, "frame_%05d.png")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-framerate", str(fps),
        "-i", overlay_pattern,
        "-filter_complex", "[1]format=rgba[ovr];[0][ovr]overlay",
        "-c:a", "copy",
        overlay_video,
    ]
    subprocess.run(cmd, check=True)
    print(f"Saved overlay → {overlay_video}")


def detect_and_label_from_wellframes(wf, output_csv, overlay_video, temp_dir,
                                     blur_ksize=5, min_area=200, peak_min_dist=15,
                                     max_dist=50, max_gap=10, min_track_len=3,
                                     merge_area_thresh=1.8, n_cells=None,
                                     roi_cx=None, roi_cy=None, roi_r=None):
    """
    --exp_dir entry point for one already-loaded RoboCam well (see
    robocam_input.WellFrames). There is no pre-existing encoded source
    video to hand to ffmpeg, so the lazily-debayered BGR frames are piped
    into ffmpeg's first input over stdin instead of a file path — same
    overlay filter graph as the --video path otherwise.
    """
    height, width = wf.height, wf.width
    circle_mask, _roi_cx, _roi_cy = _build_roi(height, width, roi_cx, roi_cy, roi_r)

    corrected_frame_tracks = _process_frames(
        wf.frames_gray, height, width, circle_mask,
        blur_ksize=blur_ksize, min_area=min_area, peak_min_dist=peak_min_dist,
        max_dist=max_dist, max_gap=max_gap, min_track_len=min_track_len,
        merge_area_thresh=merge_area_thresh, n_cells=n_cells,
    )

    write_tracks_csv(corrected_frame_tracks, output_csv)

    render_overlay_frames(corrected_frame_tracks, height, width, temp_dir,
                          circle_mask, _roi_cx, _roi_cy, roi_r)

    frame_count = len(corrected_frame_tracks)
    overlay_pattern = os.path.join(temp_dir, "frame_%05d.png")
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-s", f"{width}x{height}",
        "-r", str(wf.fps),
        "-i", "-",
        "-r", str(wf.fps),
        "-i", overlay_pattern,
        "-filter_complex", "[1]format=rgba[ovr];[0][ovr]overlay",
        "-c:v", "libx264",
        overlay_video,
    ]
    raw_bytes = b"".join(wf.get_bgr(i).tobytes() for i in range(frame_count))
    subprocess.run(cmd, input=raw_bytes, check=True)
    print(f"Saved overlay → {overlay_video}")


def run_exp_dir(exp_dir, **kwargs):
    """
    Batch entry point: process every well found under <exp_dir>/raw/,
    writing per-well CSV + overlay outputs to <exp_dir>/tracking/.
    """
    wells = ri.discover_wells(exp_dir)
    tracking_dir = os.path.join(exp_dir, "tracking")
    os.makedirs(tracking_dir, exist_ok=True)

    for well, exp_ts, metadata_path in wells:
        wf = ri.load_well_frames(exp_dir, well, exp_ts, metadata_path)
        if wf is None:
            print(f"  [skip] {well} has 0 captured frames")
            continue

        print(f"=== Well {well} ({wf.frames_gray.shape[0]} frames) ===")
        output_csv    = os.path.join(tracking_dir, f"{well}_{exp_ts}_tracks.csv")
        overlay_video = os.path.join(tracking_dir, f"{well}_{exp_ts}_overlay.mp4")
        temp_dir      = os.path.join(tracking_dir, f".overlay_tmp_{well}_{exp_ts}")

        try:
            detect_and_label_from_wellframes(
                wf, output_csv, overlay_video, temp_dir, **kwargs
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Multi-cell contour detection with bidirectional correction. "
                    "Background subtraction + Otsu + watershed, then a correction "
                    "sweep that fills gaps, removes noise, and splits merged blobs. "
                    "Use debug_frame1.py to tune detection parameters first."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--video",   help="Single input video file")
    source.add_argument("--exp_dir",
                        help="RoboCam 3.1 experiment directory — reads "
                             "raw/*.npy directly and batches every well found")
    parser.add_argument("--output",            default=None,
                        help="Output CSV path, columns frame,track_id,x,y,"
                             "correction,contour (--video mode only; --exp_dir "
                             "auto-derives per-well paths under <exp_dir>/tracking/)")
    parser.add_argument("--overlay",           help="Output overlay video path (--video mode only)")
    parser.add_argument("--blur_ksize",        type=int,   default=5,
                        help="Gaussian blur kernel before Otsu (default: 5).")
    parser.add_argument("--min_area",          type=int,   default=200,
                        help="Minimum contour area in pixels (default: 200).")
    parser.add_argument("--peak_min_dist",     type=int,   default=15,
                        help="Watershed seed spacing in pixels (default: 15).")
    parser.add_argument("--max_dist",          type=float, default=50,
                        help="Max centroid jump (px) for track assignment (default: 50).")
    parser.add_argument("--max_gap",           type=int,   default=10,
                        help="Max frames to gap-fill per track (default: 10).")
    parser.add_argument("--min_track_len",     type=int,   default=3,
                        help="Min frames a track must appear to be kept (default: 3).")
    parser.add_argument("--merge_area_thresh", type=float, default=1.8,
                        help="Blob area / median cell area ratio to flag a merge "
                             "(default: 1.8). Lower = more sensitive to merges.")
    parser.add_argument("--n_cells",           type=int,   default=None,
                        help="Expected number of cells per frame. When set, each "
                             "frame is enforced to have exactly this many contours: "
                             "under-detections are recovered via soft re-detection "
                             "then interpolation; over-detections remove the least "
                             "consistent excess tracks. Omit to skip enforcement.")
    parser.add_argument("--roi_cx",            type=float, default=None,
                        help="X coordinate (pixels) of circular ROI centre. "
                             "Defaults to horizontal frame centre when omitted.")
    parser.add_argument("--roi_cy",            type=float, default=None,
                        help="Y coordinate (pixels) of circular ROI centre. "
                             "Defaults to vertical frame centre when omitted.")
    parser.add_argument("--roi_r",             type=float, default=None,
                        help="Radius (pixels) of circular ROI. Pixels outside "
                             "are zeroed before detection. Omit for full frame.")

    args = parser.parse_args()

    tuning_kwargs = dict(
        blur_ksize        = args.blur_ksize,
        min_area          = args.min_area,
        peak_min_dist     = args.peak_min_dist,
        max_dist          = args.max_dist,
        max_gap           = args.max_gap,
        min_track_len     = args.min_track_len,
        merge_area_thresh = args.merge_area_thresh,
        n_cells           = args.n_cells,
        roi_cx            = args.roi_cx,
        roi_cy            = args.roi_cy,
        roi_r             = args.roi_r,
    )

    if args.video:
        if not args.overlay:
            parser.error("--overlay is required with --video")
        detect_and_label(
            video_path    = args.video,
            overlay_video = args.overlay,
            output_csv    = args.output,
            **tuning_kwargs,
        )
    else:
        if args.output or args.overlay:
            parser.error("--output/--overlay are not used with --exp_dir — "
                         "per-well paths are auto-derived under <exp_dir>/tracking/")
        run_exp_dir(args.exp_dir, **tuning_kwargs)