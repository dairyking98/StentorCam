#!/usr/bin/env bash
# =============================================================================
# StentorCam — Setup Script (Linux / macOS)
# =============================================================================
# Creates a virtual environment named .venv and installs all Python
# dependencies. Run once after cloning:
#   bash setup.sh
#
# To run a script afterwards:
#   source .venv/bin/activate && python stentTrack.py --video ... --output ... --overlay ...
#   -- or --
#   bash run.sh stentTrack.py --video ... --output ... --overlay ...
# =============================================================================

set -e

VENV_DIR=".venv"
PYTHON="${PYTHON:-python3}"

echo "==> Checking Python version..."
$PYTHON --version

echo "==> Creating virtual environment in '$VENV_DIR'..."
$PYTHON -m venv "$VENV_DIR"

echo "==> Activating virtual environment..."
source "$VENV_DIR/bin/activate"

echo "==> Upgrading pip..."
pip install --upgrade pip

echo "==> Installing Python dependencies..."
pip install -r requirements.txt

echo "==> Checking for ffmpeg on PATH..."
if command -v ffmpeg >/dev/null 2>&1; then
    echo "    Found: $(command -v ffmpeg)"
else
    echo "    WARNING: ffmpeg not found on PATH."
    echo "    stentTrack.py and multiTest.py both shell out to ffmpeg to composite"
    echo "    the overlay video and will fail without it. Install it via your"
    echo "    system package manager, e.g.:"
    echo "      sudo apt install ffmpeg      (Debian/Ubuntu)"
    echo "      brew install ffmpeg          (macOS)"
fi

echo ""
echo "============================================================"
echo " Setup complete!"
echo ""
echo " To run a script:"
echo "   source .venv/bin/activate"
echo "   python stentTrack.py --video <video.mp4> --output <out.csv> --overlay <overlay.mp4>"
echo ""
echo " Or use the shortcut:"
echo "   bash run.sh stentTrack.py --video <video.mp4> --output <out.csv> --overlay <overlay.mp4>"
echo "============================================================"
