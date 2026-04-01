---
name: video-subtitles
description: Generate SRT subtitles from video/audio. Uses video frame extraction + vision model to understand content, then ASR with hotwords for transcription, followed by agent-driven error correction. Supports 火山引擎 (primary) and 阿里云百炼 DashScope (fallback).
platform: [openclaw, claude-code]
---

# Video Subtitles

Generate subtitles using the "先看再听" (look first, listen second) workflow.

## ASR Provider Selection

Two ASR backends are available. The agent should **auto-select** based on environment:

| Provider | Script | Env Vars | Method | Public URL Needed |
|----------|--------|----------|--------|-------------------|
| **火山引擎** (primary) | `volc_asr.py` | `VOLC_APP_ID` + `VOLC_ACCESS_TOKEN` | HTTP upload + poll | Yes (tmpfiles.org) |
| **阿里云百炼** (fallback) | `dashscope_asr.py` | `DASHSCOPE_API_KEY` | WebSocket streaming | **No** |

**Selection logic:**
1. If `VOLC_APP_ID` and `VOLC_ACCESS_TOKEN` are set → use 火山引擎
2. Else if `DASHSCOPE_API_KEY` is set → use DashScope
3. Else → error, ask user to configure

**When to prefer DashScope even if 火山引擎 is available:**
- Server has no public IP or firewall blocks outbound upload
- tmpfiles.org upload fails
- 火山引擎 quota exhausted

## Output Convention

Subtitles go to `{project}/subtitles/`:
```
{project}/
└── subtitles/
    ├── raw.srt              # Raw ASR output
    ├── hotwords.txt         # Hotwords extracted from frames
    ├── fixes.json           # Replacement dictionary (agent-generated)
    └── final.srt            # Post-processed subtitles
```

## Workflow

### Step 1: Extract Preview Frames

Use `video-frames` skill to extract **5 evenly-spaced frames** for content analysis:

```bash
duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 video.mp4)
# Extract 5 frames at ~10%, 30%, 50%, 70%, 90% marks
for TS in 00:06:00 00:18:00 00:30:00 00:42:00 00:54:00; do
    ffmpeg -y -ss $TS -i video.mp4 -frames:v 1 -q:v 2 {project}/subtitles/preview_${TS}.jpg
done
```

### Step 2: Vision → Hotwords

Analyze frames with vision model to extract technical terms:
- Domain terminology (Chinese + English)
- Abbreviations and full names
- Product names, APIs, code keywords

Save to `{project}/subtitles/hotwords.txt` (one per line, max 5000).

### Step 3: ASR Transcription

**火山引擎 (primary):**
```bash
{baseDir}/scripts/volc_asr.py {project}/source/video.mp4 --srt \
    --hotwords-file {project}/subtitles/hotwords.txt \
    -o {project}/subtitles/raw.srt
```

**阿里云百炼 DashScope (fallback):**
```bash
{baseDir}/scripts/dashscope_asr.py {project}/source/video.mp4 --srt \
    --hotwords-file {project}/subtitles/hotwords.txt \
    -o {project}/subtitles/raw.srt
```

### Step 4: Agent Review + Fix

1. Sample 50-100 lines from `raw.srt`
2. Identify ASR errors using domain knowledge from Step 2
3. Generate `fixes.json`
4. Apply:

```bash
{baseDir}/scripts/fix_srt.py {project}/subtitles/raw.srt \
    --dict {project}/subtitles/fixes.json \
    -o {project}/subtitles/final.srt
```

## Scripts

| Script | Purpose |
|--------|---------|
| `volc_asr.py` | 火山引擎 bigmodel ASR → SRT (primary) |
| `dashscope_asr.py` | 阿里云百炼 DashScope Paraformer ASR → SRT (fallback) |
| `fix_srt.py` | Batch replacement with JSON dictionary |

## volc_asr.py Flags

| Flag | Description |
|------|-------------|
| `--srt` | Generate SRT subtitle file |
| `--burn` | Burn subtitles into video |
| `--embed` | Embed soft subtitles |
| `-o FILE` | Output file path |
| `--hotwords "a,b,c"` | Comma-separated hotwords |
| `--hotwords-file FILE` | Hotwords file (one per line) |

## dashscope_asr.py Flags

| Flag | Description |
|------|-------------|
| `--srt` | Generate SRT subtitle file |
| `-o FILE` | Output file path |
| `--hotwords "a,b,c"` | Comma-separated hotwords |
| `--hotwords-file FILE` | Hotwords file (one per line) |
| `--api-key KEY` | DashScope API Key (overrides env) |

## fix_srt.py Flags

| Flag | Description |
|------|-------------|
| `--dict FILE` | Replacement dictionary JSON (required) |
| `-o FILE` | Output path |
| `--dry-run` | Show stats only |

## Key Principles

- **先看再听** — vision model reads slides first, then ASR transcribes
- **每个视频单独分析** — no hardcoded dictionaries; agent analyzes per-video
- **hotwords 从帧中来** — terms from image recognition become ASR hotwords
- **保留原始文件** — raw.srt is never overwritten
- **hotwords only** — 只传 hotwords，不传 context_data（详见踩坑记录）

## Environment

```bash
# 火山引擎 (primary)
export VOLC_APP_ID="your_app_id"
export VOLC_ACCESS_TOKEN="your_token"

# 阿里云百炼 DashScope (fallback)
export DASHSCOPE_API_KEY="your_api_key"
```

### 火山引擎 ASR 开通指南

1. 访问 [火山引擎控制台](https://console.volcengine.com/)
2. 搜索「语音技术」→ 开通「语音识别」
3. 创建应用获取 `APP_ID`，密钥管理创建 Access Token

### 阿里云百炼 DashScope 开通指南

1. 访问 [百炼控制台](https://bailian.console.aliyun.com/)
2. API-KEY 管理 → 创建 API Key
3. Paraformer 语音识别模型免费额度充足

## DashScope 实现说明

- 使用 `paraformer-realtime-v2` 模型，通过 WebSocket 流式推送本地音频
- **无需公网 URL**，适合防火墙内或无公网 IP 的服务器
- 音频先转为 16kHz mono WAV，以 ~100x 实时速率推送
- 58 分钟视频约需 6 分钟完成转写
- 自动去重（实时 API 可能发送重叠更新）

## Requirements

- ffmpeg, ffprobe
- 火山引擎 bigmodel ASR quota **或** DashScope API Key
- `video-frames` skill (for frame extraction)
- vision model (for content understanding)
- Python packages: `requests` (火山引擎), `dashscope` (百炼)
