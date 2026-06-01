# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for MIDI2TAB  --  works on both Windows and macOS.

Windows (from project root):
    python  -m PyInstaller build/MIDI2TAB.spec --clean --noconfirm
    Output: dist/MIDI2TAB/MIDI2TAB.exe  (then Inno Setup for the installer)

macOS (from project root):
    python3 -m PyInstaller build/MIDI2TAB.spec --clean --noconfirm
    Output: dist/MIDI2TAB.app  (then build_mac.sh wraps it in a .dmg)
"""

import os
import sys
import customtkinter

project_root = os.path.dirname(SPECPATH)   # parent of build/
ctk_root     = os.path.dirname(customtkinter.__file__)  # CustomTkinter assets

# Platform-specific icon format
if sys.platform == "darwin":
    icon_path = os.path.join(project_root, "assets", "icon.icns")
else:
    icon_path = os.path.join(project_root, "assets", "icon.ico")

icon = icon_path if os.path.exists(icon_path) else None

a = Analysis(
    [os.path.join(project_root, "main.py")],
    pathex=[project_root],
    binaries=[],
    datas=[
        # App icon (loaded at runtime for the window title bar)
        (os.path.join(project_root, "assets", "icon.ico"), "assets"),
        # HTML manual (opened via webbrowser when Help is clicked)
        (os.path.join(project_root, "docs", "manual.html"), "docs"),
        # CustomTkinter themes and image assets (required at runtime)
        (ctk_root, "customtkinter"),
    ],
    hiddenimports=[
        # customtkinter UI framework
        "customtkinter",
        # mido file I/O (no playback backend needed)
        "mido",
        "mido.midifiles",
        "mido.messages",
        "mido.messages.messages",
        "mido.messages.specs",
        # reportlab PDF engine
        "reportlab",
        "reportlab.pdfgen",
        "reportlab.pdfgen.canvas",
        "reportlab.lib",
        "reportlab.lib.pagesizes",
        "reportlab.lib.units",
        # tkinter (usually auto-detected, listed for safety)
        "tkinter",
        "tkinter.ttk",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "tkinter.scrolledtext",
        "tkinter.simpledialog",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Exclude heavy scientific packages that may be present but unused
    excludes=["numpy", "scipy", "matplotlib", "pandas", "IPython",
              "jupyter", "PIL.ImageQt"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MIDI2TAB",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # skip UPX -- avoids false-positive AV flags
    console=False,       # no console window for a GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MIDI2TAB",
)

# macOS only: wrap the collected folder into a proper .app bundle
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="MIDI2TAB.app",
        icon=icon,
        bundle_identifier="com.midi2tab.app",
        info_plist={
            "CFBundleName":               "MIDI2TAB",
            "CFBundleDisplayName":        "MIDI2TAB",
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion":            "1.0.0",
            "NSHighResolutionCapable":    True,
            "NSHumanReadableCopyright":   "MIDI2TAB",
        },
    )
