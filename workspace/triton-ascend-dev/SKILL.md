---
name: triton-ascend-dev
description: End-to-end development and optimization workflow for triton-ascend operators (reference -> implementation -> accuracy -> bench -> profiler -> msprof -> rollback logging). Also covers Triton vs Torch baseline performance comparison and benchmark report generation. Invoke when user wants to "write/generate/optimize NPU operators", "benchmark/profile NPU kernels", "compare Triton vs Torch performance", or "generate operator performance reports".
platform: [openclaw, claude-code]
---

## What This Skill Solves

- Integrates "writing triton-ascend operators" and "performance tuning with profiler/msprof" into a single reusable workflow.
- Establishes unified conventions for artifacts and directories, supporting trial-and-error, rollback, comparison, and retrospective analysis.

## Prerequisites (Mandatory Constraints)
- Before carrying out this task, you must first enter Planning Mode.
- All execution/debugging must be done inside the `triton-ascend-hcq` container. First check if already in container (`ls /.dockerenv`). If already inside, no action needed; if not, enter the container before running scripts or other test commands.
- **Environment Configuration (Required for msprof)**: Must explicitly set `ASCEND_TOOLKIT_HOME` and add driver library path (`/usr/local/Ascend/driver/lib64/driver`) to `LD_LIBRARY_PATH`, otherwise `msprof` cannot detect devices.
- Correctness before performance: Any optimization attempt must pass accuracy checks first.
- Change only one main variable per iteration: Do not mix changes to meta parameters, layout, fusion strategy, etc.
- Fixed shape set: The same operator across iterations must use the same set of shapes for valid comparison.

## Environment and Execution Template (Inside Container)

```bash
docker exec -itu root triton-ascend-hcq /bin/bash -lc '
  source /usr/local/Ascend/ascend-toolkit/latest/bin/setenv.bash &&
  export PATH=/data0/hcq/Ascend/ascend-toolkit/8.3.RC2/bisheng_toolkit/bishengir/bin:$PATH &&
  cd <YOUR_WORKDIR> &&
  python3 <YOUR_ENTRY>.py --B 1 --S 2048 --N 4 --D 2560
'
```

## Recommended Engineering Conventions

### File Structure (Required)

Each operator should produce the following 4 files:

```
<operator_name>/
├── XX_fwd_triton.py      # Forward kernel and wrapper function ONLY
├── XX_fwd_ref.py         # Forward PyTorch reference implementation ONLY
├── XX_fwd_test.py        # Forward test script (accuracy + benchmark + profiler)
├── XX_bwd_triton.py      # Backward kernel and wrapper (if needed)
├── XX_bwd_ref.py         # Backward PyTorch reference (if needed)
├── XX_bwd_test.py        # Backward test script (if needed)
└── utils.py              # Common utilities (copy from skill/tools/utils.py)
```

### Naming Convention

| Component | Pattern | Example |
|-----------|---------|---------|
| Operator name | `XX` | `hc_pre_only`, `mhc_post`, `sinkhorn` |
| Forward kernel | `XX_fwd_triton.py` | `hc_pre_only_fwd_triton.py` |
| Backward kernel | `XX_bwd_triton.py` | `hc_pre_only_bwd_triton.py` |
| Forward reference | `XX_fwd_ref.py` | `hc_pre_only_fwd_ref.py` |
| Backward reference | `XX_bwd_ref.py` | `hc_pre_only_bwd_ref.py` |
| Forward test | `XX_fwd_test.py` | `hc_pre_only_fwd_test.py` |
| Backward test | `XX_bwd_test.py` | `hc_pre_only_bwd_test.py` |

### 1) XX_fwd_triton.py / XX_bwd_triton.py - Kernel Implementation

**Contains ONLY:**
- Triton kernel definition(s) with `@triton.jit` decorator
- Kernel wrapper function(s) that handle tensor preparation and kernel launch
- NO test code, NO reference implementation, NO main block

**Example structure:**
```python
import triton
import triton.language as tl
import torch

@triton.jit
def my_kernel(
    input_ptr, output_ptr,
    M, N, K,
    BLOCK_M: tl.constexpr, BLOCK_N: tl.constexpr,
):
    # Kernel implementation
    ...

def my_op_triton(input_tensor, ...):
    """Wrapper function that launches the kernel."""
    # Prepare output tensor
    output = torch.empty_like(input_tensor)
    # Calculate grid
    grid = (triton.cdiv(M, BLOCK_M), triton.cdiv(N, BLOCK_N))
    # Launch kernel
    my_kernel[grid](input_tensor, output, M, N, K, BLOCK_M=64, BLOCK_N=64)
    return output
```

### 2) XX_fwd_ref.py / XX_bwd_ref.py - Reference Implementation

**Contains ONLY:**
- PyTorch reference implementation as accuracy gold standard
- Must match operator documentation line-by-line
- NO triton code, NO test code

**Example structure:**
```python
import torch

def my_op_reference(input_tensor, ...):
    """
    PyTorch reference implementation.

    Implements the operator exactly as documented:
    1. Step 1 description
    2. Step 2 description
    ...
    """
    # Line-by-line correspondence with documentation
    x = input_tensor.float()  # Cast to FP32 per spec
    # ... computation steps
    return output.to(torch.bfloat16)  # Cast to output dtype
```

### 3) XX_fwd_test.py / XX_bwd_test.py - Test Script

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

**Example structure:**
```python
import argparse
import torch
from XX_triton import my_op_triton
from XX_ref import my_op_reference
from utils import (
    bench, profiler_wrapper, assert_close_bf16,
    set_seed, print_profiler_kernel_avg_duration
)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--B", type=int, default=1)
    parser.add_argument("--S", type=int, default=1024)
    # ... other shape args
    parser.add_argument("--no-test", action="store_true")
    parser.add_argument("--no-bench", action="store_true")
    parser.add_argument("--no-profile", action="store_true")
    parser.add_argument("--mode", choices=["run", "msprof"], default="run")
    args = parser.parse_args()

    set_seed(42)
    device = "npu:0"

    # Generate test data
    x = torch.randn(args.B, args.S, args.N, args.D, device=device, dtype=torch.bfloat16)

    # Accuracy test
    if not args.no_test:
        golden = my_op_reference(x, ...)
        result = my_op_triton(x, ...)
        assert_close_bf16(result, golden, "my_op")

    # Benchmark
    if not args.no_bench:
        out, time_us, mem_mb = bench(lambda: my_op_triton(x, ...))
        print(f"Time: {time_us:.2f} us, Memory: {mem_mb:.2f} MB")

    # Profiler
    if not args.no_profile:
        profiler_wrapper(lambda: my_op_triton(x, ...))
        print_profiler_kernel_avg_duration()

if __name__ == "__main__":
    main()
```

### 4) utils.py - Common Utilities

Copy from `skill/tools/utils.py`. Contains:
- `profiler_wrapper()`: NPU profiler collection
- `print_profiler_kernel_avg_duration()`: Parse kernel_details.csv
- `msprof_op_collect()`: msprof op collection
- `bench()`: Benchmark with timing and memory tracking
- `assert_close()`, `assert_close_bf16()`: Accuracy assertions
- `rel_err()`, `cosine_sim()`: Error metrics
- `set_seed()`: Reproducibility

Reference: [utils.py](./tools/utils.py)

## End-to-End Workflow (Main Process)

### Step 0: Input Materials and Operator Classification

- Gather input materials: operator description, pseudocode, reference implementation, or existing source code.
- Determine operator type: Cube / Vector / CV mixed, and clarify performance target metrics (total duration and breakdown).

### Step 1: Reference (Accuracy Gold Standard)

- Write PyTorch reference, implementing "line-by-line correspondence with documentation", with fixed dtype/shape/seed.
- Cross-check reference against operator description (pseudocode/formula/source code):
  - Input tensor shape/dtype/layout (stride/contiguous constraints) matches documentation
  - Output tensor shape/dtype matches documentation
  - Computation flow matches documentation: reshape, broadcast, mask, reduce dimensions, normalization, boundary handling, etc.
  - Numerical strategy matches documentation: at which step to cast to FP32, eps placement, whether clamp is needed, etc.
- **Backward operator (if needed) - CRITICAL: autograd is the first line of defense, not manual reference**:
  - **Step 1**: Use forward reference + `requires_grad=True` + PyTorch autograd to get gradient baseline (this is the **first gold standard**)
  - **Step 2**: Write manual backward reference based on documentation
  - **Step 3**: Verify manual backward vs autograd consistency (must pass before writing triton kernel)
  - **Rationale**: If manual backward reference has bugs (wrong reduction dim, transpose direction, etc.), triton kernel matching it would also be wrong. Autograd catches these errors.

  ```python
  # Example: Verify manual backward against autograd
  def test_backward_vs_autograd():
      x = torch.randn(B, S, N, D, device=device, dtype=torch.float32, requires_grad=True)
      # ... other inputs with requires_grad=True as needed

      # Forward + autograd backward
      y = forward_reference(x, ...)
      y.backward(grad_output)
      x_grad_autograd = x.grad.clone()

      # Manual backward
      x_grad_manual, ... = backward_reference(grad_output, ...)

      # Must match
      torch.testing.assert_close(x_grad_autograd, x_grad_manual, rtol=1e-5, atol=1e-5)
  ```
- Define reproducible assertions for outputs (and key intermediate values if applicable). Prefer aligning each intermediate step on small shapes before scaling to target shapes.

### Step 2: triton-ascend Implementation and Runnability

- Implement kernel and ensure stable compilation and execution on target shape set.
- If compilation fails, prioritize getting a "minimal runnable version" first, then incrementally add optimizations.

### Step 3: Accuracy Verification (Required Each Iteration)

- Compare reference and triton outputs (must re-run even when changing only one main variable):
  - Cover shape set: at least 1 small shape (for intermediate alignment) + target benchmark shapes + tail/unaligned shapes (triggering mask/remainder blocks)
  - Cover dtype: per operator convention (commonly input BF16, accumulation FP32, output BF16/FP32), reference and triton dtype strategies must match
  - Assertion criteria:
    - Forward: `torch.testing.assert_close` (set rtol/atol by dtype; BF16 allows looser tolerance)
    - Additional checks: `isfinite` (NaN/Inf), max absolute/relative error, whether errors concentrate in tail blocks
  - Backward (if needed):
    - First align forward output, then align gradients: `assert_close` + cosine similarity (directional consistency)
    - autograd baseline vs manual backward baseline vs triton gradient, all three must be consistent (at least on small shapes)
  - Stability requirement: fixed seed, fixed input generation, fixed warmup/iters, avoid "intermittent pass/fail" false positives

### Step 4: Bench (Quick Filtering)

- Use same warmup/iters rules to measure average duration, as iteration filtering entry point.
- Bench alone is insufficient to locate bottlenecks; next step uses profiler for kernel-level breakdown.
- **⚠️ IMPORTANT: Bench 打屏时间只作为参考，不作为性能判定依据。** Bench 测量的是端到端 Python 调用时间，包含 tensor 分配、view/contiguous 转换、cache 查找、kernel launch overhead 等 Python 端开销（实测固定约 200-300us）。**算子真实耗时以 Step 5 Profiler 中 kernel 平均耗时为准。**

### Step 5: Profiler (Identify "Biggest Contributor")

- Collect `kernel_details.csv`, examine average duration per kernel.
- Goal: determine optimization priority (reduce biggest contributor first; handle tail kernels only when their proportion is significant).
- **CRITICAL: Correct parsing of kernel_details.csv**:
  - The CSV contains both **warmup rows** (no `Step Id`) and **active profiling rows** (with `Step Id`)
  - **Only rows with `Step Id` should be counted** for average duration calculation
  - Warmup rows exist because profiler schedule has warmup phase before active phase

  ```python
  # Correct parsing logic
  for row in reader:
      step_id = (row.get("Step Id") or "").strip()
      if not step_id:
          continue  # Skip warmup rows

      name = row.get("Name", "").strip()
      duration = float(row.get("Duration(us)", 0))
      durations_us[name] += duration
      kernel_counts[name] += 1

  # Average = total / count (not total / len(step_ids))
  avg_duration = durations_us[name] / kernel_counts[name]
  ```

### Step 6: msprof op (Read Bottleneck Signals, Guide Actions)

Use msprof CSV metrics to translate "slow" into actionable items: wait/pipe/bandwidth/cache, etc.

**Command Template (with environment configuration):**
```bash
# Must configure environment first, otherwise msprof cannot run
export ASCEND_TOOLKIT_HOME=/usr/local/Ascend/ascend-toolkit/latest && \
source /usr/local/Ascend/ascend-toolkit/latest/bin/setenv.bash && \
export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/driver:/usr/local/Ascend/driver/lib64:$LD_LIBRARY_PATH && \
msprof op \
  --kernel-name=<KERNEL_NAME_SUBSTR> \
  --output=<YOUR_MSPROF_OUTPUT_ROOT>/<TAG> \
  --warm-up=5 \
  --launch-count=1 \
  --kill=on \
  --application="python3 <YOUR_ENTRY>.py --mode run <OTHER_ARGS>"
```

### Step 7: Trial-and-Error, Rollback, Retrospective (Must Persist)

- Each iteration changes only one main variable and records: change point, configuration, bench/profiler results, msprof signals, conclusion and next steps.
- Failures must also be recorded: UB overflow, backend unsupported paths, etc. are important information for pruning future search space.

## Key Bottleneck Signals and Tuning Actions (msprof CSV Metrics)

This skill directory includes "signal -> conclusion -> action" quick reference and examples:
- [op-optimizer.md](./references/op-optimizer.md)
- msprof usage overview: [msprof-op.md](./guides/msprof-op.md)
- msprof CSV interpretation example: [csv-interpretation.md](./guides/csv-interpretation.md)
- Pre-only tuning full process (with trial-and-error): [tuning-case-study.md](./references/tuning-case-study.md)
- **triton-ascend 平台陷阱与注意事项**: [triton-ascend-pitfalls.md](./guides/triton-ascend-pitfalls.md)

## Common Failures and Troubleshooting (Priority Order)

- UB overflow: Reduce `BLOCK_D/BLOCK_K/BLOCK_M`, or split kernel to lower UB storage.
- Backend unsupported path: Rollback to last compilable configuration, search viable range with smaller step size.
- High variance: Fix seed, increase launch-count/iters, ensure no concurrent profiling tasks on device.
- **2D 张量广播精度异常**: 避免 `[:, None] * [None, :]` 模式，改用显式变量展开。详见 [triton-ascend-pitfalls.md](./guides/triton-ascend-pitfalls.md)。
- **高 scalar_ratio + 低 vec_ratio**: Grid 块数过多，需重构 Grid 结构或显式展开循环。详见 [op-optimizer.md](./references/op-optimizer.md) "Signal -> Action" 表。

## msprof op Collection Troubleshooting Guide

### Environment Configuration Issues

**Symptoms**: "Can't find valid libdcmi.so", "cannot find msopprof,because not set environment variable ASCEND_TOOLKIT_HOME"

**Solution**:
```python
# Complete msprof environment configuration
def run_msprof_op(B, S, N, D, result_path):
    env = os.environ.copy()
    env["ASCEND_TOOLKIT_HOME"] = "/data0/hcq/Ascend/ascend-toolkit/latest"
    env["PATH"] = f"/data0/hcq/Ascend/ascend-toolkit/latest/tools/profiler/bin:{env.get('PATH', '')}"

    # Add all necessary library paths
    lib_paths = [
        "/data0/hcq/Ascend/ascend-toolkit/latest/lib64",
        "/usr/local/Ascend/driver/lib64/driver",  # Critical: driver library path
        "/usr/local/Ascend/driver/lib64",
        env.get('LD_LIBRARY_PATH', '')
    ]
    env["LD_LIBRARY_PATH"] = ":".join(filter(None, lib_paths))
```

### Python Module Import Issues

**Symptoms**: "ModuleNotFoundError: No module named 'XX_triton'"

**Solution**:
```python
# Add module path in msprof temporary script
script_content = f"""
import sys
sys.path.insert(0, '<YOUR_WORKING_DIR>')  # Add working directory to Python path
import torch
import torch_npu
from <YOUR_MODULE> import <YOUR_KERNEL_FUNC>
# ... remaining code
"""
```

### Device Profiling Not Supported

**Symptoms**: "Device profiling is not supported on current chip"

**Troubleshooting Steps**:
1. Check npu-smi device status: `npu-smi info`
2. Confirm driver version and toolkit version compatibility
3. Check if other processes are occupying profiling resources

### Collection Succeeds but No Data Output

**Symptoms**: msprof returns 0 but output directory is empty

**Troubleshooting Steps**:
1. Check if kernel name filter is correct
2. Confirm temporary script can run normally (no runtime errors)
3. Check output directory permissions

### Recommended msprof op Collection Function Template

```python
def run_msprof_op(B, S, N, D, result_path):
    """Complete msprof op collection function template"""
    # 1. Create temporary script (with correct module path)
    script_content = f"""
import sys
sys.path.insert(0, '<YOUR_WORKING_DIR>')
import torch
import torch_npu
from <YOUR_MODULE> import <YOUR_KERNEL_FUNC>

# Test code...
"""

    # 2. Set complete environment variables
    env = os.environ.copy()
    env["ASCEND_TOOLKIT_HOME"] = "<ASCEND_TOOLKIT_DIR>"
    # ... complete environment configuration

    # 3. Run msprof command
    cmd = [
        "msprof", "op",
        "--kernel-name=<YOUR_KERNEL_NAME>",
        f"--output={result_path}",
        "--warm-up=5",
        "--launch-count=1",
        "--kill=on",
        "python3", "/tmp/msprof_script.py"
    ]

    # 4. Verify collection results
    if os.path.exists(result_path):
        # Check if CSV files are generated
        for root, dirs, files in os.walk(result_path):
            for file in files:
                if file.endswith('.csv'):
                    print(f"Collection successful: {os.path.join(root, file)}")
```

## Record Template (Copy Directly)

```text
Operator:
Entry script:
kernel-name filter string:

Shape set:

Baseline (bench/profiler):

msprof directory:

Trial records (change only one main variable per iteration):
- Iteration:
  - Change point:
  - Configuration (BLOCK_* / layout / fusion strategy, etc.):
  - Results (total duration / per-kernel duration):
  - msprof signals (utilization / wait / bandwidth / cache):
  - Conclusion (continue / rollback / next steps):
```

## References

- Performance tuning loop and msprof interpretation: [op-optimizer.md](./references/op-optimizer.md)
- Tuning case study (with trial-and-error): [tuning-case-study.md](./references/tuning-case-study.md)

## Extended Guides (New)

- **Ascend Language Extension API Reference**: [ascend-api-reference.md](./guides/ascend-api-reference.md)
  - Complete reference for `tl.insert_slice`, `tl.extract_slice`, `tl.custom_op`, `tl.compile_hint`, `tl.parallel`, `tl.sync_block_*`, and custom op registration
  - Use when writing kernels that need Ascend-specific APIs beyond standard Triton

- **Compiler Pipeline**: [compiler-pipeline.md](./guides/compiler-pipeline.md)
  - TTIR → Linalg → BiSheng compilation flow with code location references
  - Use when debugging compilation failures or understanding IR transformations

- **NPUOptions Reference**: [npu-options.md](./guides/npu-options.md)
  - Complete reference for 20+ NPUOptions parameters (multibuffer, compile_mode, sync_solver, etc.)
  - Includes NPUOption ↔ msprof signal correlation table
  - Use when configuring `triton.Config` for autotune

- **CV Fusion Pattern**: [cv-fusion-pattern.md](./guides/cv-fusion-pattern.md)
  - Cube-Vector fusion programming pattern with `tl.parallel` + `tl.extract_slice`
  - Use when implementing matmul + post-processing kernels (attention, matmul+activation, etc.)

- **GPU→Ascend Migration Guide**: [migration-from-gpu.md](./guides/migration-from-gpu.md)
  - Step-by-step migration from GPU Triton to Ascend NPU
  - Key differences: device, imports, BLOCK sizes, grid limits, 2D broadcasting

- **Official Tutorials Index**: [tutorials-index.md](./references/tutorials-index.md)
  - Index of 15 official tutorials with learning path recommendations

- **Triton-Ascend Pitfalls**: [triton-ascend-pitfalls.md](./guides/triton-ascend-pitfalls.md)
  - 12 common pitfalls: 2D broadcasting, BLOCK sizes, grid limits, UB overflow, FP8, atomics, etc.

- **Triton vs Torch Baseline 性能对比**: [benchmark-comparison.md](./guides/benchmark-comparison.md)
  - msprof 全进程采集 + op_summary CSV 解析方法
  - torch.profiler 在 NPU 上不可靠的原因和替代方案
  - warmup/profiled run 拆分方法、CSV 解析陷阱（Tab 字符）
  - 性能报告模板和收益来源分析框架
  - Use when generating formal performance comparison reports between Triton kernel and Torch baseline

## Tools

- `tools/utils.py` — Profiler, benchmark, accuracy assertion utilities
- `tools/estimate_ub_usage.py` — Estimate UB memory usage before running kernel
- `tools/analyze_kernel_ir.py` — Analyze intermediate IR for optimization opportunities

## Operator Type Decision Guide

When starting a new operator, determine its type to choose the right pattern:

| Operator Type | Key Operations | Pattern | Guide |
|---------------|---------------|---------|-------|
| Pure Vector | Element-wise, small reductions | Standard kernel | [tutorials/01-vector-add](./demo/official_tutorials/01-vector-add.py) |
| Pure Cube | Matrix multiply only | tl.dot kernel | [tutorials/05-matmul](./demo/official_tutorials/05-matrix-multiplication.py) |
| CV Mixed | MatMul + activation/norm | CV fusion with `tl.parallel` | [cv-fusion-pattern.md](./guides/cv-fusion-pattern.md) |
| Memory-bound | Gather/scatter/embedding | Custom memory ops | [ascend-api-reference.md](./guides/ascend-api-reference.md) |
| Reduction-heavy | Softmax, LayerNorm | Persistent kernel | [tutorials/02-softmax](./demo/official_tutorials/02-fused-softmax.py) |
