"""
gui/steps/roi_step.py - Step 1: circular ROI mask (roi_cx/cy/r).
"""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QFormLayout, QVBoxLayout, QWidget

from gui.preview import (
    ClipPreviewWidget, bgr_to_qpixmap, composite_rgba_over_bgr,
    draw_roi_circle, gray_to_bgr,
)


class RoiStep(QWidget):
    def __init__(self, pipeline_state, parent=None):
        super().__init__(parent)
        self.pipeline_state = pipeline_state

        self._enabled_check = QCheckBox("Use circular ROI mask")
        self._cx_spin = QDoubleSpinBox()
        self._cy_spin = QDoubleSpinBox()
        self._r_spin = QDoubleSpinBox()
        for spin in (self._cx_spin, self._cy_spin, self._r_spin):
            spin.setRange(0, 100_000)
            spin.setEnabled(False)

        form = QFormLayout()
        form.addRow(self._enabled_check)
        form.addRow("roi_cx:", self._cx_spin)
        form.addRow("roi_cy:", self._cy_spin)
        form.addRow("roi_r:", self._r_spin)

        self.preview = ClipPreviewWidget()

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.preview)

        self._enabled_check.toggled.connect(self._on_toggle_enabled)
        self._cx_spin.valueChanged.connect(self._recompute)
        self._cy_spin.valueChanged.connect(self._recompute)
        self._r_spin.valueChanged.connect(self._recompute)

    def _on_toggle_enabled(self, checked):
        for spin in (self._cx_spin, self._cy_spin, self._r_spin):
            spin.setEnabled(checked)
        self._recompute()

    def get_params(self):
        if not self._enabled_check.isChecked():
            return {"roi_cx": None, "roi_cy": None, "roi_r": None}
        return {
            "roi_cx": self._cx_spin.value(),
            "roi_cy": self._cy_spin.value(),
            "roi_r": self._r_spin.value(),
        }

    def on_entered(self):
        """Called by main_window when this step becomes visible -- default
        the ROI center to the clip's frame center the first time."""
        ps = self.pipeline_state
        if ps.frames_gray is None:
            return
        if self._cx_spin.value() == 0 and self._cy_spin.value() == 0:
            self._cx_spin.setValue(ps.width / 2.0)
            self._cy_spin.setValue(ps.height / 2.0)
            self._r_spin.setValue(min(ps.width, ps.height) / 2.0)
        self.preview.set_num_frames(len(ps.frames_gray))
        self._recompute()

    def _recompute(self):
        ps = self.pipeline_state
        if ps.frames_gray is None:
            return
        params = self.get_params()
        ps.get_roi(params["roi_cx"], params["roi_cy"], params["roi_r"])

        def render(frame_idx):
            _circle_mask, roi_cx, roi_cy, roi_r = ps.get_roi(**params)
            base = gray_to_bgr(ps.frames_gray[frame_idx])
            overlay = draw_roi_circle(roi_cx, roi_cy, roi_r, ps.height, ps.width)
            composited = composite_rgba_over_bgr(base, overlay)
            return bgr_to_qpixmap(composited)

        self.preview.set_frame_renderer(render)
