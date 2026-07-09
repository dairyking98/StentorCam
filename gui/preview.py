"""
gui/preview.py - shared image-conversion helpers and the scrubbable clip
preview widget reused by every wizard step from Detection onward.
"""
from __future__ import annotations

from typing import Callable, Optional

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget


def gray_to_bgr(gray: np.ndarray) -> np.ndarray:
    """(H, W) uint8 -> (H, W, 3) uint8 BGR, for compositing overlays onto."""
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def draw_detections(detections, height, width) -> np.ndarray:
    """
    Render raw (untracked) Pass-1 detections as a green-contour RGBA
    overlay -- same visual language as multiTest.draw_overlay's default
    branch, but with no track_id (nothing has been assigned an identity
    yet at the Detection step).
    """
    overlay = np.zeros((height, width, 4), dtype=np.uint8)
    color = (0, 255, 0, 255)
    for det in detections:
        contour = det["contour"]
        cx, cy = det["centroid"]
        pts = contour.reshape(-1, 2)
        for i in range(len(pts)):
            p1 = tuple(pts[i].astype(int))
            p2 = tuple(pts[(i + 1) % len(pts)].astype(int))
            cv2.line(overlay, p1, p2, color, 2)
        cv2.circle(overlay, (int(cx), int(cy)), 4, color, -1)
    return overlay


def draw_roi_circle(roi_cx, roi_cy, roi_r, height, width) -> np.ndarray:
    """Render the circular ROI boundary as an RGBA overlay -- same style
    multiTest.render_overlay_frames draws it with in the real output."""
    overlay = np.zeros((height, width, 4), dtype=np.uint8)
    if roi_r is not None:
        cv2.circle(overlay, (int(roi_cx), int(roi_cy)), int(roi_r),
                   (200, 200, 200, 120), 2)
    return overlay


def composite_rgba_over_bgr(base_bgr: np.ndarray, overlay_rgba: np.ndarray) -> np.ndarray:
    """
    Alpha-composite an RGBA overlay (as produced by multiTest.draw_overlay,
    or a simple contour/track drawing at an earlier stage) onto a BGR base
    frame. Pure numpy/opencv -- no Qt dependency, so it's unit-testable
    without a display.
    """
    alpha = overlay_rgba[:, :, 3:4].astype(np.float32) / 255.0
    overlay_bgr = overlay_rgba[:, :, :3].astype(np.float32)
    base = base_bgr.astype(np.float32)
    blended = overlay_bgr * alpha + base * (1 - alpha)
    return blended.astype(np.uint8)


def bgr_to_qpixmap(bgr: np.ndarray) -> QPixmap:
    """(H, W, 3) uint8 BGR -> QPixmap for display in a QLabel."""
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    rgb = np.ascontiguousarray(rgb)
    h, w, _ = rgb.shape
    qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    # QImage doesn't copy the buffer by default -- copy() so the QPixmap
    # stays valid after `rgb` (a local numpy array) goes out of scope.
    return QPixmap.fromImage(qimg.copy())


def gray_to_qpixmap(gray: np.ndarray) -> QPixmap:
    """(H, W) uint8 grayscale -> QPixmap, no overlay."""
    return bgr_to_qpixmap(gray_to_bgr(gray))


class ClipPreviewWidget(QWidget):
    """
    A QLabel showing one frame of a clip, plus a scrub slider and a
    "Frame i/n" counter. The caller supplies a render callback
    (`set_frame_renderer`) that maps a frame index to a QPixmap; this
    widget only owns the scrub UI, not any tracking-specific rendering.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._renderer: Optional[Callable[[int], QPixmap]] = None
        self._num_frames = 0

        self._image_label = QLabel("No preview yet")
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setMinimumSize(200, 200)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(0)
        self._slider.valueChanged.connect(self._on_slider_changed)

        self._frame_label = QLabel("Frame 0/0")

        controls = QHBoxLayout()
        controls.addWidget(self._slider)
        controls.addWidget(self._frame_label)

        layout = QVBoxLayout(self)
        layout.addWidget(self._image_label)
        layout.addLayout(controls)

    def set_num_frames(self, n: int):
        """(Re)configure the scrub range for a clip of n frames."""
        self._num_frames = n
        self._slider.setMaximum(max(0, n - 1))
        self._slider.setValue(0)
        self._update_frame_label()

    def set_frame_renderer(self, renderer: Callable[[int], QPixmap]):
        """renderer(frame_idx) -> QPixmap, called on scrub and refresh()."""
        self._renderer = renderer
        self.refresh()

    def refresh(self):
        """Re-render the currently-selected frame (e.g. after a stage's
        cached output changed for the same scrub position)."""
        self._render_current()

    def current_frame_index(self) -> int:
        return self._slider.value()

    def _on_slider_changed(self, _value: int):
        self._update_frame_label()
        self._render_current()

    def _update_frame_label(self):
        total = max(self._num_frames - 1, 0)
        self._frame_label.setText(f"Frame {self._slider.value()}/{total}")

    def _render_current(self):
        if self._renderer is None or self._num_frames == 0:
            return
        pixmap = self._renderer(self._slider.value())
        if pixmap is not None:
            self._image_label.setPixmap(pixmap)
