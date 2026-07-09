#!/usr/bin/env python3
"""
multiTest_gui.py - launches the multiTest.py step-by-step tuning wizard.

Usage:
    python multiTest_gui.py

Walks through multiTest.py's pipeline stages one at a time (input/clip
selection, ROI, detection, track assignment, correction sweep, n_cells
enforcement, export), previewing each stage's effect on a short scrubbable
clip before running the finalized parameters against the full source.
Reuses multiTest.py's own functions directly (see gui/pipeline_state.py) --
this is not a second implementation of the tracking algorithm.
"""
import sys

from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
