# Iteration Record Template

All iteration records go in `<operator_name>/ITERATIONS.md`. Copy templates below for each iteration.

## Operator Header (once per operator, at top of ITERATIONS.md)

```markdown
# <Operator Name> — Iteration Log

**Operator:** XX
**Shape set:** (B, S, N, D) = ...
**Entry script:** XX_fwd_test.py
**Kernel-name filter:** <kernel_name_substr>
**Start date:** YYYY-MM-DD
```

## Two-Level Recording

Use **brief records** for quick failures and minor changes, **full records** for baselines and substantive optimizations. This avoids overhead while preserving important decisions.

### Brief Record (one row per trial)

Use for: UB overflow, compile errors, minor BLOCK size changes, quick rejections.

```markdown
## Trial Log

| # | Change | Result | Note |
|---|--------|--------|------|
| 01 | BLOCK_M=16, BLOCK_D=128 | UB overflow (464KB) | — |
| 02 | BLOCK_M=16, BLOCK_D=64 | UB overflow (232KB) | — |
| 03 | BLOCK_M=16, BLOCK_D=48 | 853µs kernel, accuracy PASS | → baseline, full record below |
| 04 | BLOCK_M=32, BLOCK_D=24 | 383µs, accuracy PASS | marginal improvement |
| 05 | BLOCK_M=88, BLOCK_D=4 | 261µs, accuracy PASS | best so far |
```

### Full Record (required for baseline + substantive optimizations)

Use for: (1) first runnable baseline, (2) layout changes, strategy changes, or msprof-driven optimizations.

```markdown
### Iter NN: <change_tag>

**Date:** YYYY-MM-DD
**Change:** <what was changed, ONE variable only>
**Config:** BLOCK_M=XX, BLOCK_N=XX, ...
**Profiler dir:** profiler/iter_NN_<tag>/
**msprof dir:** msprof/iter_NN_<tag>/

| Metric | Value |
|--------|-------|
| Accuracy | PASS / FAIL (max relerr: X) |
| Bench time (μs) | XXX (reference only) |
| Kernel avg duration (μs) | XXX |
| Wrapper ops (Count/Step) | e.g. TransposeAiCore ×3, TensorMoveAiCore ×1 |
| End-to-End per step (μs) | XXX = sum(avg × count_per_step) |
| msprof: cube_util | XX% |
| msprof: vec_util | XX% |
| msprof: mte2_ratio | XX% |
| msprof: wait_ratio | XX% |
| msprof: scalar_ratio | XX% |

**msprof analysis:** <key signals observed and actions taken or rationale for no action>

**Conclusion:** continue / rollback / next: <what to try next>
**Commit:** `opt(XX): iter_NN <tag>` or `rollback(XX): iter_NN <tag>`
```

## Iteration Checklist

Before moving to next iteration, verify:

- [ ] **Single variable**: Only ONE main variable changed from previous iteration
- [ ] **Accuracy PASS**: All shapes pass (re-run even if "only tuning params changed")
- [ ] **Profiler recorded**: kernel_details.csv collected, avg kernel duration logged
- [ ] **msprof collected and analyzed**: Bottleneck signals identified, actions documented
- [ ] **Record written**: Brief row OR full record written in ITERATIONS.md

**STOP gate: Do NOT start the next iteration until the current one is recorded.**

## Completion Checklist (Step 8: Finalize)

Before declaring an operator "done", verify every item:

- [ ] Reference implementation matches documentation line-by-line
- [ ] Backward reference verified against autograd (if backward exists)
- [ ] All shapes pass accuracy (small + target + tail/unaligned)
- [ ] All dtypes covered per operator convention
- [ ] `isfinite` check passes (no NaN/Inf)
- [ ] Profiler kernel duration meets target (kernel-to-kernel, not E2E with wrapper)
- [ ] End-to-End per step correctly computed (sum of avg × count_per_step)
- [ ] msprof analyzed: no unaddressed bottleneck signals (each signal either optimized or documented as not actionable)
- [ ] Wrapper ops classified (production-eliminable vs inherent overhead)
- [ ] All iteration records are complete and committed
- [ ] Final record has clear "conclusion: done" with summary metrics
- [ ] **All artifacts exist**: XX_fwd_triton.py, XX_fwd_ref.py, XX_fwd_test.py, utils.py, README.md, REPORT.md, REPORT_CN.md, ITERATIONS.md, profiler/, msprof/
- [ ] **utils.py is a local copy** (not sys.path.insert from skill directory)
- [ ] REPORT.md and REPORT_CN.md both generated with consistent data
- [ ] **Profiler data validated**: wrapper op durations confirmed by at least two profiler runs; bandwidth sanity check passed

## Integration Checklist (Step 9: Integration Packaging)

Before declaring an operator ready for network integration:

- [ ] **XX_op.py exists** with standard interface (original layout, internal transpose)
- [ ] **XX_op.py** has optimized interface (if layout transformation exists) + preparation helpers
- [ ] **test_XX_op.py**: standard interface output matches reference
- [ ] **test_XX_op.py**: standard interface output matches optimized interface (if both exist)
- [ ] **test_e2e.py** (inference operators): multi-step simulation with state accumulation, drift metrics reported
- [ ] **test_e2e.py** (training operators): mini training loop converges, gradient consistency verified
- [ ] **SUMMARY.md**: interface documentation + deployment requirements + verified performance data
- [ ] **All performance data in SUMMARY.md confirmed by repeated measurement** (no single-run numbers for architectural conclusions)
