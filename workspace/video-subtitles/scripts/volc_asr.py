#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests>=2.28.0",
# ]
# ///
"""
Transcription with subtitles using 字节火山引擎 (ByteDance Volcano Engine) ASR.

Usage:
    ./volc_asr.py video.mp4                      # Plain transcript
    ./volc_asr.py video.mp4 --srt                # Generate SRT file
    ./volc_asr.py video.mp4 --srt --burn         # Burn subtitles into video
    ./volc_asr.py audio.mp3 --srt                # Works with audio too
"""

import sys
import os
import argparse
import subprocess
import tempfile
import json
import time
import uuid
import requests
from pathlib import Path


# ============ 配置 - 火山引擎 ============
APP_ID = os.environ.get("VOLC_APP_ID", "")
ACCESS_TOKEN = os.environ.get("VOLC_ACCESS_TOKEN", "")

SUBMIT_URL = "https://openspeech-direct.zijieapi.com/api/v3/auc/bigmodel/submit"
QUERY_URL = "https://openspeech-direct.zijieapi.com/api/v3/auc/bigmodel/query"


def format_srt_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def upload_to_tmpfiles(file_path: str) -> str:
    """上传文件到 tmpfiles.org，返回直接下载 URL"""
    with open(file_path, 'rb') as f:
        resp = requests.post('https://tmpfiles.org/api/v1/upload', files={'file': f})
    resp.raise_for_status()
    url = resp.json()['data']['url']
    return url.replace('tmpfiles.org/', 'tmpfiles.org/dl/')


def split_audio(input_path: str, max_duration: int = 600) -> list:
    """将音视频分割成小段（每段最多10分钟）"""
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', input_path],
        capture_output=True, text=True
    )
    try:
        total_duration = float(result.stdout.strip())
    except:
        total_duration = 3600

    output_dir = tempfile.mkdtemp(prefix='volc_asr_')
    output_files = []
    num_parts = int((total_duration + max_duration - 1) // max_duration)

    for i in range(num_parts):
        start_time = i * max_duration
        output_file = os.path.join(output_dir, f'part_{i}.mp3')
        subprocess.run([
            'ffmpeg', '-y', '-i', input_path,
            '-ss', str(start_time), '-t', str(max_duration),
            '-vn', '-acodec', 'libmp3lame', '-ar', '16000', '-ac', '1', '-q:a', '5',
            output_file
        ], capture_output=True)
        if os.path.exists(output_file):
            output_files.append((output_file, start_time * 1000))

    return output_files


def submit_and_wait(file_url: str, appid: str, token: str, hotwords: list = None) -> list:
    """提交任务并轮询结果"""
    task_id = str(uuid.uuid4())
    headers = {
        'X-Api-App-Key': appid,
        'X-Api-Access-Key': token,
        'X-Api-Resource-Id': 'volc.bigasr.auc',
        'X-Api-Request-Id': task_id,
        'X-Api-Sequence': '-1'
    }
    request = {
        'user': {'uid': 'openclaw'},
        'audio': {'url': file_url, 'format': 'mp3'},
        'request': {
            'model_name': 'bigmodel',
            'enable_punc': True,
            'enable_itn': True,
            'show_utterances': True,
        }
    }
    
    # 注入 hotwords 上下文（如果有）
    if hotwords:
        hw_obj = {"hotwords": [{"word": w} for w in hotwords]}
        request['request']['corpus'] = {
            'context': json.dumps(hw_obj, ensure_ascii=False)
        }

    resp = requests.post(SUBMIT_URL, data=json.dumps(request), headers=headers)
    if resp.headers.get('X-Api-Status-Code') != '20000000':
        raise Exception(f"Submit failed: {resp.headers.get('X-Api-Message', 'unknown')}")

    x_tt_logid = resp.headers.get('X-Tt-Logid', '')

    for i in range(300):
        time.sleep(3)
        qh = {
            'X-Api-App-Key': appid,
            'X-Api-Access-Key': token,
            'X-Api-Resource-Id': 'volc.bigasr.auc',
            'X-Api-Request-Id': task_id,
            'X-Tt-Logid': x_tt_logid
        }
        qr = requests.post(QUERY_URL, json.dumps({}), headers=qh)
        code = qr.headers.get('X-Api-Status-Code', '')
        if code == '20000000':
            return qr.json().get('result', {}).get('utterances', [])
        elif code not in ('20000001', '20000002'):
            raise Exception(f"Query failed: {qr.headers.get('X-Api-Message', code)}")

    raise Exception("Timeout waiting for result")


def transcribe_with_volc(input_path: str, appid: str, token: str, hotwords: list = None) -> list:
    """使用火山引擎转录音视频"""
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', input_path],
        capture_output=True, text=True
    )
    try:
        duration = float(result.stdout.strip())
    except:
        duration = 600

    if duration <= 600:
        print(f"Uploading {input_path}...", flush=True)
        file_url = upload_to_tmpfiles(input_path)
        print(f"Uploaded to {file_url}", flush=True)
        utts = submit_and_wait(file_url, appid, token, hotwords=hotwords)
        for u in utts:
            u['start'] = u.get('start_time', 0) / 1000.0
            u['end'] = u.get('end_time', 0) / 1000.0
        return utts
    else:
        print(f"Long file ({duration:.0f}s), splitting...", flush=True)
        parts = split_audio(input_path)
        all_utts = []
        for i, (part_file, offset_ms) in enumerate(parts):
            print(f"Processing part {i+1}/{len(parts)}...", flush=True)
            file_url = upload_to_tmpfiles(part_file)
            utts = submit_and_wait(file_url, appid, token, hotwords=hotwords)
            for u in utts:
                u['start'] = (u.get('start_time', 0) + offset_ms) / 1000.0
                u['end'] = (u.get('end_time', 0) + offset_ms) / 1000.0
            all_utts.extend(utts)
            try:
                os.remove(part_file)
            except:
                pass
        return all_utts


def main():
    parser = argparse.ArgumentParser(description='火山引擎语音识别生成字幕')
    parser.add_argument('input', help='视频或音频文件')
    parser.add_argument('--srt', action='store_true', help='生成 SRT 字幕文件')
    parser.add_argument('--burn', action='store_true', help='烧录字幕到视频')
    parser.add_argument('--embed', action='store_true', help='嵌入软字幕')
    parser.add_argument('-o', '--output', help='输出文件路径')
    parser.add_argument('--appid', default=APP_ID, help='火山引擎 APP ID')
    parser.add_argument('--token', default=ACCESS_TOKEN, help='火山引擎 Access Token')
    parser.add_argument('--hotwords', help='热词列表，逗号分隔 (e.g. "SIMT,SIMD,昇腾,Warp")')
    parser.add_argument('--hotwords-file', help='热词文件，每行一个词')
    args = parser.parse_args()

    input_path = args.input
    if not os.path.exists(input_path):
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    print("Starting transcription with 火山引擎 bigmodel...", flush=True)
    
    # 解析热词
    hotwords = None
    if args.hotwords:
        hotwords = [w.strip() for w in args.hotwords.split(',') if w.strip()]
        print(f"Using {len(hotwords)} hotwords", flush=True)
    elif args.hotwords_file and os.path.exists(args.hotwords_file):
        with open(args.hotwords_file, 'r', encoding='utf-8') as f:
            hotwords = [line.strip() for line in f if line.strip()]
        print(f"Using {len(hotwords)} hotwords from {args.hotwords_file}", flush=True)
    
    utterances = transcribe_with_volc(input_path, args.appid, args.token, hotwords=hotwords)

    if not utterances:
        print("No transcription results")
        sys.exit(1)

    print(f"Got {len(utterances)} utterances", flush=True)

    if args.srt:
        srt_lines = []
        for idx, utt in enumerate(utterances, 1):
            text = utt.get('text', '').strip()
            if not text:
                continue
            start = utt.get('start', 0)
            end = utt.get('end', 0)
            srt_lines.append(f"{idx}\n{format_srt_timestamp(start)} --> {format_srt_timestamp(end)}\n{text}\n")

        srt_content = '\n'.join(srt_lines)
        output_path = args.output or (os.path.splitext(input_path)[0] + '_volc.srt')

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)
        print(f"SRT saved to: {output_path}")

        if args.burn:
            output_video = os.path.splitext(output_path)[0] + '_subtitled.mp4'
            subprocess.run([
                'ffmpeg', '-y', '-i', input_path,
                '-vf', f"subtitles='{output_path}'",
                '-c:a', 'copy', output_video
            ], capture_output=True)
            print(f"Burned video saved to: {output_video}")

        if args.embed:
            output_video = os.path.splitext(output_path)[0] + '_embedded.mp4'
            subprocess.run([
                'ffmpeg', '-y', '-i', input_path,
                '-i', output_path,
                '-c:v', 'copy', '-c:a', 'copy',
                '-scodec', 'mov_text',
                '-metadata:s:s:0', 'language=chi',
                output_video
            ], capture_output=True)
            print(f"Embedded video saved to: {output_video}")
    else:
        for utt in utterances:
            text = utt.get('text', '').strip()
            if text:
                start = utt.get('start', 0)
                print(f"[{format_srt_timestamp(start)}] {text}")


if __name__ == '__main__':
    main()
