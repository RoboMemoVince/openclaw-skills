# Triton-Ascend Compiler Pipeline

This document explains the compilation pipeline from Python Triton kernel to executable NPU binary.

## Overview

```
Python Kernel (@triton.jit)
        │
        ▼
┌─────────────────────────────────────┐
│  Triton Frontend (AST → TTIR)       │
│  python/triton/compiler/            │
└────────────────┬────────────────────┘
                 ▼
┌─────────────────────────────────────┐
│  TTIR Optimization Passes           │
│  make_ttir()                        │
│  - inline → combine → canonicalize  │
│  - cse → licm → loop_unroll         │
└────────────────┬────────────────────┘
                 ▼
┌─────────────────────────────────────┐
│  Ascend-Specific Lowering           │
│  ttir_to_linalg()                   │
│  - TritonToStructured               │
│  - TritonToUnstructured             │
│  - TritonToAnnotation               │
│  - TritonToHFusion                  │
│  - TritonToHIVM                     │
│  - TritonToLLVM                     │
│  - TritonToLinalg                   │
└────────────────┬────────────────────┘
                 ▼
┌─────────────────────────────────────┐
│  BiSheng Compiler                   │
│  linalg_to_bin_*()                  │
│  Linalg IR → .o executable binary   │
└────────────────┬────────────────────┘
                 ▼
┌─────────────────────────────────────┐
│  NPU Runtime                        │
│  NPUDriver / NPULauncher            │
│  Load .o and launch via CANN API   │
└─────────────────────────────────────┘
```

## Stage 1: Triton Frontend

**Location:** `python/triton/compiler/`

The Python kernel decorated with `@triton.jit` is parsed and converted to Triton IR (TTIR).

```python
@triton.jit
def my_kernel(x_ptr, y_ptr, N, BLOCK: tl.constexpr):
    pid = tl.program_id(0)
    offs = pid * BLOCK + tl.arange(0, BLOCK)
    mask = offs < N
    x = tl.load(x_ptr + offs, mask=mask)
    tl.store(y_ptr + offs, x * 2, mask=mask)
```

## Stage 2: TTIR Optimization

**Location:** `third_party/ascend/backend/compiler.py:74` (`make_ttir`)

Standard Triton optimization passes:

| Pass | Purpose |
|------|---------|
| `add_inliner` | Inline function calls |
| `add_combine` | Combine operations |
| `add_canonicalizer` | Canonicalize IR |
| `add_cse` | Common subexpression elimination |
| `add_licm` | Loop-invariant code motion |
| `add_symbol_dce` | Dead code elimination |
| `add_loop_unroll` | Loop unrolling |

```python
def make_ttir(mod, metadata, opt):
    pm = ir.pass_manager(mod.context)
    pm.enable_debug()
    passes.common.add_inliner(pm)
    passes.ttir.add_combine(pm)
    passes.common.add_canonicalizer(pm)
    passes.ttir.add_reorder_broadcast(pm)
    passes.common.add_cse(pm)
    passes.common.add_licm(pm)
    passes.common.add_symbol_dce(pm)
    passes.ttir.add_loop_unroll(pm)
    pm.run(mod)
    return mod
```

## Stage 3: Ascend-Specific Lowering

**Location:** `third_party/ascend/backend/compiler.py:97` (`ttir_to_linalg`)

This stage applies Ascend-specific transformations through multiple passes:

### 3.1 TritonToStructured

**Purpose:** Tensorize pointer/mask expressions with integer division and modulo.

| Converter | Description |
|-----------|-------------|
| `RewriteAddPtrOp` | Analyze pointer expressions, model into `PtrState` |
| `CreateAddpr` | Reconstruct pointer calculations without div/mod |
| `RewriteLoadOp` | Analyze mask expressions in `tl.load` |
| `BuildMask` | Reconstruct mask expressions without div/mod |
| `CreateLoad/Store` | Replace load/store with optimized versions |

**Example transformation:**
```python
# Before: complex pointer expression
ptr + x // 1024 * 4096 + x % 1024 * 4 + y

# After: tensorized access pattern
ptr[dim0_offset, dim1_offset]
```

### 3.2 TritonToUnstructured

**Purpose:** Convert non-contiguous memory access to scalar loops.

| Converter | Description |
|-----------|-------------|
| `DiscreteMaskStoreConversion` | Non-contiguous store → load + select + store |
| `DiscreteMaskLoadConversion` | Non-contiguous load → full load + select |
| `UnstructuredMemAccessConverter` | Convert to multi-loop scalar operations |

### 3.3 TritonToAnnotation

**Purpose:** Convert `tl.compile_hint` to backend annotations.

```python
# Python
al.compile_hint(tensor, "multi_buffer", 2)

# IR transformation
triton::AnnotationOp → annotation::MarkOp
```

### 3.4 TritonToHFusion

**Purpose:** Convert histogram operations to HFusion dialect.

```python
triton::HistogramOp → hfusion::HistogramOp
```

### 3.5 TritonToHIVM

**Purpose:** Convert block synchronization to HIVM dialect.

| Triton Op | HIVM Op |
|-----------|---------|
| `sync_block_all` | Global block sync |
| `sync_block_set` | Set sync point |
| `sync_block_wait` | Wait for sync point |

### 3.6 TritonToLLVM

**Purpose:** Convert inline assembly to LLVM dialect.

```python
triton::ElementwiseInlineAsmOp → LLVM::InlineAsmOp
```

### 3.7 TritonToLinalg

**Purpose:** Final conversion to Linalg IR (40+ converters).

| Converter | Triton Op | Linalg Op |
|-----------|-----------|-----------|
| `StoreConverter` | `triton::StoreOp` | `memref::copy` |
| `LoadConverter` | `triton::LoadOp` | `memref::copy + bufferization::ToTensorOp` |
| `MatmulConverter` | `triton::DotOp` | `linalg::MatmulOp` |
| `ReduceConverter` | `triton::ReduceOp` | `linalg::ReduceOp` |
| `BroadcastConverter` | `triton::BroadcastOp` | `linalg::BroadcastOp` |
| `TransposeConverter` | `triton::TransOp` | `linalg::TransposeOp` |

## Stage 4: BiSheng Compiler

**Location:** `third_party/ascend/backend/compiler.py:521` (`linalg_to_bin_enable_npu_compile_A2_A3`)

The BiSheng compiler (`bishengir-compile`) converts Linalg IR to NPU executable binary.

### Compilation Options

Key options passed to BiSheng:

| Option | Description |
|--------|-------------|
| `--target=<arch>` | Target architecture (e.g., `Ascend910B1`) |
| `--enable-auto-multi-buffer=<bool>` | Enable ping-pong buffering |
| `--enable-auto-bind-sub-block=<bool>` | Auto-bind to vector sub-blocks |
| `--enable-hivm-compile=true` | Enable HIVM compilation |
| `--enable-triton-kernel-compile=true` | Triton kernel mode |

### Compilation Flow

```
Linalg IR (kernel.ttadapter.mlir)
        │
        ▼
   bishengir-compile
        │
        ├── HIVM scheduling
        ├── Multi-buffer optimization
        ├── CV balance optimization
        ├── Vectorization
        │
        ▼
   kernel.o (NPU binary)
```

## Stage 5: NPU Runtime

**Location:** `third_party/ascend/backend/driver.py`

### NPUDriver

- Interfaces with CANN runtime
- Provides device properties (num_aicore, arch)
- Manages device memory

### NPULauncher

- Generates C++ launcher stub for each kernel signature
- Compiles stub to `.so` shared library
- Launches kernel via `rtKernelLaunch` CANN API

```python
class NPULauncher:
    def __init__(self, src, metadata):
        # Generate C++ wrapper
        wrapper_src = generate_npu_wrapper_src(...)
        # Compile to .so
        so_path = make_npu_launcher_stub(header_src, wrapper_src)
        # Load launcher
        self.launch = getattr(mod, "launch")

    def __call__(self, *args, **kwargs):
        self.launch(*args, **kwargs)
```

## Intermediate Artifacts

When `debug=True`, the following files are dumped:

| File | Stage | Content |
|------|-------|---------|
| `kernel.ttir.mlir` | After TTIR optimization | Triton IR |
| `kernel.ttadapter.mlir` | After Ascend lowering | Linalg IR |
| `kernel.llir.mlir` | CPU mode only | LLVM MLIR |
| `kernel.ll` | CPU mode only | LLVM IR |
| `kernel.o` | Final | NPU binary |

## Debug Tips

### Enable IR Dumping

```python
# Set debug=True in compile options
triton.compile(
    kernel,
    signature={...},
    options={"debug": True}
)
```

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `TRITON_PRINT_AUTOTUNING` | Print autotune decisions |
| `TRITON_DEBUG` | Enable debug output |
| `TRITON_CACHE_DIR` | Override cache directory |

### Inspect Cached Artifacts

```bash
# Default cache location
ls ~/.triton/cache/<hash>/

# Files:
# - kernel.ttir.mlir
# - kernel.ttadapter.mlir
# - kernel.npubin
```

## Code Location Summary

| Component | Location |
|-----------|----------|
| Triton Frontend | `python/triton/compiler/` |
| TTIR Passes | `lib/Conversion/`, `include/triton/Conversion/` |
| Ascend Backend | `third_party/ascend/backend/compiler.py` |
| NPU Driver | `third_party/ascend/backend/driver.py` |
| Ascend Passes (C++) | `third_party/ascend/lib/`, `third_party/ascend/include/` |
| Ascend NPU IR | `third_party/ascend/AscendNPU-IR/` |
