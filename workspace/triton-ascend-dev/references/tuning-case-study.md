# mHC Pre-Only Triton-Ascend Operator Development and Tuning Full Process (Including Trial-and-Error)

This document provides a retrospective of implementing the **HC_PRE_only_forward** (Pre-only forward) Triton-Ascend operator in `mHC/pre_only/test_code` and performing performance tuning, including key design decisions, validation methods, profiling results, and intermediate trial-and-error with rollbacks.

> Related files:
> - Requirements/formula document: [mHC_pre_only.md](../demo/mhc_pre_only/mHC_pre_only.md)
> - Triton kernel implementation: [hc_pre_only_fwd_triton.py](../demo/mhc_pre_only/hc_pre_only_fwd_triton.py)
> - PyTorch reference: [hc_pre_only_fwd_ref.py](../demo/mhc_pre_only/hc_pre_only_fwd_ref.py)
> - Test script: [hc_pre_only_fwd_test.py](../demo/mhc_pre_only/hc_pre_only_fwd_test.py)
> - Utility functions: [utils.py](../tools/utils.py)

---

## 1. Background and Objectives

### 1.1 Target Operator

Implement `HC_PRE_only_forward`, with input/output and computation flow defined by [mHC_pre_only.md](../demo/mhc_pre_only/mHC_pre_only.md):

- Inputs:
  - `x`: `[B,S,N,D]`, BF16
  - `hc_weight`: `[N*D, N]`, FP32
  - `alpha_pre`: scalar, FP32
  - `bias_pre`: `[N]`, FP32
  - `norm_eps` / `hc_eps`: scalars FP32
  - `gamma`: optional (commented in docs), we keep as optional parameter in implementation (for compatibility with other mHC paths)
- Output:
  - `h_in`: `[B,S,D]`, BF16

### 1.2 Key Computation (Per Documentation)

Let `M=B*S`, `K=N*D`:

1. `x_rs = Cast(x).reshape(B,S,K)` (FP32)
2. `H = x_rs @ hc_weight` (FP32, shape `[B,S,N]`)
3. `inv_rms = rsqrt(mean(x_rs^2, dim=-1, keepdim=True) + norm_eps)` (FP32)
4. `H_pre = sigmoid(alpha_pre * (H * inv_rms) + bias_pre) + hc_eps` (FP32)
5. `h_in = reduce_n(H_pre ⊙ x_rs_reshape_to_[B,S,N,D], dim=n)` (BF16 output)

---

## 2. Development Environment and Execution

### 2.1 Key Point: Must Run Inside triton-ascend Container

Initially running scripts directly on host would report:

- `ModuleNotFoundError: No module named 'torch_npu'`

Therefore, uniformly run inside container (consistent with skill recommendations):

```bash
docker exec -itu root triton-ascend-hcq /bin/bash -lc '
  source /usr/local/Ascend/ascend-toolkit/latest/bin/setenv.bash &&
  export PATH=<BISHENG_TOOLKIT_BIN>:$PATH &&
  cd <YOUR_WORKDIR> &&
  python3 hc_pre_only_fwd_test.py --B 1 --S 32 --N 4 --D 256 --no-profile
'
```

### 2.2 Test and Profiling Shape Set

Reuse mHC basic test set (consistent with skill documentation):

- `(B,S,N,D) ∈ {(1,1024,4,5120),(1,2048,4,2560),(1,4096,4,2560),(1,2048,4,5120)}`

---

## 3. Implementation Approach (Design Decisions and Structure)

### 3.1 Kernel Split and Fusion Strategy

Chose **two-stage** (1 fused + 1 reduction):

1. **Fused Kernel (Kernel A)**: `x` streaming load, completes:
   - `sumsq(K) → inv_rms`
   - `dot(x, hc_weight) → H`
   - `H_pre = sigmoid(alpha*(H*inv_rms) + bias) + eps`
   - Outputs: `inv_rms[M] fp32` (for debugging/optional use) and `H_pre[M,N] fp32`

2. **Reduction Kernel (Kernel B)**:
   - Reads `x[M,N,D]` (bf16) and `H_pre[M,N]` (fp32)
   - `h_in[M,D] = sum_n(x * H_pre)`, outputs bf16

Reasons for choosing two-stage:

- `H_pre[M,N]` is very small (at N=4, each row is ~16B level), write-back cost is very low
- `h_in` is large output (`M*D`), separate kernel makes it easier to control UB/parallelism strategy

### 3.2 Constraints and Optimization: N=4 Specialization

This implementation first specializes for mHC common configuration `N=4` (`h_in_kernel_n4`), reasons:

- `sum_n` dimension fixed at 4, can use simpler unrolling and lower overhead memory patterns
- Also easier to stably pass Ascend backend compilation and UB limits

Also did **column padding** for `hc_weight` (only enabled when `N=4` and `hc_weight.shape[1]=4`):

- Pad `[K,4]` to `[K,24]` (variable `NT=24`)
- Goal: Improve dot alignment and cube utilization, reduce probability of backend generating inefficient tiles

Implementation location: `_maybe_pad_weight_for_dot()` in [hc_pre_only_fwd_triton.py](../demo/mhc_pre_only/hc_pre_only_fwd_triton.py)

---

## 4. Correctness Validation Method

### 4.1 Reference Implementation

Implemented `hc_pre_only_reference()` (PyTorch) in script as accuracy gold standard, line-by-line correspondence with documentation:

- fp32 computation: `x_flat.float()`, `matmul`, `rsqrt`, `sigmoid`
- Output cast to bf16

### 4.2 Accuracy Check

Use utility function `assert_close_like_example()` for segmented accuracy assertion:

- `|golden| < 1` uses `atol`
- Otherwise uses `rtol`

Used to compare `h_in(bf16->fp32)`.

---

## 5. Performance Evaluation Method (bench + profiler)

### 5.1 bench Metrics

`bench()` resets peak memory after warmup, then times fn calls in measurement interval, reporting:

- Average duration (us)
- Peak memory increment (MB/MiB metrics)

This metric shows "double output simultaneously present causing ~2x output size" phenomenon.

### 5.2 profiler Metrics

`profiler_wrapper()` first triggers compilation warmup, then performs 10 active profiling runs, finally parsing and printing average duration (us) for each kernel in `kernel_details.csv`.

Used to identify bottlenecks:

- `hc_matmul_pre_only_kernel_*`: fused dot/rsqrt/sigmoid
- `h_in_kernel_n4`: reduction to generate output

---

## 6. Trial-and-Error and Fixes: Key Issues and Resolution Process

This section records in "problem → symptom → diagnosis → fix/rollback" format.

### 6.1 Problem A: Host Machine Missing torch_npu

- Symptom:
  - `ModuleNotFoundError: No module named 'torch_npu'`
- Conclusion:
  - Must run inside `triton-ascend-hcq` container
- Fix:
  - All run/bench/profiler changed to `docker exec ... setenv.bash ... python3 ...`

### 6.2 Problem B: h_in Kernel UB Overflow (BLOCK_D=256)

#### Symptom

First run inside container (small shape), `h_in_kernel_n4` compilation failed with error similar to:

- `ub overflow, requires 2625536 bits while 1572864 bits available!`

#### Diagnosis

`h_in_kernel_n4` stores in UB a tile of `x`: shape `(BLOCK_M, 4, BLOCK_D)`, plus some temporaries and `h`.

When `BLOCK_D` is large (e.g., 256), backend-generated UB requirement exceeds hardware limit, causing direct compilation failure.

#### Fix

Reducing `BLOCK_D` from 256 to 128 achieved stable compilation.

This is why the final script's `h_in_kernel_n4` defaults to `BLOCK_D=128`.

### 6.3 Problem C: Attempting to Increase Fused Kernel's BLOCK_K to 256 Caused Compilation Failure

#### Symptom

To accelerate fused kernel (dot's K loop), attempted `BLOCK_K` from 128 → 256, result was compilation failure on large shapes, with errors including:

- Multiple `Unsupported op for finding the root alloc` (e.g., `hivm.hir.vcast` / `hivm.hir.load`)
- Accompanied by UB overflow:
  - `ub overflow, requires 1575168 bits while 1572864 bits available!`

#### Conclusion

`BLOCK_K=256` in this kernel's overall tile combination triggered backend UB boundary issues (even exceeding UB by only 2304 bits), thus unusable.

#### Resolution

Rolled back and continued searching for viable compromise, finally chose `BLOCK_K=192`:

- Compiles successfully
- Significantly reduces fused kernel duration on large shapes

### 6.4 Problem D: Attempting to Increase h_in Kernel's BLOCK_D to 192 Still Caused UB Overflow

To further reduce `h_in_kernel_n4` duration, attempted `BLOCK_D=192`:

- Result was UB overflow again during profiling (requires 1970176 bits > 1572864 bits)

Finally rolled back to `BLOCK_D=128` to ensure stability.

---

## 7. Tuning Iterations and Results Display (Including Intermediate Data)

> Note: The following durations are from `Profiler Kernel Avg Duration (us)` output (runs=10), more suitable for comparing kernel body durations.

### 7.1 Baseline (BLOCK_K=128, BLOCK_D=128)

Profiler output on `(1,2048,4,5120)` (key items):

- `hc_matmul_pre_only_kernel_no_gamma`: ~`426 us`
- `h_in_kernel_n4`: ~`105 us`
- Total: ~`531 us`

On `(1,4096,4,2560)`:

- `hc_matmul_pre_only_kernel_no_gamma`: ~`373 us`
- `h_in_kernel_n4`: ~`105 us`
- Total: ~`478 us`

### 7.2 Tuning 1: BLOCK_K=192 (Success)

After setting fused kernel's `BLOCK_K` to 192:

On `(1,2048,4,5120)`:

- `hc_matmul_pre_only_kernel_no_gamma`: ~`352 us`
- `h_in_kernel_n4`: ~`106 us`
- Total: ~`458 us` (~`-14%` vs baseline)

On `(1,4096,4,2560)`:

- `hc_matmul_pre_only_kernel_no_gamma`: ~`303 us`
- `h_in_kernel_n4`: ~`105 us`
- Total: ~`408 us` (~`-15%` vs baseline)

### 7.3 Tuning 2: Attempting BLOCK_D=192 (Failed, Rolled Back)

Goal: Reduce `h_in_kernel_n4` duration (its proportion ~20%~25%).

Result: `BLOCK_D=192` compilation failed (UB overflow), so rolled back to `BLOCK_D=128`.

---

## 8. Final Delivery State (Current Script Default Configuration)

Final stable configuration:

- Fused kernel: `BLOCK_M=64, BLOCK_K=192`
- Reduction kernel: `BLOCK_M=32, BLOCK_D=128`
- Supports optional `gamma` input (default test/tuning phase uses `--no-gamma` for no-gamma path)
- `N=4` required (aligned with mHC common configuration)

Files:

- Triton kernel implementation: [hc_pre_only_fwd_triton.py](../demo/mhc_pre_only/hc_pre_only_fwd_triton.py)

---

## 9. Future Optimization Directions (Not Implemented in This Round)

1. **Autotune**:
   - Currently using fixed meta parameters. Future could introduce `@triton.autotune` to automatically select `BLOCK_K/BLOCK_D` across different shapes (note UB upper limit constraints, candidates need to be chosen carefully)

2. **Further Reduce h_in Kernel Proportion**:
   - Currently `h_in` kernel is near UB upper limit, increasing BLOCK_D easily overflows
   - Could explore different layout/blocking strategies (e.g., smaller BLOCK_M, higher parallelism) to improve throughput without increasing UB

3. **Generalize N**:
   - If future needs to support N!=4, would need to add corresponding kernels or write more general reduce implementation, and redo UB/performance validation
