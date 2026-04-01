# NPUOptions: Compilation and Auto-Tuning Parameters

This document provides a comprehensive reference for NPUOptions parameters that control Triton-Ascend compilation and optimization.

## Overview

NPUOptions is defined in `third_party/ascend/backend/compiler.py` (class `NPUOptions`, ~line 774) and controls how kernels are compiled for Ascend NPU.

```python
@triton.autotune(
    configs=[
        triton.Config({"BLOCK_M": 128, "BLOCK_N": 128}, num_warps=4),
        triton.Config({"BLOCK_M": 64, "BLOCK_N": 64}, num_warps=4),
    ],
    key=["M", "N"],
)
@triton.jit
def kernel(...):
    ...
```

## Core Options

### Execution Mode Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `compile_mode` | str | `"simd"` | Compilation mode: `"simd"`, `"unstructured_in_simt"`, `"simt_only"` |
| `parallel_mode` | str | `"simd"` | Execution parallel mode |
| `force_simt_only` | bool | `False` | Force SIMT-only execution |
| `force_simt_template` | bool | `False` | Force SIMT template for unstructured access |
| `mix_mode` | str | `""` | Mix mode: `"aiv"` (vector), `"aic"` (cube), or mixed |

**Compile Mode Details:**

| Mode | Description | Use Case |
|------|-------------|----------|
| `simd` | Default SIMD mode | Most kernels |
| `unstructured_in_simt` | SIMT for unstructured access | Irregular memory patterns |
| `simt_only` | Pure SIMT execution | Shared memory heavy kernels |

### Multi-Buffer Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `multibuffer` | bool | `True` (A2/A3) | Enable ping-pong pipeline |
| `limit_auto_multi_buffer_only_for_local_buffer` | bool | `None` | Restrict multi-buffer to local buffers only |
| `limit_auto_multi_buffer_of_local_buffer` | str | `None` | Multi-buffer limit for local buffers |
| `set_workspace_multibuffer` | int | `None` | Workspace multi-buffer count |

**Multi-buffer and msprof correlation:**
- High `wait_ratio` in msprof → Enable `multibuffer=True`
- High `mte2_ratio` → Increase `set_workspace_multibuffer`

### Sub-Block Binding Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enable_auto_bind_sub_block` | bool | `True` (A2/A3) | Auto-bind to vector sub-blocks |
| `auto_tile_and_bind_subblock` | bool | `True` | Auto-tile and bind |

**When to use:**
- CV-fused kernels with `tl.parallel()` + `bind_sub_block=True`
- Dual vector core utilization scenarios

### CV Balance Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enable_hivm_auto_cv_balance` | bool | `None` | Auto Cube/Vector load balance |
| `tile_mix_vector_loop` | int | `None` | Tile size for vector loops in CV-mixed |
| `tile_mix_cube_loop` | int | `None` | Tile size for cube loops in CV-mixed |
| `enable_mixed_cv` | bool | `None` | Enable mixed CV compilation |

**CV balance and msprof correlation:**
- Imbalanced `aic_time` vs `aiv_time` → Tune `tile_mix_*` options
- One unit idle while other works → Enable `enable_hivm_auto_cv_balance`

### Synchronization Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `sync_solver` | bool | `None` | Enable synchronization solver |
| `unit_flag` | bool | `None` | Enable sync unit flag |
| `inject_barrier_all` | bool | `None` | Inject barriers for all ops |
| `inject_block_all` | bool | `None` | Inject block sync for all ops |
| `disable_auto_inject_block_sync` | bool | `None` | Disable auto block sync injection |

**When to use sync options:**
- Race conditions or data hazards → Enable `sync_solver`
- Debugging synchronization issues → Enable `inject_barrier_all`

### Vectorization and Layout Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enable_nd2nz_on_vector` | bool | `False` | ND to NZ layout transform on vector |
| `enable_linearize` | bool | varies | Enable linearization pass |
| `enable_drop_unit_dims` | bool | `None` | Drop unit dimensions |
| `enable_auto_vectorize_v2` | bool | `None` | Enable v2 auto-vectorization |
| `enable_flatten` | bool | `None` | Enable flatten pass (simplify multi-dim to 1D) |

### Memory and UB Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enable_ubuf_saving` | bool | `None` | Enable UB saving optimization |
| `shared_mem_dynamic_size` | int | varies | Dynamic shared memory size |
| `enable_persistent` | bool | `False` | Enable persistent kernel mode |

**UB overflow handling:**
- UB overflow error → Reduce BLOCK sizes or enable `enable_ubuf_saving`
- Default dynamic sizes: 221184 (SIMD), 122880 (SIMT)

### Scheduling and Advanced Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `add_auto_scheduling` | bool | `False` | Enable SSBuffer auto-scheduling pass (DAG sync + scope + ssbuffer) |
| `enable_select_analysis` | bool | `True` | Enable select operation analysis |
| `optimize_dynamic_offset` | bool | `False` | Optimize dynamic offset computations |
| `enable_mask_fallback_conversion` | bool | `False` | Enable mask fallback conversion pass |
| `optimize_epilogue` | bool | `False` | Optimize epilogue code generation |
| `auto_blockify_size` | int | `1` | Auto-blockify size (controls AutoBlockify pass) |
| `stream` | int | `None` | Stream ID for kernel execution |

### BiSheng Compiler Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `bisheng_options` | str | `None` | Additional BiSheng compiler options |
| `vf_merge_level` | int | 1 | VF merge optimization level |
| `enable_cce_vf_auto_sync` | bool | `None` | CCE VF auto sync |
| `enable_cce_vf_remove_membar` | bool | `None` | Remove memory barriers in VF |

## Usage Examples

### Basic Autotune Configuration

```python
def get_autotune_configs():
    return [
        triton.Config(
            {"BLOCK_M": 128, "BLOCK_N": 128, "BLOCK_K": 64},
            num_warps=4,
            # NPU-specific options
            multibuffer=True,
            enable_auto_bind_sub_block=True,
        ),
        triton.Config(
            {"BLOCK_M": 64, "BLOCK_N": 64, "BLOCK_K": 32},
            num_warps=4,
            multibuffer=False,
        ),
    ]

@triton.autotune(configs=get_autotune_configs(), key=["M", "N", "K"])
@triton.jit
def matmul_kernel(...):
    ...
```

### CV-Fused Kernel Configuration

```python
triton.Config(
    {"BLOCK_M": 128, "BLOCK_N": 128},
    enable_auto_bind_sub_block=True,
    enable_hivm_auto_cv_balance=True,
    tile_mix_vector_loop=64,
)
```

### SIMT Mode Configuration

```python
triton.Config(
    {"BLOCK_M": 64, "BLOCK_N": 64},
    compile_mode="simt_only",
    force_simt_only=True,
    shared_mem_dynamic_size=122880,
)
```

### Debugging Configuration

```python
triton.Config(
    {"BLOCK_M": 64, "BLOCK_N": 64},
    debug=True,  # Enable IR dumping
    sync_solver=True,  # Debug sync issues
    inject_barrier_all=True,  # Force barriers
)
```

## Option vs msprof Signal Mapping

| msprof Signal | Indicates | Relevant Options |
|---------------|-----------|------------------|
| High `wait_ratio` | Memory stalls | `multibuffer`, `set_workspace_multibuffer` |
| High `scalar_ratio` | Too many blocks | Increase BLOCK sizes, reduce grid |
| Low `vec_ratio` | Vector underutilized | `enable_auto_bind_sub_block` |
| Imbalanced CV time | CV load imbalance | `enable_hivm_auto_cv_balance`, `tile_mix_*` |
| High `mte2_ratio` | Memory transfer bottleneck | `multibuffer`, layout optimization |
| Low `bandwidth_usage_rate` | Memory inefficiency | Coalesce accesses, increase BLOCK |
| Low `cache_hit_rate` | Cache misses | Improve data locality |

## Platform-Specific Defaults

| Option | A2/A3 Default | 910_95 Default |
|--------|---------------|----------------|
| `multibuffer` | `True` | `False` |
| `enable_auto_bind_sub_block` | `True` | `False` |
| `compile_on_910_95` | `False` | `True` |

## Code Location

- NPUOptions definition: `third_party/ascend/backend/compiler.py:774` (class NPUOptions)
- Option parsing: `third_party/ascend/backend/compiler.py` (parse_options)
- BiSheng option mapping: 910_95 at `linalg_to_bin_enable_npu_compile_910_95`, A2/A3 at `linalg_to_bin_enable_npu_compile_A2_A3`

## Troubleshooting

### UB Overflow

```
Error: UB overflow
```

**Solutions:**
1. Reduce BLOCK sizes (BLOCK_M, BLOCK_N, BLOCK_K, BLOCK_D)
2. Enable `enable_ubuf_saving=True`
3. Split kernel into smaller stages

### Backend Unsupported Path

```
Error: Backend unsupported operation
```

**Solutions:**
1. Rollback to last working configuration
2. Try different `compile_mode`
3. Disable problematic optimizations

### Sync Issues (Incorrect Results)

**Solutions:**
1. Enable `sync_solver=True`
2. Enable `inject_barrier_all=True` for debugging
3. Check for data races in CV-fused code
