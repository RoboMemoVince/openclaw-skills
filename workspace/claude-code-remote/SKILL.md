---
name: claude-code-remote
description: "Run Claude Code tasks on Alice (remote NPU dev server) via SSH. Use when user asks to run coding tasks, code reviews, refactoring, or Agent Teams on Alice. Triggers: 'claude code', 'agent teams', 'Alice上跑', '用Claude Code', '代码审查', 'review代码'."
platform: [openclaw]
---

# Claude Code Remote — Run Claude Code on Alice

Execute Claude Code CLI tasks on Alice (NPU dev server) from OpenClaw, with results delivered back to the user's chat.

## Environment

- **Alice**: root@1.95.7.166, SSH key `~/.ssh/KeyPair-d9c2.pem`
- **Docker**: `triton-ascend-hcq`, Claude Code v2.1.50
- **Work dirs**: `/data0/Musk` (算子开发), `/data0/triton-ascend-zeron` (triton-ascend), `/data0/hcq`, `/data0/mhc_post`
- **Agent Teams**: enabled (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=true`)
- **Permissions**: Root user — hooks handle permissions (PreToolUse auto-allow + block-dangerous.sh safety net)
- **Safety net**: PreToolUse Hook at `~/.claude/hooks/block-dangerous.sh` — two-tier system:
  - 🔴 Hard deny: dd, mkfs, reboot, write to /dev/ or /boot/
  - 🟡 Ask: rm -rf, git push --force, git reset --hard, chmod 777, write to /etc/
  - 🟢 Auto-allow: everything else (via `auto-allow.sh` hook)

## SSH Helper

All commands go through this pattern:
```bash
ssh -i ~/.ssh/KeyPair-d9c2.pem -o StrictHostKeyChecking=no root@1.95.7.166 \
  "docker exec triton-ascend-hcq bash -c '<COMMAND>'"
```

Ensure SSH key is in place before first use:
```bash
cp /root/.openclaw/workspace/.ssh/KeyPair-d9c2.pem ~/.ssh/ 2>/dev/null
chmod 600 ~/.ssh/KeyPair-d9c2.pem
```

## Mode A: Non-Interactive (--print) — Primary Mode

For single-agent tasks and OpenClaw-orchestrated parallel multi-agent tasks.

### Command Template

```bash
ssh -i ~/.ssh/KeyPair-d9c2.pem -o StrictHostKeyChecking=no root@1.95.7.166 \
  "docker exec triton-ascend-hcq bash -c 'cd <WORKDIR> && claude -p \
    --permission-mode dontAsk \
    --model <MODEL> \
    --max-budget-usd <BUDGET> \
    --output-format json \
    \"<TASK_PROMPT>\"'"
```

### Parameters

| Parameter | Default | Notes |
|-----------|---------|-------|
| MODEL | opus | Default opus. Use `sonnet` only when explicitly requested or for trivial tasks |
| BUDGET | 2.0 | Max USD per run. Raise for large tasks (max 10.0) |
| WORKDIR | /data0/Musk | Change based on project |
| TASK_PROMPT | (from user) | Escape single quotes in prompt |

### Output Parsing

JSON output contains:
- `result`: The text response
- `total_cost_usd`: Actual cost
- `num_turns`: How many tool-use turns it took
- `usage`: Token breakdown
- `permission_denials`: Tools that were blocked

### Handling Permission Denials

Hooks auto-allow most operations. The PreToolUse safety net still guards dangerous operations:
- 🔴 Hard-denied commands won't execute — check if expected output is missing
- 🟡 Ask-level commands will be denied in `--print` mode (no interactive prompt) — report to user
- If a task needs `rm -rf` or `git push --force`, inform user to run manually or via Mode B

### Example: Code Review

```bash
cd /data0/Musk && claude -p --permission-mode dontAsk --model opus --max-budget-usd 3.0 --output-format json \
  "Review the mhc_pre_only/hc_pre_only_fwd_triton.py kernel implementation. \
   Focus on: 1) correctness of tiling logic, 2) potential NPU performance issues, \
   3) memory access patterns. Output a structured review."
```

### Parallel Multi-Agent via OpenClaw (推荐)

When a task benefits from multiple perspectives, use OpenClaw's `sessions_spawn` to run multiple Claude Code instances in parallel. This is the **recommended alternative to Agent Teams** for remote use.

#### How It Works

```
OpenClaw 主 session
  ├── spawn 子 agent 1 → SSH → claude -p --model opus "审查安全性和正确性"
  ├── spawn 子 agent 2 → SSH → claude -p --model opus "审查性能和内存访问"
  └── spawn 子 agent 3 → SSH → claude -p --model opus "审查测试覆盖和边界情况"
  → 三个结果都回来后汇总发飞书
```

#### Advantages over Agent Teams (remote)
- ✅ 并行执行，全自动
- ✅ JSON 结果，可靠解析
- ✅ 每个子 agent 可用不同模型（如需省钱可指定 sonnet）
- ✅ 不需要人工干预
- ❌ 子 agent 之间不能直接通信（Agent Teams 的核心优势没了）

#### Prompt Template for Parallel Review

Each sub-agent gets a focused prompt like:
```
You are reviewing <FILE_OR_MODULE>.
Your SOLE focus: <ASPECT> (e.g., security, performance, test coverage).
Read the code, analyze it deeply, and produce a structured report with:
1. Summary assessment
2. Issues found (severity: critical/warning/info)
3. Specific recommendations with code references
```

## Mode A+: Parallel Hardware Exploration — NPU/GPU Optimization

When exploring multiple optimization directions on hardware with multiple devices, dispatch parallel CC instances each pinned to a different device.

**Origin**: EHQ backward kernel optimization (2026-02-26). Three CC instances explored different approaches simultaneously — one of them (explore_b) discovered the key insight that unlocked a 1.87x speedup, which hand-debugging had missed across 6 failed attempts.

### When to Use

- Have a working baseline but need to explore optimization space
- Multiple independent optimization hypotheses
- Hardware has multiple devices (NPU 0-7, multi-GPU, etc.)
- Each hypothesis can be tested independently (no shared state)

### Pre-Dispatch Checklist

1. **Write a DEV.md document** with:
   - Current baseline performance + profiler breakdown
   - All failed attempts and WHY they failed (critical! CC needs to know the minefield)
   - Hardware constraints (UB size, device count, memory limits)
   - Reference to working code files
2. **Prepare explore directories**: `mkdir explore_{a,b,c}` with all source files copied
3. **Assign one device per CC** to avoid contention
4. **Limit scope**: Each CC gets ONE direction with "max N approaches, skip on compile error"

### Standard Setup

```bash
# 1. Prepare directories (on remote)
ssh ... "docker exec <CONTAINER> bash -c '
  cd <PROJECT_DIR>
  mkdir -p explore_a explore_b explore_c
  for d in explore_a explore_b explore_c; do
    cp *.py *.md \$d/
  done
'"

# 2. Check device availability
ssh ... "docker exec <CONTAINER> npu-smi info"  # or nvidia-smi

# 3. Launch parallel CCs (from OpenClaw, use exec with background=true)
```

### Prompt Template for Hardware Exploration

```
## 任务：<DIRECTION_NAME>

你在 <PROJECT_DIR>/explore_X/ 目录下工作。

## 必读
1. 本目录下 <DEV_DOC>.md — 完整开发文档，包含踩坑记录
2. <ADDITIONAL_REFERENCES>

## 当前情况
- Baseline: <PERF>μs，精度 PASS
- 核心问题：<BOTTLENECK_DESCRIPTION>

## 你的优化方向
1. <SPECIFIC_APPROACH_1>
2. <SPECIFIC_APPROACH_2>
3. 最多尝试 <N> 种方案，遇到编译/对齐错误就跳过，不要卡死

## 执行环境
<ENV_SETUP_COMMANDS>
ASCEND_RT_VISIBLE_DEVICES=<DEVICE_ID> python3 xxx.py  # 或 CUDA_VISIBLE_DEVICES=

直接开始实现+测试。报告每种方案的精度和性能结果。
```

### Prompt Engineering Lessons (实战经验)

| ✅ Do | ❌ Don't |
|-------|---------|
| 给完整的踩坑文档（试过什么、为什么失败） | 只给代码不给背景 |
| 限定方案数量（"最多 3 种"） | 不限制，让 CC 无限发散（explore_a 写了 8 个方案） |
| 指定具体的精度验证方式和命令 | 只说"测试正确性" |
| 明确指定设备 ID（ASCEND_RT_VISIBLE_DEVICES=N） | 不指定，多个 CC 抢同一设备 |
| 说"遇到编译错误跳过，不要卡死" | 不说，CC 死磕一个编译错误 20 分钟 |
| 引用 pitfalls 文档路径让 CC 先读 | 让 CC 自己踩坑 |

### Progress Monitoring

CC 的 `--output-format json` 不支持流式输出，只能通过文件变化间接监控：

```bash
# 检查各 explore 目录的新文件（用 -newer 基准文件）
ssh ... "docker exec <CONTAINER> bash -c '
  echo \"=== explore_a ===\"
  find <DIR>/explore_a/ -name \"*.py\" -newer <DIR>/explore_a/utils.py -type f | sort
  echo \"=== explore_b ===\"
  find <DIR>/explore_b/ -name \"*.py\" -newer <DIR>/explore_b/utils.py -type f | sort
'"
```

**Monitoring cadence**: 每 3-5 分钟检查一次文件变化。不要 poll CC 进程本身（无输出直到完成）。

### Post-Completion Workflow

1. **收集结果**：CC 完成后读 JSON `result` 字段 or 手动跑 bench 脚本
2. **交叉验证最优方案**：最好的方案要在主目录重新跑精度 + profiler
3. **落盘**：最优方案 → 主目录，清理 explore 目录
4. **记录发现**：尤其是"意外发现"要沉淀到 pitfalls/经验

### SSH Robustness

Alice SSH 频繁断连（kex_exchange_identification 错误），**必须用重试模板**：

```bash
# 标准 SSH 重试模板（所有 Alice 操作都用这个）
for i in 1 2 3 4 5; do
  sleep 5
  scp -i ~/.ssh/KeyPair-d9c2.pem -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
    <LOCAL_FILE> root@1.95.7.166:/tmp/ 2>/dev/null && \
  ssh -i ~/.ssh/KeyPair-d9c2.pem -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
    root@1.95.7.166 "<COMMANDS>" 2>&1 && break
  echo "retry $i"
done
```

**CC 进程被 SIGTERM**: SSH 断连会杀死 CC 进程。如果 CC 跑了很久被杀：
- 检查 explore 目录里已有的文件（CC 可能已经跑完了部分方案）
- 手动运行 bench 脚本验证已有结果
- 不需要从头重跑

### Real Example: EHQ Backward Kernel (2026-02-26)

**问题**: 反向 kernel 的 `tl.sum` 行归约在 Ascend 上各种 UB 对齐错误，6 种方案全挂。Baseline（避开 tl.sum）4492μs。

**并行调度**:

| CC | 目录 | NPU | 方向 | 结果 |
|----|------|-----|------|------|
| explore_a | 融合 kernel + 替代归约方式 | NPU 1 | tl.dot / tl.reduce / partial reduce | 2485μs (H2) |
| explore_b | tl.sum 可用边界系统性测试 | NPU 2 | 从最小 kernel 开始逐步加复杂度 | **2401μs** 🏆 |
| explore_c | 融合 gw+gs_elem 单 kernel | NPU 3 | 省 GM 带宽，host reduction | 2747μs |

**关键发现**: explore_b 发现 tl.sum 本身没问题，之前失败是因为传入 `scale_mask_ptr` + `scale_f32_ptr` 两个预处理数组导致额外 UB 占用。在 kernel 内直接 clamp scale 就绕过了。这个 insight 是 CC 从零系统性测试才发现的，手动调试 6 次都没找到根因。

**耗时**: 3 路并行 ~15 分钟完成，串行估计需要 45+ 分钟。

## Mode B: Interactive Agent Teams — Manual Use Only

⚠️ **Not recommended for remote/automated use.** Best when user SSHes into Alice directly.

Agent Teams is interactive-only. It requires tmux panes, real-time user interaction (Shift+Up/Down to switch Teammates), and cannot reliably be operated via remote tmux scraping.

### When to Use Mode B
- User explicitly wants Agent Teams with interactive control
- Task requires Teammates to debate and challenge each other in real-time
- User will SSH into Alice themselves

### Why Not Remote
- Dynamic tmux UI is hard to parse via `capture-pane`
- No reliable way to detect completion
- Ask-level permission prompts will block with no way to approve
- Can't steer Teammates mid-flight

### Quick Setup (for user's reference)

```bash
# SSH into Alice
ssh -i ~/.ssh/KeyPair-d9c2.pem root@1.95.7.166
docker exec -it triton-ascend-hcq bash
cd /data0/Musk

# Start Claude Code (Agent Teams auto-enabled via settings.json)
claude --model opus

# Then in Claude Code, describe your team:
# "Create an agent team to review mhc_pre_only..."
```

### Agent Teams Prompt Templates

**Multi-Perspective Review**:
```
Create an agent team to review <FILE_OR_MODULE>:
- Teammate 1: Focus on correctness and algorithm logic
- Teammate 2: Focus on NPU performance (memory access, tiling, vectorization)
- Teammate 3: Focus on edge cases and test coverage
Have them share findings and debate disagreements.
```

**Competitive Debugging**:
```
<BUG_DESCRIPTION>
Create a debugging team with 3 teammates, each investigating a different hypothesis:
- Hypothesis 1: <H1>
- Hypothesis 2: <H2>
- Hypothesis 3: <H3>
Have them share evidence and argue which theory fits.
```

**Feature Development**:
```
Create an agent team to implement <FEATURE>:
- Teammate 1: Core implementation in <FILE>
- Teammate 2: Reference/test implementation
- Teammate 3: Benchmark and profiling scripts
Use Sonnet for each teammate to save cost.
```

## Workflow

1. **User requests a task** via chat (飞书/Telegram)
2. **Confirm with user** before executing (scope, budget; model defaults to opus)
3. **Choose mode**:
   - Single task → Mode A single
   - Multi-perspective task → Mode A parallel (multiple `sessions_spawn`)
   - User wants interactive Agent Teams → Mode B (guide user to SSH themselves)
4. **Execute** via SSH + docker exec
5. **Parse and summarize** results
6. **Report back** to user with: result summary, cost, any issues
7. **Save experience** to memory if noteworthy

## Cost Awareness

- **Default model: opus** (~$15/input M, ~$75/output M tokens, with caching discounts)
- Sonnet: ~$3/input M, ~$15/output M tokens — use only when explicitly requested
- Parallel multi-agent: cost scales linearly with number of sub-agents
- Agent Teams (Mode B): ~5x single session cost
- Always report actual `total_cost_usd` to user

## Safety

- **Always confirm with user before executing** — never auto-run tasks without approval
- Report permission denials transparently
- Set reasonable `--max-budget-usd` limits (default $2, raise with user approval)
- For Mode B: recommend user operates directly, not via OpenClaw remote
