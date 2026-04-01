#!/usr/bin/env python3
"""
Deduplicate scene-detected keyframes using perceptual hashing (pHash).

Usage:
  python3 dedup_frames.py --frames-dir ./frames/ --threshold 10 [--dry-run]

How it works:
  1. Computes average hash (aHash) for each frame image
  2. Compares consecutive frames by Hamming distance
  3. Removes frames that are too similar to their predecessor (distance < threshold)

Lower threshold = more aggressive dedup (removes more frames).
Default threshold 10 works well for PPT lectures.

Output:
  - Prints which frames are kept/removed
  - Removes duplicate files (unless --dry-run)
  - Renumbers remaining frames sequentially (scene_001, scene_002, ...)
"""

import argparse
import os
import re
import sys
from pathlib import Path


def average_hash(image_path: str, hash_size: int = 16) -> int:
    """Compute average hash (aHash) without PIL - uses raw pixel comparison via ffmpeg."""
    import subprocess
    import struct

    # Use ffmpeg to resize to hash_size x hash_size grayscale and output raw pixels
    cmd = [
        os.environ.get("FFMPEG", "ffmpeg"),
        "-hide_banner", "-loglevel", "error",
        "-i", image_path,
        "-vf", f"scale={hash_size}:{hash_size},format=gray",
        "-f", "rawvideo",
        "-pix_fmt", "gray",
        "-frames:v", "1",
        "pipe:1"
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed for {image_path}: {result.stderr.decode()}")

    pixels = list(result.stdout)
    if len(pixels) != hash_size * hash_size:
        raise RuntimeError(f"Expected {hash_size*hash_size} pixels, got {len(pixels)}")

    # Compute average
    avg = sum(pixels) / len(pixels)

    # Build hash: 1 if pixel > average, 0 otherwise
    hash_val = 0
    for p in pixels:
        hash_val = (hash_val << 1) | (1 if p > avg else 0)

    return hash_val


def hamming_distance(h1: int, h2: int) -> int:
    """Count differing bits between two hashes."""
    return bin(h1 ^ h2).count('1')


def parse_frame_filename(fname: str) -> dict | None:
    """Parse scene_NNN_HH:MM:SS_sN.N.jpg filename."""
    m = re.match(r"scene_(\d+)_(\d{2}:\d{2}:\d{2})_s([\d.]+)\.jpg", fname)
    if not m:
        return None
    return {
        "index": int(m.group(1)),
        "timestamp": m.group(2),
        "score": float(m.group(3)),
        "filename": fname,
    }


def main():
    parser = argparse.ArgumentParser(description="Deduplicate keyframes via perceptual hash")
    parser.add_argument("--frames-dir", required=True, help="Directory with scene keyframes")
    parser.add_argument("--threshold", type=int, default=10,
                        help="Hamming distance threshold (lower=more aggressive, default=10)")
    parser.add_argument("--hash-size", type=int, default=16,
                        help="Hash image size (default=16, gives 256-bit hash)")
    parser.add_argument("--dry-run", action="store_true", help="Don't delete, just report")
    parser.add_argument("--renumber", action="store_true", help="Renumber kept frames sequentially")
    args = parser.parse_args()

    frames_dir = Path(args.frames_dir)
    frame_files = sorted(frames_dir.glob("scene_*.jpg"))

    if not frame_files:
        print("No scene_*.jpg files found")
        sys.exit(1)

    # Parse and sort by index
    frames = []
    for f in frame_files:
        info = parse_frame_filename(f.name)
        if info:
            info["path"] = f
            frames.append(info)

    frames.sort(key=lambda x: x["index"])
    print(f"Found {len(frames)} frames, computing hashes (size={args.hash_size})...")

    # Compute hashes
    for frame in frames:
        frame["hash"] = average_hash(str(frame["path"]), args.hash_size)

    # Deduplicate: keep first, then only keep if distance >= threshold
    kept = [frames[0]]
    removed = []

    for i in range(1, len(frames)):
        dist = hamming_distance(frames[i]["hash"], kept[-1]["hash"])
        frames[i]["distance_to_prev_kept"] = dist

        if dist >= args.threshold:
            kept.append(frames[i])
        else:
            removed.append(frames[i])

    print(f"\nResults (threshold={args.threshold}):")
    print(f"  Kept:    {len(kept)} frames")
    print(f"  Removed: {len(removed)} frames")

    if removed:
        print(f"\nRemoved frames:")
        for f in removed:
            dist = f.get("distance_to_prev_kept", "?")
            print(f"  ✗ {f['filename']} (distance={dist})")

    print(f"\nKept frames:")
    for f in kept:
        dist = f.get("distance_to_prev_kept", "-")
        print(f"  ✓ {f['filename']} (distance={dist})")

    if args.dry_run:
        print("\n[DRY RUN] No files modified.")
        return

    # Remove duplicate files
    for f in removed:
        f["path"].unlink()
        print(f"  Deleted: {f['filename']}")

    # Renumber if requested
    if args.renumber and kept:
        print(f"\nRenumbering {len(kept)} frames...")
        # First rename to temp names to avoid collisions
        temp_names = []
        for i, f in enumerate(kept, 1):
            temp = f["path"].parent / f"_temp_{i:03d}_{f['timestamp']}_s{f['score']}.jpg"
            f["path"].rename(temp)
            temp_names.append((temp, i, f))

        # Then rename to final names
        for temp, new_idx, f in temp_names:
            new_name = f"scene_{new_idx:03d}_{f['timestamp']}_s{f['score']}.jpg"
            final = frames_dir / new_name
            temp.rename(final)
            print(f"  {f['filename']} → {new_name}")

    print(f"\nDone! {len(kept)} unique frames remain.")


if __name__ == "__main__":
    main()
