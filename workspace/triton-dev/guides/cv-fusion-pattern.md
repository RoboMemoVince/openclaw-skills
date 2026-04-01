# CV Fusion Programming Pattern

This document explains the Cube-Vector (CV) fusion programming pattern for Ascend NPU, enabling efficient utilization of both matrix compute (Cube) and vector compute (Vector) units.

## Ascend NPU Architecture Background

Ascend NPU has two main compute units:

| Unit | Name | Capability |
|------|------|------------|
| **Cube** | AI Core | Matrix multiplication (tl.dot) |
| **Vector** | AI Vector Core | Element-wise ops, reductions, activations |

On Ascend 910B, each AI Core has **2 Vector sub-blocks** that can work in parallel.

## Basic CV Fusion Pattern

The key insight: after Cube computes matrix multiplication, Vector can process the results in parallel using dual vector cores.

### Pattern Structure

```python
@triton.jit
def cv_fused_kernel(
    # ... pointers and dimensions ...
    BLOCK_M: tl.constexpr,
    BLOCK_N: tl.constexpr,
    BLOCK_K: tl.constexpr,
):
    # ===== CUBE PHASE =====
    # Matrix multiplication on Cube unit
    acc = tl.zeros((BLOCK_M, BLOCK_N), dtype=tl.float32)
    for k in range(0, K, BLOCK_K):
        a = tl.load(a_ptrs + k * stride_ak, mask=...)
        b = tl.load(b_ptrs + k * stride_bk, mask=...)
        acc = tl.dot(a, b, acc)  # Cube operation

    # ===== VECTOR PHASE (Dual-Core Parallel) =====
    SUB_M: tl.constexpr = BLOCK_M // 2
    for s in tl.parallel(0, 2, bind_sub_block=True):
        # Extract sub-block for this vector core
        sub_acc = tl.extract_slice(
            acc,
            offsets=(s * SUB_M, 0),
            sizes=(SUB_M, BLOCK_N),
            strides=(1, 1)
        )

        # Vector operations (run in parallel on 2 cores)
        sub_acc = activation(sub_acc)
        sub_out = sub_acc.to(tl.float16)

        # Store from this vector core
        offs_m = pid_m * BLOCK_M + s * SUB_M + tl.arange(0, SUB_M)
        offs_n = pid_n * BLOCK_N + tl.arange(0, BLOCK_N)
        out_ptrs = out_ptr + offs_m[:, None] * stride_om + offs_n[None, :] * stride_on
        out_mask = (offs_m[:, None] < M) & (offs_n[None, :] < N)
        tl.store(out_ptrs, sub_out, mask=out_mask)
```

## Key APIs

### tl.parallel

```python
for s in tl.parallel(start, end, bind_sub_block=True):
    # Loop body executed in parallel across vector sub-blocks
```

| Parameter | Description |
|-----------|-------------|
| `start` | Loop start index (typically 0) |
| `end` | Loop end index (typically 2 for dual cores) |
| `bind_sub_block` | Must be `True` to bind to vector sub-blocks |

### tl.extract_slice

```python
sub_tensor = tl.extract_slice(
    tensor,           # Source tensor
    offsets=(o1, o2), # Starting position
    sizes=(s1, s2),   # Slice size
    strides=(1, 1)    # Typically (1, 1)
)
```

### tl.insert_slice

```python
result = tl.insert_slice(
    full_tensor,      # Target tensor
    sub_tensor,       # Tensor to insert
    offsets=(o1, o2), # Insert position
    sizes=(s1, s2),   # Insert size
    strides=(1, 1)
)
```

## Complete Example: Matrix Multiplication with Activation

```python
import triton
import triton.language as tl
import torch
import torch_npu

@triton.jit
def leaky_relu(x):
    return tl.where(x >= 0, x, 0.01 * x)

@triton.autotune(
    configs=[
        triton.Config(
            {"BLOCK_M": 128, "BLOCK_N": 128, "BLOCK_K": 64},
            enable_auto_bind_sub_block=True,
        ),
    ],
    key=["M", "N", "K"],
)
@triton.jit
def matmul_leaky_relu_kernel(
    a_ptr, b_ptr, c_ptr,
    M, N, K,
    stride_am, stride_ak,
    stride_bk, stride_bn,
    stride_cm, stride_cn,
    BLOCK_M: tl.constexpr,
    BLOCK_N: tl.constexpr,
    BLOCK_K: tl.constexpr,
):
    pid = tl.program_id(0)
    num_pid_n = tl.cdiv(N, BLOCK_N)
    pid_m = pid // num_pid_n
    pid_n = pid % num_pid_n

    # Compute block pointers
    offs_am = pid_m * BLOCK_M + tl.arange(0, BLOCK_M)
    offs_bn = pid_n * BLOCK_N + tl.arange(0, BLOCK_N)
    offs_k = tl.arange(0, BLOCK_K)

    a_ptrs = a_ptr + offs_am[:, None] * stride_am + offs_k[None, :] * stride_ak
    b_ptrs = b_ptr + offs_k[:, None] * stride_bk + offs_bn[None, :] * stride_bn

    # ===== CUBE PHASE: Matrix multiplication =====
    acc = tl.zeros((BLOCK_M, BLOCK_N), dtype=tl.float32)
    for k in range(0, tl.cdiv(K, BLOCK_K)):
        k_remaining = K - k * BLOCK_K
        a_mask = (offs_am[:, None] < M) & (offs_k[None, :] < k_remaining)
        b_mask = (offs_k[:, None] < k_remaining) & (offs_bn[None, :] < N)

        a = tl.load(a_ptrs, mask=a_mask, other=0.0)
        b = tl.load(b_ptrs, mask=b_mask, other=0.0)
        acc = tl.dot(a, b, acc)

        a_ptrs += BLOCK_K * stride_ak
        b_ptrs += BLOCK_K * stride_bk

    # ===== VECTOR PHASE: Activation with dual-core parallelism =====
    SUB_M: tl.constexpr = BLOCK_M // 2
    for s in tl.parallel(0, 2, bind_sub_block=True):
        # Each vector core processes half of the M dimension
        sub_acc = tl.extract_slice(
            acc,
            offsets=(s * SUB_M, 0),
            sizes=(SUB_M, BLOCK_N),
            strides=(1, 1)
        )

        # Apply activation (vector operation)
        sub_acc = leaky_relu(sub_acc)
        sub_out = sub_acc.to(tl.float16)

        # Store results
        offs_cm = pid_m * BLOCK_M + s * SUB_M + tl.arange(0, SUB_M)
        offs_cn = pid_n * BLOCK_N + tl.arange(0, BLOCK_N)
        c_ptrs = c_ptr + offs_cm[:, None] * stride_cm + offs_cn[None, :] * stride_cn
        c_mask = (offs_cm[:, None] < M) & (offs_cn[None, :] < N)
        tl.store(c_ptrs, sub_out, mask=c_mask)


def matmul_leaky_relu(a, b):
    M, K = a.shape
    K, N = b.shape
    c = torch.empty((M, N), device=a.device, dtype=torch.float16)

    grid = lambda meta: (
        triton.cdiv(M, meta["BLOCK_M"]) * triton.cdiv(N, meta["BLOCK_N"]),
    )

    matmul_leaky_relu_kernel[grid](
        a, b, c,
        M, N, K,
        a.stride(0), a.stride(1),
        b.stride(0), b.stride(1),
        c.stride(0), c.stride(1),
    )
    return c
```

## When to Use CV Fusion

### Good Candidates

| Scenario | Why CV Fusion Helps |
|----------|---------------------|
| MatMul + Activation | Cube does matmul, Vector does activation |
| MatMul + Bias + Activation | Cube matmul, Vector adds bias and activation |
| Attention (QK + Softmax + V) | Cube for QK and AV, Vector for softmax |
| MatMul + LayerNorm | Cube matmul, Vector normalization |

### Poor Candidates

| Scenario | Why Not |
|----------|---------|
| Pure vector operations | No Cube work to parallelize with |
| Small matrices | Overhead exceeds benefit |
| Memory-bound kernels | Bottleneck is memory, not compute |

## Compiler Options for CV Fusion

```python
triton.Config(
    {"BLOCK_M": 128, "BLOCK_N": 128, "BLOCK_K": 64},
    # Enable sub-block binding
    enable_auto_bind_sub_block=True,
    # Auto CV balance (optional)
    enable_hivm_auto_cv_balance=True,
    # Tune vector loop tiling (optional)
    tile_mix_vector_loop=64,
    tile_mix_cube_loop=128,
)
```

## Diagnosing CV Fusion Issues

### msprof Signals

| Signal | Good Value | Issue Indication |
|--------|------------|------------------|
| `aic_time` | ~50% of total | Cube underutilized if too low |
| `aiv_time` | ~50% of total | Vector underutilized if too low |
| Balanced aic/aiv | Close to each other | Imbalance = one unit idle |

### Common Issues

**1. Vector underutilized (low aiv_time)**

```python
# Issue: Not using tl.parallel
for s in range(0, 2):  # Wrong: sequential
    ...

# Fix: Use tl.parallel with bind_sub_block
for s in tl.parallel(0, 2, bind_sub_block=True):  # Correct
    ...
```

**2. Cube underutilized (low aic_time)**

```python
# Issue: Not enough work for Cube
BLOCK_K = 32  # Too small

# Fix: Increase BLOCK_K for better Cube utilization
BLOCK_K = 128
```

**3. Sync issues (incorrect results)**

Enable sync solver in config:
```python
triton.Config(
    {...},
    sync_solver=True,
)
```

## Advanced: Explicit Synchronization

For complex CV pipelines, use explicit sync primitives:

```python
@triton.jit
def complex_cv_kernel(...):
    # Cube computation
    cube_result = tl.dot(a, b)

    # Signal Cube completion
    tl.sync_block_set(sender="cube", receiver="vector", event_id=0)

    # Vector waits for Cube
    tl.sync_block_wait(sender="cube", receiver="vector", event_id=0)

    # Vector processing
    vector_result = process(cube_result)
```

## Performance Tips

1. **Balance workload**: Ensure Cube and Vector have similar work duration
2. **Minimize data transfer**: Keep intermediate results in UB between phases
3. **Use appropriate BLOCK sizes**: Cube prefers larger blocks, Vector can handle smaller
4. **Profile with msprof**: Check aic/aiv time balance

## Code References

- Tutorial: `third_party/ascend/tutorials/05-matrix-multiplication.py`
- Flash Attention: `third_party/ascend/tutorials/04-fused-attention.py`
- Optimized MatMul: `third_party/ascend/tutorials/13-matrix-multiplication-optimized.py`
