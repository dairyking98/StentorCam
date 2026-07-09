"""
gui/steps/input_step.py - Step 0: choose a --video file or a RoboCam
--exp_dir + well, then pick a clip (start frame + length) to preview
against. Populates the shared PipelineState via set_clip().
"""
from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QRadioButton, QSpinBox, QVBoxLayout, QWidget,
)

import robocam_input as ri
from gui.pipeline_state import SourceInfo

DEFAULT_CLIP_LEN = 60


def _load_video_clip(video_path, start_frame, clip_len):
    """
    Seek to start_frame and decode only clip_len frames -- avoids decoding
    an entire long recording just to preview a short clip. Uses the same
    per-frame grayscale treatment as multiTest.load_video_frames so
    detection behaves identically between clip preview and full export.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")

    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps    = cap.get(cv2.CAP_PROP_FPS) or 30.0

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    frames_gray = []
    for _ in range(clip_len):
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        frames_gray.append(gray.astype(np.uint8))
    cap.release()

    return np.array(frames_gray), height, width, fps


class InputStep(QWidget):
    """Emits clip_loaded() once pipeline_state.set_clip() has been called."""
    clip_loaded = Signal()

    def __init__(self, pipeline_state, parent=None):
        super().__init__(parent)
        self.pipeline_state = pipeline_state
        self._wells = []   # list of (well, exp_ts, metadata_path)

        self._video_radio = QRadioButton("Video file (--video)")
        self._expdir_radio = QRadioButton("RoboCam experiment directory (--exp_dir)")
        self._video_radio.setChecked(True)

        self._path_edit = QLineEdit()
        self._browse_btn = QPushButton("Browse...")
        self._browse_btn.clicked.connect(self._on_browse)

        self._well_combo = QComboBox()
        self._well_combo.setEnabled(False)

        self._start_frame_spin = QSpinBox()
        self._start_frame_spin.setRange(0, 10_000_000)
        self._clip_len_spin = QSpinBox()
        self._clip_len_spin.setRange(1, 10_000)
        self._clip_len_spin.setValue(DEFAULT_CLIP_LEN)

        self._load_btn = QPushButton("Load Clip")
        self._load_btn.clicked.connect(self._on_load_clip)

        self._status_label = QLabel("No clip loaded yet.")

        source_row = QHBoxLayout()
        source_row.addWidget(self._video_radio)
        source_row.addWidget(self._expdir_radio)

        path_row = QHBoxLayout()
        path_row.addWidget(self._path_edit)
        path_row.addWidget(self._browse_btn)

        form = QFormLayout()
        form.addRow("Source:", source_row)
        form.addRow("Path:", path_row)
        form.addRow("Well:", self._well_combo)
        form.addRow("Clip start frame:", self._start_frame_spin)
        form.addRow("Clip length (frames):", self._clip_len_spin)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._load_btn)
        layout.addWidget(self._status_label)

        self._video_radio.toggled.connect(self._on_source_kind_changed)
        self._path_edit.textChanged.connect(self._on_path_changed)

    def _on_source_kind_changed(self):
        is_exp_dir = self._expdir_radio.isChecked()
        self._well_combo.setEnabled(is_exp_dir)
        if not is_exp_dir:
            self._well_combo.clear()

    def _on_browse(self):
        if self._video_radio.isChecked():
            path, _ = QFileDialog.getOpenFileName(self, "Select video file")
        else:
            path = QFileDialog.getExistingDirectory(self, "Select RoboCam experiment directory")
        if path:
            self._path_edit.setText(path)

    def _on_path_changed(self, path):
        if not self._expdir_radio.isChecked() or not path:
            return
        try:
            self._wells = ri.discover_wells(path)
        except ValueError as e:
            self._status_label.setText(str(e))
            self._wells = []
        self._well_combo.clear()
        self._well_combo.addItems([w for w, _ts, _p in self._wells])

    def _on_load_clip(self):
        start = self._start_frame_spin.value()
        clip_len = self._clip_len_spin.value()
        path = self._path_edit.text()

        if self._video_radio.isChecked():
            frames_gray, height, width, fps = _load_video_clip(path, start, clip_len)
            source = SourceInfo(kind="video", video_path=path)
        else:
            idx = self._well_combo.currentIndex()
            if idx < 0 or idx >= len(self._wells):
                self._status_label.setText("Select a well first.")
                return
            well, exp_ts, meta_path = self._wells[idx]
            wf = ri.load_well_frames(path, well, exp_ts, meta_path)
            if wf is None:
                self._status_label.setText(f"Well {well} has 0 captured frames.")
                return
            end = min(start + clip_len, wf.frames_gray.shape[0])
            frames_gray = wf.frames_gray[start:end]
            height, width, fps = wf.height, wf.width, wf.fps
            source = SourceInfo(kind="exp_dir", exp_dir=path, well=well, exp_ts=exp_ts)

        if frames_gray.shape[0] == 0:
            self._status_label.setText(
                "No frames loaded -- check the start frame is within range."
            )
            return

        self.pipeline_state.set_clip(frames_gray, height, width, fps, source)
        self._status_label.setText(
            f"Clip loaded: {frames_gray.shape[0]} frames, {width}x{height} @ {fps:.1f} fps."
        )
        self.clip_loaded.emit()
