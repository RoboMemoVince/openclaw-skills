# Triton-Ascend Script Execution in Docker: Troubleshooting Checklist

This document summarizes typical errors encountered when running triton operator scripts inside the `triton-ascend-hcq` Docker container (including accuracy and performance testing), their root causes, and solutions for quick environment and Triton kernel compilation issue diagnosis.

## 1. Working Execution Command (Final)

Execute from host:

```bash
docker exec triton-ascend-hcq bash -lc '
  source /usr/local/Ascend/ascend-toolkit/latest/bin/setenv.bash &&
  export PATH=<BISHENG_TOOLKIT_BIN>:$PATH &&
  python3 -u <YOUR_SCRIPT>.py
'
```

Key points:
- Must `source` Ascend Toolkit's `setenv.bash`, otherwise `torch_npu` may have missing libraries.
- Must ensure `bishengir-compile` is in `PATH`, otherwise Triton-Ascend backend falls back to looking for `npuc` and reports executable not found.

## 2. Error: `python: command not found`

### Symptom

Inside container:

```bash
docker exec triton-ascend-hcq bash -lc 'python -u xxx.py'
```

Reports:
- `bash: line 1: python: command not found`

### Root Cause

Container image only provides `python3`, the `python` alias is not guaranteed to exist.

### Solution

Use `python3` instead:

```bash
docker exec triton-ascend-hcq bash -lc 'python3 -u xxx.py'
```

## 3. Error: `ImportError: libhccl.so: cannot open shared object file`

### Symptom

Running `python3 -u mhc_triton_post_v2.1.py` directly fails when importing `torch_npu`:
- `ImportError: libhccl.so: cannot open shared object file`

### Root Cause

Ascend runtime dynamic libraries (including HCCL) are not added to `LD_LIBRARY_PATH` / Ascend environment is not properly initialized.

### Solution

Execute inside container first:

```bash
source /usr/local/Ascend/ascend-toolkit/latest/bin/setenv.bash
```

This script sets necessary environment variables (such as `ASCEND_HOME_PATH/ASCEND_OPP_PATH` and related library paths), enabling `torch_npu` to load correctly.

## 4. Error: `FileNotFoundError: [Errno 2] No such file or directory: 'npuc'`

### Symptom

First-time JIT compilation of Triton kernel fails, logs show:
- `ERROR: Invalid bishengir path format: npuc`
- `FileNotFoundError: [Errno 2] No such file or directory: 'npuc'`

### Root Cause (Core)

Triton-Ascend backend uses `shutil.which("bishengir-compile")` to find the compiler:
- If `bishengir-compile` exists in `PATH`: uses it directly.
- If not found: attempts to read `TRITON_NPU_COMPILER_PATH` and construct `$TRITON_NPU_COMPILER_PATH/npuc`.

When neither is properly configured, it results in "got `npuc` but no such binary exists in system" failure.

### Solution Steps

1) Find the actual `bishengir-compile` in Ascend Toolkit:

Common path (this environment):
- `<ASCEND_TOOLKIT_DIR>/bisheng_toolkit/bishengir/bin/bishengir-compile`

2) Add that directory to `PATH`:

```bash
export PATH=<BISHENG_TOOLKIT_BIN>:$PATH
```

3) Then run the script, Triton can find the correct compiler and complete JIT.

Note: In this environment `TRITON_NPU_COMPILER_PATH` is empty, so must rely on `PATH` to find `bishengir-compile`.

## 5. Triton Compilation Error: `unsupported tensor index: constexpr[0]`

### Symptom

New bmm kernel fails during compilation:
- `ValueError('unsupported tensor index: constexpr[0]')`

### Root Cause

Used unsupported index form on Triton tensor (e.g., using `acc[:, 0]` column slice on 2D tensor, which triggers restrictions in certain backends/versions).

### Solution

Avoid using column slices for write-back. Instead use 2D pointer + 2D store, or first reduce the needed result via `tl.sum` etc. to 1D, then directly `tl.store(ptr + r, vec)`.

Final implementation approach in this case:
- Keep 2D `acc` in kernel for `tl.dot`
- Use `tl.sum(acc, axis=1)` to reduce to `[4]` then store

## 6. Triton/adapter Crash: `strides must not be zero`

### Symptom

Compilation stage (triton-adapter-opt) reports:
- `<unknown>:0: error: strides must not be zero`

Accompanied by many similar messages:
- `PteAnalysis: load pointer must originate from 'addptr' operation`

### Root Cause (Common Trigger)

When constructing load pointers using "zero-stride 2D pointer trick" (e.g., using `0 * r[:, None]` to broadcast 1D vector to 2D), it's easily interpreted by backend as illegal layout or causes stride inference to be 0, triggering adapter assertion.

### Solution

Do not use "zero-stride pointers" for broadcasting.

Fix in this case:
- First load 1D `hout_vec: [BLOCK_D]`
- Use `hout_vec[None, :] + tl.zeros((4, BLOCK_D), ...)` for explicit broadcast to `[4, BLOCK_D]`

This avoids constructing stride=0 pointer layout and allows backend to more stably recognize as valid tensor computation.

## 7. Quick Troubleshooting Path (Summary)

When running Triton-Ascend scripts inside container fails, troubleshoot in this order:

1) Does `python` / `python3` exist?
2) Did you `source .../setenv.bash`? (Solves `torch_npu` missing libraries / can't find `libhccl.so`, etc.)
3) Can `which bishengir-compile` find it? If not, add bishengir's bin directory to `PATH`.
4) If entering Triton compilation errors: prioritize checking if kernel indexing/broadcast patterns trigger backend restrictions (avoid `acc[:, 0]`, avoid stride=0 pointer broadcasts).
