#!/usr/bin/env python3
"""
OpenClaw Token Usage Report — Daily breakdown by model.
Similar to ccusage for Claude Code, but for OpenClaw.

Zero dependencies (Python 3.8+ stdlib only).

Usage:
    python3 token-usage.py               # All time
    python3 token-usage.py --days 7      # Last 7 days
    python3 token-usage.py --today       # Today only
    python3 token-usage.py --month       # Current month
    python3 token-usage.py --since 2026-03-01 --until 2026-03-06
    python3 token-usage.py --json        # JSON output
    python3 token-usage.py --tz 0        # UTC timezone
"""

import json
import glob
import os
import sys
import argparse
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# ── Default pricing (USD per 1M tokens) ─────────────────────────────────────
# Override by creating ~/.config/token-usage/pricing.json
# or editing this dict directly.
DEFAULT_PRICING = {
    # Anthropic Claude
    "claude-opus-4-6":            {"input": 15.0,  "output": 75.0,  "cacheRead": 1.5,   "cacheWrite": 18.75},
    "claude-opus-4-5":            {"input": 15.0,  "output": 75.0,  "cacheRead": 1.5,   "cacheWrite": 18.75},
    "claude-opus":                {"input": 15.0,  "output": 75.0,  "cacheRead": 1.5,   "cacheWrite": 18.75},
    "claude-sonnet-4-6":          {"input": 3.0,   "output": 15.0,  "cacheRead": 0.3,   "cacheWrite": 3.75},
    "claude-sonnet-4-5-20250929": {"input": 3.0,   "output": 15.0,  "cacheRead": 0.3,   "cacheWrite": 3.75},
    "claude-sonnet-4-5":          {"input": 3.0,   "output": 15.0,  "cacheRead": 0.3,   "cacheWrite": 3.75},
    "claude-sonnet":              {"input": 3.0,   "output": 15.0,  "cacheRead": 0.3,   "cacheWrite": 3.75},
    "claude-haiku-4-5":           {"input": 0.8,   "output": 4.0,   "cacheRead": 0.08,  "cacheWrite": 1.0},
    "claude-haiku":               {"input": 0.8,   "output": 4.0,   "cacheRead": 0.08,  "cacheWrite": 1.0},
    # OpenAI GPT
    "gpt-4o":                     {"input": 2.5,   "output": 10.0,  "cacheRead": 1.25,  "cacheWrite": 2.5},
    "gpt-4o-mini":                {"input": 0.15,  "output": 0.6,   "cacheRead": 0.075, "cacheWrite": 0.15},
    "o1":                         {"input": 15.0,  "output": 60.0,  "cacheRead": 7.5,   "cacheWrite": 15.0},
    "o1-mini":                    {"input": 1.1,   "output": 4.4,   "cacheRead": 0.55,  "cacheWrite": 1.1},
    "o3":                         {"input": 2.0,   "output": 8.0,   "cacheRead": 1.0,   "cacheWrite": 2.0},
    "o3-mini":                    {"input": 1.1,   "output": 4.4,   "cacheRead": 0.55,  "cacheWrite": 1.1},
    # Google Gemini
    "gemini-2.5-pro":             {"input": 1.25,  "output": 10.0,  "cacheRead": 0.315, "cacheWrite": 1.25},
    "gemini-2.5-flash":           {"input": 0.15,  "output": 0.6,   "cacheRead": 0.0375,"cacheWrite": 0.15},
    "gemini-3-pro-image-preview": {"input": 1.25,  "output": 10.0,  "cacheRead": 0.315, "cacheWrite": 1.25},
    "gemini-3.1-pro-preview":     {"input": 1.25,  "output": 10.0,  "cacheRead": 0.315, "cacheWrite": 1.25},
    # Qwen (Alibaba Cloud / Bailian)
    "qwen3-max-2026-01-23":       {"input": 0.55,  "output": 1.65,  "cacheRead": 0.14,  "cacheWrite": 0.55},
    "qwen3-coder-plus":           {"input": 0.55,  "output": 1.65,  "cacheRead": 0.14,  "cacheWrite": 0.55},
    "qwen-max":                   {"input": 0.55,  "output": 1.65,  "cacheRead": 0.14,  "cacheWrite": 0.55},
    # GLM / Zhipu (CNY per 1M tokens, from bigmodel.cn/pricing)
    # currency=CNY — display ¥ instead of $ for these models
    # GLM-5.1: ¥6/¥8 in, ¥24/¥28 out (low-tier [0,32k) baseline)
    "glm-5.1":                    {"input": 6.0,   "output": 24.0,  "cacheRead": 1.3,   "cacheWrite": 6.0,   "currency": "CNY"},
    "glm-5-turbo":                {"input": 5.0,   "output": 22.0,  "cacheRead": 1.2,   "cacheWrite": 5.0,   "currency": "CNY"},
    "glm-5":                      {"input": 4.0,   "output": 18.0,  "cacheRead": 1.0,   "cacheWrite": 4.0,   "currency": "CNY"},
    # GLM-4.7: ¥2/¥3/¥4 in, ¥8/¥14/¥16 out ([0,32k) [0,0.2M) out baseline)
    "glm-4.7":                    {"input": 2.0,   "output": 8.0,   "cacheRead": 0.4,   "cacheWrite": 2.0,   "currency": "CNY"},
    "glm-4.7-flashx":             {"input": 0.5,   "output": 3.0,   "cacheRead": 0.1,   "cacheWrite": 0.5,   "currency": "CNY"},
    "glm-4.7-flash":              {"input": 0.0,   "output": 0.0,   "cacheRead": 0.0,   "cacheWrite": 0.0,   "currency": "CNY"},
    "glm-4.6":                    {"input": 2.0,   "output": 8.0,   "cacheRead": 0.4,   "cacheWrite": 2.0,   "currency": "CNY"},
    # GLM-4.5-Air: ¥0.8/¥1.2 in, ¥2/¥6/¥8 out ([0,32k) [0,0.2M) baseline)
    "glm-4.5-air":                {"input": 0.8,   "output": 2.0,   "cacheRead": 0.16,  "cacheWrite": 0.8,   "currency": "CNY"},
    # Legacy models
    "glm-4-plus":                 {"input": 5.0,   "output": 15.0,  "cacheRead": 1.0,   "cacheWrite": 5.0,   "currency": "CNY"},
    "glm-4":                      {"input": 5.0,   "output": 15.0,  "cacheRead": 1.0,   "cacheWrite": 5.0,   "currency": "CNY"},
    "glm-4-air":                  {"input": 0.5,   "output": 1.5,   "cacheRead": 0.1,   "cacheWrite": 0.5,   "currency": "CNY"},
    "glm-4-flashx":               {"input": 0.1,   "output": 0.3,   "cacheRead": 0.02,  "cacheWrite": 0.1,   "currency": "CNY"},
    "glm-4-flash":                {"input": 0.0,   "output": 0.0,   "cacheRead": 0.0,   "cacheWrite": 0.0,   "currency": "CNY"},
    "glm-4-long":                 {"input": 1.0,   "output": 3.0,   "cacheRead": 0.2,   "cacheWrite": 1.0,   "currency": "CNY"},
    # Kimi (Moonshot)
    "kimi-for-coding":            {"input": 0.55,  "output": 2.20,  "cacheRead": 0.14,  "cacheWrite": 0.55},
    # MiniMax
    "MiniMax-M2.5":               {"input": 0.0,   "output": 0.0,   "cacheRead": 0.0,   "cacheWrite": 0.0},
    # DeepSeek
    "deepseek-chat":              {"input": 0.27,  "output": 1.10,  "cacheRead": 0.07,  "cacheWrite": 0.27},
    "deepseek-reasoner":          {"input": 0.55,  "output": 2.19,  "cacheRead": 0.14,  "cacheWrite": 0.55},
}

# ── ANSI helpers ─────────────────────────────────────────────────────────────
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[36m"
YELLOW = "\033[33m"
GREEN  = "\033[32m"
WHITE  = "\033[97m"
RESET  = "\033[0m"
GRAY   = "\033[90m"


def _no_color():
    """Disable color when not a TTY or NO_COLOR is set."""
    global BOLD, DIM, CYAN, YELLOW, GREEN, WHITE, RESET, GRAY
    BOLD = DIM = CYAN = YELLOW = GREEN = WHITE = RESET = GRAY = ""


def fmt_num(n):
    """Format number with commas."""
    return f"{n:,}" if n else "0"


def fmt_cost(c, currency="USD"):
    """Format cost as $X.XX or ¥X.XX"""
    if c < 0.005:
        return "$0.00" if currency == "USD" else "¥0.00"
    if currency == "CNY":
        return f"¥{c:,.2f}"
    return f"${c:,.2f}"


# ── Pricing ──────────────────────────────────────────────────────────────────
def load_pricing():
    """Load pricing: user override > default."""
    pricing = dict(DEFAULT_PRICING)

    # Check for user pricing override
    for config_dir in [
        os.path.expanduser("~/.config/token-usage"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."),
    ]:
        override_path = os.path.join(config_dir, "pricing.json")
        if os.path.exists(override_path):
            try:
                with open(override_path) as f:
                    user_pricing = json.load(f)
                pricing.update(user_pricing)
            except Exception:
                pass
            break

    return pricing


def calc_cost(pricing, model_id, input_t, output_t, cache_read, cache_write):
    """Calculate estimated cost for a message. Returns (cost, currency)."""
    bare = model_id.split("/")[-1] if "/" in model_id else model_id
    p = pricing.get(bare)
    if not p:
        return 0.0, "USD"
    currency = p.get("currency", "USD")
    cost = (
        input_t    * p.get("input", 0)      / 1_000_000
        + output_t * p.get("output", 0)     / 1_000_000
        + cache_read  * p.get("cacheRead", 0)  / 1_000_000
        + cache_write * p.get("cacheWrite", 0) / 1_000_000
    )
    return cost, currency


# ── Parse JSONL sessions ────────────────────────────────────────────────────
def parse_sessions(base_dir, tz_offset, pricing, since_ts=None, until_ts=None):
    """Parse all JSONL session files under base_dir/agents/*/sessions/*.jsonl"""
    pattern = os.path.join(base_dir, "agents", "*", "sessions", "*.jsonl")
    files = glob.glob(pattern)

    # Determine default model from config as fallback
    default_model = None
    config_path = os.path.join(base_dir, "openclaw.json")
    try:
        with open(config_path) as cf:
            config = json.load(cf)
        dm = config.get("agents", {}).get("defaults", {}).get("model", {})
        if isinstance(dm, dict):
            primary = dm.get("primary", "")
            default_model = primary.split("/")[-1] if "/" in primary else primary
        elif isinstance(dm, str):
            default_model = dm.split("/")[-1] if "/" in dm else dm
    except Exception:
        pass

    tz = timezone(timedelta(hours=tz_offset))
    records = []

    for fpath in files:
        current_model = None

        try:
            with open(fpath, "r", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        continue

                    entry_type = obj.get("type", "")

                    if entry_type == "model_change":
                        current_model = obj.get("modelId")

                    elif entry_type == "custom" and obj.get("customType") == "model-snapshot":
                        data = obj.get("data", {})
                        mid = data.get("modelId")
                        if mid:
                            current_model = mid

                    elif entry_type == "message":
                        msg = obj.get("message", {})
                        if msg.get("role") != "assistant":
                            continue
                        usage = msg.get("usage")
                        if not usage:
                            continue

                        # Prefer message-level model, fall back to current_model / default
                        msg_model = msg.get("model")
                        model = msg_model or current_model or default_model

                        # Skip internal/mirror models with no real usage
                        if model in ("delivery-mirror",):
                            continue
                        if not model:
                            continue

                        ts_ms = msg.get("timestamp", 0)
                        if not ts_ms:
                            continue
                        if since_ts and ts_ms < since_ts:
                            continue
                        if until_ts and ts_ms > until_ts:
                            continue

                        dt = datetime.fromtimestamp(ts_ms / 1000, tz=tz)
                        date_str = dt.strftime("%Y-%m-%d")

                        inp = max(usage.get("input", 0), 0)
                        out = max(usage.get("output", 0), 0)
                        cr  = max(usage.get("cacheRead", 0), 0)
                        cw  = max(usage.get("cacheWrite", 0), 0)

                        cost_val, cost_cur = calc_cost(pricing, model, inp, out, cr, cw)
                        records.append({
                            "date": date_str,
                            "model": model,
                            "input": inp,
                            "output": out,
                            "cacheRead": cr,
                            "cacheWrite": cw,
                            "cost": cost_val,
                            "currency": cost_cur,
                        })
        except Exception:
            continue

    return records


# ── Aggregate ────────────────────────────────────────────────────────────────
def aggregate(records):
    """Aggregate records by (date, model) → sorted list of daily summaries with per-model breakdown."""
    # Two-level aggregation: date → model → stats
    daily_models = defaultdict(lambda: defaultdict(lambda: {
        "input": 0, "output": 0, "cacheWrite": 0, "cacheRead": 0, "cost": 0.0, "currency": "USD",
    }))

    for r in records:
        d = daily_models[r["date"]][r["model"]]
        for k in ("input", "output", "cacheWrite", "cacheRead", "cost"):
            d[k] += r[k]
        # Propagate currency from the model (all records for same model share currency)
        if r.get("currency"):
            d["currency"] = r["currency"]

    result = []
    for date in sorted(daily_models):
        models_data = []
        day_total_usd = {"input": 0, "output": 0, "cacheWrite": 0, "cacheRead": 0, "cost": 0.0}
        day_total_cny = {"input": 0, "output": 0, "cacheWrite": 0, "cacheRead": 0, "cost": 0.0}
        for model in sorted(daily_models[date]):
            m = daily_models[date][model]
            total = m["input"] + m["output"] + m["cacheWrite"] + m["cacheRead"]
            cur = m.get("currency", "USD")
            models_data.append({
                "model": model,
                "input": m["input"],
                "output": m["output"],
                "cacheWrite": m["cacheWrite"],
                "cacheRead": m["cacheRead"],
                "total": total,
                "cost": m["cost"],
                "currency": cur,
            })
            bucket = day_total_cny if cur == "CNY" else day_total_usd
            for k in ("input", "output", "cacheWrite", "cacheRead", "cost"):
                bucket[k] += m[k]

        day_total = {
            "input": day_total_usd["input"] + day_total_cny["input"],
            "output": day_total_usd["output"] + day_total_cny["output"],
            "cacheWrite": day_total_usd["cacheWrite"] + day_total_cny["cacheWrite"],
            "cacheRead": day_total_usd["cacheRead"] + day_total_cny["cacheRead"],
            "cost_usd": day_total_usd["cost"],
            "cost_cny": day_total_cny["cost"],
        }
        day_total["total"] = day_total["input"] + day_total["output"] + day_total["cacheWrite"] + day_total["cacheRead"]
        result.append({
            "date": date,
            "models": models_data,
            **day_total,
        })
    return result


# ── Render ───────────────────────────────────────────────────────────────────
def render_table(rows):
    """Render ccusage-style daily table."""
    if not rows:
        print(f"{DIM}No data found.{RESET}")
        return

    print()
    print(f"  {BOLD}{WHITE}OpenClaw Token Usage Report — Daily{RESET}")
    print()

    W_DATE, W_MODELS, W_NUM, W_COST = 12, 30, 14, 12

    print(
        f"  {BOLD}{CYAN}{'Date':<{W_DATE}}{'Models':<{W_MODELS}}"
        f"{'Input':>{W_NUM}}{'Output':>{W_NUM}}{'Cache Create':>{W_NUM}}"
        f"{'Cache Read':>{W_NUM}}{'Total Tokens':>{W_NUM}}{'Cost':>{W_COST}}{RESET}"
    )

    sep = f"  {GRAY}{'─' * (W_DATE + W_MODELS + W_NUM * 5 + W_COST)}{RESET}"
    print(sep)

    grand_usd = {"input": 0, "output": 0, "cacheWrite": 0, "cacheRead": 0, "total": 0, "cost": 0.0}
    grand_cny = {"input": 0, "output": 0, "cacheWrite": 0, "cacheRead": 0, "total": 0, "cost": 0.0}

    for row in rows:
        models = row["models"]  # list of {model, input, output, ...}

        for i, m in enumerate(models):
            date_col = row["date"] if i == 0 else ""
            model_label = f"– {m['model']}"

            print(
                f"  {BOLD}{WHITE}{date_col:<{W_DATE}}{RESET}"
                f"{YELLOW}{model_label:<{W_MODELS}}{RESET}"
                f"{WHITE}{fmt_num(m['input']):>{W_NUM}}"
                f"{fmt_num(m['output']):>{W_NUM}}"
                f"{fmt_num(m['cacheWrite']):>{W_NUM}}"
                f"{fmt_num(m['cacheRead']):>{W_NUM}}"
                f"{fmt_num(m['total']):>{W_NUM}}{RESET}"
                f"{GREEN}{fmt_cost(m['cost'], m.get('currency', 'USD')):>{W_COST}}{RESET}"
            )

        # Day subtotal line if multiple models
        if len(models) > 1:
            # Show separate USD/CNY subtotals if both exist
            cost_parts = []
            if row.get("cost_usd", 0) > 0:
                cost_parts.append(fmt_cost(row["cost_usd"], "USD"))
            if row.get("cost_cny", 0) > 0:
                cost_parts.append(fmt_cost(row["cost_cny"], "CNY"))
            cost_str = " + ".join(cost_parts) if cost_parts else "$0.00"
            print(
                f"  {'':<{W_DATE}}"
                f"{DIM}{'(day total)':<{W_MODELS}}{RESET}"
                f"{DIM}{fmt_num(row['input']):>{W_NUM}}"
                f"{fmt_num(row['output']):>{W_NUM}}"
                f"{fmt_num(row['cacheWrite']):>{W_NUM}}"
                f"{fmt_num(row['cacheRead']):>{W_NUM}}"
                f"{fmt_num(row['total']):>{W_NUM}}"
                f"{cost_str:>{W_COST}}{RESET}"
            )

        for m in models:
            cur = m.get("currency", "USD")
            bucket = grand_cny if cur == "CNY" else grand_usd
            for k in ("input", "output", "cacheWrite", "cacheRead"):
                bucket[k] += m[k]
            bucket["total"] += m["total"]
            bucket["cost"] += m["cost"]

    print(sep)
    total_input = grand_usd["input"] + grand_cny["input"]
    total_output = grand_usd["output"] + grand_cny["output"]
    total_cw = grand_usd["cacheWrite"] + grand_cny["cacheWrite"]
    total_cr = grand_usd["cacheRead"] + grand_cny["cacheRead"]
    total_tokens = grand_usd["total"] + grand_cny["total"]
    cost_parts = []
    if grand_usd["cost"] > 0:
        cost_parts.append(fmt_cost(grand_usd["cost"], "USD"))
    if grand_cny["cost"] > 0:
        cost_parts.append(fmt_cost(grand_cny["cost"], "CNY"))
    cost_str = " + ".join(cost_parts) if cost_parts else "$0.00"
    print(
        f"  {BOLD}{WHITE}{'Total':<{W_DATE}}{'':<{W_MODELS}}"
        f"{fmt_num(total_input):>{W_NUM}}"
        f"{fmt_num(total_output):>{W_NUM}}"
        f"{fmt_num(total_cw):>{W_NUM}}"
        f"{fmt_num(total_cr):>{W_NUM}}"
        f"{fmt_num(total_tokens):>{W_NUM}}{RESET}"
        f"{BOLD}{GREEN}{cost_str:>{W_COST}}{RESET}"
    )
    print()


def render_json(rows):
    """Output as JSON."""
    grand_usd = {"input": 0, "output": 0, "cacheWrite": 0, "cacheRead": 0, "total": 0, "cost": 0.0}
    grand_cny = {"input": 0, "output": 0, "cacheWrite": 0, "cacheRead": 0, "total": 0, "cost": 0.0}
    for row in rows:
        for m in row["models"]:
            cur = m.get("currency", "USD")
            bucket = grand_cny if cur == "CNY" else grand_usd
            for k in ("input", "output", "cacheWrite", "cacheRead", "total"):
                bucket[k] += m[k]
            bucket["cost"] += m["cost"]

    # Flatten models list to just names for backward compat
    out_rows = []
    for row in rows:
        out_rows.append({
            **row,
            "model_details": row["models"],
            "models": [m["model"] for m in row["models"]],
        })

    print(json.dumps({
        "title": "OpenClaw Token Usage Report — Daily",
        "days": out_rows,
        "total_usd": grand_usd,
        "total_cny": grand_cny,
    }, indent=2, ensure_ascii=False))


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="OpenClaw Token Usage Report — ccusage-style daily breakdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --today          Today only
  %(prog)s --week           Last 7 days
  %(prog)s --month          Current calendar month
  %(prog)s --days 30        Last 30 days
  %(prog)s --since 2026-03-01 --until 2026-03-06
  %(prog)s --json           JSON output for scripting
  %(prog)s --tz 0           Use UTC timezone
""",
    )
    parser.add_argument("--days", type=int, metavar="N", help="Show last N days")
    parser.add_argument("--today", action="store_true", help="Today only")
    parser.add_argument("--week", action="store_true", help="Last 7 days")
    parser.add_argument("--month", action="store_true", help="Current calendar month")
    parser.add_argument("--since", type=str, metavar="DATE", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--until", type=str, metavar="DATE", help="End date (YYYY-MM-DD)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--tz", type=int, default=8, metavar="OFFSET",
                        help="UTC offset in hours (default: 8 for Asia/Shanghai)")
    parser.add_argument("--no-color", action="store_true", help="Disable colors")
    parser.add_argument("--dir", type=str, default=os.path.expanduser("~/.openclaw"),
                        metavar="PATH", help="OpenClaw data directory (default: ~/.openclaw)")
    args = parser.parse_args()

    if args.no_color or not sys.stdout.isatty():
        _no_color()

    tz = timezone(timedelta(hours=args.tz))
    now = datetime.now(tz=tz)

    since_ts = None
    until_ts = None

    if args.today:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        since_ts = int(start.timestamp() * 1000)
    elif args.week:
        start = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
        since_ts = int(start.timestamp() * 1000)
    elif args.month:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        since_ts = int(start.timestamp() * 1000)
    elif args.days:
        start = (now - timedelta(days=args.days)).replace(hour=0, minute=0, second=0, microsecond=0)
        since_ts = int(start.timestamp() * 1000)

    if args.since:
        dt = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=tz)
        since_ts = int(dt.timestamp() * 1000)
    if args.until:
        dt = datetime.strptime(args.until, "%Y-%m-%d").replace(tzinfo=tz)
        dt = dt.replace(hour=23, minute=59, second=59)
        until_ts = int(dt.timestamp() * 1000)

    pricing = load_pricing()
    records = parse_sessions(args.dir, args.tz, pricing, since_ts, until_ts)
    rows = aggregate(records)

    if args.json:
        render_json(rows)
    else:
        render_table(rows)


if __name__ == "__main__":
    main()
