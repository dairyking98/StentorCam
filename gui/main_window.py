"""
gui/main_window.py - multiTest.py tuning wizard main window.

A QMainWindow stepping through the pipeline stages one at a time
(Input -> ROI -> Detection -> Tracking -> Correction -> n_cells -> Export),
back/next navigation, all steps sharing one PipelineState instance so
caching/invalidation works across the whole session.
"""
from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from gui.pipeline_state import PipelineState
from gui.steps.correction_step import CorrectionStep
from gui.steps.detection_step import DetectionStep
from gui.steps.export_step import ExportStep
from gui.steps.input_step import InputStep
from gui.steps.ncells_step import NCellsStep
from gui.steps.roi_step import RoiStep
from gui.steps.tracking_step import TrackingStep

STEP_TITLES = [
    "1. Input & Clip",
    "2. ROI",
    "3. Detection",
    "4. Track Assignment",
    "5. Correction Sweep",
    "6. n_cells Enforcement",
    "7. Export",
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("multiTest.py Tuning Wizard")
        self.setGeometry(100, 100, 1000, 800)

        self.pipeline_state = PipelineState()

        self.input_step = InputStep(self.pipeline_state)
        self.roi_step = RoiStep(self.pipeline_state)
        self.detection_step = DetectionStep(self.pipeline_state)
        self.tracking_step = TrackingStep(self.pipeline_state)
        self.correction_step = CorrectionStep(self.pipeline_state)
        self.ncells_step = NCellsStep(self.pipeline_state)
        self.export_step = ExportStep(self.pipeline_state)

        self._steps = [
            self.input_step, self.roi_step, self.detection_step,
            self.tracking_step, self.correction_step, self.ncells_step,
            self.export_step,
        ]

        self._stack = QStackedWidget()
        for step in self._steps:
            self._stack.addWidget(step)

        self._title_label = QLabel()
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        self._title_label.setFont(title_font)

        self._back_btn = QPushButton("< Back")
        self._next_btn = QPushButton("Next >")
        self._back_btn.clicked.connect(self._on_back)
        self._next_btn.clicked.connect(self._on_next)

        nav = QHBoxLayout()
        nav.addWidget(self._back_btn)
        nav.addStretch()
        nav.addWidget(self._next_btn)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self._title_label)
        layout.addWidget(self._stack)
        layout.addLayout(nav)
        self.setCentralWidget(central)

        self.input_step.clip_loaded.connect(self._on_clip_loaded)

        self._set_index(0)

    def _current_index(self):
        return self._stack.currentIndex()

    def _set_index(self, index):
        self._stack.setCurrentIndex(index)
        self._title_label.setText(STEP_TITLES[index])
        self._back_btn.setEnabled(index > 0)

        clip_loaded = self.pipeline_state.frames_gray is not None
        self._next_btn.setEnabled(index < len(self._steps) - 1 and (index > 0 or clip_loaded))

        step = self._steps[index]
        if step is self.ncells_step:
            peak_min_dist = self.detection_step.get_params()["peak_min_dist"]
            step.on_entered(peak_min_dist)
        elif hasattr(step, "on_entered"):
            step.on_entered()

    def _on_back(self):
        if self._current_index() > 0:
            self._set_index(self._current_index() - 1)

    def _on_next(self):
        if self._current_index() < len(self._steps) - 1:
            self._set_index(self._current_index() + 1)

    def _on_clip_loaded(self):
        self._next_btn.setEnabled(True)
