"""
gui/steps/correction_step.py - Step 4: Pass 2 bidirectional correction
sweep (max_gap, min_track_len, merge_area_thresh).
"""
from __future__ import annotations

from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QSpinBox, QVBoxLayout, QWidget

import multiTest as mt
from gui.preview import ClipPreviewWidget, bgr_to_qpixmap, composite_rgba_over_bgr, gray_to_bgr


class CorrectionStep(QWidget):
    def __init__(self, pipeline_state, parent=None):
        super().__init__(parent)
        self.pipeline_state = pipeline_state

        self._max_gap_spin = QSpinBox()
        self._max_gap_spin.setRange(0, 10_000)
        self._max_gap_spin.setValue(10)

        self._min_track_len_spin = QSpinBox()
        self._min_track_len_spin.setRange(1, 10_000)
        self._min_track_len_spin.setValue(3)

        self._merge_area_thresh_spin = QDoubleSpinBox()
        self._merge_area_thresh_spin.setRange(0.1, 100)
        self._merge_area_thresh_spin.setSingleStep(0.1)
        self._merge_area_thresh_spin.setValue(1.8)

        form = QFormLayout()
        form.addRow("max_gap:", self._max_gap_spin)
        form.addRow("min_track_len:", self._min_track_len_spin)
        form.addRow("merge_area_thresh:", self._merge_area_thresh_spin)

        self.preview = ClipPreviewWidget()

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.preview)

        for spin in (self._max_gap_spin, self._min_track_len_spin,
                    self._merge_area_thresh_spin):
            spin.valueChanged.connect(self._recompute)

    def get_params(self):
        return {
            "max_gap": self._max_gap_spin.value(),
            "min_track_len": self._min_track_len_spin.value(),
            "merge_area_thresh": self._merge_area_thresh_spin.value(),
        }

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
        corrected, _global_median_area, _tracks = ps.get_correction(**params)

        def render(frame_idx):
            base = gray_to_bgr(ps.frames_gray[frame_idx])
            entries = list(corrected[frame_idx].values())
            overlay = mt.draw_overlay(entries, ps.height, ps.width)
            composited = composite_rgba_over_bgr(base, overlay)
            return bgr_to_qpixmap(composited)

        self.preview.set_frame_renderer(render)
