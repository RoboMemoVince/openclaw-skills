# Triton-Ascend 环境变量参考

本文档整理 triton-ascend 开发中常用的环境变量，按使用场景分类。

完整列表参见仓库 `docs/en/environment_variable_reference.md`。

## 1. 调试与日志

| 变量 | 默认 | 说明 |
|------|------|------|
| `TRITON_DEBUG` | 0 | 启用调试输出，打印编译/执行详细信息。设为 1 启用。 |
| `MLIR_ENABLE_DUMP` | 0 | 转储每个 MLIR 优化前的 IR。`1`=全部 kernel，`<kernel_name>`=指定 kernel。若不生效需清 cache：`rm -r ~/.triton/cache/*` |
| `LLVM_IR_ENABLE_DUMP` | 0 | 转储每个 LLVM IR 优化前的 IR |
| `TRITON_KERNEL_DUMP` | 0 | 启用 kernel 代码转储（IR + 最终产物），保存到 `TRITON_DUMP_DIR` |
| `TRITON_DUMP_DIR` | cwd | 指定 kernel dump 保存目录 |
| `TRITON_REPRODUCER_PATH` | — | 生成 MLIR 复现文件，编译失败时保存故障前状态 |
| `TRITON_INTERPRET` | 0 | 使用解释器替代 NPU 执行，**可在 kernel 中插入 Python 断点** |
| `TRITON_DEVICE_PRINT` | 0 | 启用 `tl.device_print()` 功能（每线程 GM buffer 上限 16KB） |
| `TRITON_PRINT_AUTOTUNING` | 0 | autotune 完成后输出最优配置和各配置耗时 |
| `USE_IR_LOC` | 0 | 在生成的 IR 中包含位置信息（文件名、行号），用于精细性能分析 |
| `MLIR_ENABLE_REMARK` | 0 | 启用 MLIR 编译过程中的 remark 输出（含性能警告） |
| `ENABLE_PRINT_UB_BITS` | 0 | 打印当前 UB 使用量信息 |

### 调试常用组合

```bash
# 查看编译全流程 IR
TRITON_ALWAYS_COMPILE=1 MLIR_ENABLE_DUMP=1 python3 your_script.py

# 只转储特定 kernel 的 IR
TRITON_ALWAYS_COMPILE=1 MLIR_ENABLE_DUMP=my_kernel_name python3 your_script.py

# 保存 kernel 代码到指定目录
TRITON_KERNEL_DUMP=1 TRITON_DUMP_DIR=/tmp/triton_dump python3 your_script.py

# 解释器模式调试（可 pdb 打断点）
TRITON_INTERPRET=1 python3 your_script.py

# 检查 UB 使用量
ENABLE_PRINT_UB_BITS=1 python3 your_script.py
```

## 2. 编译控制

| 变量 | 默认 | 说明 |
|------|------|------|
| `TRITON_ALWAYS_COMPILE` | 0 | **强制重编译**，跳过缓存。调试/测试新编译器特性必备。 |
| `DISABLE_LLVM_OPT` | 0 | `1`=禁用 LLVM 优化步骤。也可设为特定 flag 字符串，如 `"disable-lsr"` 禁用循环强度优化。 |
| `TRITON_DEFAULT_FP_FUSION` | 1 | 浮点运算融合优化（如 mul+add→fma）。设为 0 可关闭以排查精度问题。 |
| `TRITON_ASCEND_COMPILE_SPEED_OPT` | 0 | 编译失败时跳过后续阶段尝试，加快编译速度 |
| `TRITON_COMPILE_ONLY` | 0 | 只编译不执行（remote_launch 场景） |
| `TRITON_DISABLE_FFTS` | 0 | 禁用 FFTS 优化 |
| `MLIR_ENABLE_TIMING` | 0 | 输出 MLIR 编译各阶段耗时统计 |
| `LLVM_ENABLE_TIMING` | 0 | 输出 LLVM 编译各阶段耗时统计 |
| `TRITON_KERNEL_OVERRIDE` | 0 | 启用 kernel 覆盖功能（用外部 IR/PTX 文件替代编译结果） |
| `TRITON_OVERRIDE_DIR` | cwd | 指定 kernel 覆盖文件目录 |

### 精度问题排查

```bash
# 关闭 FP 融合排查精度偏差来源
TRITON_DEFAULT_FP_FUSION=0 TRITON_ALWAYS_COMPILE=1 python3 your_test.py
```

## 3. 运行与调度

| 变量 | 默认 | 说明 |
|------|------|------|
| `TRITON_ALL_BLOCKS_PARALLEL` | 0 | **自动将逻辑核数对齐到物理核数**，减少调度开销。启用后 grid 可 >65535。**限制：kernel 逻辑必须对执行顺序不敏感，否则死锁。** |
| `TRITON_ENABLE_TASKQUEUE` | 0 | 启用 task queue 调度 |
| `TRITON_ENABLE_SANITIZER` | 0 | 启用 SANITIZER |

### TRITON_ALL_BLOCKS_PARALLEL 使用场景

当 grid block 数远大于物理 AI Core 数时（如 M=2048, num_aicore=24），启用此变量相当于编译器自动实现 cooperative grid 模式：

```bash
TRITON_ALL_BLOCKS_PARALLEL=1 python3 your_script.py
```

**注意**：这是 pitfalls.md #5 中手写 cooperative grid 的编译器级替代方案。手写方式更灵活（可控制 grid_size），此变量更便捷但要求 kernel 无顺序依赖。

## 4. Benchmark

| 变量 | 默认 | 说明 |
|------|------|------|
| `TRITON_BENCH_METHOD` | — | 设为 `"npu"` 时将 `do_bench` 切换为 `do_bench_npu`（配合 `INDUCTOR_ASCEND_AGGRESSIVE_AUTOTUNE=1` 使用）。设为 `"default"` 强制使用原始 `do_bench`。 |

## 5. 速查：按开发阶段使用

| 阶段 | 推荐变量 |
|------|----------|
| **初始开发** | `TRITON_ALWAYS_COMPILE=1`（避免 cache 干扰） |
| **编译失败排查** | `MLIR_ENABLE_DUMP=1` + `TRITON_ALWAYS_COMPILE=1` |
| **精度排查** | `TRITON_INTERPRET=1`（断点调试）或 `TRITON_DEFAULT_FP_FUSION=0` |
| **UB 问题** | `ENABLE_PRINT_UB_BITS=1` |
| **性能调优** | `TRITON_PRINT_AUTOTUNING=1`（autotune 结果）、`TRITON_ALL_BLOCKS_PARALLEL=1`（自动并行） |
| **kernel 代码审查** | `TRITON_KERNEL_DUMP=1` + `TRITON_DUMP_DIR=<dir>` |
| **编译时间分析** | `MLIR_ENABLE_TIMING=1` + `LLVM_ENABLE_TIMING=1` |
