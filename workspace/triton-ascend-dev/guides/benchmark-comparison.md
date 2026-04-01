# Triton vs Torch Baseline 性能对比指南

## 场景

算子开发完成后，需要以 msprof profiler 级别的精度对比 Triton kernel 与 Torch 原生实现的性能差异，生成正式的性能报告。

**关键原则：以 profiler kernel 时间为准，不以 bench (Python `time.perf_counter`) 为准。**

Bench 包含 Python wrapper overhead（tensor 分配、view/contiguous、cache 查找、kernel launch 等），实测固定约 200-300μs，会严重扭曲短 kernel 的加速比。

## 方法：msprof 全进程采集 + CSV 解析

### 为什么不用 torch.profiler

在 Ascend NPU 上，以下方式**均不可靠**：
1. `torch.npu.profile(out_dir)` — 某些 torch_npu 版本没有此 API，会 `AttributeError`
2. `torch.profiler.ProfilerActivity.NPU` — 不存在，NPU 注册为 `PrivateUse1`
3. 即使用 `ProfilerActivity.PrivateUse1`，`evt.device_time_total` 全为 0，拿不到 NPU kernel 时间

**结论：直接用 msprof 命令行工具，采集 op_summary CSV，手动解析。**

### Step 1: 编写单次执行脚本

为每个 case（torch_fwd / triton_fwd / torch_bwd / triton_bwd）编写统一入口脚本，通过命令行参数选择 case：

```python
import torch, torch_npu, sys
sys.path.insert(0, '/path/to/operator_dir')

def run_case(case):
    device = "npu:0"
    torch.npu.set_device(device)
    
    # 生成输入数据（固定 shape 和 seed）
    weight = torch.randn(N, M, dtype=torch.bfloat16, device=device)
    # ...
    
    # Warmup（重要！msprof 会采集全部 kernel，warmup 需要在脚本内做）
    for _ in range(5):
        fn()
    torch.npu.synchronize()
    
    # Profiled run（这一次的 kernel 数据是我们要的）
    result = fn()
    torch.npu.synchronize()

if __name__ == "__main__":
    run_case(sys.argv[1])
```

### Step 2: msprof 采集

```bash
source /usr/local/Ascend/ascend-toolkit/set_env.sh

for CASE in torch_fwd triton_fwd torch_bwd triton_bwd; do
    msprof --output="result_profiling/bench/$CASE" \
           --application="python3 bench_case.py $CASE" \
           --aic-metrics=PipeUtilization \
           --ai-core=on \
           --task-time=on
done
```

**注意**：这里用的是 `msprof`（全进程采集），不是 `msprof op`（单 kernel 采集）。因为我们需要采集 Torch 的多个分散 kernel，`msprof op --kernel-name` 只能过滤单个 kernel 名。

### Step 3: 解析 op_summary CSV

CSV 路径：`result_profiling/bench/<case>/PROF_*/mindstudio_profiler_output/op_summary_*.csv`

关键列：
- `Op Name`（第 5 列）：算子名
- `OP Type`（第 6 列）：算子类型
- `Task Duration(us)`（第 10 列）：**kernel 耗时，这是我们要的数据**

**⚠️ 陷阱：`Task Duration(us)` 字段值后面带 tab 字符，解析时必须 strip/trim。**

### Step 4: 正确拆分 warmup 和 profiled run

msprof 从进程启动就开始采集，CSV 包含：
1. **Tensor 初始化 ops**：DSARandomNormal、DSARandomUniform、Cast（初始 bf16 转换）等
2. **Warmup 迭代**（5 次）
3. **Profiled 迭代**（最后 1 次）← 我们只要这个

**拆分方法**：识别重复的算子模式，提取最后一次迭代。

对于 Triton 算子：找最后一个 `ehq_fwd_kernel` 或 `ehq_bwd_kernel` 及其前后的 host ops（scale clamp、Cast 等）。

对于 Torch 算子：识别重复的算子序列模式。例如 forward 每次迭代都是 `Cast → Greater → SelectV2 → Cast → RealDiv → Round → ClipByValue → Mul → Cast`，找最后一次这个序列。

```python
# 示例：提取 Triton kernel 最后一次迭代
kernel_indices = [i for i, (name, _, _) in enumerate(ops) if "ehq_fwd_kernel" in name]
last_kernel_idx = kernel_indices[-1]
# 加上前后的 host ops（scale clamp、Cast 等）
iteration_ops = ops[last_kernel_idx - 1 : last_kernel_idx + 1]
```

### Step 5: 汇总对比

分别统计 Torch 和 Triton 最后一次迭代的所有 kernel 耗时之和，计算加速比。

## 性能报告模板

报告应包含：
1. **总览表**：Forward / Backward / Fwd+Bwd 的 Torch vs Triton 耗时和加速比
2. **详细拆解**：Torch 每个 kernel 的耗时和占比（按计算阶段归类）
3. **性能收益来源分析**：
   - 算子融合（kernel 数量减少 + GM 带宽节省估算）
   - 消除中间 tensor 分配
   - 消除 kernel launch 开销
   - 融合归约（如有 ReduceSum）
   - 类型转换节省（Cast 占比）
4. **优化空间与瓶颈**：当前 kernel 的已知瓶颈

## 常见问题

### docker exec 环境变量

必须 `source /usr/local/Ascend/ascend-toolkit/set_env.sh`，否则：
- `import torch` 报 `libhccl.so: cannot open shared object file`
- `python` 命令可能不存在（用 `python3`）

### 文件传输到容器

SSH 远程操作时，`docker exec -i ... bash -c 'cat > file'` 通过 stdin 写文件**不可靠**（可能静默失败）。推荐：
```bash
scp file user@host:/tmp/
ssh user@host "docker cp /tmp/file container:/path/file"
```

### Torch 反向 baseline 选择

- **推荐用手写的 ref 函数**（如 `ehq_bwd_reference`），而非 autograd。autograd 会引入额外的计算图构建开销，不适合做 benchmark baseline。
- ref 函数应该已在开发阶段和 autograd 对齐过精度（见 SKILL.md Step 1）。

### msprof vs msprof op

- `msprof`（全进程采集）：适合对比 Torch 多 kernel vs Triton 单 kernel 的总耗时
- `msprof op --kernel-name=xxx`：适合单个 Triton kernel 的详细管线分析（pipe utilization、cache、bandwidth 等）
- 性能对比用 `msprof`，kernel 调优用 `msprof op`
