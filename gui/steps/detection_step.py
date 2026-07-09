"""
gui/steps/detection_step.py - Step 2: Pass 1 detection
(blur_ksize, min_area, peak_min_dist).
"""
from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QSpinBox, QVBoxLayout, QWidget

from gui.preview import (
    ClipPreviewWidget, bgr_to_qpixmap, composite_rgba_over_bgr,
    draw_detections, gray_to_bgr,
)


class DetectionStep(QWidget):
    def __init__(self, pipeline_state, parent=None):
        super().__init__(parent)
        self.pipeline_state = pipeline_state

        self._blur_ksize_spin = QSpinBox()
        self._blur_ksize_spin.setRange(1, 99)
        self._blur_ksize_spin.setValue(5)

        self._min_area_spin = QSpinBox()
        self._min_area_spin.setRange(1, 1_000_000)
        self._min_area_spin.setValue(200)

        self._peak_min_dist_spin = QSpinBox()
        self._peak_min_dist_spin.setRange(1, 1000)
        self._peak_min_dist_spin.setValue(15)

        form = QFormLayout()
        form.addRow("blur_ksize:", self._blur_ksize_spin)
        form.addRow("min_area:", self._min_area_spin)
        form.addRow("peak_min_dist:", self._peak_min_dist_spin)

        self.preview = ClipPreviewWidget()

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.preview)

        for spin in (self._blur_ksize_spin, self._min_area_spin, self._peak_min_dist_spin):
            spin.valueChanged.connect(self._recompute)

    def get_params(self):
        return {
            "blur_ksize": self._blur_ksize_spin.value(),
            "min_area": self._min_area_spin.value(),
            "peak_min_dist": self._peak_min_dist_spin.value(),
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
        all_detections, _all_masks = ps.get_detection(**params)

        def render(frame_idx):
            base = gray_to_bgr(ps.frames_gray[frame_idx])
            overlay = draw_detections(all_detections[frame_idx], ps.height, ps.width)
            composited = composite_rgba_over_bgr(base, overlay)
            return bgr_to_qpixmap(composited)

        self.preview.set_frame_renderer(render)
