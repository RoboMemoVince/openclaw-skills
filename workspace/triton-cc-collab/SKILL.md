---
name: triton-cc-collab
description: "OpenClaw + Claude Code collaborative development for triton-ascend NPU operators. Two-layer agent architecture: Musk (strategy/orchestration) + CC (execution/exploration). Use when developing or optimizing NPU operators with parallel CC exploration. Triggers: '算子开发', 'CC并行', '并行探索优化', 'triton算子联合开发'."
platform: [openclaw]
---

# Triton-CC-Collab — OpenClaw × Claude Code 联合算子开发

## 为什么需要这个技能

`triton-dev` 是单 agent 的完整算子开发流程。但在实际开发中：
- 单 agent 串行探索优化空间太慢（一次编译 30-60s，一轮迭代 3-5 分钟）
- CC（Claude Code）有直接在容器内执行代码的能力，比 OpenClaw SSH 快得多
- 硬件有多个设备（NPU 0-7），天然适合并行

本技能定义 **Musk（OpenClaw）和 CC 的分工协议**，以及并行探索的标准化流程。

## 核心原则

### 两层 Agent 分工

```
┌──────────────────────────────────────────────────┐
│  Musk (OpenClaw) — 策略层                         │
│  · 读 SKILL.md 做整体决策                          │
│  · 决定探索方向和资源分配                            │
│  · 跨 CC 信息中继（关键！CC 之间不能直接通信）         │
│  · 结果验证、落盘、向用户汇报                         │
│  · CC 空闲时做不依赖探索结果的并行工作                 │
└──────────────────────────────────────────────────┘
        │ dispatch (SSH + claude -p)
        │ monitor (file changes)
        │ relay (kill + re-dispatch with new insight)
        ▼
┌──────────────────────────────────────────────────┐
│  CC (Claude Code) — 执行层                        │
│  · 读 pitfalls.md / api-reference.md 避坑          │
│  · 写代码、编译、测试、报告结果                       │
│  · 使用项目现有的标准测试脚本（不自行创造新的）          │
│  · 结果写入 RESULTS.txt（标准格式）                  │
└──────────────────────────────────────────────────┘
```

### 为什么不是对称分工

| 维度 | Musk (OpenClaw) | CC (Claude Code) |
|------|-----------------|-------------------|
| 上下文 | 完整历史（memory + 多轮对话） | 只有当次 prompt |
| 硬件状态 | 知道哪个 NPU 空闲、之前跑过什么 | 不知道 |
| 跨 session 信息 | 知道其他 CC 的发现 | 只知道自己目录 |
| 执行速度 | SSH 慢，一次一个命令 | 容器内直接跑，快 |
| 编码能力 | 一般 | 很强（Opus 级别） |

**所以**：Musk 做决策和协调，CC 做编码和执行。

## 技能引用关系

本技能**引用但不复制**以下技能的内容：

| 引用 | 路径 | CC 应读 | Musk 应读 |
|------|------|---------|-----------|
| 算子开发完整流程 | `triton-dev/SKILL.md` | 按需 | ✅ 策略决策 |
| 平台陷阱 | `triton-dev/guides/triton-ascend-pitfalls.md` | ✅ 必读 | ✅ 了解 |
| Ascend API | `triton-dev/guides/ascend-api-reference.md` | ✅ 按需 | 不需要 |
| msprof 分析 | `triton-dev/guides/msprof-op.md` | ✅ 按需 | ✅ 解读结果 |
| 瓶颈信号→行动 | `triton-dev/references/op-optimizer.md` | ✅ 按需 | ✅ 选方向 |
| NPUOptions | `triton-dev/guides/npu-options.md` | ✅ 按需 | 不需要 |
| CC 远程执行 | `claude-code-remote/SKILL.md` | 不需要 | ✅ 调度用 |

**Musk 和 CC 都已安装 `triton-dev` 技能**，在 prompt 中用关键词触发或直接指定技能名即可。

## 完整协作流程

### Phase 1: 基础开发（Musk 主导或 Musk+单CC）

对应 `triton-dev` 的 Step 0-3：

1. **Musk 写 reference**（或 dispatch 单 CC 写）
2. **Musk 写初版 triton kernel**（或 dispatch 单 CC）
3. **精度验证 PASS** → 有 baseline

**此阶段遵循 `triton-dev` 完整纪律**（Iron Laws、git commit、ITERATIONS.md），不需要并行。

### Phase 2: 性能分析（Musk 主导）

对应 `triton-dev` 的 Step 4-6：

1. **Bench**: 获得端到端时间
2. **Profiler**: 拆解 kernel 耗时
3. **msprof**（可选）: 获取瓶颈信号
4. **Musk 分析瓶颈 → 确定 2-3 个独立优化方向**

**此阶段 Musk 做分析决策，不 dispatch CC。**

### Phase 3: 并行探索（核心差异化阶段）

#### Explore 轻量纪律

`triton-dev` 定义了完整的 Iron Laws 和 git discipline，但 explore 目录是**临时实验空间**，需要速度优先。纪律分级如下：

| 纪律 | 主目录（triton-dev 完整版） | explore 目录（轻量版） |
|------|--------------------------|---------------------|
| **精度优先** | ✅ Iron Law：不过精度不许看性能 | ✅ **保持**：精度不过的方案直接标 FAIL，不算成功 |
| **单变量原则** | ✅ Iron Law：每次只改一个变量 | ⚠️ **放宽**：每个方案内可组合多个变量（如同时改 BLOCK + layout），但不同方案之间要有明确区分 |
| **迭代记录** | ✅ ITERATIONS.md 完整记录 | ❌ **替代**：RESULTS.txt 一行一条，格式 `方案名 \| PASS/FAIL \| bench_μs \| 备注` |
| **Git commit** | ✅ 每个 milestone 提交 | ❌ **不需要**：explore 不在 repo 内，最优方案收敛后才 commit |
| **Profiler/msprof 落盘** | ✅ profiler/iter_NN_\<tag\>/ | ❌ **不需要**：CC 只跑 bench，收敛后 Musk 在主目录跑 profiler |
| **REPORT.md** | ✅ 最终报告 | ❌ **不需要** |
| **交叉验证** | — | ✅ **Musk 在主目录做**：CC 的数字不直接采信 |

**收敛回主目录后，恢复 `triton-dev` 完整纪律。**

#### 3.1 写 DEV.md 文档

**Musk 必须做，不能跳过。** 这是给 CC 的上下文包：

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

#### 3.2 准备 explore 目录

```bash
ssh ... "docker exec <CONTAINER> bash -c '
  cd <PROJECT_DIR>
  mkdir -p explore_a explore_b explore_c
  for d in explore_a explore_b explore_c; do
    cp *.py *.md \$d/
  done
'"
```

#### 3.3 检查设备可用性

```bash
ssh ... "docker exec <CONTAINER> npu-smi info"
```

**每个 CC 必须分配不同设备。** 同设备并发会互相干扰。

#### 3.4 Dispatch CC — Prompt 模板

```
## 任务：<方向名称>

你在 <PROJECT_DIR>/explore_X/ 目录下工作。

## 必读（先读再开始！）
1. 本目录下 <DEV_DOC>.md — 完整开发文档，包含踩坑记录
2. 使用 triton-dev 技能（已安装），重点读 pitfalls 避坑

## 当前情况
- Baseline: <PERF>μs（profiler kernel 时间），精度 PASS
- 核心瓶颈：<BOTTLENECK>

## 你的优化方向
<具体方向描述，2-3 条>

## 约束
- 最多尝试 3 种方案，遇到编译/对齐错误跳过，不要卡死
- 使用本目录下已有的 XX_test.py 做精度验证（不要自己写新的 test 脚本）
- 每完成一个方案，追加一行到 RESULTS.txt：
  `方案名 | PASS/FAIL | bench_μs | 备注`

## 执行环境
source /usr/local/Ascend/ascend-toolkit/latest/bin/setenv.bash
export PATH=/data0/hcq/Ascend/ascend-toolkit/8.3.RC2/bisheng_toolkit/bishengir/bin:$PATH
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

#### 3.5 SSH Command

```bash
ssh -i ~/.ssh/KeyPair-d9c2.pem -o StrictHostKeyChecking=no root@1.95.7.166 \
  "docker exec triton-ascend-hcq bash -c 'cd <DIR>/explore_X && claude -p \
    --permission-mode dontAsk \
    --model opus \
    --output-format json \
    \"<PROMPT>\"'"
```

**使用 `exec` with `background=true`** 并行 dispatch 多个。

### Phase 4: 监控与中继（Musk 的核心价值）

#### 4.1 进度监控

**不要 poll CC 进程**（无中间输出）。通过文件变化监控：

```bash
# 检查新文件
ssh ... "docker exec <CONTAINER> bash -c '
  for d in explore_a explore_b explore_c; do
    echo \"=== \$d ===\"
    find <DIR>/\$d/ -name \"*.py\" -newer <DIR>/\$d/utils.py -type f | sort
    cat <DIR>/\$d/RESULTS.txt 2>/dev/null
  done
'"
```

**监控频率**：每 3-5 分钟。编译一个 kernel 约 30-60s，一轮完整测试 2-3 分钟。

#### 4.2 关键中继决策

**这是并行探索中 Musk 最大的价值点。**

当一路 CC 产出突破性发现时：

```
场景：explore_b 发现 tl.sum 在 kernel 内 clamp scale 后可以跑通
      explore_a 还在基于"tl.sum 不可用"的前提探索替代方案

Musk 的决策：
  选项 1: kill explore_a，用新 insight 重新 dispatch → 省时间
  选项 2: 等 explore_a 自然结束 → 可能有意外收获但浪费资源
  选项 3: 不干预，继续监控 → 最简单但可能错过优化窗口
```

**决策框架**：
- 如果突破性发现**改变了问题前提**（如"tl.sum 不可用"被推翻）→ 选项 1
- 如果只是**找到一个更好的数字** → 选项 3，等全部完成再对比
- 如果剩余 CC **快完成了**（>80% 进度）→ 选项 3

#### 4.3 Musk 的并行利用

CC 跑探索时，Musk 不应该干等。可以同时做：
- 写 profiler 分析脚本（不依赖探索结果）
- 准备落盘模板
- 整理文档
- 回复用户其他消息
- 提前规划下一步实验

### Phase 5: 收敛与落盘

#### 5.1 结果收集

CC 完成后，读 RESULTS.txt + JSON result：

```bash
ssh ... "docker exec <CONTAINER> bash -c '
  for d in explore_a explore_b explore_c; do
    echo \"=== \$d ===\"
    cat <DIR>/\$d/RESULTS.txt 2>/dev/null || echo \"(no results)\"
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

### Phase 6: 微优化（Musk 串行或再次并行）

如果 Phase 5 的最优方案还有优化空间（profiler 显示明确瓶颈）：
- 小幅度优化：Musk 自己做（改一个变量跑一次）
- 多方向探索：回到 Phase 3 再来一轮

**判断标准**：如果连续 3 次微优化都在噪声范围内，停止。

## SSH 鲁棒性

Alice SSH 频繁断连（kex_exchange_identification 错误），**所有操作必须用重试模板**：

```bash
for i in 1 2 3 4 5; do
  sleep 5
  scp -i ~/.ssh/KeyPair-d9c2.pem -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
    <LOCAL_FILE> root@1.95.7.166:/tmp/ 2>/dev/null && \
  ssh -i ~/.ssh/KeyPair-d9c2.pem -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
    root@1.95.7.166 "<COMMANDS>" 2>&1 && break
  echo "retry $i"
done
```

**CC 进程被 SIGTERM**：SSH 断连会杀死 CC 进程。处理方式：
1. 检查 explore 目录已有文件和 RESULTS.txt（CC 可能已跑完部分方案）
2. 手动运行 bench 脚本验证已有结果
3. 只对未完成的方案重新 dispatch

## 定时汇报

如果用户要求定时汇报，用 cron 设置提醒。但需要**事件驱动的判断**：

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

### ❌ CC 全权负责、Musk 不参与
CC 没有跨 session 上下文，无法做策略决策。Musk 不介入 = 3 路 CC 可能探索重叠方向。

### ❌ Musk 全干、CC 只当编译器
浪费 CC 的编码能力。Musk SSH 执行慢，不适合高频试错。

### ❌ 不给踩坑文档就 dispatch
CC 会重复踩同样的坑，浪费时间和 token。

### ❌ CC 自己写 test 脚本
CC 的 test 脚本精度标准可能和项目标准不一致。必须复用已有的。

### ❌ 干等 CC 完成
Musk 在 CC 跑的时候应该做并行工作（文档、脚本准备、其他任务）。

### ❌ 不做交叉验证就落盘
CC 报告的数字可能是自己新 test 脚本的结果，标准和 bench 参数可能不一致。

### ❌ 用固定频率 cron 汇报无信息内容
"还在跑"不是有效汇报。有新进展时汇报，无进展时沉默。
