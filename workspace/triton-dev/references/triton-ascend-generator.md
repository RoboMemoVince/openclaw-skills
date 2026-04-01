---
name: triton-ascend-generator
description: Automatically generate triton-ascend operators optimized for Huawei Ascend NPU hardware. Based on operator description documents, pseudocode, or source code inputs, generate corresponding triton-ascend kernels and perform accuracy validation and performance testing.
---

## Script Execution and Debugging

- All script debugging and execution is done inside Docker:
    ```bash
    docker exec -itu root triton-ascend-hcq /bin/bash
    ```
- Run scripts with python3. Note there is no python alias; use python3 command.
- For other configuration issues, see [troubleshooting.md](../troubleshooting.md)

## Script Naming Convention

- `XX_fwd_triton.py`: Forward operator triton-ascend kernel test script
- `XX_bwd_triton.py`: Backward operator triton-ascend kernel test script

## Basic Test Set (mHC Related Operators)

- mHC related operators (including: sinkhorn, pre, post, pre_only, etc.) test set: (B,S,N,D)={(1,1024,4,5120),(1,2048,4,2560),(1,4096,4,2560),(1,2048,4,5120)}
    - Note: Sinkhorn actually uses tensor shape H_comb_before [B,S,N,N], D is only used for consistency with other mHC operator records
    - Example scripts: /data0/hcq/.trae/skills/triton-ascend-dev/demo/demo_mHC_post/
    - Execution (Profiler, run each shape separately):
        ```bash
        docker exec -itu root triton-ascend-hcq /bin/bash -lc '
          source /usr/local/Ascend/ascend-toolkit/latest/bin/setenv.bash &&
          export PATH=/data0/hcq/Ascend/ascend-toolkit/8.3.RC2/bisheng_toolkit/bishengir/bin:$PATH &&
          cd /data0/hcq/.trae/skills/triton-ascend-dev/demo/demo_mHC_post/XXXX &&
          python3 XX_fwd_triton.py --B 1 --S 1024 --N 4 --D 5120 --iters 20 --no-test --no-bench &&
          python3 XX_fwd_triton.py --B 1 --S 2048 --N 4 --D 2560 --iters 20 --no-test --no-bench &&
          python3 XX_fwd_triton.py --B 1 --S 4096 --N 4 --D 2560 --iters 20 --no-test --no-bench &&
          python3 XX_fwd_triton.py --B 1 --S 2048 --N 4 --D 5120 --iters 20 --no-test --no-bench
        '
        ```

## Workflow

### Read Input Materials (One or More of the Following)

- Operator description document: Detailed description document written according to operator functionality and computation flow.
- Pseudocode: Pseudocode written based on operator description document to represent operator computation flow.
- Source code: Open source code for this operator.
- Other: As needed, can add other related input materials such as test cases, performance metrics, etc.

### Write PyTorch Version of Operator as Accuracy Baseline

- Naming: Based on operator name, name PyTorch version operator as `def XX_reference()` in test script, where XX is the operator name, e.g., `def hc_post_fwd_reference()`, `def hc_post_bwd_reference()`.

- Forward operator: Based on operator description document and other input materials, implement forward operator computation and verify reference script implementation matches operator description document (pseudocode, source code, etc.), including input tensor shape/dtype, output tensor shape/dtype, computation flow, etc.

- Backward operator:
    1. If PyTorch version of corresponding forward operator already exists, use PyTorch autograd to implement backward operator as original accuracy baseline based on corresponding forward operator, named `def XX_bwd_autoGrad()`.
    2. Based on corresponding backward operator description document and other input materials, implement PyTorch version backward operator computation and verify reference script implementation matches operator description document (pseudocode, source code, etc.), including input tensor shape/dtype, output tensor shape/dtype, computation flow, etc. Verify autograd result matches manually implemented backward operator.
    3. If no PyTorch version of corresponding forward operator exists, implement PyTorch version backward operator computation based on operator description document and other input materials, and verify reference script implementation matches operator description document (pseudocode, source code, etc.), including input tensor shape/dtype, output tensor shape/dtype, computation flow, etc.

### Write or Call Test Tools

- Accuracy test: Use PyTorch's `torch.testing.assert_close()` function to compare triton-ascend operator output with PyTorch version operator output to determine if operator accuracy meets requirements. For backward gradient accuracy testing, add cosine similarity as additional metric to determine if gradients are consistent. Refer to utility functions: /data0/hcq/.trae/skills/triton-ascend-dev/mhc_tools.py.
- Performance test: Use triton-ascend provided performance testing tools to test operator runtime across different input shapes to determine if operator performance meets requirements. Refer to performance testing section in demo directories.
- Example test scripts: /data0/hcq/.trae/skills/triton-ascend-dev/demo/demo_mHC_post/mhc_post_fwd/mhc_post_fwd_triton.py, /data0/hcq/.trae/skills/triton-ascend-dev/demo/demo_mHC_post/mhc_post_bwd/mhc_post_bwd_triton.py

### Write triton-ascend Operator

- Based on operator description document and other input materials (forward or backward), implement triton-ascend operator computation and verify triton-ascend operator implementation matches operator description document (pseudocode, source code, etc.), including input tensor shape/dtype, output tensor shape/dtype, computation flow, etc.
- Run test script to ensure triton-ascend operator compiles successfully and runs, with output accuracy matching PyTorch version operator.
- Check triton-ascend operator performance. Performance is based on profiler data; see profiling data interpretation section in SKILL.md. Based on kernel_details.csv file generated by current test, check operator runtime (duration) and breakdown (aic_mac_time, aiv_vec_time for compute time; aic_mte2_time, aiv_mte2_time for memory transfer time) to determine if operator performance meets expectations. (File storage path is typically: /data0/hcq/result_profiling/XXXX/ASCEND_PROFILER_OUTPUT/kernel_details.csv, where XXXX is specific test name like devserver-c007-376t-1-1_343530_20260123084217671_ascend_pt)

### triton-ascend Operator Performance Optimization

- Based on kernel_details.csv file generated by current test, check operator runtime (duration) and breakdown (aic_mac_time, aiv_vec_time for compute time; aic_mte2_time, aiv_mte2_time for memory transfer time) to determine if operator performance meets expectations.
- Address operator performance bottlenecks with optimizations. For example, adjust thread block size (block_size), use shared memory techniques to reduce memory accesses, improve computation efficiency.
- Determine operator type: Pure Cube operator, Pure Vector operator, CV mixed operator.
    - Pure Cube operator: Contains only Cube operations, no other operation types, data doesn't need to be moved to vector cores, only transfers between Cube cores and memory. These operators can reference triton-ascend provided Cube operator examples. (See demo folder: demo/official_tutorials/05-matrix-multiplication.py, demo/official_tutorials/mm_demo.py)
    - Pure Vector operator: Contains only Vector operations, no other operation types, data doesn't need to be moved to Cube cores, only transfers between Vector cores and memory. These operators can reference triton-ascend provided Vector operator examples. (See demo folder: demo/official_tutorials/01-vector-add.py)
    - CV mixed operator: Contains both Cube and Vector operations, data needs to transfer between Cube and Vector cores. These operators can reference triton-ascend provided CV mixed operator examples. (See demo folder: demo/official_tutorials/04-fused-attention.py)
- Based on determined operator type, first evaluate if operator type is appropriate. If not, adjust operator type based on operator computation flow. For example, if involving large-scale matrix multiplication (M, N, K all large), consider prioritizing Cube cores for computation rather than Vector cores.
- For different operator types, perform targeted optimizations. For example, pure Cube operators can consider reducing memory accesses, improving computation efficiency. Pure Vector operators can consider using vector instructions and other techniques to improve computation efficiency. CV mixed operators can consider using parallel computation between Cube and Vector cores to improve computation efficiency.

## Profiling Data Interpretation

| Field | Description |
|-------|-------------|
| Duration(us) | Operator runtime in microseconds |
| aic_mac_time(us) | Operator computation time on Cube core in microseconds |
| aiv_vec_time(us) | Operator computation time on Vector core in microseconds |
| aic_mte2_time(us) | Operator memory transfer time on Cube core in microseconds, specifically L2/HBM to L1 cache time |
| aiv_mte2_time(us) | Operator memory transfer time on Vector core in microseconds, specifically L2/HBM to L1 cache time |
| Accelerator Core | AI_CORE indicates Cube core, AI_VECTOR_CORE indicates Vector core |
| Block Dim | Number of blocks |
| aicore_time(us) | Cube core total time, including data load, compute, store, instruction time, etc. |
| aic_scalar_time(us) | Operator scalar computation time on Cube core in microseconds |
| aic_mte1_time(us) | Operator memory transfer time on Cube core in microseconds, specifically L1 cache to L0 cache time |
| aiv_mte1_time(us) | Operator memory transfer time on Vector core in microseconds, specifically L1 cache to UB cache time |
| aic_fixpipe_time(us) | Operator data store time on Cube core in microseconds, specifically L0 cache to L2/HBM time |
| aiv_mte3_time(us) | Operator data store time on Vector core in microseconds, specifically UB cache to L2/HBM time |
