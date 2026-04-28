---
name: claude-code-remote
description: "Run Claude Code tasks on remote servers via SSH (SDK/Headless mode). Use when user asks to run coding tasks, code reviews, refactoring, or parallel multi-agent exploration on remote machines. Triggers: 'claude code', '远程CC', '用Claude Code', '代码审查', 'review代码'."
---

# Claude Code Remote — Run CC on Remote Servers via SSH

Execute Claude Code CLI tasks on remote servers from OpenClaw. Supports two modes: **tmux 交互式**（首选）和 **SDK/Headless**（`-p`）。

## 运行模式选择

| 场景 | 模式 | 原因 |
|------|------|------|
| **长任务、自治开发、需要 stop-hook** | **tmux 交互式** ✅ 首选 | stop-hook 生效，CC 不会提前退出 |
| **短任务、一次性查询、code review** | `-p` headless | 简单直接，JSON 结果好解析 |
| **需要 tda/plugin commands** | **tmux 交互式** ✅ 必须 | plugins 在 `-p` 下部分功能失效 |
| **并行探索（triton 优化）** | **tmux 交互式** ✅ 首选 | 每路 CC 独立 tmux session |

**经验法则：预期运行超过 5 分钟的任务，用 tmux 交互式。**

## 目标主机（运行时确定）

本技能**不绑定特定主机**。执行前需确定：

| 参数 | 说明 | 来源 |
|------|------|------|
| `HOST` | 远程主机地址（user@ip） | 用户指定 或 TOOLS.md |
| `SSH_KEY` | SSH 私钥路径 | TOOLS.md |
| `CONTAINER` | Docker 容器名（如有） | TOOLS.md，无容器则留空 |
| `WORKDIR` | 项目工作目录 | 用户指定 |

### SSH 命令模板

```bash
# 有 Docker 容器
ssh -i <SSH_KEY> -o StrictHostKeyChecking=no -o ConnectTimeout=10 <HOST> \
  "docker exec <CONTAINER> bash -c '<COMMAND>'"

# 无容器
ssh -i <SSH_KEY> -o StrictHostKeyChecking=no -o ConnectTimeout=10 <HOST> '<COMMAND>'
```

## 模式 A: tmux 交互式（首选）

### 环境准备（一次性）

```bash
<SSH_CMD> "which tmux || apt-get update -qq && apt-get install -y -qq tmux"
```

### 启动

```bash
# 1. 创建 tmux session
<SSH_CMD> "tmux new-session -d -s <SESSION_NAME> \
  'cd <WORKDIR> && <CC_BIN> --model opus [--plugin-dir <PLUGIN_DIR>]'"

# 2. 等 CC 启动（看到 ❯ 提示符）
sleep 12

# 3a. 如果有 tda 插件 → 使用 /tda:run 启动（⚠️ 推荐）
<SSH_CMD> "tmux send-keys -t <SESSION_NAME> \
  '/tda:run 按照算子说明文档[<OP_NAME>_task.docx](./<OP_NAME>_task.docx)进行算子开发并调优 --operator <OP_NAME> --direction fwd' Enter"

# 3b. 如果没有 tda 插件 → 发送普通 prompt
<SSH_CMD> "tmux send-keys -t <SESSION_NAME> '<TASK_PROMPT>' Enter"
```

**⚠️ Triton 开发任务必须用 `/tda:run`（3a），不要用普通 prompt（3b）**

原因：
1. `/tda:run` 通过 `allowed-tools` 白名单授权 CC 访问 `.claude/` 目录下的 tda 状态文件
2. `/tda:run` 强制 CC 读取 SKILL.md，加载 Iron Laws（"NO ITERATION WITHOUT A WRITTEN RECORD"）
3. stop-hook 依赖 CC 能更新 `.claude/triton-agent.local.md` 的 iteration 计数器
4. 普通 prompt 启动的 CC 不会加载 tda 的工具白名单，导致状态文件无法更新，迭代记录被跳过

**如果 `/tda:run` 无法使用**（如 plugin 未加载），退回到等效 prompt，确保 CC 读取 SKILL.md 和状态文件。由于不再使用 dontAsk，CC 遇到权限确认会暂停等待，编排智能体需通过 `tmux capture-pane` 监控，看到确认提示时用 `tmux send-keys 'Y' Enter` 自动确认。

**关键注意事项：**
- 不要加 `| tee` 或 pipe — 会让 CC 误判为 headless 模式
- 等 CC 完全启动后再发 prompt（`sleep 10-15` 或用 `tmux capture-pane` 确认看到提示符）
- 每个长任务一个 tmux session，命名有意义（如 `review_kernel`、`op_softmax`）

### 监控

```bash
# 查看 CC 当前屏幕输出
<SSH_CMD> "tmux capture-pane -t <SESSION_NAME> -p -S -20"

# 列出所有 CC sessions
<SSH_CMD> "tmux ls"
```

### 追加指令（CC 运行中注入新信息）

```bash
<SSH_CMD> "tmux send-keys -t <SESSION_NAME> '<ADDITIONAL_INSTRUCTION>' Enter"
```

### 优雅取消

```bash
# 如果用了 tda plugin（有 state 文件），修改状态触发干净退出
<SSH_CMD> "sed -i 's/^status: active/status: cancelled/' <WORKDIR>/.claude/triton-agent.local.md"

# 通用：直接关闭 tmux session
<SSH_CMD> "tmux kill-session -t <SESSION_NAME>"
```

### 检查完成

tmux session 消失 = CC 退出。检查产出文件判断是否成功。

## 模式 B: SDK/Headless（`-p`，短任务用）

### Command Template

```bash
<SSH_CMD> 'cd <WORKDIR> && claude -p \
  --permission-mode dontAsk \
  --model <MODEL> \
  --max-budget-usd <BUDGET> \
  --output-format json \
  "<TASK_PROMPT>"'
```

### Parameters

| Parameter | Default | Notes |
|-----------|---------|-------|
| MODEL | opus | `sonnet` for trivial tasks |
| BUDGET | 2.0 | Max USD per run |
| WORKDIR | (from user) | Remote project directory |

### Output Parsing

JSON output contains: `result`, `total_cost_usd`, `num_turns`, `usage`, `permission_denials`

### 局限性

- **stop-hook 不生效** — CC 做完当前轮就退出，不会被 hook 拦住
- **slash commands 不触发 LLM** — `/xxx:run` 只执行 setup 脚本后退出
- **plugin 的 bash execution 不工作** — `dontAsk` 阻止 plugin commands 的 `!` 执行
- 无法中途注入新指令

## 并行执行

### tmux 并行（推荐）

为每个子任务创建独立 tmux session：

```bash
# 创建多个 sessions
for task in task_a task_b task_c; do
  <SSH_CMD> "tmux new-session -d -s $task 'cd <WORKDIR>/$task && claude ...'"
done

# 等待启动
sleep 15

# 发送 prompts
for task in task_a task_b task_c; do
  <SSH_CMD> "tmux send-keys -t $task '<PROMPT>' Enter"
done
```

### `-p` 并行（短任务）

用 `exec background=true` 并行 dispatch：

```bash
exec background=true: ssh ... "claude -p ... 'Review security'"
exec background=true: ssh ... "claude -p ... 'Review performance'"
exec background=true: ssh ... "claude -p ... 'Review test coverage'"
```

### 硬件设备隔离（NPU/GPU）

每个 CC 绑定不同设备：
```bash
# NPU
tmux new-session -d -s op_a "cd ... && export ASCEND_RT_VISIBLE_DEVICES=0 && claude ..."
tmux new-session -d -s op_b "cd ... && export ASCEND_RT_VISIBLE_DEVICES=1 && claude ..."

# GPU
tmux new-session -d -s op_a "cd ... && export CUDA_VISIBLE_DEVICES=0 && claude ..."
```

## SSH 鲁棒性

```bash
# 重试模板
for i in 1 2 3 4 5; do
  sleep 5
  ssh <SSH_OPTS> <HOST> "<COMMAND>" 2>&1 && break
  echo "retry $i"
done
```

注意部分主机有 SSH 频率限制（如 M5），快速连续连接会被拒。**合并操作到一次 SSH 调用，或 `sleep 3-5` 间隔。**

## CC 能力边界与 OpenClaw 主动协助（ARRIVE 框架）

CC 对非代码文件解析、外部资源获取、隐含依赖判断等环节存在不确定性——有时能完成，有时会失败或遗漏。OpenClaw 在 dispatch CC 前应主动预判可能的失败点并加一层保险，而非等 CC 卡住再响应。

### 预检清单（dispatch 前必查）

1. **CC 需要读哪些文件？** 格式 CC 能可靠处理吗？（docx/PDF/飞书等 → 有概率解析不完整，需预处理兜底）
2. **CC 需要哪些外部资源？** 能可靠获取吗？（下载链接可能丢失、文件可能不存在）
3. **CC 需要哪些工具/权限？** 环境里有吗？（jq、wget、特定 CLI 等）
4. **任务完成标准是什么？** CC 能独立验证吗？

### 预处理 → Prompt 注入

做了预处理但不告诉 CC，等于没做。**必须将预处理结果注入 CC prompt。**

Prompt 中应包含：
- **已下载文件**：文件名、大小、用途（CC 不用再找）
- **已提取信息**：从非代码文档中提取的关键参数、约束、规范（CC 不用解析原始文档）
- **已配置环境**：设备绑定、依赖安装、权限调整（CC 不用再装）
- **注意事项**："不要下载文件"、"不要解析 docx"、"性能未达标不要退出"

**原则**：代替 CC 做了什么，就告诉 CC 不用再做。"不要做X"比"已做X"更有效。

## 工作流

1. **确定目标主机**
2. **选择模式**：长任务 → tmux，短任务 → `-p`
3. **确认范围和预算**
4. **执行**（单任务或并行）
5. **监控**：tmux → `capture-pane`，`-p` → 等 JSON 返回
6. **结果收集和汇报**
7. **清理**：`tmux kill-session` / 检查残留进程

## Cost Awareness

- Default model: opus (~$15/input M, ~$75/output M with caching)
- tmux 模式无法预设 `--max-budget-usd`，需 编排智能体侧监控运行时间
- 并行 N 路 ≈ N× 费用
- 向用户报告实际费用

## 实战踩坑

1. **root + `bypassPermissions` 被拒** — CC 2.1.96+ 不允许。tmux 交互模式不需要指定 `--permission-mode`（CC 遇到确认会暂停，编排智能体可自动确认）；`-p` headless 模式仍需 `dontAsk`
2. **tmux 里加 pipe 导致 CC 退出** — stdin 变非 TTY，CC 以为是 `-p` 模式
3. **settings.json 默认模型** — 远程机器的 `~/.claude/settings.json` model 字段会覆盖命令行，需确认设为 `opus`
4. **`-p` 模式 CC 提前退出** — 没有 stop-hook 兜底，长任务请用 tmux
5. **CC 内置 `.claude/` 目录保护** ⚠️（04-10 发现）— dontAsk 模式下，CC 拒绝 Edit/Write/Bash 任何涉及 `.claude/` 路径的操作。tmux 交互模式下不使用 dontAsk 时，CC 遇到 `.claude/` 编辑会弹出确认提示，编排智能体可自动确认。Triton 开发任务**必须**通过 `/tda:run` 启动（allowed-tools 白名单绕过保护），不能用普通 prompt
6. **CC 选择性不遵守流程规则** — 即使 ITERATIONS.md 在项目根目录（能写），CC 也可能跳过记录步骤。通过 `/tda:run` 启动可强制加载 SKILL.md，stop-hook 的 resume prompt 会持续提醒
