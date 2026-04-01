"""
Triton-Ascend operator development utilities.

This module provides common functions for:
- Profiler data collection and parsing
- msprof op collection and CSV parsing
- Benchmark utilities
- Accuracy validation utilities
"""

import csv
import os
import shlex
import subprocess
import time
from collections import defaultdict

import torch
import torch_npu
import triton.runtime.driver as driver
from rich import box
from rich.console import Console
from rich.table import Table


# =============================================================================
# Profiler Utilities
# =============================================================================

def profiler_wrapper(fn, result_path=None, skip_first=10, warmup=10, active=10, repeat=1):
    """
    NPU profiler collection wrapper for triton functions.

    - First call triggers Triton compilation, so an extra warmup run is done first
    - Trace output goes to result_path (can be parsed with tensorboard/torch_npu profiler tools)

    Args:
        fn: Callable to profile (typically a triton wrapper function that takes no args)
        result_path: Output directory for profiler trace (default: ./result_profiling)
        skip_first: Number of iterations to skip before profiling
        warmup: Number of warmup iterations in profiling schedule
        active: Number of active profiling iterations
        repeat: Number of profiling cycles to repeat

    Returns:
        None (results written to result_path)
    """
    if result_path is None:
        result_path = "./result_profiling"

    wait = 0
    stream = torch.npu.current_stream()
    experimental_config = torch_npu.profiler._ExperimentalConfig(
        aic_metrics=torch_npu.profiler.AiCMetrics.PipeUtilization,
        profiler_level=torch_npu.profiler.ProfilerLevel.Level1,
        l2_cache=False,
        data_simplification=False
    )

    # First run to trigger triton compilation, avoiding compilation overhead in profiling
    fn()
    stream.synchronize()

    with torch_npu.profiler.profile(
            activities=[
                torch_npu.profiler.ProfilerActivity.CPU,
                torch_npu.profiler.ProfilerActivity.NPU
            ],
            schedule=torch_npu.profiler.schedule(wait=wait, warmup=warmup, active=active, repeat=repeat,
                                                 skip_first=skip_first),
            on_trace_ready=torch_npu.profiler.tensorboard_trace_handler(result_path),
            record_shapes=True,
            profile_memory=False,
            with_stack=False,
            with_flops=False,
            with_modules=False,
            experimental_config=experimental_config) as prof:
        stream.synchronize()
        for i in range(skip_first + (wait + warmup + active) * repeat):
            fn()
            prof.step()
        stream.synchronize()


def print_profiler_kernel_avg_duration(result_path="./result_profiling"):
    """
    Parse and print average kernel durations from profiler's kernel_details.csv.

    Args:
        result_path: Root directory containing profiler output

    Returns:
        dict: {kernel_name: avg_duration_us} or None if not found
    """
    latest_csv_path = None
    latest_mtime = None
    for root, _, files in os.walk(result_path):
        if "kernel_details.csv" not in files:
            continue
        path = os.path.join(root, "kernel_details.csv")
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if latest_mtime is None or mtime > latest_mtime:
            latest_mtime = mtime
            latest_csv_path = path

    if latest_csv_path is None:
        print(f"[Profiler] kernel_details.csv not found in {result_path}")
        return None

    durations_us = defaultdict(float)
    kernel_counts = defaultdict(int)

    with open(latest_csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        if "Duration(us)" not in fieldnames:
            print(f"[Profiler] CSV missing Duration(us) column: {latest_csv_path}")
            return None
        if "Name" not in fieldnames:
            print(f"[Profiler] CSV missing Name column: {latest_csv_path}")
            return None

        for row in reader:
            # Skip warmup rows (no Step Id) - only count active profiling phase
            step_id = (row.get("Step Id") or "").strip()
            if not step_id:
                continue

            name = (row.get("Name") or "").strip()
            duration_raw = (row.get("Duration(us)") or "").strip()
            if not name or not duration_raw:
                continue
            try:
                duration = float(duration_raw)
            except ValueError:
                continue
            durations_us[name] += duration
            kernel_counts[name] += 1

    profiled_runs = max(kernel_counts.values()) if kernel_counts else 1
    rows = [
        (name, total / kernel_counts[name])
        for name, total in durations_us.items()
    ]
    rows.sort(key=lambda x: x[1], reverse=True)

    console = Console()
    table = Table(
        title=f"\nProfiler Kernel Avg Duration (us) | runs={profiled_runs}\n{latest_csv_path}",
        box=box.SIMPLE_HEAVY,
    )
    table.add_column("Kernel", justify="left", style="cyan", no_wrap=True)
    table.add_column("Avg Duration (us)", justify="right", style="magenta")
    for name, avg_us in rows:
        table.add_row(name, f"{avg_us:.3f}")
    console.print(table)
    total_avg_us = sum(avg_us for _, avg_us in rows)
    console.print(f"Total Avg Duration (us): {total_avg_us:.3f}")

    return {name: avg_us for name, avg_us in rows}


# =============================================================================
# msprof op Utilities
# =============================================================================

def _find_first_csv_with_columns(root, required_cols):
    """Find first CSV file containing all required columns."""
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if not name.endswith(".csv"):
                continue
            path = os.path.join(dirpath, name)
            try:
                with open(path, "r", newline="") as f:
                    reader = csv.DictReader(f)
                    cols = set(reader.fieldnames or [])
                    if required_cols.issubset(cols):
                        return path
            except Exception:
                continue
    return None


def parse_msprof_op_avg_duration_us(msprof_out_dir, kernel_name_substr):
    """
    Parse average duration from msprof op output directory.

    Args:
        msprof_out_dir: msprof output directory
        kernel_name_substr: Substring to match kernel name

    Returns:
        tuple: (avg_duration_us, csv_path) or (None, None) if not found
    """
    for dirpath, _, filenames in os.walk(msprof_out_dir):
        if "OpBasicInfo.csv" not in filenames:
            continue
        csv_path = os.path.join(dirpath, "OpBasicInfo.csv")
        try:
            with open(csv_path, "r", newline="") as f:
                reader = csv.DictReader(f)
                fields = reader.fieldnames or []
                if "Op Name" not in fields or "Task Duration(us)" not in fields:
                    continue
                durs = []
                for row in reader:
                    name = (row.get("Op Name") or "").strip()
                    if not name or kernel_name_substr not in name:
                        continue
                    dur_raw = (row.get("Task Duration(us)") or "").strip()
                    try:
                        durs.append(float(dur_raw))
                    except Exception:
                        continue
                if durs:
                    return sum(durs) / len(durs), csv_path
        except Exception:
            continue

    candidates = [
        {"Kernel Name", "Duration(us)"},
        {"KernelName", "Duration(us)"},
        {"Name", "Duration(us)"},
        {"Kernel Name", "Duration (us)"},
        {"Name", "Duration (us)"},
    ]
    for cols in candidates:
        csv_path = _find_first_csv_with_columns(msprof_out_dir, cols)
        if csv_path is None:
            continue
        if "Kernel Name" in cols:
            key_name = "Kernel Name"
        elif "KernelName" in cols:
            key_name = "KernelName"
        else:
            key_name = "Name"
        if "Duration(us)" in cols:
            key_dur = "Duration(us)"
        else:
            key_dur = "Duration (us)"
        durations = []
        with open(csv_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = (row.get(key_name) or "").strip()
                if not name or kernel_name_substr not in name:
                    continue
                dur_raw = (row.get(key_dur) or "").strip()
                try:
                    dur = float(dur_raw)
                except Exception:
                    continue
                durations.append(dur)
        if durations:
            return sum(durations) / len(durations), csv_path

    return None, None


def _prepare_msprof_env(base_env=None):
    """Prepare environment variables for msprof execution."""
    if base_env is None:
        env = os.environ.copy()
    else:
        env = dict(base_env)
    env.setdefault("ASCEND_TOOLKIT_HOME", "/usr/local/Ascend/ascend-toolkit/latest")
    ld = env.get("LD_LIBRARY_PATH", "")
    driver_lib = "/usr/local/Ascend/driver/lib64/driver"
    parts = []
    for p in ld.split(":"):
        if p:
            parts.append(p)
    if driver_lib not in parts:
        parts.insert(0, driver_lib)
    env["LD_LIBRARY_PATH"] = ":".join(parts)
    return env


def msprof_op_collect(
    kernel_name,
    output_root,
    entry_py,
    entry_args=None,
    tag=None,
    warm_up=5,
    launch_count=1,
    kill="on",
    extra_env=None,
    python_bin="python3",
):
    """
    Collect kernel performance data using msprof op mode.

    Args:
        kernel_name: Kernel name filter (substring matching)
        output_root: Root directory for msprof output
        entry_py: Python entry script path to be executed by msprof
        entry_args: List of arguments for entry script
        tag: Output subdirectory prefix (default: kernel_name)
        warm_up: Number of warmup iterations
        launch_count: Number of profiling samples
        kill: Whether to kill process after collection ("on"/"off")
        extra_env: Additional environment variables
        python_bin: Python executable path

    Returns:
        tuple: (out_dir, avg_duration_us, csv_path)
    """
    ts = time.strftime("%Y%m%d_%H%M%S")
    prefix = tag if tag is not None else kernel_name
    out_dir = os.path.join(output_root, f"{prefix}_{ts}")
    os.makedirs(out_dir, exist_ok=True)

    cmd = [
        "msprof",
        "op",
        f"--kernel-name={kernel_name}",
        f"--output={out_dir}",
        f"--warm-up={warm_up}",
        f"--launch-count={launch_count}",
        f"--kill={kill}",
        python_bin,
        entry_py,
    ]
    if entry_args:
        cmd.extend(list(entry_args))

    env = _prepare_msprof_env(extra_env)

    print(f"\n[msprof] {out_dir}")
    print(f"[msprof] {shlex.join(cmd)}")
    subprocess.run(cmd, check=True, env=env)

    avg_us, csv_path = parse_msprof_op_avg_duration_us(out_dir, kernel_name)
    return out_dir, avg_us, csv_path


# =============================================================================
# Benchmark Utilities
# =============================================================================

def bench(fn, warmup=5, iters=10):
    """
    Benchmark wrapper: warmup + timed iterations with peak memory tracking.

    Args:
        fn: Callable to benchmark (takes no args, returns output tensor(s))
        warmup: Number of warmup iterations
        iters: Number of timed iterations

    Returns:
        tuple: (output, avg_time_us, peak_mem_mb)
               If fn returns tuple: (*outputs, avg_time_us, peak_mem_mb)
    """
    # 1. Warmup
    for _ in range(warmup):
        fn()
    torch.npu.synchronize()

    # 2. Memory tracking setup
    torch.npu.reset_peak_memory_stats()
    begin_mem = torch.npu.memory_allocated()

    # 3. Timing
    start_event = torch.npu.Event(enable_timing=True)
    end_event = torch.npu.Event(enable_timing=True)

    with torch.no_grad():
        start_event.record()
        for _ in range(iters):
            out = fn()
        end_event.record()
    torch.npu.synchronize()

    # 4. Calculate metrics
    elapsed_time_us = start_event.elapsed_time(end_event) / iters * 1000  # us
    peak_mem = torch.npu.max_memory_allocated()
    active_mem_mb = (peak_mem - begin_mem) / 1024 / 1024  # MB

    if isinstance(out, tuple):
        return (*out, elapsed_time_us, active_mem_mb)
    else:
        return (out, elapsed_time_us, active_mem_mb)


# =============================================================================
# Accuracy Validation Utilities
# =============================================================================

def rel_err(a, b, eps=1e-12):
    """
    Compute relative error: ||a-b|| / (||b|| + eps).

    Args:
        a: Result tensor
        b: Reference tensor
        eps: Small constant for numerical stability

    Returns:
        float: Relative error scalar
    """
    return (torch.norm((a - b).abs()) / (torch.norm(b) + eps)).item()


def cosine_sim(a, b, eps=1e-8):
    """
    Compute cosine similarity between two tensors.

    Args:
        a: First tensor
        b: Second tensor
        eps: Small constant for numerical stability

    Returns:
        float: Cosine similarity scalar
    """
    return torch.nn.functional.cosine_similarity(
        a.float().flatten(), b.float().flatten(), dim=0, eps=eps
    ).item()


def assert_close(result, golden, name, rtol=1e-5, atol=1e-5):
    """
    Assert two tensors are close with detailed error reporting.

    Args:
        result: Result tensor from triton implementation
        golden: Reference tensor from PyTorch implementation
        name: Name for logging
        rtol: Relative tolerance
        atol: Absolute tolerance

    Raises:
        AssertionError: If tensors are not close
    """
    try:
        torch.testing.assert_close(result, golden, rtol=rtol, atol=atol)
        print(f"[Accuracy] {name}: PASS")
    except AssertionError as e:
        max_abs = (result - golden).abs().max().item()
        denom = golden.abs().clamp_min(1e-6)
        max_rel = ((result - golden).abs() / denom).max().item()
        print(f"[Accuracy] {name}: FAIL  max_abs={max_abs:.3e} max_rel={max_rel:.3e}")
        raise


def assert_close_bf16(result, golden, name, rtol=2**-6, atol=2**-6):
    """
    Assert two BF16 tensors are close with segmented tolerance.

    For |golden| < 1: uses atol only
    For |golden| >= 1: uses rtol only

    Args:
        result: Result tensor
        golden: Reference tensor
        name: Name for logging
        rtol: Relative tolerance for large values
        atol: Absolute tolerance for small values

    Raises:
        AssertionError: If tensors are not close
    """
    mask = golden.abs() < 1.0
    try:
        torch.testing.assert_close(result[mask], golden[mask], atol=atol, rtol=0)
        torch.testing.assert_close(result[~mask], golden[~mask], atol=0, rtol=rtol)
        print(f"[Accuracy] {name}: PASS")
    except AssertionError as e:
        max_abs = (result - golden).abs().max().item()
        denom = golden.abs().clamp_min(1e-6)
        max_rel = ((result - golden).abs() / denom).max().item()
        print(f"[Accuracy] {name}: FAIL  max_abs={max_abs:.3e} max_rel={max_rel:.3e}")
        raise


def check_finite(tensor, name):
    """
    Check tensor contains no NaN or Inf values.

    Args:
        tensor: Tensor to check
        name: Name for logging

    Raises:
        AssertionError: If tensor contains NaN or Inf
    """
    assert torch.isfinite(tensor).all(), f"[Accuracy] {name}: contains NaN or Inf"
    print(f"[Accuracy] {name}: finite check PASS")


# =============================================================================
# Device Utilities
# =============================================================================

def get_npu_properties():
    """
    Get current NPU device properties.

    Returns:
        Device properties object from Triton runtime driver
    """
    device = torch.npu.current_device()
    return driver.active.utils.get_device_properties(device)


def set_seed(seed=42):
    """
    Set random seed for reproducibility.

    Args:
        seed: Random seed value
    """
    import random
    random.seed(seed)
    torch.manual_seed(seed)
    torch.npu.manual_seed_all(seed)
