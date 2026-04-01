---
name: token-usage
platform: [openclaw]
description: Use when user asks about token usage, cost tracking, daily consumption, or wants a ccusage-style report for OpenClaw. Triggers - token usage, cost, how much did I spend, daily report, usage breakdown, token stats, 用量统计, token 消耗, 费用查询.
---

# Token Usage Report

Generate ccusage-style daily token usage reports for OpenClaw, with per-model breakdown, cache stats, and estimated cost.

## Quick Start

```bash
# Run the report script (zero dependencies, Python 3.8+)
python3 scripts/token-usage.py

# Common filters
python3 scripts/token-usage.py --today
python3 scripts/token-usage.py --week
python3 scripts/token-usage.py --month
python3 scripts/token-usage.py --days 30
python3 scripts/token-usage.py --since 2026-03-01 --until 2026-03-06

# JSON output (for scripting)
python3 scripts/token-usage.py --json

# Custom OpenClaw data dir
python3 scripts/token-usage.py --dir /path/to/.openclaw
```

Resolve `scripts/token-usage.py` relative to this skill's directory.

## Output Delivery (by channel)

Check `channel` from the runtime system prompt or inbound metadata to decide how to deliver:

- **Telegram**: Telegram 不渲染 Markdown 表格。运行脚本后用 `aha` 转 HTML + Playwright 截图，通过 `message` tool 发图片。流程：
  1. `python3 scripts/token-usage.py --week 2>&1 | aha --no-header > /tmp/tr.html`
  2. 包一层深色背景 HTML（`background: #1a1a2e`, monospace 字体）
  3. Playwright 截图 → 通过 message tool 发送图片（filePath）
  4. 清理临时文件

- **Feishu / TUI / Webchat / Discord**: 这些渠道支持 Markdown 表格。用 `--json` 拿数据，自己渲染成 Markdown 表格直接回复即可，不需要截图。

- **WhatsApp**: 不支持表格，用列表格式或代码块。

## What It Does

- Parses all `~/.openclaw/agents/*/sessions/*.jsonl` transcript files
- Extracts `model_change` + assistant `message` entries with `usage` fields
- Groups by date (local timezone) and model
- Calculates estimated cost from built-in pricing table
- Renders a colored terminal table or JSON

## Cost Estimation

Built-in pricing for Claude, GPT, Gemini, Qwen, DeepSeek, Kimi, GLM, MiniMax.

Custom pricing override: create `~/.config/token-usage/pricing.json`:

```json
{
  "my-custom-model": {"input": 1.0, "output": 5.0, "cacheRead": 0.1, "cacheWrite": 1.0}
}
```

Prices are USD per 1M tokens. Unknown models show $0.00.

## CLI Options

| Flag | Effect |
|------|--------|
| `--today` | Today only |
| `--week` | Last 7 days |
| `--month` | Current calendar month |
| `--days N` | Last N days |
| `--since DATE` | Start date (YYYY-MM-DD) |
| `--until DATE` | End date (YYYY-MM-DD) |
| `--json` | JSON output for scripting |
| `--tz OFFSET` | UTC offset hours (default: 8) |
| `--no-color` | Disable ANSI colors |
| `--dir PATH` | OpenClaw data dir (default: ~/.openclaw) |

## Output Columns

| Column | Meaning |
|--------|---------|
| Input | New input tokens (non-cached) |
| Output | Generated output tokens |
| Cache Create | Tokens written to prompt cache |
| Cache Read | Tokens read from prompt cache |
| Total Tokens | Sum of all columns |
| Cost (USD) | Estimated cost based on pricing table |

## Fallback Model

Sessions without a `model_change` event use the default model from `openclaw.json` config. If not found, those messages are skipped.

## Requirements

- Python 3.8+ (stdlib only, zero external dependencies)
- OpenClaw session data in `~/.openclaw/agents/`
