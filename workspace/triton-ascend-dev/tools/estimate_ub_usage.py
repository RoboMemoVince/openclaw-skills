#!/usr/bin/env python3
"""
Estimate UB (Unified Buffer) usage based on BLOCK parameters.

Helps predict whether a kernel configuration will cause UB overflow
before actually running the kernel.
"""

import argparse
from typing import Dict, List, Tuple

# Ascend NPU UB capacity (typical values)
UB_CAPACITY_BYTES = {
    "910B": 256 * 1024,    # 256 KB
    "910_95": 192 * 1024,  # 192 KB
    "default": 256 * 1024,
}

# Data type sizes in bytes
DTYPE_SIZES = {
    "float32": 4,
    "fp32": 4,
    "float16": 2,
    "fp16": 2,
    "bfloat16": 2,
    "bf16": 2,
    "int32": 4,
    "int16": 2,
    "int8": 1,
    "float8": 1,
    "fp8": 1,
}


def estimate_tensor_size(shape: Tuple[int, ...], dtype: str) -> int:
    """Estimate memory size for a tensor in bytes."""
    dtype_size = DTYPE_SIZES.get(dtype.lower(), 4)
    num_elements = 1
    for dim in shape:
        num_elements *= dim
    return num_elements * dtype_size


def estimate_ub_usage(
    block_params: Dict[str, int],
    tensor_specs: List[Dict],
    include_accumulator: bool = True,
    accumulator_dtype: str = "float32",
) -> Tuple[int, Dict[str, int]]:
    """
    Estimate total UB usage for a kernel configuration.

    Args:
        block_params: Dict of BLOCK_* parameters, e.g., {"BLOCK_M": 128, "BLOCK_N": 128, "BLOCK_K": 64}
        tensor_specs: List of tensor specifications, each dict has:
            - "name": tensor name
            - "shape_expr": shape as tuple of strings referencing block_params, e.g., ("BLOCK_M", "BLOCK_K")
            - "dtype": data type string
            - "count": number of buffers (e.g., 2 for double buffering)
        include_accumulator: Whether to include accumulator tensor
        accumulator_dtype: Data type for accumulator

    Returns:
        Tuple of (total_bytes, breakdown_dict)
    """
    breakdown = {}
    total = 0

    for spec in tensor_specs:
        name = spec["name"]
        shape_expr = spec["shape_expr"]
        dtype = spec["dtype"]
        count = spec.get("count", 1)

        # Resolve shape expression
        shape = []
        for dim_expr in shape_expr:
            if isinstance(dim_expr, str):
                if dim_expr in block_params:
                    shape.append(block_params[dim_expr])
                else:
                    # Try to evaluate as expression
                    try:
                        shape.append(eval(dim_expr, {"__builtins__": {}}, block_params))
                    except:
                        raise ValueError(f"Cannot resolve dimension expression: {dim_expr}")
            else:
                shape.append(dim_expr)

        tensor_size = estimate_tensor_size(tuple(shape), dtype) * count
        breakdown[name] = tensor_size
        total += tensor_size

    # Add accumulator if needed (typically BLOCK_M x BLOCK_N x fp32)
    if include_accumulator and "BLOCK_M" in block_params and "BLOCK_N" in block_params:
        acc_shape = (block_params["BLOCK_M"], block_params["BLOCK_N"])
        acc_size = estimate_tensor_size(acc_shape, accumulator_dtype)
        breakdown["accumulator"] = acc_size
        total += acc_size

    return total, breakdown


def check_ub_overflow(
    total_bytes: int,
    platform: str = "default",
    safety_margin: float = 0.9,
) -> Tuple[bool, float]:
    """
    Check if UB usage exceeds capacity.

    Args:
        total_bytes: Total estimated UB usage
        platform: Platform name for UB capacity lookup
        safety_margin: Safety margin (0.9 = use 90% of UB max)

    Returns:
        Tuple of (is_safe, utilization_ratio)
    """
    capacity = UB_CAPACITY_BYTES.get(platform, UB_CAPACITY_BYTES["default"])
    safe_capacity = capacity * safety_margin
    utilization = total_bytes / capacity
    is_safe = total_bytes <= safe_capacity
    return is_safe, utilization


def print_report(
    block_params: Dict[str, int],
    total_bytes: int,
    breakdown: Dict[str, int],
    platform: str = "default",
):
    """Print a formatted UB usage report."""
    is_safe, utilization = check_ub_overflow(total_bytes, platform)
    capacity = UB_CAPACITY_BYTES.get(platform, UB_CAPACITY_BYTES["default"])

    print("=" * 60)
    print("UB Usage Estimation Report")
    print("=" * 60)

    print(f"\nBlock Parameters:")
    for name, value in block_params.items():
        print(f"  {name}: {value}")

    print(f"\nTensor Breakdown:")
    for name, size in breakdown.items():
        print(f"  {name}: {size:,} bytes ({size/1024:.1f} KB)")

    print(f"\nSummary:")
    print(f"  Total estimated: {total_bytes:,} bytes ({total_bytes/1024:.1f} KB)")
    print(f"  UB capacity ({platform}): {capacity:,} bytes ({capacity/1024:.1f} KB)")
    print(f"  Utilization: {utilization*100:.1f}%")
    print(f"  Status: {'✓ SAFE' if is_safe else '✗ OVERFLOW RISK'}")

    if not is_safe:
        print(f"\n  Recommendation: Reduce BLOCK sizes to stay under {capacity*0.9/1024:.1f} KB")

    print("=" * 60)


# Example configurations for common kernel types
MATMUL_TENSOR_SPECS = [
    {"name": "A_block", "shape_expr": ("BLOCK_M", "BLOCK_K"), "dtype": "float16", "count": 2},
    {"name": "B_block", "shape_expr": ("BLOCK_K", "BLOCK_N"), "dtype": "float16", "count": 2},
]

ATTENTION_TENSOR_SPECS = [
    {"name": "Q_block", "shape_expr": ("BLOCK_M", "HEAD_DIM"), "dtype": "float16", "count": 1},
    {"name": "K_block", "shape_expr": ("BLOCK_N", "HEAD_DIM"), "dtype": "float16", "count": 2},
    {"name": "V_block", "shape_expr": ("BLOCK_N", "HEAD_DIM"), "dtype": "float16", "count": 2},
    {"name": "QK_scores", "shape_expr": ("BLOCK_M", "BLOCK_N"), "dtype": "float32", "count": 1},
]


def main():
    parser = argparse.ArgumentParser(description="Estimate UB usage for Triton-Ascend kernels")
    parser.add_argument("--type", choices=["matmul", "attention", "custom"], default="matmul",
                        help="Kernel type for preset tensor specs")
    parser.add_argument("--BLOCK_M", type=int, default=128)
    parser.add_argument("--BLOCK_N", type=int, default=128)
    parser.add_argument("--BLOCK_K", type=int, default=64)
    parser.add_argument("--HEAD_DIM", type=int, default=64)
    parser.add_argument("--platform", default="default", help="Platform: 910B, 910_95, default")
    args = parser.parse_args()

    block_params = {
        "BLOCK_M": args.BLOCK_M,
        "BLOCK_N": args.BLOCK_N,
        "BLOCK_K": args.BLOCK_K,
        "HEAD_DIM": args.HEAD_DIM,
    }

    if args.type == "matmul":
        tensor_specs = MATMUL_TENSOR_SPECS
    elif args.type == "attention":
        tensor_specs = ATTENTION_TENSOR_SPECS
    else:
        print("Custom mode: define tensor_specs in code")
        tensor_specs = []

    total, breakdown = estimate_ub_usage(block_params, tensor_specs)
    print_report(block_params, total, breakdown, args.platform)


if __name__ == "__main__":
    main()
