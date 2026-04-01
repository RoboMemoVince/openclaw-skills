# Autotune 指南

## 概述

`@triton.autotune` 让编译器在多组配置中自动选出最快的一组。在 Ascend NPU 上，除了标准的 `BLOCK_SIZE` 等 constexpr 参数，还可以在 Config 中直接设置 NPUOptions（如 `multibuffer`, `enable_auto_bind_sub_block` 等），实现编译选项级别的自动搜索。

## 基本用法

```python
import triton
import triton.language as tl

@triton.autotune(
    configs=[
        triton.Config({"BLOCK_SIZE": 1024}, multibuffer=True),
        triton.Config({"BLOCK_SIZE": 4096}, multibuffer=True),
        triton.Config({"BLOCK_SIZE": 8192}, multibuffer=False),
    ],
    key=["n_elements"],  # 当 n_elements 变化时重新 autotune
)
@triton.jit
def kernel(x_ptr, out_ptr, n_elements, BLOCK_SIZE: tl.constexpr):
    pid = tl.program_id(0)
    offs = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = offs < n_elements
    x = tl.load(x_ptr + offs, mask=mask)
    tl.store(out_ptr + offs, x * 2, mask=mask)
```

### 关键要素

| 参数 | 说明 |
|------|------|
| `configs` | `triton.Config` 列表，每个 Config 指定一组 constexpr 值和编译选项 |
| `key` | 字符串列表，指定哪些 kernel 参数变化时需要重新 autotune |

### Grid 使用 lambda

Autotune 中 grid 必须用 lambda 读取 `meta` 字典（包含当前 Config 的 constexpr 值）：

```python
# ✅ 正确：通过 lambda 获取当前 Config 的 BLOCK_SIZE
kernel[lambda meta: (triton.cdiv(n_elements, meta["BLOCK_SIZE"]),)](
    x, out, n_elements
)

# ❌ 错误：直接用固定值，BLOCK_SIZE 在不同 config 间不同
kernel[(n_elements // 1024,)](x, out, n_elements)
```

## Config 中可用的 NPUOptions

除了 constexpr dict，`triton.Config` 的关键字参数直接映射到 NPUOptions：

```python
triton.Config(
    {"BLOCK_M": 128, "BLOCK_N": 128, "BLOCK_K": 64},  # constexpr 参数
    # 以下为 NPUOptions
    multibuffer=True,
    enable_auto_bind_sub_block=True,
    enable_hivm_auto_cv_balance=True,
    tile_mix_vector_loop=64,
    tile_mix_cube_loop=32,
    sync_solver=True,
    compile_mode="simd",
)
```

常用于 autotune 的 NPUOptions：

| Option | 搜索场景 |
|--------|----------|
| `multibuffer` | True/False 对比，看 ping-pong 是否有效 |
| `enable_auto_bind_sub_block` | CV 融合 kernel 中双核绑定是否有效 |
| `enable_hivm_auto_cv_balance` | CV 负载均衡是否改善 |
| `tile_mix_vector_loop` / `tile_mix_cube_loop` | CV 混合模式的 tile 大小搜索 |
| `compile_mode` | `"simd"` vs `"simt_only"` 等不同编译路径 |

详见 [npu-options.md](./npu-options.md)。

## @libentry 装饰器

`@libentry()` 用于函数库导出场景（如 FlagGems），与 `@triton.autotune` 配合使用。

```python
from triton.runtime.libentry import libentry

@triton.autotune(
    configs=[
        triton.Config({"BLOCK_SIZE": 1024, "multibuffer": True}),
        triton.Config({"BLOCK_SIZE": 8192, "multibuffer": True}),
    ],
    key=["n_elements"],
)
@libentry()
@triton.jit
def add_kernel(x_ptr, y_ptr, out_ptr, n_elements, BLOCK_SIZE: tl.constexpr):
    ...
```

**装饰器顺序**：`@autotune` → `@libentry()` → `@triton.jit`

**注意**：在 `@triton.autotune` 和 `@triton.jit` 之间插入其他装饰器（除 `@libentry`）会**禁用 autotune 并行编译**。

## 查看 Autotune 结果

```bash
TRITON_PRINT_AUTOTUNING=1 python3 your_script.py
```

输出每个 kernel 的最优配置和各配置的测试耗时。

## 空 configs 自动搜索

当 `configs=[]` 时，triton-ascend 使用内置的默认配置空间：

```python
@triton.autotune(configs=[], key=["n_elements"])
@triton.jit
def kernel(...):
    ...
```

这对快速原型开发有用，但生产代码建议手动指定 configs 以缩小搜索空间。

## 实践建议

### Config 设计原则

1. **覆盖 BLOCK 大小的合理范围**：从小（1024）到大（目标维度全覆盖），不要只搜 2 的幂
2. **交叉搜索编译选项**：同一 BLOCK 大小配 multibuffer=True/False
3. **控制搜索空间**：一般 4-8 个 Config 足够，过多会增加首次运行时间
4. **固定 key 维度**：key 参数应包含影响最优 BLOCK 的输入维度

### 与 triton-dev 工作流的关系

| 阶段 | Autotune 使用 |
|------|---------------|
| Step 2（初始实现） | 先用固定 BLOCK 跑通，**不要一开始就 autotune** |
| Step 3（精度验证） | 用固定配置验证，确保每个 config 精度正确 |
| Step 7（调优迭代） | msprof 定位瓶颈后，基于信号设计 autotune configs |
| Step 8（最终化） | 最终版可以保留 autotune，记录最优 config 到 REPORT |

### 常见陷阱

1. **Autotune 不能替代 msprof 分析**：autotune 只告诉你"哪个快"，不告诉你"为什么慢"
2. **首次运行时间长**：N 个 configs × M 次 bench = N×M 次编译+运行。可用 `TRITON_ASCEND_COMPILE_SPEED_OPT=1` 跳过编译失败的 config
3. **Cache 干扰**：修改 kernel 后 autotune cache 可能未清除，用 `TRITON_ALWAYS_COMPILE=1` 强制重编译
