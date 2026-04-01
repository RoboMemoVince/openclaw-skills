---
name: bilibili-downloader
description: Download videos, audio, subtitles, and covers from Bilibili using bilibili-api. Use when working with Bilibili content for downloading videos in various qualities, extracting audio, getting subtitles and danmaku, downloading covers, and managing download preferences.
platform: [openclaw, claude-code]
---

# Bilibili Downloader

Download videos from Bilibili.

## Output Convention

Downloads go to `{project}/source/`:
```
{project}/
└── source/
    └── video.mp4          # Downloaded video file
```

The agent should name the video descriptively (e.g. `ascend_simt.mp4`).

## Quick Start

```bash
python3 {baseDir}/scripts/download_video.py <bvid_or_url> <output_dir> [quality]
```

Example:
```bash
python3 {baseDir}/scripts/download_video.py BV1zNPwzaEeB ./project/source/ 64
```

## Quality Codes

| qn | Quality | Login Required |
|----|---------|---------------|
| 127 | 8K | ✅ |
| 120 | 4K | ✅ |
| 116 | 1080P60 | ✅ |
| 80 | 1080P | ✅ |
| **64** | **720P** | ❌ (default) |
| 32 | 480P | ❌ |
| 16 | 360P | ❌ |

**Default: 720P (qn=64)** — highest without login.

⚠️ Do NOT use `html5=1` — it caps quality at 480P.

## Authentication

For 1080P+, set cookie:
```bash
export BILIBILI_SESSDATA='your_cookie_value'
```

## Requirements

```bash
pip install bilibili-api-python
```
