---
name: op-optimizer
description: Reusable msprof op + CSV interpretation workflow for bottleneck identification and tuning action guidance. Invoke when user wants to do operator performance tuning or trial-and-error rollback.
---

## Objective and Deliverables

> **See also:**
> - [csv-interpretation.md](../guides/csv-interpretation.md) — msprof CSV 各字段详细解读
> - [msprof-op.md](../guides/msprof-op.md) — msprof 采集完整指南与算子代码示例

- Objective: Establish a "reproducible, comparable, rollback-able" performance tuning loop for any new operator, and quickly identify bottlenecks using msprof data.
- Deliverables (should be persisted for each tuning iteration):
  - Run script: Single-file driver (supports run / bench / profiler / msprof modes)
  - Results directory:
    - profiler: `<RESULT_PROFILING_DIR>/.../kernel_details.csv`
    - msprof op: `<RESULT_MSPROF_OP_DIR>/<TAG>/OPPROF_.../*.csv`
  - Records: Configuration, conclusions, and rollback status for each attempt

## Prerequisites (Mandatory)

- Fix random seed, fix input shape set, fix device ID, ensuring different iterations are comparable.
- Correctness before performance: Any "acceleration attempt" must pass accuracy check before profiler/msprof.
- Change only one main variable: Each iteration changes only one core parameter (e.g., `BLOCK_K`, layout, whether to fuse), avoiding misjudgment due to variable coupling.

## Environment and Execution

### Inside Container Execution (Recommended)

```bash
docker exec -itu root triton-ascend-hcq /bin/bash -lc '
  source /usr/local/Ascend/ascend-toolkit/latest/bin/setenv.bash &&
  export PATH=<BISHENG_TOOLKIT_BIN>:$PATH &&
  cd <YOUR_WORKDIR> &&
  python3 <YOUR_ENTRY>.py --B 1 --S 2048 --N 4 --D 2560
'
```

## Unified Driver Script Template (Recommended Form)

Recommend each new operator provides a "single-file driver" script with these capabilities:
- `--no-test / --no-bench / --no-profile`: Toggle correctness/benchmark/profiling
- `--mode {run|direct|msprof}`: `run` for actual execution loop, `msprof` for collection mode
- `--shapes "B,S,N,D;..."`: Batch multiple shapes (convenient for generating multiple msprof directories at once)
- Expose key tunable parameters as CLI arguments (e.g., `BLOCK_M/BLOCK_N/BLOCK_K`, stage, layout switches, etc.)

Repository reference implementations (examples, can directly copy structure):
- Complete example following new file structure: [demo/mhc_pre_only/](../demo/mhc_pre_only/)
- Utility functions (profiler, msprof, bench, accuracy): [utils.py](../tools/utils.py)

## Tuning Loop (Recommended Sequential Execution)

### Step 0: Clarify "Operator Type" and Performance Target

- First determine if this is Cube-heavy (matrix/tensor) or Vector-heavy (elementwise/small reduction), or CV mixed.
- Clarify target metrics:
  - end-to-end: total operator duration (us)
  - kernel breakdown: average duration per kernel (us)
  - bottleneck signals: wait ratio, pipe proportion, bandwidth usage rate, cache hits, etc.

### Step 1: Correctness Baseline (Reference Alignment)

- Write PyTorch reference (or reuse existing formula implementation), and assert on key outputs.
- Recommend encapsulating assertions as reusable functions, ensuring every change can quickly regress.

### Step 2: Performance Baseline (bench + profiler)

- bench: Get stable average duration (microsecond level)
- profiler: Get average duration per kernel, identify "biggest contributor" and tail kernels
- **⚠️ IMPORTANT: Bench 打屏时间只作为参考，不作为性能判定依据。** Bench 测量的是端到端 Python 调用时间，包含 tensor 分配、view/contiguous 转换、cache 查找、kernel launch overhead 等 Python 端开销（实测固定约 200-300us）。**算子真实耗时以 Profiler 中 kernel 平均耗时为准。**

Prioritize profiler for iteration filtering; when performance approaches target or bottleneck is unclear, proceed to msprof op for deeper investigation.

### Step 3: msprof op On-Device Collection (To "Read Bottleneck Signals")

Command template:
```bash
msprof op \
  --kernel-name=<KERNEL_NAME_SUBSTR> \
  --output=<RESULT_MSPROF_OP_DIR>/<TAG> \
  --warm-up=5 \
  --launch-count=1 \
  --kill=on \
  python3 <YOUR_ENTRY>.py --mode run <OTHER_ARGS>
```

Conventions and notes:
- `<KERNEL_NAME_SUBSTR>` uses "substring matching", just ensure only target kernel is collected.
- `--launch-count` controls sample count; increase and take mean when variance is high.
- Do not start multiple collection tasks concurrently on same device, to avoid interference.
- Directory naming should include shape and timestamp: `B{B}_S{S}_N{N}_D{D}_YYYYmmdd_HHMMSS`

## msprof Output Directory Structure (Quick CSV Location)

Typical structure:
- `<OUT_DIR>/OPPROF_*/OpBasicInfo.csv`
- `<OUT_DIR>/OPPROF_*/ArithmeticUtilization.csv`
- `<OUT_DIR>/OPPROF_*/PipeUtilization.csv`
- `<OUT_DIR>/OPPROF_*/ResourceConflictRatio.csv`
- `<OUT_DIR>/OPPROF_*/Memory*.csv`
- `<OUT_DIR>/OPPROF_*/L2Cache.csv`

## CSV Interpretation Quick Reference (What to Look At, How to Conclude)

The following "signal -> conclusion -> action" is used to quickly translate CSVs into actionable tuning directions.

### 1) OpBasicInfo.csv (Overview Metrics)

- Key fields: `Op Name`, `Task Duration(us)`, `Block Dim`, `Mix Block Dim`
- Usage: As "total duration metric for cross-version horizontal comparison"; also confirms if block/mix configuration matches expectations.

### 2) ArithmeticUtilization.csv (Compute Utilization/Instruction Composition)

- Key fields:
  - cube: `aic_time(us)`, `aic_cube_ratio`
  - vector: `aiv_time(us)`, `aiv_vec_ratio`
- Common signals:
  - Very low `aic_cube_ratio`: Not cube-dominated, or cube is masked by wait/scalar/transfer
  - Medium but not high `aiv_vec_ratio`: Vector side also has wait/transfer/branch issues

### 3) PipeUtilization.csv (Time Spent on Which Pipe)

- Key fields:
  - cube: `aic_cube_ratio`, `aic_mte2_ratio`, `aic_scalar_ratio`
  - vector: `aiv_vec_ratio`, `aiv_mte2_ratio`, `aiv_mte3_ratio`
- Common signals:
  - High `*_mte2_ratio`: Transfer proportion high, prioritize checking memory access granularity/alignment/reuse and pipeline overlap
  - High `*_scalar_ratio`: Scalar/control flow proportion high, prioritize reducing scalar stages, merging small operators, avoiding frequent sync points

### 4) ResourceConflictRatio.csv (Is It Waiting?)

- Key fields:
  - cube: `aic_cube_wait_ratio`, `aic_mte*_wait_ratio`
  - vector: `aiv_vec_wait_ratio`, `aiv_mte2_wait_ratio`
- Common signals:
  - High wait ratio with low bandwidth usage rate: More like latency/stall (dependency chains, memory access fragmentation, non-continuous bursts), not bus bandwidth saturation

### 5) Memory.csv / MemoryUB.csv / MemoryL0.csv (Bandwidth and Data Volume)

- Key fields:
  - `GM_to_UB_bw_usage_rate(%)`, `UB_to_GM_bw_usage_rate(%)`
  - `*_read_bw(GB/s)`, `*_write_bw(GB/s)` and datas(KB)
- Common signals:
  - Very low usage rate but high wait: Prioritize optimizing access patterns (continuity/alignment/coalesced loads), increase reuse, reduce intermediate persistence
  - Stable UB bandwidth but low GM<->UB usage: Bottleneck likely in GM-side access patterns, not UB internal

### 6) L2Cache.csv (Cache Hits and Variance)

- Key fields: `*_total_hit_rate(%)` (check separately for aic/aiv)
- Common signals:
  - Few blocks with significantly worse hit rate: Prioritize checking tail blocks, masks, strides, alignment causing uneven memory access

## "Signal -> Action" Decision Table (Where to Start Tuning)

- Low cube/vector utilization + High MTE2 proportion:
  - Priority: Increase effective tile reuse, reduce intermediate write-backs, change layout for continuous loads, coalesce small-granularity loads
  - Secondary: Adjust `BLOCK_*` for better alignment
- High wait ratio + Low bandwidth usage:
  - Priority: Reduce dependency chains, reduce sync points, reduce small-granularity memory accesses
  - Secondary: Padding/alignment for critical tensors
- High scalar proportion:
  - Priority: Move scalar logic to compile-time, reduce branches and mask triggers, merge scattered elementwise operations
- Large L2 hit variance:
  - Priority: Check if access is continuous, if scatter/gather exists; reorder or adjust blocking strategy if needed
- **High scalar_ratio (>50%) + Low vec_ratio (<20%) + High Block Dim (>10000)**:
  - Root cause: Grid block count too high, scalar overhead (address calculation, loop control) dominates vector compute
  - Priority: **Restructure Grid** - merge small dimensions (e.g., N heads) into single block processing
  - Secondary: **Explicit loop unrolling** - replace `for n in range(N)` with explicit scalar variables (`H_post_0, H_post_1, ...`)
  - Secondary: Increase BLOCK size to reduce total block count
  - Reference: [triton-ascend-pitfalls.md](../guides/triton-ascend-pitfalls.md)
- **Block Dim >> num_aicore (e.g., M=2048, num_aicore=24)**:
  - Root cause: Excessive block scheduling overhead, each block's compute insufficient to amortize scheduling cost
  - Priority: **Cooperative Grid** — shrink grid to `num_cores * 4`, each block loops over multiple positions
  - Template:
    ```python
    import triton.runtime.driver as driver
    num_cores = driver.active.utils.get_device_properties(device)["num_aicore"]
    grid_size = min(M, num_cores * 4)

    @triton.jit
    def kernel(..., M: tl.constexpr, num_cores: tl.constexpr):
        pid = tl.program_id(0)
        for idx in range(pid, M, num_cores):
            ...

    kernel[(grid_size,)](..., M=M, num_cores=grid_size)
    ```
  - Note: Applicable when M >> num_aicore and no cross-position data dependencies
  - Reference: [triton-ascend-pitfalls.md](../guides/triton-ascend-pitfalls.md)
- **High scalar_ratio (>30%) with many independent tl.sum calls**:
  - Root cause: Each tl.sum generates scalar reduction instructions, cannot utilize cube parallelism
  - Priority: **Batch tl.dot replacement** — merge N×M independent tl.sum into one tl.dot, triggering cube unit acceleration
  - Template:
    ```python
    # Before: N*M independent tl.sum (scalar reduction)
    for i in range(N):
        for j in range(M):
            out[i][j] = tl.sum(a[i] * b[j])

    # After: 1 tl.dot (cube matmul)
    a_blk = tl.load(...)  # [N, K]
    b_blk = tl.load(...)  # [M, K]
    out = tl.dot(a_blk, tl.trans(b_blk))  # [N, M]
    ```
  - Note: Data must be organizable as 2D tiles; K dimension should be large enough (>256) to amortize tl.dot overhead

## Common Trial-and-Error and Rollback Patterns (Turning Failures into Information)

### 1) UB Overflow (Compilation Failure)

- Typical error: `ub overflow, requires ... bits while ... bits available!`
- Common causes:
  - `BLOCK_*` too large causing tile storage to exceed UB
  - Too many temporary tensors (multiple loads, extra intermediate results)
- Resolution:
  - First reduce `BLOCK_D/BLOCK_K/BLOCK_M`
  - Try splitting kernel: separate large outputs or large reductions

### 2) Backend Unsupported / Root Allocation Failure (Compilation Failure)

- Typical symptom: Error contains `Unsupported op for finding the root alloc`
- Common causes:
  - Tile combination triggers backend boundary/unsupported path (often with too-large `BLOCK_K` combinations)
- Resolution:
  - Rollback to last compilable configuration, then search with smaller step size

## Record Template (Recommended Copy to Your Tuning Retrospective)

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

## NPUOptions to msprof Signal Correlation

When a bottleneck is identified via msprof, use the corresponding NPUOptions to tune:

| msprof Signal | Indicates | Relevant NPUOptions |
|---------------|-----------|---------------------|
| High `wait_ratio` | Memory stalls, pipeline bubbles | `multibuffer=True`, `set_workspace_multibuffer=2` |
| High `mte2_ratio` | Memory transfer dominated | `multibuffer=True`, layout optimization |
| High `scalar_ratio` | Too many blocks, control overhead | Increase BLOCK sizes, reduce grid |
| Low `vec_ratio` | Vector underutilized | `enable_auto_bind_sub_block=True` |
| Imbalanced aic/aiv time | CV load imbalance | `enable_hivm_auto_cv_balance=True`, `tile_mix_*` |
| Low `bandwidth_usage_rate` | Inefficient memory access | Coalesce accesses, padding/alignment |
| Low `cache_hit_rate` | Cache misses | Improve data locality, tiling strategy |
| Sync issues (incorrect results) | Data races | `sync_solver=True` |

### NPUOptions Quick Reference

| Option | Default | When to Enable/Tune |
|--------|---------|---------------------|
| `multibuffer` | True (A2/A3) | High wait ratio, memory stalls |
| `enable_auto_bind_sub_block` | True (A2/A3) | CV-fused kernels, dual vector core |
| `enable_hivm_auto_cv_balance` | None | Imbalanced Cube/Vector time |
| `sync_solver` | None | Debugging sync issues |
| `tile_mix_vector_loop` | None | Fine-tune vector loop tiling in CV |
| `tile_mix_cube_loop` | None | Fine-tune cube loop tiling in CV |
| `compile_mode` | "simd" | Try "simt_only" for irregular access |

See [npu-options.md](../guides/npu-options.md) for complete reference.

## Reference Materials (Migrated to This Skill Directory)

- msprof usage overview: [msprof-op.md](../guides/msprof-op.md)
- Pre-only tuning full process (with trial-and-error): [tuning-case-study.md](./tuning-case-study.md)
- msprof CSV example interpretation report: [csv-interpretation.md](../guides/csv-interpretation.md)
- NPUOptions reference: [npu-options.md](../guides/npu-options.md)
- Ascend API reference: [ascend-api-reference.md](../guides/ascend-api-reference.md)
- CV fusion pattern: [cv-fusion-pattern.md](../guides/cv-fusion-pattern.md)
