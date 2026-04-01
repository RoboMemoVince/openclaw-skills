#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "dashscope>=1.20.0",
# ]
# ///
"""
Transcription with subtitles using 阿里云百炼 DashScope Paraformer ASR.

Fallback ASR provider when 火山引擎 is unavailable.
Uses WebSocket streaming (paraformer-realtime-v2), no public URL needed.

Usage:
    ./dashscope_asr.py video.mp4                         # Plain transcript
    ./dashscope_asr.py video.mp4 --srt                   # Generate SRT file
    ./dashscope_asr.py video.mp4 --srt --hotwords-file h.txt  # With hotwords
    ./dashscope_asr.py audio.mp3 --srt -o output.srt     # Custom output

Environment:
    DASHSCOPE_API_KEY  — 阿里云百炼 API Key (required)
"""

import sys
import os
import argparse
import subprocess
import tempfile
import json
import time
from pathlib import Path

try:
    import dashscope
    from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult
except ImportError:
    print("Error: pip install dashscope")
    sys.exit(1)


def format_srt_timestamp(ms: int) -> str:
    hours = ms // 3600000
    minutes = (ms % 3600000) // 60000
    seconds = (ms % 60000) // 1000
    millis = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def extract_wav(input_path: str) -> str:
    """Extract audio as 16kHz mono PCM WAV."""
    wav_path = tempfile.mktemp(suffix='.wav')
    subprocess.run(
        ['ffmpeg', '-y', '-i', input_path, '-ar', '16000', '-ac', '1', '-f', 'wav', wav_path],
        capture_output=True
    )
    if not os.path.exists(wav_path) or os.path.getsize(wav_path) < 100:
        raise RuntimeError(f"Failed to extract audio from {input_path}")
    return wav_path


def transcribe_streaming(wav_path: str, hotwords: dict = None) -> list:
    """
    Stream audio via WebSocket to DashScope paraformer-realtime-v2.
    Returns list of {'begin_time': ms, 'end_time': ms, 'text': str}.
    """
    all_sentences = []
    is_done = False
    error_msg = None

    class Callback(RecognitionCallback):
        def on_open(self):
            print("  WebSocket opened", flush=True)

        def on_close(self):
            nonlocal is_done
            is_done = True

        def on_event(self, result: RecognitionResult):
            try:
                sent = result.get_sentence()
                if not sent:
                    return
                text = (sent.get('text', '') or '').strip()
                begin = sent.get('begin_time', 0) or 0
                end = sent.get('end_time', 0) or 0
                if text and end > begin:
                    all_sentences.append({
                        'begin_time': begin,
                        'end_time': end,
                        'text': text
                    })
                    if len(all_sentences) % 50 == 0:
                        print(f"  [{len(all_sentences)}] {begin // 1000}s: {text[:50]}", flush=True)
            except Exception as e:
                print(f"  on_event error: {e}", flush=True)

        def on_error(self, result: RecognitionResult):
            nonlocal error_msg, is_done
            error_msg = str(result)
            print(f"  ASR Error: {result}", flush=True)
            is_done = True

        def on_complete(self):
            nonlocal is_done
            print(f"  Recognition complete ({len(all_sentences)} sentences)", flush=True)
            is_done = True

    recognition = Recognition(
        model='paraformer-realtime-v2',
        format='pcm',
        sample_rate=16000,
        callback=Callback(),
    )

    recognition.start()

    chunk_size = 3200  # 100ms at 16kHz 16bit mono
    total_bytes = os.path.getsize(wav_path) - 44
    sent_bytes = 0
    t0 = time.time()

    with open(wav_path, 'rb') as f:
        f.read(44)  # skip WAV header
        while True:
            data = f.read(chunk_size)
            if not data:
                break
            recognition.send_audio_frame(data)
            sent_bytes += len(data)
            time.sleep(0.01)  # ~100x realtime pacing
            if sent_bytes % (chunk_size * 500) == 0:
                pct = sent_bytes * 100 / max(total_bytes, 1)
                elapsed = time.time() - t0
                print(
                    f"  {sent_bytes / 1024 / 1024:.0f}/{total_bytes / 1024 / 1024:.0f}MB "
                    f"({pct:.0f}%) {elapsed:.0f}s - {len(all_sentences)} sents",
                    flush=True
                )

    elapsed = time.time() - t0
    print(f"  Stream done ({elapsed:.0f}s), stopping...", flush=True)
    recognition.stop()

    # Wait for completion
    for _ in range(120):
        if is_done:
            break
        time.sleep(1)

    if error_msg:
        raise RuntimeError(f"DashScope ASR error: {error_msg}")

    # Deduplicate (realtime API may send overlapping updates)
    seen = set()
    unique = []
    for s in all_sentences:
        key = (s['begin_time'], s['text'])
        if key not in seen:
            seen.add(key)
            unique.append(s)
    unique.sort(key=lambda x: x['begin_time'])

    return unique


def main():
    parser = argparse.ArgumentParser(description='阿里云百炼 DashScope Paraformer ASR')
    parser.add_argument('input', help='视频或音频文件')
    parser.add_argument('--srt', action='store_true', help='生成 SRT 字幕文件')
    parser.add_argument('-o', '--output', help='输出文件路径')
    parser.add_argument('--hotwords', help='热词列表，逗号分隔')
    parser.add_argument('--hotwords-file', help='热词文件，每行一个词')
    parser.add_argument('--api-key', default=os.environ.get('DASHSCOPE_API_KEY', ''),
                        help='DashScope API Key')
    args = parser.parse_args()

    api_key = args.api_key
    if not api_key:
        print("Error: Set DASHSCOPE_API_KEY environment variable")
        print("Get it from: https://bailian.console.aliyun.com/ → API-KEY 管理")
        sys.exit(1)
    dashscope.api_key = api_key

    input_path = args.input
    if not os.path.exists(input_path):
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    # Parse hotwords (note: paraformer-realtime-v2 doesn't support inline hotwords
    # via WebSocket, but we load them for future file-transcription API support)
    hotwords = {}
    if args.hotwords:
        for w in args.hotwords.split(','):
            w = w.strip()
            if w:
                hotwords[w] = 3
    elif args.hotwords_file and os.path.exists(args.hotwords_file):
        with open(args.hotwords_file, 'r', encoding='utf-8') as f:
            for line in f:
                w = line.strip()
                if w:
                    hotwords[w] = 3
    if hotwords:
        print(f"Loaded {len(hotwords)} hotwords (for reference)", flush=True)

    # Extract WAV
    ext = Path(input_path).suffix.lower()
    if ext in ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.mp3', '.m4a', '.ogg', '.flac'):
        print(f"Extracting audio from {input_path}...", flush=True)
        wav_path = extract_wav(input_path)
        wav_size = os.path.getsize(wav_path) / 1024 / 1024
        print(f"  WAV: {wav_size:.1f} MB", flush=True)
        cleanup_wav = True
    elif ext == '.wav':
        wav_path = input_path
        cleanup_wav = False
    else:
        print(f"Unknown format {ext}, trying to convert...", flush=True)
        wav_path = extract_wav(input_path)
        cleanup_wav = True

    # Transcribe
    print("Starting DashScope Paraformer streaming ASR...", flush=True)
    try:
        sentences = transcribe_streaming(wav_path, hotwords)
    finally:
        if cleanup_wav and os.path.exists(wav_path):
            os.remove(wav_path)

    if not sentences:
        print("No transcription results")
        sys.exit(1)

    print(f"Got {len(sentences)} sentences", flush=True)

    if args.srt:
        srt_lines = []
        for idx, s in enumerate(sentences, 1):
            text = s['text'].strip()
            if not text:
                continue
            srt_lines.append(
                f"{idx}\n"
                f"{format_srt_timestamp(s['begin_time'])} --> {format_srt_timestamp(s['end_time'])}\n"
                f"{text}\n"
            )

        srt_content = '\n'.join(srt_lines)
        output_path = args.output or (os.path.splitext(input_path)[0] + '_dashscope.srt')

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        print(f"SRT saved to: {output_path} ({len(srt_lines)} subtitles)")
    else:
        for s in sentences:
            print(f"[{format_srt_timestamp(s['begin_time'])}] {s['text']}")


if __name__ == '__main__':
    main()
