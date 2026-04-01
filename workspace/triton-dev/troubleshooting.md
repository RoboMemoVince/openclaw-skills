# Triton-Ascend Environment Troubleshooting Checklist

This document summarizes typical errors encountered when running triton operator scripts on Ascend NPU environments (host or container), their root causes, and solutions for quick environment and Triton kernel compilation issue diagnosis.

## 1. Environment Self-Check (Run First)

Before troubleshooting specific errors, run all checks:

```bash
python3 -c "import triton; print('triton:', triton.__version__)"
python3 -c "import torch_npu; import torch; print('NPU available:', torch.npu.is_available())"
echo "ASCEND_HOME_PATH=$ASCEND_HOME_PATH"
which bishengir-compile
npu-smi info | head -10
```

If any check fails, source the CANN env script:

```bash
# Pick the one that exists on your machine:
source $HOME/Ascend/ascend-toolkit/set_env.sh                    # non-root default
source /usr/local/Ascend/ascend-toolkit/latest/bin/setenv.bash   # root default
source $HOME/Ascend/cann-<version>/set_env.sh                    # specific version
```

Once all checks pass, run your script directly:

```bash
python3 -u <YOUR_SCRIPT>.py
```

Key points:
- Must source CANN env script, otherwise `torch_npu` may have missing libraries.
- Must ensure `bishengir-compile` is in `PATH`, otherwise Triton-Ascend backend falls back to looking for `npuc` and reports executable not found.

## 2. Error: `python: command not found`

### Symptom

```
bash: line 1: python: command not found
```

### Root Cause

Some environments only provide `python3`, the `python` alias is not guaranteed to exist.

### Solution

Use `python3` instead of `python`.

## 3. Error: `ImportError: libhccl.so: cannot open shared object file`

### Symptom

Running script fails when importing `torch_npu`:
- `ImportError: libhccl.so: cannot open shared object file`

### Root Cause

Ascend runtime dynamic libraries (including HCCL) are not added to `LD_LIBRARY_PATH` / Ascend environment is not properly initialized.

### Solution

Source the CANN env script:

```bash
# This sets ASCEND_HOME_PATH, LD_LIBRARY_PATH, and related variables
source $HOME/Ascend/ascend-toolkit/set_env.sh          # non-root
source /usr/local/Ascend/ascend-toolkit/latest/bin/setenv.bash  # root
```

Tip: add the source command to your `~/.bashrc` so it persists across sessions.

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

1) Find the actual `bishengir-compile` in your CANN installation:

```bash
find $ASCEND_HOME_PATH -name "bishengir-compile" -type f 2>/dev/null
```

Common locations:
- `$ASCEND_HOME_PATH/tools/bishengir/bin/bishengir-compile`
- `$ASCEND_HOME_PATH/bin/bishengir-compile`
- `<ascend-toolkit-dir>/bisheng_toolkit/bishengir/bin/bishengir-compile`

2) Add that directory to `PATH`:

```bash
export PATH=<found_bishengir_bin_dir>:$PATH
```

3) Then run the script, Triton can find the correct compiler and complete JIT.

Note: If `TRITON_NPU_COMPILER_PATH` is empty, Triton relies solely on `PATH` to find `bishengir-compile`.

## 5. Error: `Can't find libdcmi.so` (msprof)

### Symptom

Running `msprof op ...` reports:
- `Can't find libdcmi.so`

### Root Cause

The Ascend driver library path is not in `LD_LIBRARY_PATH`.

### Solution

```bash
export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64:$LD_LIBRARY_PATH
```

This path is typically set by the CANN env script. If not, add it manually.

## 6. Triton Compilation Error: `unsupported tensor index: constexpr[0]`

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

## 7. Triton/adapter Crash: `strides must not be zero`

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

## 8. Quick Troubleshooting Path (Summary)

When running Triton-Ascend scripts fails, troubleshoot in this order:

1) Does `python3` exist?
2) Did you source the CANN env script? (Solves `torch_npu` missing libraries / can't find `libhccl.so`, etc.)
3) Can `which bishengir-compile` find it? If not, locate it and add its directory to `PATH`.
4) Is `ASCEND_HOME_PATH` set? (Required for msprof and runtime.)
5) Is the NPU device visible? (`npu-smi info`)
6) If entering Triton compilation errors: prioritize checking if kernel indexing/broadcast patterns trigger backend restrictions (avoid `acc[:, 0]`, avoid stride=0 pointer broadcasts).
