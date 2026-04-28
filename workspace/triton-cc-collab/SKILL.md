---
name: triton-cc-collab
description: "OpenClaw + Claude Code collaborative development for triton-ascend NPU operators. Two-layer agent architecture: 编排智能体 (strategy/orchestration) + CC (execution/exploration). Use when developing or optimizing NPU operators with parallel CC exploration. Triggers: '算子开发', 'CC并行', '并行探索优化', 'triton算子联合开发'."
---

# Triton-CC-Collab — OpenClaw × Claude Code 联合算子开发

## 为什么需要这个技能

`triton-dev` 是单 agent 的完整算子开发流程。但在实际开发中：
- 单 agent 串行探索优化空间太慢（一次编译 30-60s，一轮迭代 3-5 分钟）
- CC（Claude Code）有直接在容器内执行代码的能力，比 OpenClaw SSH 快得多
- 硬件有多个设备（NPU 0-7），天然适合并行

本技能定义 **编排智能体（OpenClaw）和 CC 的分工协议**，以及并行探索的标准化流程。

## 运行模式

**首选 tmux 交互式模式**，每路 CC 一个独立 tmux session。

| 模式 | 适用 | stop-hook | tda plugin |
|------|------|-----------|------------|
| **tmux 交互式** ✅ | 长任务、自治开发 | ✅ 生效 | ✅ 完整 |
| `-p` headless | 短任务、一次性查询 | ❌ 不生效 | ⚠️ 部分失效 |

**经验教训**（04-08 实战）：`-p` 模式下 CC 做几步就退出，tda 的 stop-hook 无法阻止。tmux 交互式模式下 stop-hook 正常生效，CC 会持续工作直到任务完成或被主动取消。

## 目标主机（运行时确定）

本技能**不绑定特定主机**。执行前需确定：

| 参数 | 说明 | 来源 |
|------|------|------|
| `HOST` | 远程主机地址 | 用户指定 或从 TOOLS.md 查 SSH 配置 |
| `SSH_KEY` | SSH 私钥路径 | TOOLS.md 中对应主机的 key |
| `CONTAINER` | Docker 容器名（如有） | TOOLS.md 或用户指定，无容器则留空 |
| `WORKDIR` | 项目工作目录 | 用户指定 或从上下文推断 |
| `DEVICES` | 可用设备列表 | 运行时 `npu-smi info` 检测 |

### 确定主机的流程

1. 用户 prompt 中明确指定了主机 → 直接使用
2. 用户未指定 → 查 TOOLS.md 中的 NPU 开发机列表，询问用户选择
3. 确认后，组装 SSH 命令模板：

**有 Docker 容器**：
```bash
ssh -i <SSH_KEY> -o StrictHostKeyChecking=no <HOST> \
  "docker exec <CONTAINER> bash -c '<COMMAND>'"
```

**无容器（直接在宿主机执行）**：
```bash
ssh -i <SSH_KEY> -o StrictHostKeyChecking=no <HOST> '<COMMAND>'
```

## 核心原则

### 并行探索架构

tmux 交互式模式下，CC 可以使用原生 **Agent Teams**（`Agent` tool）在 session 内 fork 子 agent 并行探索。这比 编排智能体 SSH 中继快得多。

**首选：CC Agent Teams（同设备并行探索）**

```
┌──────────────────────────────────────────────────┐
│  编排智能体 (OpenClaw) — 策略层                         │
│  · 分析瓶颈、确定探索方向                            │
│  · 准备 DEV.md 上下文包                             │
│  · 启动 CC tmux session                            │
│  · 监控进度、向用户汇报                              │
│  · 结果验证、落盘                                   │
└──────────────────────────────────────────────────┘
        │ dispatch (tmux + prompt)     ▲ monitor (tmux capture + files)
        ▼                              │
┌──────────────────────────────────────────────────┐
│  CC (Claude Code) — tmux 交互式                   │
│  · 读 DEV.md + tda skill 获取上下文                 │
│  · 用 Agent tool 自行 fork 子 agent 并行探索         │
│    ├── Agent("explore_a: NPUOptions 方向")         │
│    ├── Agent("explore_b: block_ptr 方向")          │
│    └── Agent("explore_c: micro-opt 方向")          │
│  · 汇总子 agent 结果、选最优方案                     │
│  · 写 RESULTS.txt + 更新 ITERATIONS.md              │
└──────────────────────────────────────────────────┘
```

**优势 vs 编排智能体手动中继：**
- ✅ 子 agents 共享 CC 上下文（不需要重复给踩坑记录）
- ✅ CC 自己做信息中继（子 agent A 的发现可立刻传给 B）
- ✅ 更快（无 SSH 延迟）
- ✅ CC 自行判断收敛时机

**备选：编排智能体 多 session 编排（跨设备隔离）**

当需要**不同 NPU 设备隔离**时（如每路探索需要独立编译和执行），仍然由 编排智能体多个 tmux session：

```
编排智能体 → tmux session explore_a (NPU 0) → CC_A
     → tmux session explore_b (NPU 1) → CC_B
     → tmux session explore_c (NPU 2) → CC_C
```

### 选择规则

| 场景 | 方式 |
|------|------|
| 同一设备上探索不同优化方向 | **CC Agent Teams** ✅ |
| 不同设备上跑不同实验（需隔离） | 编排智能体 多 tmux session |
| 需要跨 session 信息中继 | 编排智能体 |
| CC 自己能判断方向和收敛 | **CC Agent Teams** ✅ |
| 编排智能体需要控制每路的方向和预算 | 编排智能体 |

### 编排智能体 vs CC 分工

| 维度 | 编排智能体 (OpenClaw) | CC (Claude Code) |
|------|-----------------|-------------------|
| 上下文 | 完整历史（memory + 多轮对话） | 当次 session + tda 知识 |
| 硬件状态 | 知道全局 NPU 状态 | 知道自己绑定的设备 |
| 并行探索 | 跨设备编排 | **Agent Teams 同设备并行** |
| 执行速度 | SSH 慢 | 容器内直接跑，快 |
| 编码能力 | 一般 | 很强（Opus） |
| 策略决策 | ✅ 瓶颈分析、方向选择 | 可自行决策（tda 知识充足时） |

## 技能引用关系

本技能**引用但不复制**以下技能的内容。

triton-dev 技能独立维护于 [CAKE-math/triton-dev](https://github.com/CAKE-math/triton-dev)，CC 端通过 [tda 插件](https://github.com/CAKE-math/tda) 获取该技能的完整知识。

| 引用 | 路径 | CC 应读 | 编排智能体应读 |
|------|------|---------|-----------|
| 算子开发完整流程 | `triton-dev/SKILL.md` | ✅ tda 插件自带 | ✅ 策略决策 |
| 平台陷阱 | `triton-dev/guides/triton-ascend-pitfalls.md` | ✅ tda 插件自带 | ✅ 了解 |
| Ascend API | `triton-dev/guides/ascend-api-reference.md` | ✅ tda 插件自带 | 不需要 |
| msprof 分析 | `triton-dev/guides/msprof-op.md` | ✅ tda 插件自带 | ✅ 解读结果 |
| 瓶颈信号→行动 | `triton-dev/references/op-optimizer.md` | ✅ tda 插件自带 | ✅ 选方向 |
| NPUOptions | `triton-dev/guides/npu-options.md` | ✅ tda 插件自带 | 不需要 |

## 完整协作流程

### Phase 1: 基础开发（编排智能体主导或 编排智能体+单CC）

对应 `triton-dev` 的 Step 0-3：

1. **编排智能体写 reference**（或 dispatch 单 CC 写）
2. **编排智能体写初版 triton kernel**（或 dispatch 单 CC）
3. **精度验证 PASS** → 有 baseline

**此阶段遵循 `triton-dev` 完整纪律**（Iron Laws、git commit、ITERATIONS.md），不需要并行。

### Phase 2: 性能分析（编排智能体主导）

对应 `triton-dev` 的 Step 4-6：

1. **Bench**: 获得端到端时间
2. **Profiler**: 拆解 kernel 耗时
3. **msprof**（可选）: 获取瓶颈信号
4. **编排智能体分析瓶颈 → 确定 2-3 个独立优化方向**

**此阶段 编排智能体做分析决策，不 dispatch CC。**

### Phase 3: 并行探索（核心差异化阶段）

#### Explore 轻量纪律

`triton-dev` 定义了完整的 Iron Laws 和 git discipline，但 explore 目录是**临时实验空间**，需要速度优先。纪律分级如下：

| 纪律 | 主目录（triton-dev 完整版） | explore 目录（轻量版） |
|------|--------------------------|---------------------|
| **精度优先** | ✅ Iron Law：不过精度不许看性能 | ✅ **保持**：精度不过的方案直接标 FAIL，不算成功 |
| **单变量原则** | ✅ Iron Law：每次只改一个变量 | ⚠️ **放宽**：每个方案内可组合多个变量（如同时改 BLOCK + layout），但不同方案之间要有明确区分 |
| **迭代记录** | ✅ ITERATIONS.md 完整记录 | ❌ **替代**：RESULTS.txt 一行一条，格式 `方案名 \| PASS/FAIL \| bench_μs \| 备注` |
| **Git commit** | ✅ 每个 milestone 提交 | ❌ **不需要**：explore 不在 repo 内，最优方案收敛后才 commit |
| **Profiler/msprof 落盘** | ✅ profiler/iter_NN_\<tag\>/ | ❌ **不需要**：CC 只跑 bench，收敛后 编排智能体在主目录跑 profiler |
| **REPORT.md** | ✅ 最终报告 | ❌ **不需要** |
| **交叉验证** | — | ✅ **编排智能体在主目录做**：CC 的数字不直接采信 |

**收敛回主目录后，恢复 `triton-dev` 完整纪律。**

#### 3.1 写 DEV.md 文档

**编排智能体必须做，不能跳过。** 这是给 CC 的上下文包，也是 ARRIVE 框架中 Render 环节的产出：

```markdown
# <OP_NAME> — 开发文档

## 算子概述
<公式、输入输出、典型 shape>

## 硬件约束
<UB 大小、设备数、带宽>

## 当前 baseline
<精度状态、profiler 拆解、bench 数字>

## 踩过的坑（关键！）
<每种失败方案：做了什么、怎么失败的、错误信息>

## 优化方向
<方向 A/B/C 的简要描述>
```

> **踩坑记录的重要性**：EHQ 反向开发中，6 种 tl.sum 方案全挂的详细记录使得 explore_b 能直接跳过死路，从最小 kernel 开始系统性测试，最终找到根因。如果不给踩坑记录，CC 会重复踩同样的坑。

#### 3.1b ARRIVE 预处理（dispatch 前必做）

在 dispatch CC 之前，OpenClaw 必须做预检并清除障碍：

1. **Analyze**: CC 需要什么文件/资源/工具？哪些它自己搞不定？
2. **Resolve**: 下载缺失文件、安装依赖、调整权限、解析非代码文档提取信息
3. **Render**: 将预处理结果注入 CC prompt（见下方 prompt 模板）
4. **Inspect**: 验证文件非空、环境就绪、设备空闲

**做了预处理必须告诉 CC**，否则等于没做。在 prompt 中包含预处理报告。

#### 3.2 准备 explore 目录

```bash
ssh <SSH_OPTS> <HOST> "<DOCKER_PREFIX> bash -c '
  cd <WORKDIR>
  mkdir -p explore_a explore_b explore_c
  for d in explore_a explore_b explore_c; do
    cp *.py *.md \$d/
  done
'"
```

> `<SSH_OPTS>` = `-i <SSH_KEY> -o StrictHostKeyChecking=no -o ConnectTimeout=10`
> `<DOCKER_PREFIX>` = `docker exec <CONTAINER>` （无容器时省略）

#### 3.3 检查设备可用性

```bash
ssh <SSH_OPTS> <HOST> "<DOCKER_PREFIX> npu-smi info"
```

**每个 CC 必须分配不同设备。** 同设备并发会互相干扰。

#### 3.4 Dispatch — 方式 A: CC Agent Teams（首选）

只需启动**一个** tmux CC session，通过 `/tda:run` 命令启动：

```bash
# 1. 创建 tmux session
ssh <SSH_OPTS> <HOST> \
  "<DOCKER_PREFIX> tmux new-session -d -s optimize \
    'cd <WORKDIR> && export ASCEND_RT_VISIBLE_DEVICES=<N> && <CC_BIN> --model opus --plugin-dir <TDA_DIR>'"

# 2. 等 CC 启动
sleep 12

# 3. 使用 /tda:run 启动（⚠️ 必须，不要用普通 prompt）
ssh <SSH_OPTS> <HOST> \
  "<DOCKER_PREFIX> tmux send-keys -t optimize '/tda:run 按照算子说明文档[<OP_NAME>_task.docx](./<OP_NAME>_task.docx)进行算子开发并调优 --operator <OP_NAME> --direction fwd' Enter"
```

**⚠️ 为什么必须用 `/tda:run`？**
1. `/tda:run` 通过 `allowed-tools` 白名单授权 CC 访问 `.claude/` 目录下的 tda 状态文件
2. 强制 CC 读取 SKILL.md，加载 Iron Laws（"NO ITERATION WITHOUT A WRITTEN RECORD"）
3. stop-hook 依赖 CC 能更新 `.claude/triton-agent.local.md` 的 iteration 计数器
4. 普通 prompt 启动的 CC 不会加载 tda 工具白名单，导致状态文件无法更新，迭代记录被跳过

**如果 `/tda:run` 无法使用**（如 plugin 未加载），退回到等效 prompt：
```
You are the Triton Dev Agent. Read .claude/triton-agent.local.md and <TDA_DIR>/skills/triton-dev/SKILL.md first.
You MUST update ITERATIONS.md after every iteration — this is Iron Law #3, non-negotiable.
```
由于不再使用 dontAsk，CC 遇到权限确认会暂停等待，编排智能体需通过 `tmux capture-pane` 监控，看到确认提示时用 `tmux send-keys 'Y' Enter` 自动确认。

**Agent Teams Prompt 模板：**

```
Read DEV.md for full context (baseline, bottleneck, failed approaches).

You need to explore 3 optimization directions in parallel using the Agent tool:

1. Agent("Direction A: <description>. Work in explore_a/. Copy files first: cp *.py *.md explore_a/. Run bench with ASCEND_RT_VISIBLE_DEVICES=<N>. Write results to explore_a/RESULTS.txt")
2. Agent("Direction B: <description>. Work in explore_b/. ...")  
3. Agent("Direction C: <description>. Work in explore_c/. ...")

After all agents complete, compare results and pick the best approach.
Write the winner to RESULTS.txt in the main directory.

Constraints:
- Each agent: max 3 attempts, skip on compile errors
- Use existing XX_test.py for accuracy (don't write new tests)
- Accuracy PASS is mandatory before looking at performance
```

**Agent Teams 的优势：**
- CC 自己做信息中继（A 的发现自动对 B 可见）
- 无 SSH 延迟
- CC 自行判断收敛（"A 找到突破，B 不用继续了"）
- 单 prompt 启动，编排智能体只需监控

#### 3.5 Dispatch — 方式 B: 编排智能体 多 tmux session（跨设备隔离）

需要不同 NPU 设备时，每路 CC 独立 tmux session：

**Prompt 模板（每路 CC，含 ARRIVE 预处理报告）：**

```
## 任务：<方向名称>

你在 <WORKDIR>/explore_X/ 目录下工作。

## 必读（先读再开始！）
1. 本目录下 <DEV_DOC>.md — 完整开发文档，包含踩坑记录
2. 使用 triton-dev 技能（已安装），重点读 pitfalls 避坑

## 当前情况
- Baseline: <PERF>μs（profiler kernel 时间），精度 PASS
- 核心瓶颈：<BOTTLENECK>

## 你的优化方向
<具体方向描述，2-3 条>

## 环境准备（OpenClaw 预处理完成）

### 已下载/准备文件
- `./XX_test.py` — 精度验证脚本（已存在，不要自己写新的）
- `./XX_ref.py` — 参考实现
- `./XX_triton.py` — 当前 triton 实现
- （列出其他预处理下载的文件）

### 已配置环境
- NPU <N> 已绑定（ASCEND_RT_VISIBLE_DEVICES=<N>）
- CANN <VERSION>, torch_npu <VERSION>

### ⚠️ 注意事项
- 不要尝试下载任何文件，所需文件已在当前目录
- 不要解析原始任务文档（docx/PDF），关键信息已在上方列出
- 使用已下载的 XX_test.py 做精度验证（不要自己写新 test）
- 遇到编译错误跳过，不要卡死
- 每完成一个方案，追加一行到 RESULTS.txt：`方案名 | PASS/FAIL | bench_μs | 备注`

## 执行环境
source /usr/local/Ascend/ascend-toolkit/latest/bin/setenv.bash
ASCEND_RT_VISIBLE_DEVICES=<N> python3 xxx.py

直接开始实现+测试。
```

#### Prompt 工程规则

| ✅ Do | ❌ Don't |
|-------|---------|
| 给完整踩坑记录 | 只给代码不给背景 |
| 限定方案数量（"最多 3 种"） | 不限制，CC 会发散（实测出现 8 种方案） |
| 指定具体的精度验证脚本 | 只说"验证精度"（CC 会自己写新 test） |
| 明确设备 ID（ASCEND_RT_VISIBLE_DEVICES=N） | 不指定，CC 争抢设备 |
| 说"遇到编译错误跳过，不要卡死" | 不说，CC 死磕一个错误 20 分钟 |
| 让 CC 调用 triton-dev 技能 | 让 CC 自己踩坑 |
| 要求结果写入 RESULTS.txt | 靠 CC 的最终 JSON 输出（可能丢失中间结果） |

#### Dispatch 方式 B — tmux 命令

**tmux 交互式，使用 `/tda:run` 启动（⚠️ 必须）：**

```bash
# 每路 CC 一个 tmux session + 一个 NPU
ssh <SSH_OPTS> <HOST> \
  "<DOCKER_PREFIX> tmux new-session -d -s explore_a \
    'cd <WORKDIR>/explore_a && export ASCEND_RT_VISIBLE_DEVICES=<N> && <CC_BIN> --model opus --plugin-dir <TDA_DIR>'"

sleep 12

# 使用 /tda:run 启动（确保 tda 工具白名单和 SKILL.md 加载）
ssh <SSH_OPTS> <HOST> \
  "<DOCKER_PREFIX> tmux send-keys -t explore_a '/tda:run 按照算子说明文档[<OP_NAME>_task.docx](./<OP_NAME>_task.docx)进行算子开发并调优，优化方向：<DIRECTION_DESC> --operator <OP_NAME> --direction fwd' Enter"
```

**如果 `/tda:run` 无法使用**，退回到等效 prompt（确保 CC 读取 SKILL.md 和状态文件）。由于不再使用 dontAsk，CC 遇到权限确认会暂停，编排智能体需监控 tmux 输出并自动确认。

**不要在 tmux 命令里加 `| tee`**（让 stdin 变非 TTY，CC 会误判为 headless 模式退出）。

### Phase 4: 监控与中继（编排智能体的核心价值）

#### 4.1 进度监控

**tmux 方式（推荐）：**

```bash
# 查看 CC 实时状态
ssh <SSH_OPTS> <HOST> "<DOCKER_PREFIX> tmux capture-pane -t explore_a -p -S -20"

# 列出所有 sessions
ssh <SSH_OPTS> <HOST> "<DOCKER_PREFIX> tmux ls"
```

**文件系统方式（量化进度）：**

```bash
ssh <SSH_OPTS> <HOST> "<DOCKER_PREFIX> bash -c '
  for d in explore_a explore_b explore_c; do
    echo \"=== \$d ===\"
    find <WORKDIR>/\$d/ -name \"*.py\" -newer <WORKDIR>/\$d/utils.py -type f | sort
    cat <WORKDIR>/\$d/RESULTS.txt 2>/dev/null
  done
'"
```

**监控频率**：每 3-5 分钟。编译一个 kernel 约 30-60s，一轮完整测试 2-3 分钟。

#### 4.2 关键中继决策

**这是并行探索中编排智能体最大的价值点。**

当一路 CC 产出突破性发现时：

```
场景：explore_b 发现 tl.sum 在 kernel 内 clamp scale 后可以跑通
      explore_a 还在基于"tl.sum 不可用"的前提探索替代方案

编排智能体的决策：
  选项 1: kill explore_a，用新 insight 重新 dispatch → 省时间
  选项 2: 等 explore_a 自然结束 → 可能有意外收获但浪费资源
  选项 3: 不干预，继续监控 → 最简单但可能错过优化窗口
```

**决策框架**：
- 如果突破性发现**改变了问题前提**（如"tl.sum 不可用"被推翻）→ 选项 1
- 如果只是**找到一个更好的数字** → 选项 3，等全部完成再对比
- 如果剩余 CC **快完成了**（>80% 进度）→ 选项 3

#### 4.3 编排智能体的并行利用

CC 跑探索时，编排智能体不应该干等。可以同时做：
- 写 profiler 分析脚本（不依赖探索结果）
- 准备落盘模板
- 整理文档
- 回复用户其他消息
- 提前规划下一步实验

### Phase 5: 收敛与落盘

#### 5.1 结果收集

CC 完成后，读 RESULTS.txt + JSON result：

```bash
ssh <SSH_OPTS> <HOST> "<DOCKER_PREFIX> bash -c '
  for d in explore_a explore_b explore_c; do
    echo \"=== \$d ===\"
    cat <WORKDIR>/\$d/RESULTS.txt 2>/dev/null || echo \"(no results)\"
  done
'"
```

#### 5.2 交叉验证

**最优方案必须在主目录用标准测试重新验证。** CC 自己报的数字不能直接信。

```bash
# 复制最优方案到主目录
cp explore_b/XX_triton.py ../XX_triton.py

# 用标准测试脚本重新验证
ASCEND_RT_VISIBLE_DEVICES=1 python3 XX_test.py
```

验证点：
- 精度：scalar + per_row 双模式 PASS
- Bench：和 CC 报告的数字一致（±5% 噪声内）
- Profiler：拿到 kernel 级别真实耗时

#### 5.3 落盘（恢复 triton-dev 完整纪律）

从此刻起，回到 `triton-dev` 的完整 Iron Laws、git discipline、artifact inventory。

```bash
# 清理 explore 目录
rm -rf explore_a explore_b explore_c

# 清理 debug 文件
rm -f *_derive.py *_verify*.py *_debug.py

# 清理 triton cache
rm -rf /root/.triton/cache/ __pycache__/
```

#### 5.4 记录（按 triton-dev 规范）

更新主目录 ITERATIONS.md（按 `triton-dev/record-template.md` 格式）：
- 每路 CC 的方向和结果
- 关键发现（尤其是意外发现）
- 中继决策及原因
- 最终性能数字（profiler kernel 时间）

Git commit: `opt(XX): parallel explore — <best_result_summary>`

### Phase 6: 微优化（编排智能体串行或再次并行）

如果 Phase 5 的最优方案还有优化空间（profiler 显示明确瓶颈）：
- 小幅度优化：编排智能体自己做（改一个变量跑一次）
- 多方向探索：回到 Phase 3 再来一轮

**判断标准**：如果连续 3 次微优化都在噪声范围内，停止。

## SSH 鲁棒性

远程 SSH 可能断连，**建议对关键操作使用重试模板**：

```bash
for i in 1 2 3 4 5; do
  sleep 5
  ssh <SSH_OPTS> <HOST> "<COMMAND>" 2>&1 && break
  echo "retry $i"
done
```

**CC 进程被 SIGTERM**：SSH 断连会杀死 CC 进程。处理方式：
1. 检查 explore 目录已有文件和 RESULTS.txt（CC 可能已跑完部分方案）
2. 手动运行 bench 脚本验证已有结果
3. 只对未完成的方案重新 dispatch

## 定时汇报

如果用户要求定时汇报，**用 `sessions_spawn` 启动独立监控子代理**（不要靠"记着"汇报）。监控子代理每 N 分钟自动检查文件变化并发消息。

汇报策略：事件驱动而非固定频率——

```
if CC 都还在跑且无新进展:
    不发消息（避免"还在跑"的无信息汇报）
elif 有 CC 完成且有结果:
    汇总已有结果发送
elif 全部 CC 完成:
    发送最终对比表
```

## 实战案例索引

### EHQ 前向算子 3 路并行优化（2026-02-26 下午）
- **背景**：v7 kernel 1716μs 已是 baseline，探索进一步优化空间
- **3 路**：NPUOptions / block_ptr+stages / micro-opt
- **结论**：全在噪声范围内，确认 GM→UB 带宽是不可突破的瓶颈
- **经验**：并行探索也有价值——快速确认"没有优化空间"比串行试 3 天好

### EHQ 反向算子 3 路并行突破（2026-02-26 晚上）
- **背景**：tl.sum UB 对齐灾难，6 种手动方案全挂，baseline 4492μs
- **3 路**：融合+替代归约 / tl.sum 边界测试 / 融合+host优化
- **突破**：explore_b 发现 tl.sum 本身没问题，是预处理数组占 UB → kernel 内 clamp 绕过
- **结果**：2401μs（1.87x 加速），单 kernel 融合
- **经验**：CC 从零系统性测试发现了人手动调试 6 次都没找到的根因

## 反模式（避免）

### ❌ CC 全权负责、编排智能体不参与
CC 没有跨 session 上下文，无法做策略决策。编排智能体不介入 = 3 路 CC 可能探索重叠方向。

### ❌ 编排智能体全干、CC 只当编译器
浪费 CC 的编码能力。编排智能体 SSH 执行慢，不适合高频试错。

### ❌ 不给踩坑文档就 dispatch
CC 会重复踩同样的坑，浪费时间和 token。

### ❌ CC 自己写 test 脚本
CC 的 test 脚本精度标准可能和项目标准不一致。必须复用已有的。

### ❌ 干等 CC 完成
编排智能体在 CC 跑的时候应该做并行工作（文档、脚本准备、其他任务）。

### ❌ 不做交叉验证就落盘
CC 报告的数字可能是自己新 test 脚本的结果，标准和 bench 参数可能不一致。

### ❌ 用固定频率 cron 汇报无信息内容
"还在跑"不是有效汇报。有新进展时汇报，无进展时沉默。

### ❌ 用 `-p` headless 模式跑长任务
stop-hook 不生效，CC 做几步就退出。长任务（>5 分钟）必须用 tmux 交互式。

### ❌ tmux 里加 pipe（tee/log redirect）
让 stdin 变非 TTY，CC 误判为 headless 模式立即退出。tmux 直接运行 CC，不加 pipe。

### ❌ 靠"记着"定时汇报
心跳/其他消息会打断。必须 spawn 独立监控子代理做定时检查。

### ❌ 用普通 prompt 启动 triton 开发 CC（04-10 血的教训）
直接 `tmux send-keys` 发普通文本 prompt 导致：
1. CC 不加载 SKILL.md → 不知道 Iron Laws → 不记录迭代
2. CC 没有 tda `allowed-tools` 白名单 → 无法更新 `.claude/triton-agent.local.md` → stop-hook iteration 计数器失效
3. CC 行为脱离 tda 管控，变成自由发挥
**必须用 `/tda:run` 命令启动**（通过 allowed-tools 绕过 `.claude/` 保护，强制加载 SKILL.md）。
