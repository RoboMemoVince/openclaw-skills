# Official Tutorials Index

Complete index of Triton-Ascend official tutorials from `third_party/ascend/tutorials/`.

## Tutorials Overview

| # | Tutorial | Operator Type | Key Concepts |
|---|----------|--------------|--------------|
| 01 | Vector Addition | Vector | Basic programming model, `@triton.jit`, masking |
| 02 | Fused Softmax | Vector | Row-wise reduction, persistent kernels, `tl.range` |
| 03 | Layer Norm | Vector | Multi-pass reduction, numerical stability |
| 04 | Fused Attention | CV Mixed | Flash Attention, multi-stage, causal masking |
| 05 | Matrix Multiplication | CV Mixed | `tl.dot`, `tl.parallel`, `extract_slice`, autotune |
| 06 | Demo Autotune | Any | `triton.autotune`, `triton.Config` |
| 07 | Profiler | Any | NPU profiler, `kernel_details.csv` parsing |
| 08 | Demo LibEntry | Any | Library entry point, kernel registration |
| 09 | Gather | Vector | Gather operations, index-based access |
| 10 | Gather Sorted | Vector | Optimized gather with sorted indices |
| 11 | RAB Time | Any | Time measurement, benchmarking methodology |
| 12 | HSTU Attention | CV Mixed | High-Speed Token Unshuffle attention |
| 13 | MatMul Optimized | CV Mixed | Advanced matmul optimizations |
| 14 | Accuracy Comparison | Any | Reference vs triton validation, tolerance |
| 15 | Embedding Gather | Vector | Embedding lookup, gather patterns |

## Detailed Descriptions

### 01 - Vector Addition (Entry Level)

**File:** `01-vector-add.py`

**What you learn:**
- Basic `@triton.jit` decorator usage
- `tl.program_id()` for block identification
- `tl.arange()` for offset computation
- Masking with `offsets < n_elements`
- `tl.load()` and `tl.store()` with masks
- Grid lambda for dynamic grid computation

**Key pattern:**
```python
pid = tl.program_id(axis=0)
offsets = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
mask = offsets < n_elements
x = tl.load(x_ptr + offsets, mask=mask)
```

### 02 - Fused Softmax

**File:** `02-fused-softmax.py`

**What you learn:**
- Row-wise reduction pattern
- Persistent kernel with `tl.range()` and `tl.num_programs()`
- Numerical stability (subtract max before exp)
- `tl.max()`, `tl.sum()`, `tl.exp()` usage

**Key pattern:**
```python
for row_idx in tl.range(row_start, n_rows, row_step):
    row = tl.load(input_ptrs, mask=mask, other=-float('inf'))
    row_max = tl.max(row, axis=0)
    numerator = tl.exp(row - row_max)
    denominator = tl.sum(numerator, axis=0)
    softmax_output = numerator / denominator
```

### 03 - Layer Norm

**File:** `03-layer-norm.py`

**What you learn:**
- Two-pass normalization (mean, variance)
- FP32 accumulation for numerical stability
- Weight and bias application

### 04 - Fused Attention (Advanced)

**File:** `04-fused-attention.py`

**What you learn:**
- Flash Attention v2 implementation
- Multi-stage processing (QK → softmax → AV)
- Causal masking
- Online softmax normalization
- Block-level K/V iteration

### 05 - Matrix Multiplication (CV Fusion)

**File:** `05-matrix-multiplication.py`

**What you learn:**
- `tl.dot()` for Cube-unit matrix multiply
- CV fusion pattern: `tl.parallel(0, 2, bind_sub_block=True)`
- `tl.extract_slice()` for sub-block partitioning
- Autotune configuration
- Fused activation (leaky ReLU)

**Key pattern (CV fusion):**
```python
# Cube phase
acc = tl.dot(a, b, acc)

# Vector phase (dual core)
SUB_BLK_M: tl.constexpr = BLOCK_SIZE_M // 2
for s in tl.parallel(0, 2, bind_sub_block=True):
    vec_sub_blk = tl.extract_slice(acc, (s * SUB_BLK_M, 0), ...)
    vec_sub_blk = leaky_relu(vec_sub_blk)
```

### 06 - Demo Autotune

**File:** `06-demo-autotune.py`

**What you learn:**
- `triton.autotune` decorator
- `triton.Config` with meta-parameters
- Key parameters for autotune search
- NPU-specific config options

### 07 - Profiler

**File:** `07-profiler.py`

**What you learn:**
- NPU profiler integration
- `kernel_details.csv` parsing
- Performance metric collection

### 08 - Demo LibEntry

**File:** `08-demo-libentry.py`

**What you learn:**
- Library entry point registration
- Kernel pre-compilation
- Deployment patterns

### 09/10 - Gather Operations

**Files:** `09-gather.py`, `10-gather_sorted.py`

**What you learn:**
- Index-based gather operations
- Boundary handling for indices
- Sorted index optimization

### 13 - Optimized Matrix Multiplication

**File:** `13-matrix-multiplication-optimized.py`

**What you learn:**
- Advanced tiling strategies
- Multi-buffer optimization
- Pipeline optimization
- Performance tuning techniques

### 14 - Accuracy Comparison

**File:** `14-accuracy-comparison.py`

**What you learn:**
- Reference implementation vs Triton comparison
- Tolerance setting for different dtypes
- Error metrics (max abs error, relative error)

## Learning Path

### Beginner
1. `01-vector-add.py` → Basic model
2. `02-fused-softmax.py` → Reductions
3. `14-accuracy-comparison.py` → Validation

### Intermediate
4. `06-demo-autotune.py` → Autotune
5. `05-matrix-multiplication.py` → CV fusion
6. `07-profiler.py` → Profiling
7. `09-gather.py` → Memory patterns

### Advanced
8. `04-fused-attention.py` → Complex kernels
9. `13-matrix-multiplication-optimized.py` → Performance tuning
10. `12-hstu_attention.py` → Production patterns

## Source Location

All tutorials are in the triton-ascend repository:
```
third_party/ascend/tutorials/
```

Local demo copies are available in this skill:
```
demo/official_tutorials/
```
