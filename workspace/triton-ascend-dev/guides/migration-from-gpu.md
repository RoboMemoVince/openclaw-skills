# GPU Triton to Ascend NPU Migration Guide

This guide helps developers migrate existing GPU Triton kernels to Triton-Ascend for Huawei Ascend NPU.

## Quick Comparison Table

| Aspect | GPU Triton (CUDA) | Triton-Ascend (NPU) |
|--------|-------------------|---------------------|
| Device | `device='cuda'` | `device='npu'` |
| Import | `import triton` | `import triton` + `import torch_npu` |
| Memory hierarchy | Global → Shared → Register | GM → UB → Register |
| Multi-core | Warps/Blocks | AI Cores / Vector Sub-blocks |
| Sync primitive | `tl.debug_barrier()` | `tl.sync_block_*` |
| BLOCK sizes | Must be power of 2 | Any size works |
| Max grid dim | Varies | 65536 per dimension |

## Step-by-Step Migration

### Step 1: Update Imports

**Before (GPU):**
```python
import torch
import triton
import triton.language as tl
```

**After (NPU):**
```python
import torch
import torch_npu  # Required for NPU support
import triton
import triton.language as tl
```

### Step 2: Update Device Allocation

**Before (GPU):**
```python
x = torch.randn(1024, device='cuda', dtype=torch.float16)
```

**After (NPU):**
```python
x = torch.randn(1024, device='npu', dtype=torch.float16)
# or
x = torch.randn(1024, device='npu:0', dtype=torch.float16)
```

### Step 3: Kernel Code (Usually No Changes Needed)

Most kernel code works as-is:

```python
@triton.jit
def add_kernel(x_ptr, y_ptr, output_ptr, n_elements, BLOCK_SIZE: tl.constexpr):
    pid = tl.program_id(axis=0)
    block_start = pid * BLOCK_SIZE
    offsets = block_start + tl.arange(0, BLOCK_SIZE)
    mask = offsets < n_elements
    x = tl.load(x_ptr + offsets, mask=mask)
    y = tl.load(y_ptr + offsets, mask=mask)
    output = x + y
    tl.store(output_ptr + offsets, output, mask=mask)
```

### Step 4: Update Wrapper Function

**Before (GPU):**
```python
def add(x: torch.Tensor, y: torch.Tensor):
    output = torch.empty_like(x)
    n_elements = output.numel()
    grid = lambda meta: (triton.cdiv(n_elements, meta['BLOCK_SIZE']),)
    add_kernel[grid](x, y, output, n_elements, BLOCK_SIZE=1024)
    return output
```

**After (NPU):**
```python
def add(x: torch.Tensor, y: torch.Tensor):
    output = torch.empty_like(x)  # Automatically on same device
    n_elements = output.numel()
    grid = lambda meta: (triton.cdiv(n_elements, meta['BLOCK_SIZE']),)
    add_kernel[grid](x, y, output, n_elements, BLOCK_SIZE=1024)
    return output

# Usage
x = torch.randn(98432, device='npu')
y = torch.randn(98432, device='npu')
result = add(x, y)
```

## Key Differences and Adaptations

### 1. BLOCK Size Flexibility

**GPU:** Must be power of 2 (32, 64, 128, 256, ...)

**NPU:** Any size works, and non-power-of-2 can be optimal

```python
# NPU: This is valid and often optimal
BLOCK_D = 2560  # Matches dimension exactly
BLOCK_D = 1280  # Also valid
```

**Migration tip:** Try BLOCK sizes that exactly divide your dimensions.

### 2. Grid Size Limits

**GPU:** Large grids generally okay

**NPU:** Single dimension limited to 65536

```python
# Before (GPU): Might work
grid = (B * S * N * cdiv(D, BLOCK_D),)  # Could exceed 65536

# After (NPU): Use 2D grid if needed
grid = (B * S * N, cdiv(D, BLOCK_D))  # Split dimensions
```

### 3. 2D Broadcasting Issues

**GPU:** 2D tensor broadcasting works reliably

**NPU:** May cause precision issues

```python
# Before (GPU): Works fine
result = tensor_a[:, None] * tensor_b[None, :]

# After (NPU): Use explicit expansion for small N
# If N is small (e.g., 4), expand explicitly:
val_0 = tl.load(ptr + 0)
val_1 = tl.load(ptr + 1)
val_2 = tl.load(ptr + 2)
val_3 = tl.load(ptr + 3)
result_0 = val_0 * vector
result_1 = val_1 * vector
# ...
```

### 4. Multi-Core Parallelism

**GPU:** Warps within blocks

**NPU:** Vector sub-blocks with `tl.parallel`

```python
# NPU-specific: Dual vector core parallelism
SUB_SIZE: tl.constexpr = BLOCK_SIZE // 2
for s in tl.parallel(0, 2, bind_sub_block=True):
    sub_data = tl.extract_slice(data, (s * SUB_SIZE,), (SUB_SIZE,), (1,))
    # Process on separate vector cores
```

### 5. Synchronization

**GPU:**
```python
tl.debug_barrier()  # Block-level barrier
```

**NPU:**
```python
# Cross-core synchronization
tl.sync_block_all(mode, event_id)
tl.sync_block_set(sender, receiver, event_id)
tl.sync_block_wait(sender, receiver, event_id)
```

### 6. Atomic Operations

Both support similar atomics, but NPU has specific patterns:

```python
# Both platforms
tl.atomic_add(ptr, val, mask=mask)
tl.atomic_max(ptr, val, mask=mask)
tl.atomic_min(ptr, val, mask=mask)
```

### 7. Matrix Multiplication

**GPU:**
```python
acc = tl.dot(a, b, acc)  # Uses tensor cores
```

**NPU:**
```python
acc = tl.dot(a, b, acc)  # Uses Cube unit
```

Same API, but NPU benefits from CV fusion pattern for post-processing.

## Performance Optimization Differences

### GPU Optimization Focus

- Maximize tensor core utilization
- Minimize shared memory bank conflicts
- Optimize warp divergence
- L2 cache tiling

### NPU Optimization Focus

- Minimize grid block count (reduce scheduling overhead)
- Balance Cube/Vector workload (CV fusion)
- Utilize dual vector cores (`tl.parallel`)
- Optimize UB (Unified Buffer) usage
- Use appropriate BLOCK sizes (not limited to power of 2)

## Autotune Configuration Migration

**GPU:**
```python
@triton.autotune(
    configs=[
        triton.Config({'BLOCK_M': 128, 'BLOCK_N': 256, 'BLOCK_K': 64}, num_warps=8),
        triton.Config({'BLOCK_M': 64, 'BLOCK_N': 256, 'BLOCK_K': 32}, num_warps=4),
    ],
    key=['M', 'N', 'K'],
)
```

**NPU:**
```python
@triton.autotune(
    configs=[
        triton.Config(
            {'BLOCK_M': 128, 'BLOCK_N': 128, 'BLOCK_K': 128},
            num_warps=4,
            # NPU-specific options
            multibuffer=True,
            enable_auto_bind_sub_block=True,
        ),
        triton.Config(
            {'BLOCK_M': 64, 'BLOCK_N': 64, 'BLOCK_K': 64},
            num_warps=4,
            multibuffer=False,
        ),
    ],
    key=['M', 'N', 'K'],
)
```

## Common Migration Issues

### Issue 1: Import Error

```
ModuleNotFoundError: No module named 'torch_npu'
```

**Solution:** Install torch_npu or ensure CANN environment is set up.

### Issue 2: Device Not Found

```
RuntimeError: NPU device not found
```

**Solution:**
```bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh
```

### Issue 3: Compilation Error

```
Error: bishengir-compile not found
```

**Solution:**
```bash
export PATH=/path/to/bisheng_toolkit/bishengir/bin:$PATH
```

### Issue 4: UB Overflow

```
Error: UB overflow
```

**Solution:** Reduce BLOCK sizes (NPU UB is limited, typically ~256KB).

### Issue 5: Precision Mismatch

**Solution:**
- Avoid 2D broadcasting patterns
- Use explicit variable expansion for small dimensions
- Match dtype handling between reference and kernel

## Migration Checklist

- [ ] Add `import torch_npu`
- [ ] Change `device='cuda'` to `device='npu'`
- [ ] Check grid size limits (max 65536 per dimension)
- [ ] Replace 2D broadcasting with explicit expansion if needed
- [ ] Tune BLOCK sizes (try non-power-of-2 values)
- [ ] Add NPU-specific autotune options if using autotune
- [ ] Consider CV fusion for matmul + post-processing
- [ ] Profile with msprof to identify bottlenecks
- [ ] Validate accuracy against PyTorch reference

## Further Reading

- [Ascend API Reference](./ascend-api-reference.md)
- [NPUOptions Reference](./npu-options.md)
- [CV Fusion Pattern](./cv-fusion-pattern.md)
- [Triton-Ascend Pitfalls](./triton-ascend-pitfalls.md)
