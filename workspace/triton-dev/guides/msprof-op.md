# msprof op Performance Tuning Guide

The msprof tool is used to collect and analyze key performance metrics for operators running on Ascend AI processors. Users can use the output performance data to quickly identify software and hardware performance bottlenecks, improving operator performance analysis efficiency. It supports triton operator performance data collection, simulation pipeline diagram generation, etc. This section demonstrates the application of the operator performance tuning tool in triton operator development.

## 1. Environment Preparation

Before using the tool, complete environment preparation. See [SKILL.md](../SKILL.md) for container and setenv instructions.

Other configurations:
- Compilation options
  For operator simulation scenarios, if you need to add -g information to get code line call stack information, you need to enable operator code hotspot diagram and code call stack functionality by setting the following environment variable:
  ```bash
  export TRITON_DISABLE_LINE_INFO=0
  ```
- Simulation environment variables
  Before operator simulation, you need to set the specified operator simulation chip type.

Usage reference: [Operator Development Tools - Operator Tuning](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/83RC1/devaids/optool/atlasopdev_16_0082.html)

## 2. Operator Tuning

The msprof tool includes two usage modes: msprof op (on-device) and msprof op simulator (simulation), helping users identify operator memory, code, and instruction anomalies for comprehensive operator tuning.

Feature Overview:
| Feature Name | Applicable Scenarios | Displayed Graphics |
|--------------|---------------------|-------------------|
| msprof op | Suitable for performance analysis in actual runtime environments | Compute-memory heatmap, Roofline bottleneck analysis, Cache heatmap, Compute-transfer pipeline diagram, Operator code hotspot diagram |
| msprof op simulator | Suitable for detailed simulation tuning during development and debugging | Instruction pipeline diagram, Operator code hotspot diagram, Memory path throughput waveform |

This document uses an add operator as an example to demonstrate how to use the msprof op operator performance tuning tool in various scenarios.

### 2.1 Operator Code Example

Add operator code example:
```Python
import triton
import triton.language as tl
import numpy as np
import torch
import pytest
import test_common

def torch_pointwise(x0, x1):
    res = x0 + x1
    return res


@triton.jit
def triton_add(in_ptr0, in_ptr1, out_ptr0, XBLOCK: tl.constexpr, XBLOCK_SUB: tl.constexpr):
    offset = tl.program_id(0) * XBLOCK
    base1 = tl.arange(0, XBLOCK_SUB)
    loops1: tl.constexpr = (XBLOCK + XBLOCK_SUB - 1) // XBLOCK_SUB
    for loop1 in range(loops1):
        x0 = offset + (loop1 * XBLOCK_SUB) + base1
        tmp0 = tl.load(in_ptr0 + (x0), None)
        tmp1 = tl.load(in_ptr1 + (x0), None)
        tmp2 = tmp0 + tmp1
        tl.store(out_ptr0 + (x0), tmp2, None)


@pytest.mark.parametrize('param_list',
                         [
                             ['float32', (2, 4096, 8), 2, 32768, 1024]
                         ]
                         )

def test_case(param_list):
    dtype, shape, ncore, xblock, xblock_sub = param_list
    x0 = test_common.generate_tensor(shape, dtype).npu()
    x1 = test_common.generate_tensor(shape, dtype).npu()
    y_ref = torch_pointwise(x0, x1)
    y_cal = torch.zeros(shape, dtype = eval('torch.' + dtype)).npu()
    triton_add[ncore, 1, 1](x0, x1, y_cal, xblock, xblock_sub)
    test_common.validate_cmp(dtype, y_cal, y_ref)
```

### 2.2 On-Device Operator Tuning

On-device operator information collection, reference command:
```bash
msprof op --kernel-name=triton_add pytest test_add.py
```
Note: `pytest test_add.py` is the executable command to be tested. For more features, refer to official documentation [Operator Development Tools - Operator Tuning](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/82RC1alpha003/devaids/optool/atlasopdev_16_0082.html)

Execution results: Refer to msprof output directory and insight view.

Persisted data: Refer to msprof output directory and insight view.
For detailed explanation of persisted performance metric data, refer to msprof op documentation: [Operator Development Tools - Operator Tuning](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/82RC1alpha003/devaids/optool/atlasopdev_16_0082.html)

Operator basic information:

Operator block Pipe information:

Insight information display (Memory):


### 2.3 Operator Simulation Tuning

Operator simulation information collection, reference command:
```bash
msprof op simulator --kernel-name=triton_add --soc-version=Ascend910B1 pytest test_add.py
```
Note: For more features, refer to official documentation [Operator Development Tools - Operator Tuning](https://www.hiascend.com/document/detail/zh/CANNCommunityEdition/82RC1alpha003/devaids/optool/atlasopdev_16_0082.html)

Execution results: Refer to simulator output directory and pipeline/hotspot views.

Persisted data: Refer to simulator output directory and pipeline/hotspot views.

Simulation pipeline diagram: Refer to simulator output directory and pipeline view.

Code hotspot diagram: Refer to simulator output directory and hotspot view.


Other usage notes:
- The msprof tool depends on the msopprof executable in the CANN package. The interface usage is consistent with msprof op. This file comes with the CANN package and requires no separate installation.
- Does not support starting multiple performance collection tasks on the same Device simultaneously.
- Before using msprof op and msprof op simulator, users need to ensure app functionality is normal.
- Currently does not support --aic-metrics=TimeLineDetail, kernelScale
