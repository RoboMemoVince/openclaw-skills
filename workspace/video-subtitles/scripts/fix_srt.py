#!/usr/bin/env -S uv run --script --quiet
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
SRT 字幕批量替换工具。

接收一个 JSON 词表文件，对 SRT 进行批量查找替换。
词表由 agent 根据具体内容动态生成，而非固定模板。

Usage:
    ./fix_srt.py input.srt --dict fixes.json                # 应用词表
    ./fix_srt.py input.srt --dict fixes.json -o output.srt  # 指定输出
    ./fix_srt.py input.srt --dict fixes.json --dry-run      # 只看统计
"""

import argparse
import json
import os
import re
import sys


def apply_replacements(text: str, replacements: dict) -> tuple[str, dict]:
    """应用替换规则，返回 (修正后文本, 统计)。
    
    替换规则按 key 长度降序执行（长的优先），避免部分匹配冲突。
    key 以 "re:" 开头视为正则表达式。
    """
    stats = {}
    
    # 按 key 长度降序排列
    sorted_rules = sorted(replacements.items(),
                          key=lambda x: len(x[0].replace("re:", "")),
                          reverse=True)
    
    for wrong, correct in sorted_rules:
        if wrong == correct:
            continue
        
        if wrong.startswith("re:"):
            pattern = wrong[3:]
            matches = len(re.findall(pattern, text))
            if matches > 0:
                text = re.sub(pattern, correct, text)
                stats[f"/{pattern}/ → {correct}"] = matches
        else:
            count = text.count(wrong)
            if count > 0:
                text = text.replace(wrong, correct)
                stats[f"{wrong} → {correct}"] = count
    
    return text, stats


def main():
    parser = argparse.ArgumentParser(description='SRT 字幕批量替换工具')
    parser.add_argument('input', help='输入 SRT 文件')
    parser.add_argument('--dict', required=True, help='替换词表 JSON 文件 {"错误": "正确", ...}')
    parser.add_argument('-o', '--output', help='输出路径（默认: input_fixed.srt）')
    parser.add_argument('--dry-run', action='store_true', help='只显示统计，不写文件')
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: {args.input} not found")
        sys.exit(1)
    
    if not os.path.exists(args.dict):
        print(f"Error: {args.dict} not found")
        sys.exit(1)
    
    # 加载词表
    with open(args.dict, 'r', encoding='utf-8') as f:
        replacements = json.load(f)
    print(f"Loaded {len(replacements)} rules from {args.dict}")
    
    # 读取 SRT
    with open(args.input, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换
    fixed, stats = apply_replacements(content, replacements)
    total = sum(stats.values())
    
    # 统计
    if stats:
        print(f"\n{'='*50}")
        print(f"替换统计 ({total} 处修正)")
        print(f"{'='*50}")
        for rule, count in sorted(stats.items(), key=lambda x: -x[1]):
            print(f"  {rule}: {count}次")
        print(f"{'='*50}")
    else:
        print("没有发现匹配项。")
    
    # 写入
    if not args.dry_run:
        output = args.output or (os.path.splitext(args.input)[0] + '_fixed.srt')
        with open(output, 'w', encoding='utf-8') as f:
            f.write(fixed)
        print(f"\nSaved to: {output}")


if __name__ == '__main__':
    main()
