"""
gui/steps/export_step.py - Step 6: run the finalized parameters against
the FULL source (not just the preview clip) via multiTest.py's existing,
unchanged CLI entry points -- so a GUI-driven export and a CLI-driven run
with the same parameters produce identical output (same code path).
"""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QProgressBar,
    QPushButton, QVBoxLayout, QWidget,
)

import multiTest as mt


class _ExportWorker(QThread):
    """Runs the full-source export on a background thread so the UI stays
    responsive -- mirrors RoboCam3.1's ui/processing_panel.py _ProcessWorker
    pattern."""
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, source, params, output_csv=None, overlay_video=None, parent=None):
        super().__init__(parent)
        self.source = source
        self.params = params
        self.output_csv = output_csv
        self.overlay_video = overlay_video

    def run(self):
        try:
            if self.source.kind == "video":
                mt.detect_and_label(
                    self.source.video_path, self.overlay_video,
                    output_csv=self.output_csv, **self.params,
                )
                self.finished_ok.emit(
                    f"Saved {self.output_csv} and {self.overlay_video}"
                )
            else:
                mt.run_exp_dir(self.source.exp_dir, **self.params)
                self.finished_ok.emit(
                    f"Saved per-well output under {self.source.exp_dir}/tracking/"
                )
        except Exception as e:  # noqa: BLE001 - surface any failure to the UI
            self.failed.emit(str(e))


class ExportStep(QWidget):
    def __init__(self, pipeline_state, parent=None):
        super().__init__(parent)
        self.pipeline_state = pipeline_state
        self._worker = None

        self._output_csv_edit = QLineEdit()
        self._output_csv_browse = QPushButton("Browse...")
        self._output_csv_browse.clicked.connect(self._on_browse_csv)

        self._overlay_edit = QLineEdit()
        self._overlay_browse = QPushButton("Browse...")
        self._overlay_browse.clicked.connect(self._on_browse_overlay)

        self._exp_dir_note = QLabel()
        self._exp_dir_note.setWordWrap(True)

        csv_row = QHBoxLayout()
        csv_row.addWidget(self._output_csv_edit)
        csv_row.addWidget(self._output_csv_browse)

        overlay_row = QHBoxLayout()
        overlay_row.addWidget(self._overlay_edit)
        overlay_row.addWidget(self._overlay_browse)

        form = QFormLayout()
        form.addRow("Output CSV:", csv_row)
        form.addRow("Overlay video:", overlay_row)

        self._run_btn = QPushButton("Run Export")
        self._run_btn.clicked.connect(self._on_run)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)   # indeterminate -- multiTest.py has no
                                        # single overall progress fraction to report
        self._progress.setVisible(False)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._exp_dir_note)
        layout.addWidget(self._run_btn)
        layout.addWidget(self._progress)
        layout.addWidget(self._status_label)

    def _on_browse_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Output CSV", filter="CSV (*.csv)")
        if path:
            self._output_csv_edit.setText(path)

    def _on_browse_overlay(self):
        path, _ = QFileDialog.getSaveFileName(self, "Overlay video", filter="MP4 (*.mp4)")
        if path:
            self._overlay_edit.setText(path)

    def on_entered(self):
        source = self.pipeline_state.source
        is_video = source is not None and source.kind == "video"
        self._output_csv_edit.setEnabled(is_video)
        self._output_csv_browse.setEnabled(is_video)
        self._overlay_edit.setEnabled(is_video)
        self._overlay_browse.setEnabled(is_video)
        if is_video:
            self._exp_dir_note.setText("")
        elif source is not None:
            self._exp_dir_note.setText(
                f"--exp_dir mode: every well under {source.exp_dir}/raw/ will be "
                f"batch-processed, writing to {source.exp_dir}/tracking/ "
                f"(not just well {source.well})."
            )

    def _on_run(self):
        try:
            params = self.pipeline_state.get_final_params()
        except RuntimeError as e:
            self._status_label.setText(str(e))
            return

        source = self.pipeline_state.source
        output_csv = self._output_csv_edit.text() or None
        overlay_video = self._overlay_edit.text() or None
        if source.kind == "video" and not overlay_video:
            self._status_label.setText("Set an overlay video output path first.")
            return

        self._run_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status_label.setText("Running...")

        self._worker = _ExportWorker(source, params, output_csv, overlay_video)
        self._worker.finished_ok.connect(self._on_finished_ok)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_finished_ok(self, message):
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)
        self._status_label.setText(message)

    def _on_failed(self, message):
        self._progress.setVisible(False)
        self._run_btn.setEnabled(True)
        self._status_label.setText(f"Export failed: {message}")
