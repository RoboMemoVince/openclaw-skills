# File Conventions, Artifact Inventory, and Git Discipline

## Complete Artifact Inventory (Required)

A completed operator MUST produce all of the following. Missing any one means the operator is NOT done.

```
<operator_name>/
│
│  ── Core Scripts (6 files for fwd+bwd, 3 for fwd-only) ──
├── XX_fwd_triton.py          # Forward kernel and wrapper ONLY
├── XX_fwd_ref.py             # Forward PyTorch reference ONLY
├── XX_fwd_test.py            # Forward test (accuracy + bench + profiler)
├── XX_bwd_triton.py          # Backward kernel and wrapper (if needed)
├── XX_bwd_ref.py             # Backward PyTorch reference (if needed)
├── XX_bwd_test.py            # Backward test (if needed)
├── utils.py                  # Common utilities (copy from skill/tools/utils.py)
│
│  ── Documentation (3 files) ──
├── README.md                 # Operator description: what it computes, I/O spec, formula
├── REPORT.md                 # Final test report: accuracy + bench + profiler summary (English)
├── REPORT_CN.md              # 中文测试报告：与 REPORT.md 内容一致，面向中文读者
│
│  ── Iteration Records (1 file) ──
├── ITERATIONS.md             # All trial-and-error records (template in record-template.md)
│
│  ── Profiler Artifacts (directories) ──
├── profiler/                 # Profiler outputs (kernel_details.csv etc.)
│   ├── iter_01_baseline/
│   ├── iter_02_<change_tag>/
│   └── ...
├── msprof/                   # msprof outputs (op-level metrics)
│   ├── iter_01_baseline/
│   ├── iter_02_<change_tag>/
│   └── ...
│
│  ── Integration Packaging (Step 9) ──
├── XX_op.py                 # Integration wrapper (callable function or autograd.Function)
├── test_XX_op.py            # Wrapper consistency tests
├── test_e2e.py              # End-to-end validation (multi-step / training loop)
└── SUMMARY.md               # Integration summary (interface, deployment, performance)
```

### Artifact Descriptions

| Artifact | When to Create | Content |
|----------|---------------|---------|
| `XX_fwd_triton.py` | Step 2 | `@triton.jit` kernel + wrapper. NO test, NO reference, NO main. |
| `XX_fwd_ref.py` | Step 1 | PyTorch reference. Line-by-line match to docs. NO triton. |
| `XX_fwd_test.py` | Step 1-2 | CLI test script with `--no-test/--no-bench/--no-profile/--mode`. |
| `utils.py` | Step 1 | Copy from `skill/tools/utils.py`. |
| `README.md` | Step 0 | Operator doc: formula, I/O tensor specs, dtype convention, shape constraints. |
| `REPORT.md` | Completion | Final report: accuracy table + bench table + profiler kernel table + summary. |
| `REPORT_CN.md` | Completion | 中文版测试报告，与 REPORT.md 数据一致，使用中文描述。 |
| `ITERATIONS.md` | Step 4 onwards | Every tuning iteration. Use template from [record-template.md](./record-template.md). |
| `profiler/iter_XX_<tag>/` | Step 5 each iter | Raw profiler CSV outputs. Keep for comparison. |
| `msprof/iter_XX_<tag>/` | Step 6 each iter | Raw msprof outputs. Keep for bottleneck analysis. |
| `XX_op.py` | Step 9 | Integration wrapper: standard + optimized interfaces, preparation helpers. |
| `test_XX_op.py` | Step 9 | Tests: wrapper output matches kernel directly, standard matches optimized. |
| `test_e2e.py` | Step 9 | E2E validation: multi-step accumulation (inference) or training loop (training). |
| `SUMMARY.md` | Step 9 | Integration summary: interface docs, deployment requirements, verified performance data. |

### Files NOT to Commit

- `__pycache__/`, `*.pyc`
- Temporary msprof scripts (`/tmp/msprof_*.py`)
- `.npu_cache/` (Triton compilation cache)

## Script Naming Convention

| Component | Pattern | Example |
|-----------|---------|---------|
| Operator name | `XX` (snake_case) | `hc_pre_only`, `mhc_post`, `sinkhorn` |
| Forward kernel | `XX_fwd_triton.py` | `hc_pre_only_fwd_triton.py` |
| Backward kernel | `XX_bwd_triton.py` | `hc_pre_only_bwd_triton.py` |
| Forward reference | `XX_fwd_ref.py` | `hc_pre_only_fwd_ref.py` |
| Backward reference | `XX_bwd_ref.py` | `hc_pre_only_bwd_ref.py` |
| Forward test | `XX_fwd_test.py` | `hc_pre_only_fwd_test.py` |
| Backward test | `XX_bwd_test.py` | `hc_pre_only_bwd_test.py` |

### Kernel Function Naming

| Component | Pattern | Example |
|-----------|---------|---------|
| Triton kernel | `XX_fwd_kernel` / `XX_bwd_kernel` | `hc_pre_only_fwd_kernel` |
| Wrapper function | `XX_fwd_triton` / `XX_bwd_triton` | `hc_pre_only_fwd_triton` |
| Reference function | `XX_fwd_reference` / `XX_bwd_reference` | `hc_pre_only_fwd_reference` |

Multi-kernel operators: append descriptive suffix: `XX_fwd_kernel_matmul`, `XX_fwd_kernel_norm`.

### Profiler/msprof Directory Naming

Pattern: `iter_<NN>_<change_tag>`

| Example | Meaning |
|---------|---------|
| `iter_01_baseline` | Initial baseline measurement |
| `iter_02_block_m128` | Changed BLOCK_M to 128 |
| `iter_03_fuse_norm` | Fused normalization into kernel |
| `iter_04_rollback_to_02` | Rolled back to iter_02 config |

## Git Discipline

### When to Commit

| Event | Commit? | Message Format |
|-------|---------|---------------|
| Step 1: reference written + accuracy verified | ✅ | `feat(XX): add reference implementation` |
| Step 2: triton kernel runnable | ✅ | `feat(XX): add triton kernel (initial)` |
| Step 3: first accuracy PASS (all shapes) | ✅ | `feat(XX): accuracy pass on all shapes` |
| Step 4-5: baseline bench + profiler collected | ✅ | `bench(XX): baseline profiler collected` |
| Step 7: iteration accuracy PASS | ✅ | `opt(XX): iter_NN <change_tag> — <result summary>` |
| Step 7: iteration FAIL (rollback) | ✅ | `rollback(XX): iter_NN <change_tag> — <reason>` |
| REPORT.md written | ✅ | `docs(XX): add final report` |
| WIP / untested changes | ❌ | Do NOT commit broken or unverified code |

### Commit Message Format

```
<type>(XX): <concise description>

<optional body: key metrics or decisions>
```

Types: `feat`, `opt`, `bench`, `rollback`, `fix`, `docs`, `refactor`

Examples:
```
feat(ehq): add forward reference implementation
feat(ehq): add triton kernel (initial, BLOCK_M=64 BLOCK_N=64)
feat(ehq): accuracy pass on all shapes (3/3 PASS, max relerr 1.25e-4)
bench(ehq): baseline profiler — fwd kernel 204us, total 259us
opt(ehq): iter_02 block_m128 — fwd kernel 178us (-12.7%)
rollback(ehq): iter_03 fuse_norm — UB overflow at BLOCK_D=2560
docs(ehq): add final report
```

### Rollback Strategy

- **Config rollback** (most common): revert BLOCK/layout params in code, commit as `rollback(XX)`.
- **Code rollback** (structural change failed): `git checkout <last_good_commit> -- <file>`, then commit.
- **Never** use `git revert` on shared branches — it creates confusing merge history.
- **Always** record the failed attempt in ITERATIONS.md **before** rolling back the code.

### Branch Convention

- Feature branch per operator: `op/XX` (e.g., `op/ehq`, `op/sinkhorn`)
- Merge to main only when REPORT.md is complete and all accuracy checks pass
- For quick experiments, stay on feature branch; don't pollute main with WIP

## Code Templates

### XX_fwd_triton.py / XX_bwd_triton.py — Kernel Implementation

**Contains ONLY:**
- Triton kernel definition(s) with `@triton.jit` decorator
- Kernel wrapper function(s) that handle tensor preparation and kernel launch
- NO test code, NO reference implementation, NO main block

```python
import triton
import triton.language as tl
import torch

@triton.jit
def XX_fwd_kernel(
    input_ptr, output_ptr,
    M, N, K,
    BLOCK_M: tl.constexpr, BLOCK_N: tl.constexpr,
):
    # Kernel implementation
    ...

def XX_fwd_triton(input_tensor, ...):
    """Wrapper function that launches the kernel."""
    output = torch.empty_like(input_tensor)
    grid = (triton.cdiv(M, BLOCK_M), triton.cdiv(N, BLOCK_N))
    XX_fwd_kernel[grid](input_tensor, output, M, N, K, BLOCK_M=64, BLOCK_N=64)
    return output
```

### XX_fwd_ref.py / XX_bwd_ref.py — Reference Implementation

**Contains ONLY:**
- PyTorch reference implementation as accuracy gold standard
- Must match operator documentation line-by-line
- NO triton code, NO test code

```python
import torch

def XX_fwd_reference(input_tensor, ...):
    """
    PyTorch reference implementation.
    Implements the operator exactly as documented.
    """
    x = input_tensor.float()
    # ... computation steps matching documentation
    return output.to(torch.bfloat16)
```

### XX_fwd_test.py / XX_bwd_test.py — Test Script

**Contains:**
- Imports from XX_triton.py, XX_ref.py, and utils.py
- CLI argument parsing for shapes, modes, and tuning parameters
- Accuracy test, benchmark, and profiler collection logic
- Main entry point

**Required CLI arguments:**
- `--B, --S, --N, --D` (or relevant shape parameters)
- `--no-test`: Skip accuracy test
- `--no-bench`: Skip benchmark
- `--no-profile`: Skip profiler collection
- `--mode {run|msprof}`: Execution mode
- Tuning parameters: `--BLOCK_M, --BLOCK_N, --BLOCK_K`, etc.

```python
import argparse
import torch
from XX_fwd_triton import XX_fwd_triton
from XX_fwd_ref import XX_fwd_reference
from utils import (
    bench, profiler_wrapper, assert_close_bf16,
    set_seed, print_profiler_kernel_avg_duration
)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--B", type=int, default=1)
    parser.add_argument("--S", type=int, default=1024)
    parser.add_argument("--no-test", action="store_true")
    parser.add_argument("--no-bench", action="store_true")
    parser.add_argument("--no-profile", action="store_true")
    parser.add_argument("--mode", choices=["run", "msprof"], default="run")
    args = parser.parse_args()

    set_seed(42)
    device = "npu:0"
    x = torch.randn(args.B, args.S, args.N, args.D, device=device, dtype=torch.bfloat16)

    if not args.no_test:
        golden = XX_fwd_reference(x, ...)
        result = XX_fwd_triton(x, ...)
        assert_close_bf16(result, golden, "XX_fwd")

    if not args.no_bench:
        out, time_us, mem_mb = bench(lambda: XX_fwd_triton(x, ...))
        print(f"Time: {time_us:.2f} us, Memory: {mem_mb:.2f} MB")

    if not args.no_profile:
        profiler_wrapper(lambda: XX_fwd_triton(x, ...))
        print_profiler_kernel_avg_duration()

if __name__ == "__main__":
    main()
```

### utils.py — Common Utilities

Copy from `tools/utils.py`. Contains:
- `profiler_wrapper()`: NPU profiler collection
- `print_profiler_kernel_avg_duration()`: Parse kernel_details.csv
- `msprof_op_collect()`: msprof op collection
- `bench()`: Benchmark with timing and memory tracking
- `assert_close()`, `assert_close_bf16()`: Accuracy assertions
- `rel_err()`, `cosine_sim()`: Error metrics
- `set_seed()`: Reproducibility

### README.md — Operator Documentation

```markdown
# <Operator Name>

## Description
<What this operator computes, 1-2 sentences>

## Formula
<Mathematical formula or pseudocode>

## I/O Specification

| Tensor | Shape | Dtype | Notes |
|--------|-------|-------|-------|
| input | (B, S, N, D) | bfloat16 | Contiguous |
| output | (B, S, N, D) | bfloat16 | |

## Shape Constraints
<Any alignment, power-of-2, or minimum size requirements>

## Numerical Convention
<FP32 accumulation? Where to cast? eps placement?>
```

### REPORT.md — Final Test Report

```markdown
# <Operator Name> Test Report

**Date:** YYYY-MM-DD
**Hardware:** <device info>
**Operator:** <operator name and direction>

## Accuracy

| Shape | Result | Max RelErr |
|-------|--------|------------|
| ... | ✅ PASS | ... |

## Benchmark

| Shape | Ref (μs) | Triton (μs) | Speedup | Mem Ref (MB) | Mem Triton (MB) |
|-------|----------|-------------|---------|-------------|-----------------|
| ... | ... | ... | ... | ... | ... |

## Profiler Kernel Duration

| Shape | Kernel | Avg (μs) | Count/Step | Subtotal/Step (μs) |
|-------|--------|----------|------------|---------------------|
| ... | ... | ... | ... | ... |
| ... | **End-to-End/Step** | | **N** | **XXX** |

> Note: Wrapper operations (transpose, copy) may fire multiple times per step.
> End-to-End = sum(Avg × Count/Step), NOT sum of unique kernel averages.

## Wrapper Ops Classification

| Wrapper Operation | Profiler Kernel | Classification | Rationale |
|-------------------|----------------|----------------|-----------|
| `weight.t().contiguous()` | TransposeAiCore | Production-eliminable | Static weight, transpose once at model load |
| `input.contiguous()` | TensorMoveAiCore | Production-eliminable | Upstream output already contiguous |
| `conv_state.permute().contiguous()` | TransposeAiCore | Inherent / Negotiable | Depends on upstream layout convention |
| ... | ... | ... | ... |

> Classification guide:
> - **Production-eliminable**: Can be removed in deployment (e.g. static weights, upstream guarantees)
> - **Inherent overhead**: Cannot be avoided without upstream API changes
> - **Negotiable**: Could be eliminated if upstream accepts alternative layout

## Summary
<Key findings, speedup, memory savings, known limitations>
```

### REPORT_CN.md — 中文测试报告

与 REPORT.md 数据完全一致，使用中文撰写，面向中文读者。在算子开发完成时与 REPORT.md 同时生成。

```markdown
# <算子名称> 测试报告

**日期:** YYYY-MM-DD
**硬件:** <设备信息>
**算子:** <算子名称及方向>

## 精度验证

| Shape | 结果 | 最大相对误差 |
|-------|------|-------------|
| ... | PASS | ... |

## 性能基准（含 Python 开销）

| Shape | 参考实现 (μs) | Triton (μs) | 加速比 | 参考显存 (MB) | Triton 显存 (MB) |
|-------|-------------|-------------|--------|-------------|-----------------|
| ... | ... | ... | ... | ... | ... |

## Profiler 算子耗时

| Shape | 算子 | 平均耗时 (μs) | 次数/Step | 小计/Step (μs) |
|-------|------|-------------|-----------|----------------|
| ... | ... | ... | ... | ... |
| ... | **端到端/Step** | | **N** | **XXX** |

> 注意：Wrapper 操作（transpose、copy 等）可能每 Step 触发多次。
> 端到端 = sum(平均耗时 × 次数/Step)，而非各算子平均值简单相加。

## 与原始实现对比（如适用）

| 组件 | 原始耗时 (μs) | 融合后 (μs) | 节省 |
|------|-------------|------------|------|
| ... | ... | ... | ... |

## Wrapper 操作分类

| Wrapper 操作 | Profiler 算子 | 分类 | 说明 |
|-------------|--------------|------|------|
| `weight.t().contiguous()` | TransposeAiCore | 生产可消除 | 静态权重，模型加载时一次性转置 |
| `input.contiguous()` | TensorMoveAiCore | 生产可消除 | 上游输出已是 contiguous |
| `conv_state.permute().contiguous()` | TransposeAiCore | 固有/可协商 | 取决于上游 layout 约定 |
| ... | ... | ... | ... |

> 分类说明：
> - **生产可消除**：部署时可移除（如静态权重、上游保证 contiguous）
> - **固有开销**：无法避免，除非上游修改 API
> - **可协商**：如果上游接受替代 layout 则可消除

## 总结
<核心发现、加速效果、显存节省、已知限制、后续优化方向>
```
