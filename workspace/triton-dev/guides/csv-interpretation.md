# msprof op CSV Analysis Report Guide

**Example Directory**: `<RESULT_MSPROF_OP_DIR>/B1_S1024_N4_D5120_20260129_023104`
**OPPROF Directory**: `<RESULT_MSPROF_OP_DIR>/B1_S1024_N4_D5120_20260129_023104/OPPROF_20260129023104_QHUFJZWUFYIGWZSD`

This guide explains each `*.csv` file's field meanings in the directory, how to read them, and practical conclusions from a "performance tuning perspective".

---

## General Reading: Understanding block/sub_block

From `OpBasicInfo.csv`:

- `Block Dim = 16`: This kernel launched 16 blocks (think of them as 16 "parallel work groups").
- `Mix Block Dim = 32` and `Op Type = mix`: This kernel is in mixed execution mode (mix), where multiple sub-executors appear under the same block (commonly aicore/cube combined with aivector/vector).

In most CSVs you'll see:

- `block_id`: `0..15` (16 total).
- `sub_block_id`:
  - `cube0`: cube/aicore (matrix/tensor compute unit) related metrics.
  - `vector0`, `vector1`: vector/aivector (vector/scalar compute, transfer) related metrics.
- `NA`: Field not applicable for that row. For example, `cube0` rows show `NA` for aiv fields, `vector*` rows show `NA` for aic fields.

Correct "comparison method" for these tables:

- Within same `block_id`, compare `cube0` vs `vector0/1`: Check if bottlenecks are consistent across sub-executors within that block.
- Across `block_id` do statistics (mean/min/max): Check if there's high variance across blocks (high variance may indicate uneven memory access, branch/mask causing load imbalance, etc.).

---

## 1) OpBasicInfo.csv: Operator Basic Info (Most Important "Overview")

Key fields explained:

- `Op Name`: Actual kernel name executed on device. Example: `hc_matmul_pre_only_kernel_gamma_mix_aic`, where `_mix_aic` is backend suffix for mixed execution mode.
- `Op Type`: Kernel mode. Example: `mix`.
- `Task Duration(us)`: msprof's overall duration statistic for this op (microseconds).
- `Block Dim` / `Mix Block Dim`: Number of launched blocks / mixed sub-blocks (corresponds to `block_id/sub_block_id` in subsequent CSVs).
- `Current Freq` / `Rated Freq`: Actual frequency during collection / rated frequency.

**How to use:**

- `Task Duration(us)` is the "macro-level" single op time, suitable for horizontal comparison across versions (different BLOCK_K, different layouts).
- Other CSVs' `aic_time/aiv_time` are more like "sub-executor duration breakdown"; their values don't necessarily strictly sum to `Task Duration` (may have parallelism/overlap, different statistical scopes).

---

## 2) ArithmeticUtilization.csv: Compute Utilization (Is the operator "compute-saturated"?)

Field structure (by sub-executor):

**cube/aic** (valid in `cube0` rows):
- `aic_time(us)`, `aic_total_cycles`
- `aic_cube_ratio`: cube execution proportion (higher means more time in cube compute).
- `aic_cube_fp16_ratio/int8_ratio`: cube instruction proportion by data type.
- `aic_cube_fops`: floating point operations counted on cube side.

**vector/aiv** (valid in `vector0/1` rows):
- `aiv_time(us)`, `aiv_total_cycles`
- `aiv_vec_ratio`: vector compute proportion (higher means more "computing").
- `aiv_vec_fp32_ratio/fp16_ratio/int32_ratio/...`: vector execution composition.
- `aiv_vec_misc_ratio`: misc instruction proportion (typically want this low).
- `aiv_vec_fops`: floating point operations counted on vector side.

**Tuning interpretation:**

- If cube utilization (`aic_cube_ratio`) is low and you expect a GEMM-dominated kernel, this typically means: either memory/sync/pipeline wait proportions are high, or compute is fragmented into lots of non-cube scalar/transfer stages.
- Low `aiv_vec_ratio` similarly indicates vector side affected by waits/transfers/branches.

---

## 3) PipeUtilization.csv: Pipeline Breakdown (Where time is spent by pipe)

Common fields:

**aic/cube0:**
- `aic_cube_time/us` + `aic_cube_ratio`: cube compute
- `aic_scalar_time/us` + `aic_scalar_ratio`: scalar execution (typically includes scalar ops, control flow, some scalar data processing)
- `aic_mte1_time/us`, `aic_mte2_time/us`, `aic_mte3_time/us`: each transfer engine (MTE) time and proportion
- `aic_mte*_active_bw(GB/s)`: MTE active bandwidth (note: very short active time may cause large numbers, consider with ratio)

**aiv/vector0/1:**
- `aiv_vec_time/us` + `aiv_vec_ratio`: vector execution
- `aiv_scalar_time/us` + `aiv_scalar_ratio`: vector-side scalar
- `aiv_mte2_time/us`, `aiv_mte3_time/us`: vector-side MTE

**Tuning interpretation:**

- High `*_mte2_ratio`: transfer proportion high, prioritize checking memory access granularity/alignment/reuse and pipeline overlap
- High `*_scalar_ratio`: scalar/control flow proportion high, prioritize reducing scalar stages, merging small operators, avoiding frequent sync points

---

## 4) ResourceConflictRatio.csv: Wait/Conflict Ratio (Is it "waiting"?)

Common fields:

**aic/cube0:**
- `aic_cube_wait_ratio`: cube wait ratio (higher means more time waiting for resources/data/scheduling).
- `aic_mte1_wait_ratio` / `aic_mte2_wait_ratio` / `aic_mte3_wait_ratio`: corresponding MTE wait ratios.

**aiv/vector0/1:**
- `aiv_vec_total_cflt_ratio`: vector-side total conflict ratio (aggregate).
- `aiv_vec_bankgroup_cflt_ratio` / `aiv_vec_bank_cflt_ratio`: finer bank conflict breakdown.
- `aiv_vec_wait_ratio`: vector wait ratio.
- `aiv_mte2_wait_ratio` / `aiv_mte3_wait_ratio`: transfer-related wait ratios.

**Tuning interpretation:**

- High wait ratio with low bandwidth usage rate: more like latency/stall (dependency chains, memory access fragmentation, non-continuous bursts), not total bus bandwidth saturation

---

## 5) Memory.csv: GM/L1/UB Bandwidth and Data Volume (Is it "bandwidth bottleneck"?)

Many fields, common reading approach looks at two types:

- **Bandwidth (GB/s)**: e.g., `aic_main_mem_read_bw(GB/s)`, `aiv_gm_to_ub_bw(GB/s)`
- **Data volume (KB)**: e.g., `read_main_memory_datas(KB)`, `GM_to_UB_datas(KB)`
- **Bandwidth usage rate (%)**: e.g., `GM_to_UB_bw_usage_rate(%)`, `UB_to_GM_bw_usage_rate(%)`

**Tuning interpretation:**

- Low bandwidth usage rate (e.g., `GM_to_UB_bw_usage_rate(%)~5.95%`): not "bandwidth-saturated slowness".
- Combined with high wait ratios in ResourceConflictRatio: more like access pattern causing waits (e.g., insufficient burst/alignment, small memory access granularity, long dependency chains making pipeline hard to fill), not "total bus bandwidth insufficient".

---

## 6) MemoryL0.csv: L0A/L0B/L0C Bandwidth (Cube Local Cache/Matrix Unit)

This table is mainly meaningful for `cube0` rows (vector rows mostly NA).

Common fields:
- `aic_l0a_*_bw`: L0A read/write bandwidth
- `aic_l0b_*_bw`: L0B read/write bandwidth
- `aic_l0c_*_bw_cube`: L0C (cube-related) read/write bandwidth

**Tuning interpretation:**

- This table is better for comparing "whether changing tile/layout affects L0 behavior" across versions; absolute values alone are hard to judge "good or bad", but can be used to observe abnormal jitter or sudden zeros.

---

## 7) MemoryUB.csv: UB Bandwidth (Vector Local Cache/Intermediate Buffer)

Field explanation:
- `aiv_ub_read_bw_vector(GB/s)` / `aiv_ub_write_bw_vector(GB/s)`: vector executor read/write bandwidth on UB
- `*_scalar`: scalar read/write bandwidth (often 0)

**Tuning interpretation:**

- Stable UB-side bandwidth suggests UB internal access may not be main bottleneck; bottleneck more likely in GM<->UB (see Memory.csv) or in waits/dependencies (see ResourceConflictRatio.csv).

---

## 8) L2Cache.csv: L2 Cache Hit Rate (Is it cached? Is it thrashing?)

Common fields:

**aic/cube0:**
- `aic_*_cache_hit/_miss_allocate`: write/read hit and miss breakdown (r0/r1 two read ports)
- `aic_write_hit_rate(%)`, `aic_read_hit_rate(%)`, `aic_total_hit_rate(%)`

**aiv/vector0/1:**
- Same set of `aiv_*` fields

**Tuning interpretation:**

- High cube-side L2 hit rate overall is positive for performance, but individual blocks dropping (e.g., to ~87%): "few blocks significantly worse" often indicates uneven access patterns (e.g., tail block, mask, alignment, stride causing some blocks to have higher misses).
- Large vector-side hit rate variance: commonly seen with scatter/gather or non-continuous access causing unstable cache effectiveness.

---

## Summary: Most Direct Bottleneck Signals

Based solely on these CSVs (without other tools), several conclusions "sufficient to guide next tuning direction":

- **Low compute utilization**: `aic_cube_ratio~0.137`, `aiv_vec_ratio~0.450`, not "compute-saturated".
- **High wait ratios**: `aic_cube_wait_ratio~0.45`, `aiv_mte2_wait_ratio~0.78`, large amount of time waiting for resources/data.
- **Low bandwidth usage rate**: `GM_to_UB_bw_usage_rate(%)~5.95%`, not typical "bandwidth-saturated" bottleneck, more like **memory access efficiency/granularity/dependency chain causing latency/stall**.

If translating these conclusions to triton tuning actions, generally prioritize checking:

- Whether `BLOCK_K/BLOCK_M` causes memory access misalignment or too-small granularity (non-continuous bursts).
- Whether dot and other scalar/vector stages can reduce intermediate reads/writes, reduce sync points, improve pipeline overlap.
- Whether `gamma` loading method causes extra bandwidth/waiting (e.g., repeated loads, no reuse, cache-unfriendly).

---

## Signal -> Action Decision Table (Where to Start Tuning)

| Signal Pattern | Priority Action | Secondary Action |
|---------------|-----------------|------------------|
| Low cube/vector utilization + High MTE2 ratio | Increase effective tile reuse, reduce intermediate write-backs, change layout for continuous loads, merge small-granularity loads | Adjust `BLOCK_*` for better alignment |
| High wait ratio + Low bandwidth usage | Reduce dependency chains, reduce sync points, reduce small-granularity memory accesses | Padding/alignment for critical tensors |
| High scalar ratio | Move scalar logic to compile-time, reduce branches and mask triggers, merge scattered elementwise ops | - |
| Large L2 hit rate variance | Check if access is continuous, if scatter/gather exists; reorder or adjust blocking strategy if needed | - |
