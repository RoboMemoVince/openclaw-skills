# Triton-Ascend 常见陷阱与注意事项

本文档记录在 triton-ascend 开发过程中遇到的平台特性和常见陷阱，帮助避免重复踩坑。

## 1. 2D 张量广播不可靠

### 问题描述

在标准 Triton (CUDA) 中常用的 2D 张量广播模式，在 triton-ascend 上可能导致**精度异常**：

```python
# ❌ 不推荐：2D 广播模式（可能导致精度问题）
H_comb_col = tl.load(...)  # [N] - 一列标量
x_vals = tl.load(...)      # [BLOCK_D] - 向量

# 2D 广播乘法
result = H_comb_col[:, None] * x_vals[None, :]  # [N, BLOCK_D]
```

### 实际案例

在 `mhc_post_fwd` 算子优化中，使用上述 2D 广播模式导致 74% 元素误差，精度验证失败。

### 推荐方案：显式展开

对于小规模 N 维度（如 N=4），改用显式标量变量展开：

```python
# ✅ 推荐：显式展开（准确且高效）
H_post_0 = tl.load(H_post_ptr + base + 0)
H_post_1 = tl.load(H_post_ptr + base + 1)
H_post_2 = tl.load(H_post_ptr + base + 2)
H_post_3 = tl.load(H_post_ptr + base + 3)

h_out_vals = tl.load(h_out_ptr + offs, mask=mask, other=0.0)  # [BLOCK_D]

# 4 路独立计算
h_post_term_0 = H_post_0 * h_out_vals
h_post_term_1 = H_post_1 * h_out_vals
h_post_term_2 = H_post_2 * h_out_vals
h_post_term_3 = H_post_3 * h_out_vals
```

### 适用场景

- N 维度较小（N ≤ 8）
- 需要对 N 个 head 或 channel 进行相同向量运算
- Grid 结构可以合并 N 维度到单个 block 处理

---

## 2. 非 2 的幂 BLOCK 大小可正常工作

### 问题描述

在 CUDA Triton 中，BLOCK 大小通常限制为 2 的幂（32, 64, 128, 256, 512, 1024...）。

### triton-ascend 特性

triton-ascend 支持**非 2 的幂**的 BLOCK 大小，且在某些场景下是最优选择：

```python
# ✅ 非 2 的幂 BLOCK 大小在 triton-ascend 上可用
BLOCK_D = 2560  # D=2560 时最优
BLOCK_D = 1280  # D=2560 时次优
BLOCK_D = 640   # 也可用
```

### 实际案例

在 `mhc_post_fwd` 优化中，D=2560 时的 BLOCK_D 调参结果：

| BLOCK_D | Grid 块数 | 耗时 (us) | 加速比 |
|---------|-----------|-----------|--------|
| 256     | 20480     | 1555      | 1.5x   |
| 512     | 10240     | 717       | 3.4x   |
| 1024    | 6144      | 509       | 4.7x   |
| 1280    | 4096      | 295       | 8.2x   |
| **2560**| **2048**  | **181**   | **13.4x** |

### 调参建议

- **优先尝试让 BLOCK_D 完全覆盖目标维度**（减少块数 = 减少调度开销）
- 非 2 的幂值（如 2560, 1280, 640）在 triton-ascend 上可编译、可运行
- 通过实测确定最优值，不要预设 "必须是 2 的幂"

---

## 3. Grid 块数过多导致性能退化

### 问题描述

Grid 块数过多会导致：
- 标量开销（地址计算、循环控制）占比过高
- 调度开销增加
- 数据局部性下降

### 诊断信号（msprof）

| 指标 | 异常值 | 含义 |
|------|--------|------|
| `aiv_scalar_ratio` | > 50% | 标量开销主导 |
| `aiv_vec_ratio` | < 20% | 向量计算利用率极低 |
| `Block Dim` | > 10000 | 块数可能过多 |

### 优化策略

1. **合并小维度到单个 block 处理**
   - 原始：`Grid = (B*S*N, cdiv(D, BLOCK_D))` → 40960 块
   - 优化：`Grid = (B*S, cdiv(D, BLOCK_D))` → 2048 块

2. **增大 BLOCK 大小减少块数**
   - 在 UB 容量允许范围内，尽可能增大 BLOCK_D

3. **显式展开代替循环**
   - 将小 N 维度的循环展开为独立变量，减少循环控制开销

### 实际案例

`mhc_post_fwd` 通过 Grid 结构重组，块数从 40960 降到 2048，性能提升 15.5x。

---

## 4. Grid 大小限制

### 限制条件

单维度 Grid 大小不能超过 65536：

```python
# ❌ 会报错
grid = (B * S * N * cdiv(D, BLOCK_D), )  # 如果 > 65536

# ✅ 使用 2D grid 或增大 BLOCK 大小
grid = (B * S * N, cdiv(D, BLOCK_D))
```

### 解决方案

- 使用 2D grid 分散维度
- 增大 BLOCK 大小减少块数
- 合并维度减少 grid 维度

---

## 5. Cooperative Grid 降低调度开销

### 问题描述

当工作单元数 M 远大于 AI Core 数量时，简单 Grid 启动过多 block，调度开销主导耗时：

```python
# ❌ M=2048 个 block，num_aicore=24，调度开销大
kernel[(M,)](...)
```

### 解法：Cooperative Loop

限制 block 数量，每个 block 循环处理多个工作单元：

```python
import triton.runtime.driver as driver

num_cores = driver.active.utils.get_device_properties(device)["num_aicore"]
grid_size = min(M, num_cores * 4)

@triton.jit
def kernel(..., M: tl.constexpr, num_cores: tl.constexpr):
    pid = tl.program_id(0)
    for idx in range(pid, M, num_cores):
        ...

kernel[(grid_size,)](..., M=M, num_cores=grid_size)
```

### 适用条件

- M >> num_aicore（典型值：M > num_aicore * 10）
- 每个工作单元的计算量中等（能填满 pipeline）
- 无跨位置数据依赖

### 诊断信号

通过 bench 对比 `grid=(M,)` vs `grid=(num_cores*4,)` + cooperative loop 即可判断是否有效。

### 替代方案：TRITON_ALL_BLOCKS_PARALLEL

triton-ascend 提供了编译器级的自动实现，无需手写 cooperative loop：

```bash
TRITON_ALL_BLOCKS_PARALLEL=1 python3 your_script.py
```

编译器会自动将逻辑核数对齐到物理核数，等效于内置版 cooperative grid。

**优势**：零代码改动，启用后 grid 可突破 65535 限制。

**限制**：kernel 逻辑必须对执行顺序不敏感（无跨 block 依赖），否则可能死锁。

**选择建议**：
- 快速验证 → 先用 `TRITON_ALL_BLOCKS_PARALLEL=1`，确认有效再决定是否保留
- 需要精细控制 grid_size → 手写 cooperative loop
- 存在跨 block 依赖 → 只能手写（设定安全的 grid_size 上界）

---

## 6. tl.dot 替换大量 tl.sum 降低 scalar_ratio

### 问题描述

当 kernel 中存在大量独立的 `tl.sum` 调用时，msprof 会显示高 `scalar_ratio`（>30%）：

```python
# ❌ 16 个独立 tl.sum，每个产生 scalar 归约指令
out_00 = tl.sum(a_0 * b_0)
out_01 = tl.sum(a_0 * b_1)
# ... 共 16 个
```

### 解法：tl.dot 批量替换

将 N×M 个独立 `tl.sum(a[i] * b[j])` 合并为一个 `tl.dot`，触发 cube 单元加速：

```python
# ✅ 1 个 tl.dot 替换 N*M 个 tl.sum
a_blk = tl.load(a_ptrs, ...)  # [N, K]
b_blk = tl.load(b_ptrs, ...)  # [M, K]
out = tl.dot(a_blk, tl.trans(b_blk))  # [N, M]
```

### 适用条件

- 存在 N×M 个形如 `sum(a[i] * b[j])` 的独立归约
- 数据可组织为 2D tile（[N, K] 和 [M, K]）
- K 维度足够大（>256）以摊销 tl.dot 固定开销

### 注意事项

- tl.dot 需配合 cooperative grid 使用效果更佳
- 若 tl.dot 无 cooperative grid，可能因双 kernel launch overhead 反而更慢

---

---

## 7. UB Capacity Limitations

### Problem Description

Ascend NPU Unified Buffer (UB) has limited capacity (typically 256KB on 910B). Large BLOCK sizes can cause overflow.

### Error Symptom

```
Error: ub overflow, requires X bits while Y bits available!
```

### Solutions

1. **Reduce BLOCK sizes**: Lower `BLOCK_M`, `BLOCK_N`, `BLOCK_K`, `BLOCK_D`
2. **Enable UB saving**: Set `enable_ubuf_saving=True` in config
3. **Split kernel**: Separate large operations into multiple kernels

### Estimation Tool

Use `tools/estimate_ub_usage.py` to predict UB usage before running:

```bash
python3 estimate_ub_usage.py --type matmul --BLOCK_M 128 --BLOCK_N 128 --BLOCK_K 64
```

---

## 8. FP8 Type Support Limitations

### Current Status

Triton-Ascend supports FP8 types (`float8e5`, `float8e4nv`, `float8e4b15`, `float8e4b8`, `float8e5b16`) but with important limitations:

- **FP8 tensors cannot be directly stored via `tl.store()`** — causes "unexpected type fp8" compilation error
- FP8 is intended **only for `tl.dot` / `tl.dot_scaled` accumulation**, not general purpose
- Must convert back to FP16/FP32 for output operations

### Recommended Pattern: tl.fp_to_fp (basic conversion)

```python
# Convert to FP8
fp8_tensor = tl.fp_to_fp(fp16_tensor, dtype=tl.float8e5)

# Convert back for computation or storage
fp16_result = tl.fp_to_fp(fp8_tensor, dtype=tl.float16)
```

### tl.dot_scaled (FP8 matrix multiply with microscaling)

For FP8 matrix multiplication with per-block scaling (MX format):

```python
# lhs, rhs: 2D tensors in FP8 format (packed as int32 or int8)
# lhs_scale, rhs_scale: ue8m0 scale factors (int8 tensors)
# lhs_format, rhs_format: "e4m3", "e5m2", "e2m3", "e3m2", or "e2m1"
result = tl.dot_scaled(
    lhs, lhs_scale, "e4m3",
    rhs, rhs_scale, "e5m2",
    acc=accumulator,           # Optional: add to existing accumulator
    out_dtype=tl.float32,      # Output precision
)
```

**注意**: `dot_scaled` 是 FP8 在 Ascend 上的主要使用场景，适用于 LLM 推理中的低精度矩阵乘法。

---

## 9. Transpose Limitations

### Problem Description

`tl.trans()` has specific requirements:

- Works best on 2D tensors
- May require specific dimension orderings for 3D+ tensors

### Recommended Pattern

```python
# For 2D transpose
b_t = tl.trans(b)  # [K, N] -> [N, K]

# For higher dimensions, consider reshape + trans + reshape
```

---

## 10. Stride=0 Pointer Issues

### Problem Description

Pointers with zero stride can cause compilation errors in certain patterns.

### Error Symptom

```
Error: Cannot handle stride=0 pointer in this context
```

### Solution

Avoid creating pointers with stride=0. Use explicit broadcasting instead:

```python
# Instead of stride=0 broadcast
# Use tl.broadcast_to or explicit loops
```

---

## 11. constexpr Indexing Requirements

### Problem Description

Some operations require `tl.constexpr` for indexing, especially in slice operations.

### Incorrect Pattern

```python
# May fail
for i in range(N):  # N is runtime value
    slice = tl.extract_slice(tensor, (i * SIZE, 0), ...)
```

### Correct Pattern

```python
# Use constexpr
N: tl.constexpr = 4
for i in tl.static_range(N):
    slice = tl.extract_slice(tensor, (i * SIZE, 0), ...)
```

---

## 12. Atomic Operation Considerations

### Masking with Atomics

Masked atomics may behave differently than expected:

```python
# Ensure mask properly excludes out-of-bounds
mask = offs < n_elements
tl.atomic_add(ptr + offs, val, mask=mask)
```

### Contention Patterns

High contention on same address can degrade performance:

```python
# Consider reduction pattern instead of many atomic_adds to same location
```

---

## 13. stride-N gather 访存导致性能灾难

### 问题描述

当 kernel 的 BLOCK 处理维度（通常是 D）不是 tensor 的最内层维度时，`tl.load` 产生 stride-N 的 gather 模式。在 Ascend NPU 上，这导致 MTE2 带宽利用率暴跌至理论值的 1-2%。

```python
# ❌ conv_state [M, D, W]: 沿 D 处理时 stride = W = 4
cs_base = m * stride_cs_m + d_offs * W  # stride-4 gather
s0 = tl.load(conv_state_ptr + cs_base + 0)  # 每 4 个元素取 1 个

# ✅ conv_state [W, M, D]: D 在最内层，load 连续
cs_md = m * D + d_offs  # stride-1, contiguous
s0 = tl.load(conv_state_ptr + 0 * M * D + cs_md)  # 连续读取
```

### 诊断信号 (msprof)

| 指标 | 异常值 | 含义 |
|------|--------|------|
| `aiv_mte2_ratio` | > 60% | 内存读取占主导 |
| `aiv_vec_ratio` | < 25% | 向量计算饥饿 |
| `GM_to_UB_bw` | < 2 GB/s | 远低于理论值 (~40 GB/s/core) |

### 实际案例

ShortConvGateFusion: conv_state `[M, D, W]`，BLOCK_D=256 沿 D 处理，stride = W = 4。
- stride-4 gather: kernel **1192μs**, aiv_mte2_ratio = 73%
- 变换为 `[W, M, D]` 后: kernel **14μs** (**85x 提速**)

### 解法

1. **首选**: 将 tensor 变换为「BLOCK 处理维度在最内层」的 layout
2. **最优**: 让上游直接以 kernel-friendly layout 存储，避免运行时 transpose
3. **判断方法**: 若 stride > 1 且 BLOCK 元素数 > 64，必须做 layout 变换

---

## 14. CANN 内置算子首次 profiler 耗时虚高

### 问题描述

`profiler_wrapper` 的 warmup 只覆盖 Triton kernel 的编译缓存。CANN 内置算子（TransposeAiCore, TensorMoveAiCore, CastAiCore 等）有独立的 JIT 编译/缓存流程，首次 profiler 采集可能包含冷启动开销，导致耗时虚高 5-10x。

### 诊断方法

对 wrapper op 计算有效带宽：

```
effective_bw = data_size_bytes / (duration_us × 1e-6) / 1e9  (GB/s)
```

参考值（910B 单 core）：
- contiguous transpose/copy 应达到 20-40 GB/s
- 若 < 5 GB/s → 数据可疑，需复测
- 若 < 1 GB/s → 几乎必定是冷启动异常

### 解法

1. **profiler 至少跑两次**，取第二次（稳定）的数据
2. **对 wrapper op 做带宽 sanity check** 再写入 REPORT
3. **绝不基于单次未验证测量做架构决策**（如 "方案 X 不可行"）

---

## Summary: Quick Checklist

When developing triton-ascend operators, check:

- [ ] **分析每个 tensor 的 BLOCK 维度是否连续** (stride=1)，若 stride>1 必须做 layout 变换
- [ ] Avoid `[:, None] * [None, :]` 2D broadcasting, use explicit expansion
- [ ] BLOCK sizes need not be power of 2, try sizes that exactly cover dimensions
- [ ] Keep grid block count reasonable (< 10000) to avoid scheduling overhead
- [ ] Single grid dimension must not exceed 65536, use 2D grid if needed
- [ ] Use msprof to check `scalar_ratio` and `vec_ratio` for scalar overhead diagnosis
- [ ] When M >> num_aicore, consider Cooperative Grid pattern
- [ ] When many independent `tl.sum` exist, consider batch replacement with `tl.dot`
- [ ] Estimate UB usage before tuning, avoid overflow
- [ ] Use `tl.constexpr` for slice/indexing where required
- [ ] Test with edge cases: tail blocks, unaligned sizes, boundary conditions
- [ ] **Profiler 至少跑两次**，wrapper op 做带宽 sanity check，不基于单次测量定结论

## Related Documentation

- [Ascend API Reference](./ascend-api-reference.md) - Full API documentation
- [NPUOptions Reference](./npu-options.md) - Compilation options
- [CV Fusion Pattern](./cv-fusion-pattern.md) - Dual-core parallelism
- [Migration Guide](./migration-from-gpu.md) - GPU to NPU migration
