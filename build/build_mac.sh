#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# MIDI2TAB  --  macOS build script
# Run from any directory; the script cd's to the project root automatically.
#
# Produces:
#   dist/MIDI2TAB.app                    -- the application bundle
#   installer_output/MIDI2TAB_v1.0.0.dmg -- drag-to-install disk image
#
# Requirements:
#   Python 3.9+  (python.org build recommended -- includes Tcl/Tk for tkinter)
#   pip3 install pyinstaller mido reportlab Pillow
#   Xcode Command Line Tools: xcode-select --install
# ---------------------------------------------------------------------------
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=================================================="
echo "  MIDI2TAB Build Script (macOS)"
echo "=================================================="
echo

# ---- Python detection -------------------------------------------------------
PY=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PY="$candidate"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "ERROR: Python not found."
    echo "  Install from https://python.org  or:  brew install python"
    exit 1
fi

echo "Using Python: $($PY --version)"
echo

# ---- Step 1: Generate icons -------------------------------------------------
echo "[1/3] Generating icons..."
"$PY" assets/create_icon.py
echo

# ---- Step 2: PyInstaller ----------------------------------------------------
echo "[2/3] Bundling application with PyInstaller..."
"$PY" -m PyInstaller build/MIDI2TAB.spec --clean --noconfirm
echo

# ---- Step 3: Create DMG -----------------------------------------------------
echo "[3/3] Creating disk image (.dmg)..."
mkdir -p installer_output

VERSION="1.0.0"
DMG_NAME="MIDI2TAB_v${VERSION}.dmg"
DMG_PATH="installer_output/${DMG_NAME}"

# Staging folder: .app + Applications symlink for drag-and-drop install
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

cp -r "dist/MIDI2TAB.app" "$TMP_DIR/"
ln -s /Applications "$TMP_DIR/Applications"

# Build compressed read-only DMG
hdiutil create \
    -volname "MIDI2TAB" \
    -srcfolder "$TMP_DIR" \
    -ov \
    -format UDZO \
    "$DMG_PATH"

echo
echo "=================================================="
echo "  SUCCESS"
echo "  App:       dist/MIDI2TAB.app"
echo "  Installer: ${DMG_PATH}"
echo "=================================================="
