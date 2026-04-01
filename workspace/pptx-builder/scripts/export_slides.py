#!/usr/bin/env python3
"""Export each slide of a PPTX to individual PNG files for visual review.

Usage:
    python export_slides.py <pptx_path> [--outdir /tmp/ppt_review] [--dpi 200] [--max-width 1600]

Requires: libreoffice, pdftoppm (poppler-utils), Pillow
"""
import argparse
import os
import subprocess
import sys


def export(pptx_path, outdir="/tmp/ppt_review", dpi=200, max_width=1600):
    os.makedirs(outdir, exist_ok=True)
    basename = os.path.splitext(os.path.basename(pptx_path))[0]

    # Step 1: PPTX → PDF via LibreOffice
    print(f"Converting {pptx_path} → PDF...")
    subprocess.run(
        ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", outdir, pptx_path],
        check=True, capture_output=True,
    )
    pdf_path = os.path.join(outdir, f"{basename}.pdf")
    print(f"  PDF: {pdf_path}")

    # Step 2: PDF → per-page PNG via pdftoppm
    print(f"Converting PDF → PNG (DPI={dpi})...")
    subprocess.run(
        ["pdftoppm", "-png", "-r", str(dpi), pdf_path, os.path.join(outdir, "slide")],
        check=True, capture_output=True,
    )

    # Step 3: List and optionally resize for review
    files = sorted(f for f in os.listdir(outdir) if f.startswith("slide") and f.endswith(".png"))
    print(f"  Generated {len(files)} slides:")
    for f in files:
        path = os.path.join(outdir, f)
        size_kb = os.path.getsize(path) / 1024
        print(f"    {f} ({size_kb:.0f}KB)")

    if max_width:
        try:
            from PIL import Image
            print(f"\nResizing to max width {max_width}px...")
            for f in files:
                path = os.path.join(outdir, f)
                img = Image.open(path)
                w, h = img.size
                if w > max_width:
                    ratio = max_width / w
                    resized = img.resize((max_width, int(h * ratio)), Image.LANCZOS)
                    review_name = f.replace("slide", "review")
                    review_path = os.path.join(outdir, review_name)
                    resized.save(review_path)
            print(f"  Review images saved as review-*.png")
        except ImportError:
            print("  (Pillow not installed — skipping resize)")

    print(f"\nDone. Review images in: {outdir}/")
    return files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export PPTX slides to PNG for review")
    parser.add_argument("pptx", help="Path to .pptx file")
    parser.add_argument("--outdir", default="/tmp/ppt_review", help="Output directory")
    parser.add_argument("--dpi", type=int, default=200, help="Export DPI")
    parser.add_argument("--max-width", type=int, default=1600, help="Max width for review images (0=skip)")
    args = parser.parse_args()
    export(args.pptx, args.outdir, args.dpi, args.max_width)
