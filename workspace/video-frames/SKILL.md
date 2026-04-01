---
name: video-frames
description: Extract frames or short clips from videos using ffmpeg. Supports single frame extraction and scene-change detection (PPT slide transitions).
platform: [openclaw, claude-code]
---

# Video Frames (ffmpeg)

Extract keyframes from video via scene-change detection or manual timestamp.

## Output Convention

Frames go to `{project}/frames/`:
```
{project}/
└── frames/
    ├── scene_001_00:00:08_s11.3.jpg
    ├── scene_002_00:01:49_s5.7.jpg
    └── ...
```

Filename format: `scene_{NNN}_{HH:MM:SS}_s{score}.jpg`

## Quick Start

### Scene Detection (recommended for lectures/PPTs)

```bash
FFMPEG=/tmp/ffmpeg bash {baseDir}/scripts/frame.sh /path/to/video.mp4 \
  --scene-detect --threshold 3.0 --outdir {project}/frames/
```

### Single Frame

```bash
bash {baseDir}/scripts/frame.sh /path/to/video.mp4 --time 00:05:00 --out /tmp/frame.jpg
```

## Deduplication (Optional)

After scene detection, you may have many similar frames (especially for lectures where the same slide is shown during explanation). Use the dedup script to remove duplicates:

```bash
FFMPEG=/tmp/ffmpeg python3 {baseDir}/scripts/dedup_frames.py \
    --frames-dir {project}/frames/ \
    --threshold 10 --renumber
```

- Lower threshold = more aggressive deduplication (removes more frames)
- `--renumber` renames remaining frames sequentially
- Uses perceptual hashing (pHash) via ffmpeg to compare frame similarity

## Threshold Guide

| Threshold | Sensitivity | Use Case |
|-----------|------------|----------|
| 1.0 | Very high | Fast-paced videos, animations |
| **3.0** | **Good default** | **PPT lectures, slide transitions** |
| 5.0 | Medium | Only major transitions |
| 10.0+ | Low | Drastic scene cuts only |

## Environment

- `FFMPEG` — path to ffmpeg binary (default: `ffmpeg` in PATH)

## Requirements

- ffmpeg with `scdet` filter support
