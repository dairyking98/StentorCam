"""
gui/pipeline_state.py - shared cache/invalidation state for the multiTest.py
tuning wizard.

Each pipeline stage (roi -> detection -> tracking -> correction -> ncells)
is cached against the parameters that produced it. Changing a stage's
parameters invalidates every stage after it (a simple linear chain -- five
stages, one direction, no general dirty-tracking graph needed). Navigating
back to an earlier, still-valid stage costs nothing; moving forward past
an invalidated stage recomputes it lazily, once, from the first
invalidated stage onward.

All actual algorithm work is delegated to multiTest.py's existing
functions -- this module only owns caching, not tracking logic.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

import multiTest as mt

STAGE_ORDER = ["roi", "detection", "tracking", "correction", "ncells"]


@dataclass
class SourceInfo:
    """Describes where the full (non-clip) source lives, for the Export
    step -- kind is "video" or "exp_dir"."""
    kind: str
    video_path: Optional[str] = None
    exp_dir: Optional[str] = None
    well: Optional[str] = None
    exp_ts: Optional[str] = None


class PipelineState:
    def __init__(self):
        self.source: Optional[SourceInfo] = None
        self.frames_gray: Optional[np.ndarray] = None   # clip only, (n,H,W) uint8
        self.height: Optional[int] = None
        self.width: Optional[int] = None
        self.fps: Optional[float] = None

        self._stage_params = {name: None for name in STAGE_ORDER}
        self._stage_output = {name: None for name in STAGE_ORDER}

    # ------------------------------------------------------------------
    # Clip / source setup
    # ------------------------------------------------------------------

    def set_clip(self, frames_gray, height, width, fps, source: SourceInfo):
        """Load a new clip (a slice of the full source). Invalidates every
        stage -- a new clip has no valid cached output for anything."""
        self.frames_gray = frames_gray
        self.height = height
        self.width = width
        self.fps = fps
        self.source = source
        self._invalidate_from(0)

    def _invalidate_from(self, index):
        for name in STAGE_ORDER[index:]:
            self._stage_params[name] = None
            self._stage_output[name] = None

    def _needs_recompute(self, name, params):
        return self._stage_params[name] != params

    def _require(self, name):
        if self._stage_output[name] is None:
            raise RuntimeError(
                f"'{name}' stage has no cached output yet -- visit that "
                f"wizard step before this one."
            )
        return self._stage_output[name]

    # ------------------------------------------------------------------
    # Stage 1 -- ROI
    # ------------------------------------------------------------------

    def get_roi(self, roi_cx, roi_cy, roi_r):
        params = (roi_cx, roi_cy, roi_r)
        if self._needs_recompute("roi", params):
            circle_mask, _roi_cx, _roi_cy = mt._build_roi(
                self.height, self.width, roi_cx, roi_cy, roi_r
            )
            self._stage_output["roi"] = (circle_mask, _roi_cx, _roi_cy, roi_r)
            self._stage_params["roi"] = params
            self._invalidate_from(1)
        return self._stage_output["roi"]

    # ------------------------------------------------------------------
    # Stage 2 -- Detection (Pass 1)
    # ------------------------------------------------------------------

    def get_detection(self, blur_ksize, min_area, peak_min_dist):
        params = (blur_ksize, min_area, peak_min_dist)
        if self._needs_recompute("detection", params):
            circle_mask, *_ = self._require("roi")
            all_detections, all_masks = mt.run_pass1(
                self.frames_gray, circle_mask,
                blur_ksize=blur_ksize, min_area=min_area,
                peak_min_dist=peak_min_dist,
            )
            self._stage_output["detection"] = (all_detections, all_masks)
            self._stage_params["detection"] = params
            self._invalidate_from(2)
        return self._stage_output["detection"]

    # ------------------------------------------------------------------
    # Stage 3 -- Track assignment (Pass 1b)
    # ------------------------------------------------------------------

    def get_tracking(self, max_dist):
        params = (max_dist,)
        if self._needs_recompute("tracking", params):
            all_detections, _all_masks = self._require("detection")
            tracks, frame_tracks = mt.assign_tracks(all_detections, max_dist=max_dist)
            self._stage_output["tracking"] = (tracks, frame_tracks)
            self._stage_params["tracking"] = params
            self._invalidate_from(3)
        return self._stage_output["tracking"]

    # ------------------------------------------------------------------
    # Stage 4 -- Correction sweep (Pass 2)
    # ------------------------------------------------------------------

    def get_correction(self, max_gap, min_track_len, merge_area_thresh):
        params = (max_gap, min_track_len, merge_area_thresh)
        if self._needs_recompute("correction", params):
            tracks, frame_tracks = self._require("tracking")
            _all_detections, all_masks = self._require("detection")
            # correction_sweep mutates `tracks`/`frame_tracks` in place
            # (pops short tracks) -- work on copies so re-entering this
            # stage with different params doesn't compound onto an
            # already-pruned tracks dict.
            tracks_copy = copy.deepcopy(tracks)
            frame_tracks_copy = copy.deepcopy(frame_tracks)
            corrected, global_median_area = mt.correction_sweep(
                tracks_copy, frame_tracks_copy, all_masks,
                n_frames=len(self.frames_gray),
                height=self.height, width=self.width,
                max_gap=max_gap, min_track_len=min_track_len,
                merge_area_thresh=merge_area_thresh,
            )
            self._stage_output["correction"] = (corrected, global_median_area, tracks_copy)
            self._stage_params["correction"] = params
            self._invalidate_from(4)
        return self._stage_output["correction"]

    # ------------------------------------------------------------------
    # Stage 5 -- n_cells enforcement (Pass 2b, optional)
    # ------------------------------------------------------------------

    def get_ncells(self, enabled, n_cells, peak_min_dist):
        params = (enabled, n_cells, peak_min_dist)
        if self._needs_recompute("ncells", params):
            corrected, global_median_area, tracks = self._require("correction")
            _all_detections, all_masks = self._require("detection")

            if enabled and n_cells:
                # enforce_n_cells mutates `corrected` in place -- copy so
                # the correction stage's own cache stays untouched.
                corrected_copy = copy.deepcopy(corrected)
                mt.enforce_n_cells(
                    corrected_copy, tracks, all_masks,
                    n_frames=len(self.frames_gray),
                    height=self.height, width=self.width,
                    n_cells=n_cells,
                    global_median_area=global_median_area,
                    peak_min_dist=peak_min_dist,
                )
                result = corrected_copy
            else:
                result = corrected

            frame_tracks_final = [
                list(result[f].values()) for f in range(len(self.frames_gray))
            ]
            self._stage_output["ncells"] = frame_tracks_final
            self._stage_params["ncells"] = params
        return self._stage_output["ncells"]

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def get_final_params(self):
        """
        Assemble the full multiTest.py CLI kwarg set from each stage's
        last-applied parameters, for the Export step's full-source run.
        Raises RuntimeError if any step hasn't been visited yet.
        """
        stage_params = {name: self._stage_params[name] for name in STAGE_ORDER}
        missing = [name for name, params in stage_params.items() if params is None]
        if missing:
            raise RuntimeError(
                f"Visit every wizard step before exporting -- missing: {missing}"
            )

        roi_cx, roi_cy, roi_r = stage_params["roi"]
        blur_ksize, min_area, peak_min_dist = stage_params["detection"]
        (max_dist,) = stage_params["tracking"]
        max_gap, min_track_len, merge_area_thresh = stage_params["correction"]
        enabled, n_cells, _peak_min_dist_ncells = stage_params["ncells"]

        return dict(
            blur_ksize=blur_ksize, min_area=min_area, peak_min_dist=peak_min_dist,
            max_dist=max_dist, max_gap=max_gap, min_track_len=min_track_len,
            merge_area_thresh=merge_area_thresh,
            n_cells=(n_cells if enabled else None),
            roi_cx=roi_cx, roi_cy=roi_cy, roi_r=roi_r,
        )

    # ------------------------------------------------------------------
    # Introspection (used by the UI to decide what to (re)display)
    # ------------------------------------------------------------------

    def is_stale(self, name):
        """True if this stage's cache has been invalidated by an earlier
        stage's parameter change and needs recomputing before it can be
        displayed again."""
        return self._stage_output[name] is None
