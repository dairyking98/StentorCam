#!/usr/bin/env bash
# =============================================================================
# StentorCam — Run Script
# =============================================================================
# Activates the .venv (created by setup.sh) and runs the given script with
# the given arguments. This repo has no single entry point — it's a
# collection of standalone CLI tools — so this just saves re-activating the
# venv by hand each time.
#
# Usage:
#   bash run.sh <script.py> [args...]
#
# Examples:
#   bash run.sh stentTrack.py --video cell.mp4 --output tracks.csv --overlay overlay.mp4
#   bash run.sh multiTest.py --video colony.mp4 --overlay overlay.mp4 --n_cells 4
#   bash run.sh csv_compiler.py -i ./trackmate_csvs -o compiled.csv
#   bash run.sh full_data_plot.py -i compiled.csv -o avg_velocity.png
#   bash run.sh track_plot.py -i compiled.csv -o track.png -s1 1,2,3
# =============================================================================

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Warning: .venv not found. Run 'bash setup.sh' first. Falling back to system python."
fi

if [ "$#" -eq 0 ]; then
    echo "Usage: bash run.sh <script.py> [args...]"
    echo "Available scripts: stentTrack.py, multiTest.py, csv_compiler.py, full_data_plot.py, track_plot.py"
    exit 1
fi

python3 "$@"
