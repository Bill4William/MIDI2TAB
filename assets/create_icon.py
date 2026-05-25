"""
Generate assets/icon.ico (Windows) and assets/icon.icns (macOS) for MIDI2TAB.
Run from the project root: python assets/create_icon.py
"""

import os
import shutil
import subprocess
import sys
from PIL import Image, ImageDraw


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded-square background (indigo-blue)
    radius = max(2, size // 5)
    draw.rounded_rectangle([0, 0, size - 1, size - 1],
                            radius=radius, fill=(45, 85, 200))

    fg = (255, 255, 255)

    if size <= 24:
        # Tiny sizes: minimal note head + stem
        hx, hy = size * 38 // 100, size * 70 // 100
        hr = max(2, size // 5)
        draw.ellipse([hx - hr, hy - int(hr * 0.7),
                      hx + hr, hy + int(hr * 0.7)], fill=fg)
        lw = max(1, size // 12)
        stem_x = hx + hr - lw
        draw.rectangle([stem_x, size * 22 // 100, stem_x + lw, hy], fill=fg)
        return img

    # Scale everything to this icon size
    s = size / 256.0
    lw = max(2, int(13 * s))   # stem / line width

    # Note head — axis-aligned oval, slightly wider than tall
    hx = int(85 * s)
    hy = int(185 * s)
    hw = int(50 * s)     # half-width
    hh = int(33 * s)     # half-height
    draw.ellipse([hx - hw, hy - hh, hx + hw, hy + hh], fill=fg)

    # Stem — up from the right edge of the note head
    sx = hx + hw - lw
    stem_top = int(65 * s)
    draw.rectangle([sx, stem_top, sx + lw, hy], fill=fg)

    # Flag — arc from the top of the stem curving right and down
    ft = stem_top
    fl = sx + lw
    fw = int(90 * s)
    fh = int(100 * s)
    draw.arc([fl, ft, fl + fw, ft + fh], start=270, end=30,
             fill=fg, width=lw)
    # Second flag (makes it look like an eighth note group / MIDI symbol)
    draw.arc([fl, ft + int(30 * s), fl + int(70 * s), ft + fh + int(20 * s)],
             start=270, end=30, fill=fg, width=lw)

    return img


def _create_icns(out_dir: str) -> str:
    """
    Build icon.icns using macOS iconutil.
    Requires Xcode Command Line Tools (xcode-select --install).
    Returns the path to the created .icns file.
    """
    # macOS iconset filenames are fixed by the OS spec
    iconset_sizes = [
        (16,   "icon_16x16.png"),
        (32,   "icon_16x16@2x.png"),
        (32,   "icon_32x32.png"),
        (64,   "icon_32x32@2x.png"),
        (128,  "icon_128x128.png"),
        (256,  "icon_128x128@2x.png"),
        (256,  "icon_256x256.png"),
        (512,  "icon_256x256@2x.png"),
        (512,  "icon_512x512.png"),
        (1024, "icon_512x512@2x.png"),
    ]

    iconset_dir = os.path.join(out_dir, "icon.iconset")
    os.makedirs(iconset_dir, exist_ok=True)

    try:
        for size, filename in iconset_sizes:
            draw_icon(size).save(os.path.join(iconset_dir, filename))

        icns_path = os.path.join(out_dir, "icon.icns")
        subprocess.run(
            ["iconutil", "-c", "icns", iconset_dir, "-o", icns_path],
            check=True,
            capture_output=True,
        )
    finally:
        shutil.rmtree(iconset_dir, ignore_errors=True)

    return icns_path


def main() -> None:
    out_dir = os.path.dirname(os.path.abspath(__file__))

    # --- Windows / Linux: .ico ---
    ico_sizes = [16, 32, 48, 256]
    ico_images = [draw_icon(s) for s in ico_sizes]
    ico_path = os.path.join(out_dir, "icon.ico")
    ico_images[0].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in ico_sizes],
        append_images=ico_images[1:],
    )
    print(f"Icon written to {ico_path}")

    # --- macOS: .icns ---
    if sys.platform == "darwin":
        try:
            icns_path = _create_icns(out_dir)
            print(f"Icon written to {icns_path}")
        except FileNotFoundError:
            print(
                "Warning: iconutil not found — skipping .icns.\n"
                "Install Xcode Command Line Tools:  xcode-select --install"
            )
        except subprocess.CalledProcessError as exc:
            print(f"Warning: iconutil failed — {exc.stderr.decode().strip()}")


if __name__ == "__main__":
    main()
