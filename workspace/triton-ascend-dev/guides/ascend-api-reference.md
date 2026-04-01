# Ascend Language Extension API Reference

This document provides a comprehensive reference for Triton-Ascend specific APIs that extend the standard Triton language.

## 1. Tensor Slicing Operations

### tl.insert_slice

Insert a source tensor into a target tensor at specified offsets.

```python
result = tl.insert_slice(full, src, offsets, sizes, strides)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `full` | tensor | Target tensor to insert into |
| `src` | tensor | Source tensor to insert |
| `offsets` | tuple[int] | Offset position in target tensor |
| `sizes` | tuple[int] | Size of the source tensor |
| `strides` | tuple[int] | Stride in target tensor |

**Example:**
```python
# Insert a [64, 64] block into a [128, 128] tensor at position (32, 32)
result = tl.insert_slice(
    full_tensor,           # [128, 128]
    sub_block,             # [64, 64]
    offsets=(32, 32),
    sizes=(64, 64),
    strides=(1, 1)
)
```

### tl.extract_slice

Extract a slice from a tensor at specified offsets.

```python
result = tl.extract_slice(full, offsets, sizes, strides)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `full` | tensor | Source tensor to extract from |
| `offsets` | tuple[int] | Starting offset position |
| `sizes` | tuple[int] | Size of the extracted slice |
| `strides` | tuple[int] | Stride in source tensor |

**Example:**
```python
# Extract a [64, 128] slice from position (0, 0)
sub_block = tl.extract_slice(
    full_tensor,           # [128, 128]
    offsets=(0, 0),
    sizes=(64, 128),
    strides=(1, 1)
)
```

### tl.get_element

Read a single scalar element from a tensor at specified offset.

```python
scalar = tl.get_element(source, offset)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `source` | tensor | Source tensor |
| `offset` | tuple[int] | Index of the element to extract |

---

## 2. Custom Memory Operations

### tl.custom_op / al.custom

Invoke Ascend-specific custom operations for optimized memory access patterns.

```python
from triton.language.extra.cann import extension as al

result = al.custom("op_name", arg1, arg2, ..., out=output_tensor)
```

### Available Custom Operations

| Operation | Description | Use Case |
|-----------|-------------|----------|
| `index_select` | Gather data along dimension by indices | Embedding lookup |
| `index_put` | Scatter indexed values into tensor | Gradient accumulation |
| `gather_out_to_ub` | Gather from GM to UB with boundary check | Optimized gather |
| `scatter_ub_to_out` | Scatter from UB to GM | Optimized scatter |
| `indirect_load` | Load from indirect address | Sparse access |
| `indirect_store` | Store to indirect address | Sparse write |
| `index_select_simd` | SIMD-accelerated index select | Large-scale embedding |

### index_select Example

```python
result = al.index_select(
    src=src_tensor,           # Source tensor
    index=indices,            # Index tensor
    dim=0,                    # Gather dimension
    index_boundary=max_idx,   # Index upper bound
    default_value=0.0         # Value for out-of-bounds
)
```

### gather_out_to_ub Example

```python
result = al.gather_out_to_ub(
    src=src_ptr,
    index=indices,
    index_boundary=max_idx,
    dim=0,
    src_stride=(stride_d0, stride_d1, ...),
    start_offset=(0, 0, ...),
    end_offset=(size_d0, size_d1, ...)
)
```

### scatter_ub_to_out Example

```python
al.scatter_ub_to_out(
    dst=dst_ptr,
    src=ub_data,
    index=indices,
    dim=0,
    dst_stride=(stride_d0, stride_d1, ...)
)
```

---

## 3. Parallel Execution

### tl.parallel

Iterator for parallel execution across multiple vector cores (dual-core on Ascend 910B).

```python
for s in tl.parallel(start, end, bind_sub_block=True):
    # Code executed in parallel across cores
    sub_data = tl.extract_slice(data, (s * SUB_SIZE, 0), ...)
    # Process sub_data
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `start` | int | Loop start index |
| `end` | int | Loop end index |
| `bind_sub_block` | bool | Bind iteration to vector sub-block (default: False) |

**CV Fusion Pattern:**
```python
@triton.jit
def matmul_with_cv_fusion(...):
    # Cube computation
    acc = tl.zeros((BLOCK_M, BLOCK_N), dtype=tl.float32)
    for k in range(0, K, BLOCK_K):
        acc = tl.dot(a_block, b_block, acc)

    # Vector post-processing with dual-core parallelism
    SUB_M: tl.constexpr = BLOCK_M // 2
    for s in tl.parallel(0, 2, bind_sub_block=True):
        sub_acc = tl.extract_slice(acc, (s * SUB_M, 0), (SUB_M, BLOCK_N), (1, 1))
        sub_acc = activation(sub_acc)  # Vector operation
        # Store sub_acc
```

---

## 4. Compiler Hints

### tl.compile_hint / al.compile_hint

Provide hints to the compiler for optimization.

```python
al.compile_hint(tensor, hint_name, hint_value)
```

| Hint Name | Values | Description |
|-----------|--------|-------------|
| `multi_buffer` | 2, 3, 4 | Enable multi-buffering (ping-pong) |
| `overflow_mode` | "saturate", "truncate" | Integer overflow handling |
| `saturate_src_unsigned` | True/False | Unsigned saturation for source |

**Example:**
```python
result = tl.cast(x, tl.int8)
al.compile_hint(result, "multi_buffer", 2)      # Enable double buffering
al.compile_hint(result, "overflow_mode", "saturate")  # Saturate on overflow
```

---

## 5. Synchronization Primitives

For cross-core synchronization in CV-fused kernels.

### tl.sync_block_all

Global synchronization across all blocks.

```python
tl.sync_block_all(mode, event_id)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `mode` | str | Synchronization mode |
| `event_id` | int | Event identifier (0-15) |

### tl.sync_block_set

Set a synchronization event (sender side).

```python
tl.sync_block_set(sender, receiver, event_id)
```

### tl.sync_block_wait

Wait for a synchronization event (receiver side).

```python
tl.sync_block_wait(sender, receiver, event_id)
```

**CV Synchronization Example:**
```python
@triton.jit
def cv_fused_kernel(...):
    # Cube computation
    cube_result = tl.dot(a, b)

    # Signal cube completion
    tl.sync_block_set(sender="cube", receiver="vector", event_id=0)

    # Vector waits for cube
    tl.sync_block_wait(sender="cube", receiver="vector", event_id=0)

    # Vector post-processing
    vector_result = activation(cube_result)
```

---

## 6. Enhanced Cast Operations

### tl.cast with Ascend Extensions

```python
result = tl.cast(x, dtype, overflow_mode="saturate")
```

**Supported Features:**
- Floating-point downcast rounding modes (RTNE, RTZ)
- Overflow mode handling (truncate or saturate)
- Special handling for fp8 and bf16 conversions

**Example:**
```python
# Cast to int8 with saturation
int8_result = tl.cast(fp32_tensor, tl.int8, overflow_mode="saturate")

# Cast to fp8 (requires FP8 support)
fp8_result = tl.fp_to_fp(fp16_tensor, dtype=tl.float8e5)
```

---

## 7. Additional Vector Operations

### al.flip

Reverse tensor along specified dimension.

```python
result = al.flip(tensor, dim=0)
```

### al.sort

Sort tensor along last dimension.

```python
sorted_tensor = al.sort(tensor, descending=False)
```

---

## 8. Custom Operation Registration

For advanced users who need to register custom operations.

```python
from triton.language.extra.cann.extension import register_custom_op, CORE, PIPE, MODE

@register_custom_op
class my_custom_op:
    name = 'my_custom_op'
    core = CORE.VECTOR      # VECTOR or CUBE
    pipe = PIPE.PIPE_V      # Pipeline: PIPE_V, PIPE_M, PIPE_MTE1/2/3
    mode = MODE.SIMD        # SIMD or SIMT

    def __init__(self, src, dst, _builder=None):
        self.arg_type = {'src': src.dtype, 'dst': dst.dtype}
        # Optional: custom implementation
        # self.source = "path/to/impl.cce"
        # self.compile = "bisheng compile cmd"
```

**Core Types:**
- `CORE.VECTOR` - Vector compute unit
- `CORE.CUBE` - Matrix compute unit (Cube)

**Pipeline Types:**
- `PIPE.PIPE_S` - Scalar pipeline
- `PIPE.PIPE_V` - Vector pipeline
- `PIPE.PIPE_M` - Matrix pipeline
- `PIPE.PIPE_MTE1/2/3` - Data movement pipelines

---

## Quick Reference Table

| Category | API | Purpose |
|----------|-----|---------|
| **Slicing** | `tl.insert_slice` | Insert tensor into another |
| | `tl.extract_slice` | Extract tensor slice |
| | `tl.get_element` | Read single element |
| **Memory** | `al.index_select` | Gather by indices |
| | `al.index_put` | Scatter by indices |
| | `al.gather_out_to_ub` | GM→UB gather |
| | `al.scatter_ub_to_out` | UB→GM scatter |
| **Parallel** | `tl.parallel` | Multi-core iteration |
| **Hints** | `al.compile_hint` | Compiler optimization hints |
| **Sync** | `tl.sync_block_*` | Cross-core synchronization |
| **Vector** | `al.flip` | Reverse tensor |
| | `al.sort` | Sort tensor |

---

## Code Location References

- Extension definitions: `third_party/ascend/language/cann/extension/`
  - `mem_ops.py` - Memory operations
  - `vec_ops.py` - Vector operations
  - `aux_ops.py` - Auxiliary operations (parallel, compile_hint, sync)
  - `math_ops.py` - Math operations
  - `custom_op.py` - Custom operation registration
- Base language: `python/triton/language/`
