"""
HC Pre-Only Forward Test Script.

This script performs:
- Accuracy testing (triton vs reference)
- Benchmark (timing and memory)
- Profiler collection

Usage:
    python3 hc_pre_only_fwd_test.py --B 1 --S 2048 --N 4 --D 2560
    python3 hc_pre_only_fwd_test.py --B 1 --S 1024 --N 4 --D 5120 --no-profile
    python3 hc_pre_only_fwd_test.py --no-test --no-bench  # profiler only
"""

import argparse
import torch
import torch_npu
from rich import box
from rich.console import Console
from rich.table import Table

from hc_pre_only_fwd_triton import hc_pre_only_triton
from hc_pre_only_fwd_ref import hc_pre_only_reference
from utils import (
    assert_close_bf16,
    bench,
    profiler_wrapper,
    print_profiler_kernel_avg_duration,
    rel_err,
    set_seed,
)


# =============================================================================
# Test Data Generation
# =============================================================================

def generate_test_data(B: int, S: int, N: int, D: int, device: str, with_gamma: bool):
    """Generate test data with fixed shapes."""
    x = torch.randn((B, S, N, D), device=device, dtype=torch.bfloat16)
    gamma = torch.randn((N * D,), device=device, dtype=torch.float32) if with_gamma else None
    hc_weight = torch.randn((N * D, N), device=device, dtype=torch.float32)
    alpha_pre = torch.tensor([0.8], device=device, dtype=torch.float32)
    bias_pre = torch.randn((N,), device=device, dtype=torch.float32)
    return x, gamma, hc_weight, alpha_pre, bias_pre


# =============================================================================
# Accuracy Test
# =============================================================================

def check_accuracy(x, gamma, hc_weight, alpha_pre, bias_pre, norm_eps, hc_eps):
    """Compare triton implementation against reference."""
    h_in_triton = hc_pre_only_triton(
        x, hc_weight, alpha_pre, bias_pre,
        gamma=gamma, norm_eps=norm_eps, hc_eps=hc_eps
    )
    h_in_ref = hc_pre_only_reference(
        x, hc_weight, alpha_pre, bias_pre,
        gamma=gamma, norm_eps=norm_eps, hc_eps=hc_eps
    )

    # Check dtype
    assert h_in_triton.dtype == torch.bfloat16, f"Expected BF16, got {h_in_triton.dtype}"

    # Accuracy assertion
    assert_close_bf16(
        h_in_triton.float(), h_in_ref.float(),
        "h_in", rtol=2**-5, atol=2**-5
    )


# =============================================================================
# Benchmark
# =============================================================================

def run_benchmark(x, gamma, hc_weight, alpha_pre, bias_pre, norm_eps, hc_eps):
    """Run benchmark comparing triton vs reference."""
    # Triton benchmark
    out_triton, t_triton, m_triton = bench(
        lambda: hc_pre_only_triton(
            x, hc_weight, alpha_pre, bias_pre,
            gamma=gamma, norm_eps=norm_eps, hc_eps=hc_eps
        )
    )

    # Reference benchmark
    out_ref, t_ref, m_ref = bench(
        lambda: hc_pre_only_reference(
            x, hc_weight, alpha_pre, bias_pre,
            gamma=gamma, norm_eps=norm_eps, hc_eps=hc_eps
        )
    )

    # Relative error
    e = rel_err(out_triton.float(), out_ref.float())

    # Display results
    console = Console()
    table = Table(
        title=f"\nHC Pre-Only Forward: B={x.shape[0]} S={x.shape[1]} N={x.shape[2]} D={x.shape[3]}",
        box=box.SIMPLE_HEAVY,
    )
    table.add_column("Method", justify="left", style="cyan", no_wrap=True)
    table.add_column("Time (us)", justify="right", style="magenta")
    table.add_column("Memory (MB)", justify="right", style="green")
    table.add_column("RelErr", justify="right", style="red")
    table.add_row("Reference", f"{t_ref:.0f}", f"{m_ref:.1f}", "-")
    table.add_row("Triton", f"{t_triton:.0f}", f"{m_triton:.1f}", f"{e:.2e}")
    console.print(table)


# =============================================================================
# Profiler
# =============================================================================

def run_profiler(x, gamma, hc_weight, alpha_pre, bias_pre, norm_eps, hc_eps, result_path):
    """Run NPU profiler and print kernel durations."""
    profiler_wrapper(
        lambda: hc_pre_only_triton(
            x, hc_weight, alpha_pre, bias_pre,
            gamma=gamma, norm_eps=norm_eps, hc_eps=hc_eps
        ),
        result_path=result_path
    )
    print_profiler_kernel_avg_duration(result_path)


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="HC Pre-Only Forward Test")

    # Shape parameters
    parser.add_argument("--B", type=int, default=1, help="Batch size")
    parser.add_argument("--S", type=int, default=2048, help="Sequence length")
    parser.add_argument("--N", type=int, default=4, help="N dimension (must be 4)")
    parser.add_argument("--D", type=int, default=2560, help="D dimension")

    # Test options
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--norm-eps", type=float, default=1e-6)
    parser.add_argument("--hc-eps", type=float, default=1e-6)
    parser.add_argument("--no-gamma", action="store_true", help="Disable gamma")

    # Mode switches
    parser.add_argument("--no-test", action="store_true", help="Skip accuracy test")
    parser.add_argument("--no-bench", action="store_true", help="Skip benchmark")
    parser.add_argument("--no-profile", action="store_true", help="Skip profiler")

    # Profiler output
    parser.add_argument("--result-path", type=str, default="./result_profiling",
                        help="Profiler output directory")

    args = parser.parse_args()

    # Set seed for reproducibility
    set_seed(args.seed)

    # Device
    device = "npu:0"

    # Generate test data
    x, gamma, hc_weight, alpha_pre, bias_pre = generate_test_data(
        args.B, args.S, args.N, args.D,
        device=device,
        with_gamma=not args.no_gamma
    )

    if args.no_gamma:
        gamma = None

    # Run tests
    if not args.no_test:
        print("\n[Accuracy Test]")
        check_accuracy(x, gamma, hc_weight, alpha_pre, bias_pre, args.norm_eps, args.hc_eps)

    if not args.no_bench:
        print("\n[Benchmark]")
        run_benchmark(x, gamma, hc_weight, alpha_pre, bias_pre, args.norm_eps, args.hc_eps)

    if not args.no_profile:
        print("\n[Profiler]")
        run_profiler(x, gamma, hc_weight, alpha_pre, bias_pre, args.norm_eps, args.hc_eps, args.result_path)


if __name__ == "__main__":
    main()
