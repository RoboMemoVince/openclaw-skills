# mhc_pre_only 算子测试报告

**日期:** 2026-02-08  
**服务器:** Alice (1.95.7.166) / Docker: triton-ascend-hcq  
**算子:** HC Pre-Only Forward (mhc_pre_only)

---

## 1. 精度测试

所有 shape 精度测试均 **PASS**。

| Shape (B×S×N×D) | 精度结果 |
|---|---|
| 1×2048×4×2560 | ✅ PASS |
| 1×1024×4×5120 | ✅ PASS |
| 1×4096×4×2560 | ✅ PASS |

---

## 2. Benchmark 结果

| Shape (B×S×N×D) | Reference (us) | Triton (us) | 加速比 | Ref Mem (MB) | Triton Mem (MB) | RelErr |
|---|---|---|---|---|---|---|
| 1×2048×4×2560 | 557 | 533 | 1.05x | 250.1 | 20.0 | 1.25e-04 |
| 1×1024×4×5120 | 598 | 493 | 1.21x | 250.1 | 20.0 | 1.44e-04 |
| 1×4096×4×2560 | 1454 | 703 | 2.07x | 500.2 | 40.1 | 1.25e-04 |

**关键发现:**
- Triton 算子在所有 shape 上均快于 Reference 实现
- 内存占用大幅降低（约 12.5x 节省）
- S=4096 时加速比最显著，达到 2.07x
- 相对误差均在 1.5e-04 以内，精度良好

---

## 3. Profiler Kernel 耗时

| Shape (B×S×N×D) | hc_matmul_pre_only_kernel_gamma (us) | h_in_kernel_n4 (us) | Total (us) |
|---|---|---|---|
| 1×2048×4×2560 | 204.308 | 54.469 | 258.777 |
| 1×1024×4×5120 | 185.354 | 54.777 | 240.131 |
| 1×4096×4×2560 | 323.979 | 106.586 | 430.565 |

**Kernel 分析:**
- `hc_matmul_pre_only_kernel_gamma` 是主要耗时 kernel，占总时间约 75-79%
- `h_in_kernel_n4` 耗时相对稳定，S 翻倍时耗时也近似翻倍
- Profiler 总耗时 < Benchmark 耗时，差值为 launch overhead 和其他框架开销

---

## 4. 总结

mhc_pre_only 算子在 Alice 服务器上部署成功，所有测试通过：
- ✅ 精度：3/3 shape 全部 PASS
- ✅ 性能：Triton 实现在所有 shape 上均优于 Reference（1.05x ~ 2.07x 加速）
- ✅ 内存：Triton 内存占用仅为 Reference 的 ~8%（显著节省）
- ✅ Profiler：kernel 级别耗时数据已收集
