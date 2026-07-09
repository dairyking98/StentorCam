"""
gui/steps/ncells_step.py - Step 5 (optional): Pass 2b n_cells enforcement.
"""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QFormLayout, QSpinBox, QVBoxLayout, QWidget

import multiTest as mt
from gui.preview import ClipPreviewWidget, bgr_to_qpixmap, composite_rgba_over_bgr, gray_to_bgr


class NCellsStep(QWidget):
    def __init__(self, pipeline_state, parent=None):
        super().__init__(parent)
        self.pipeline_state = pipeline_state

        self._enabled_check = QCheckBox("Enforce a known cell count per frame (n_cells)")

        self._n_cells_spin = QSpinBox()
        self._n_cells_spin.setRange(1, 10_000)
        self._n_cells_spin.setValue(1)
        self._n_cells_spin.setEnabled(False)

        form = QFormLayout()
        form.addRow(self._enabled_check)
        form.addRow("n_cells:", self._n_cells_spin)

        self.preview = ClipPreviewWidget()

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.preview)

        self._enabled_check.toggled.connect(self._on_toggle_enabled)
        self._n_cells_spin.valueChanged.connect(self._recompute)

    def _on_toggle_enabled(self, checked):
        self._n_cells_spin.setEnabled(checked)
        self._recompute()

    def get_params(self):
        enabled = self._enabled_check.isChecked()
        return {"n_cells": self._n_cells_spin.value() if enabled else None}

    def on_entered(self, peak_min_dist: int):
        """peak_min_dist comes from the Detection step's params -- the
        same watershed-seed-spacing parameter enforce_n_cells() reuses for
        its soft re-detection pass."""
        self._peak_min_dist = peak_min_dist
        ps = self.pipeline_state
        if ps.frames_gray is None:
            return
        self.preview.set_num_frames(len(ps.frames_gray))
        self._recompute()

    def _recompute(self):
        ps = self.pipeline_state
        if ps.frames_gray is None:
            return
        enabled = self._enabled_check.isChecked()
        n_cells = self._n_cells_spin.value() if enabled else None
        frame_tracks_final = ps.get_ncells(enabled, n_cells, self._peak_min_dist)

        def render(frame_idx):
            base = gray_to_bgr(ps.frames_gray[frame_idx])
            overlay = mt.draw_overlay(frame_tracks_final[frame_idx], ps.height, ps.width)
            composited = composite_rgba_over_bgr(base, overlay)
            return bgr_to_qpixmap(composited)

        self.preview.set_frame_renderer(render)
