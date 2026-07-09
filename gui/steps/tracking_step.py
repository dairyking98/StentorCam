"""
gui/steps/tracking_step.py - Step 3: Pass 1b proximity-based track
assignment (max_dist).
"""
from __future__ import annotations

from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QVBoxLayout, QWidget

import multiTest as mt
from gui.preview import ClipPreviewWidget, bgr_to_qpixmap, composite_rgba_over_bgr, gray_to_bgr


class TrackingStep(QWidget):
    def __init__(self, pipeline_state, parent=None):
        super().__init__(parent)
        self.pipeline_state = pipeline_state

        self._max_dist_spin = QDoubleSpinBox()
        self._max_dist_spin.setRange(1, 100_000)
        self._max_dist_spin.setValue(50)

        form = QFormLayout()
        form.addRow("max_dist:", self._max_dist_spin)

        self.preview = ClipPreviewWidget()

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.preview)

        self._max_dist_spin.valueChanged.connect(self._recompute)

    def get_params(self):
        return {"max_dist": self._max_dist_spin.value()}

    def on_entered(self):
        ps = self.pipeline_state
        if ps.frames_gray is None:
            return
        self.preview.set_num_frames(len(ps.frames_gray))
        self._recompute()

    def _recompute(self):
        ps = self.pipeline_state
        if ps.frames_gray is None:
            return
        params = self.get_params()
        _tracks, frame_tracks = ps.get_tracking(**params)

        def render(frame_idx):
            base = gray_to_bgr(ps.frames_gray[frame_idx])
            # frame_tracks entries have no "corrected" tag yet -- draw_overlay
            # falls back to its default solid-line style for those.
            overlay = mt.draw_overlay(frame_tracks[frame_idx], ps.height, ps.width)
            composited = composite_rgba_over_bgr(base, overlay)
            return bgr_to_qpixmap(composited)

        self.preview.set_frame_renderer(render)
