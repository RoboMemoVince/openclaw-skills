"""
HC Pre-Only Forward Triton Kernel Implementation.

This file contains ONLY:
- Triton kernel definitions
- Kernel wrapper function

NO test code, NO reference implementation.
"""

import torch
import triton
import triton.language as tl


# =============================================================================
# Triton Kernels
# =============================================================================

@triton.jit
def hc_matmul_pre_only_kernel_no_gamma(
    x_ptr,
    w_ptr,
    inv_rms_ptr,
    hpre_ptr,
    bias_ptr,
    M: tl.constexpr,
    K: tl.constexpr,
    N: tl.constexpr,
    NT: tl.constexpr,
    alpha_pre: tl.constexpr,
    norm_eps: tl.constexpr,
    hc_eps: tl.constexpr,
    BLOCK_M: tl.constexpr,
    BLOCK_K: tl.constexpr,
):
    """Fused kernel: dot + rsqrt + sigmoid (without gamma)."""
    pid = tl.program_id(0)
    m_start = pid * BLOCK_M
    m = m_start + tl.arange(0, BLOCK_M)

    bias = tl.load(bias_ptr + tl.arange(0, N))

    x_blk_ptr = tl.make_block_ptr(
        base=x_ptr,
        shape=(M, K),
        strides=(K, 1),
        offsets=(m_start, 0),
        block_shape=(BLOCK_M, BLOCK_K),
        order=(1, 0),
    )
    w_blk_ptr = tl.make_block_ptr(
        base=w_ptr,
        shape=(K, NT),
        strides=(NT, 1),
        offsets=(0, 0),
        block_shape=(BLOCK_K, NT),
        order=(1, 0),
    )

    acc = tl.zeros((BLOCK_M, NT), dtype=tl.float32)
    sumsq = tl.zeros((BLOCK_M,), dtype=tl.float32)

    for _ in range(0, K, BLOCK_K):
        x_blk = tl.load(x_blk_ptr, boundary_check=(0, 1), padding_option="zero").to(tl.float32)
        w_blk = tl.load(w_blk_ptr, boundary_check=(0, 1), padding_option="zero")
        sumsq += tl.sum(x_blk * x_blk, axis=1)
        acc = tl.dot(x_blk, w_blk, acc)
        x_blk_ptr = tl.advance(x_blk_ptr, (0, BLOCK_K))
        w_blk_ptr = tl.advance(w_blk_ptr, (BLOCK_K, 0))

    inv_rms = tl.rsqrt(sumsq / K + norm_eps)
    acc = acc * inv_rms[:, None]

    tl.store(inv_rms_ptr + m, inv_rms, mask=(m < M))

    acc_pre = tl.extract_slice(acc, (0, 0), (BLOCK_M, N), (1, 1))
    hpre = tl.sigmoid(alpha_pre * acc_pre + bias[None, :]) + hc_eps

    hpre_out_ptr = tl.make_block_ptr(
        base=hpre_ptr,
        shape=(M, N),
        strides=(N, 1),
        offsets=(m_start, 0),
        block_shape=(BLOCK_M, N),
        order=(1, 0),
    )
    tl.store(hpre_out_ptr, hpre, boundary_check=(0, 1))


@triton.jit
def hc_matmul_pre_only_kernel_gamma(
    x_ptr,
    gamma_ptr,
    w_ptr,
    inv_rms_ptr,
    hpre_ptr,
    bias_ptr,
    M: tl.constexpr,
    K: tl.constexpr,
    N: tl.constexpr,
    NT: tl.constexpr,
    alpha_pre: tl.constexpr,
    norm_eps: tl.constexpr,
    hc_eps: tl.constexpr,
    BLOCK_M: tl.constexpr,
    BLOCK_K: tl.constexpr,
):
    """Fused kernel: dot + rsqrt + sigmoid (with gamma)."""
    pid = tl.program_id(0)
    m_start = pid * BLOCK_M
    m = m_start + tl.arange(0, BLOCK_M)

    bias = tl.load(bias_ptr + tl.arange(0, N))

    x_blk_ptr = tl.make_block_ptr(
        base=x_ptr,
        shape=(M, K),
        strides=(K, 1),
        offsets=(m_start, 0),
        block_shape=(BLOCK_M, BLOCK_K),
        order=(1, 0),
    )
    w_blk_ptr = tl.make_block_ptr(
        base=w_ptr,
        shape=(K, NT),
        strides=(NT, 1),
        offsets=(0, 0),
        block_shape=(BLOCK_K, NT),
        order=(1, 0),
    )

    acc = tl.zeros((BLOCK_M, NT), dtype=tl.float32)
    sumsq = tl.zeros((BLOCK_M,), dtype=tl.float32)

    for k in range(0, K, BLOCK_K):
        x_blk = tl.load(x_blk_ptr, boundary_check=(0, 1), padding_option="zero").to(tl.float32)
        w_blk = tl.load(w_blk_ptr, boundary_check=(0, 1), padding_option="zero")
        sumsq += tl.sum(x_blk * x_blk, axis=1)
        gamma_offsets = k + tl.arange(0, BLOCK_K)
        gamma_mask = gamma_offsets < K
        gamma_blk = tl.load(gamma_ptr + gamma_offsets, mask=gamma_mask, other=0.0)
        x_blk = x_blk * gamma_blk[None, :]
        acc = tl.dot(x_blk, w_blk, acc)
        x_blk_ptr = tl.advance(x_blk_ptr, (0, BLOCK_K))
        w_blk_ptr = tl.advance(w_blk_ptr, (BLOCK_K, 0))

    inv_rms = tl.rsqrt(sumsq / K + norm_eps)
    acc = acc * inv_rms[:, None]

    tl.store(inv_rms_ptr + m, inv_rms, mask=(m < M))

    acc_pre = tl.extract_slice(acc, (0, 0), (BLOCK_M, N), (1, 1))
    hpre = tl.sigmoid(alpha_pre * acc_pre + bias[None, :]) + hc_eps

    hpre_out_ptr = tl.make_block_ptr(
        base=hpre_ptr,
        shape=(M, N),
        strides=(N, 1),
        offsets=(m_start, 0),
        block_shape=(BLOCK_M, N),
        order=(1, 0),
    )
    tl.store(hpre_out_ptr, hpre, boundary_check=(0, 1))


@triton.jit
def h_in_kernel_n4(
    x_ptr,
    hpre_ptr,
    out_ptr,
    M: tl.constexpr,
    D: tl.constexpr,
    stride_xm: tl.constexpr,
    stride_xn: tl.constexpr,
    stride_xd: tl.constexpr,
    stride_hm: tl.constexpr,
    stride_hn: tl.constexpr,
    stride_om: tl.constexpr,
    stride_od: tl.constexpr,
    BLOCK_M: tl.constexpr,
    BLOCK_D: tl.constexpr,
):
    """Reduction kernel: h_in = sum_n(H_pre * x) for N=4."""
    pid_m = tl.program_id(0)
    pid_d = tl.program_id(1)

    m_ids = pid_m * BLOCK_M + tl.arange(0, BLOCK_M)
    d_ids = pid_d * BLOCK_D + tl.arange(0, BLOCK_D)
    n_ids = tl.arange(0, 4)

    m_mask = m_ids < M
    d_mask = d_ids < D

    h = tl.load(
        hpre_ptr + m_ids[:, None] * stride_hm + n_ids[None, :] * stride_hn,
        mask=m_mask[:, None],
        other=0.0,
    )
    x = tl.load(
        x_ptr
        + m_ids[:, None, None] * stride_xm
        + n_ids[None, :, None] * stride_xn
        + d_ids[None, None, :] * stride_xd,
        mask=m_mask[:, None, None] & d_mask[None, None, :],
        other=0.0,
    ).to(tl.float32)

    acc = tl.sum(x * h[:, :, None], axis=1)
    tl.store(
        out_ptr + m_ids[:, None] * stride_om + d_ids[None, :] * stride_od,
        acc.to(tl.bfloat16),
        mask=m_mask[:, None] & d_mask[None, :],
    )


# =============================================================================
# Weight Padding Cache
# =============================================================================

_WEIGHT_PAD_CACHE = {}


def _maybe_pad_weight_for_dot(hc_weight: torch.Tensor, N: int):
    """Pad weight from [K,4] to [K,24] for better cube alignment."""
    if N != 4:
        return hc_weight, N
    if hc_weight.shape[1] != 4:
        return hc_weight, hc_weight.shape[1]
    NT = 24
    cache_key = (hc_weight.data_ptr(), tuple(hc_weight.shape), hc_weight.dtype, hc_weight.device)
    cached = _WEIGHT_PAD_CACHE.get(cache_key)
    if cached is not None:
        return cached, NT
    padded = torch.zeros((hc_weight.shape[0], NT), device=hc_weight.device, dtype=hc_weight.dtype)
    padded[:, :N].copy_(hc_weight)
    _WEIGHT_PAD_CACHE[cache_key] = padded
    return padded, NT


# =============================================================================
# Wrapper Function
# =============================================================================

def hc_pre_only_triton(
    x: torch.Tensor,
    hc_weight: torch.Tensor,
    alpha_pre: torch.Tensor | float,
    bias_pre: torch.Tensor,
    gamma: torch.Tensor | None = None,
    norm_eps: float = 1e-6,
    hc_eps: float = 1e-6,
):
    """
    HC Pre-Only Forward Triton Implementation.

    Args:
        x: Input tensor [B, S, N, D], BF16
        hc_weight: Weight tensor [N*D, N], FP32
        alpha_pre: Scalar or tensor, FP32
        bias_pre: Bias tensor [N], FP32
        gamma: Optional gamma tensor [N*D], FP32
        norm_eps: RMS normalization epsilon
        hc_eps: HC epsilon added after sigmoid

    Returns:
        h_in: Output tensor [B, S, D], BF16
    """
    assert x.is_npu and hc_weight.is_npu
    x = x.contiguous()
    hc_weight = hc_weight.contiguous()
    if gamma is not None:
        gamma = gamma.contiguous()

    B, S, N, D = x.shape
    if N != 4:
        raise ValueError(f"Current implementation only supports N=4, got N={N}")

    M = B * S
    K = N * D

    x_flat_mk = x.view(M, K)
    x_flat_mnd = x.view(M, N, D)

    if isinstance(alpha_pre, torch.Tensor):
        alpha_pre_val = alpha_pre.item() if alpha_pre.numel() == 1 else float(alpha_pre.flatten()[0].item())
    else:
        alpha_pre_val = float(alpha_pre)

    bias_pre = bias_pre.contiguous()
    inv_rms = torch.empty((M,), device=x.device, dtype=torch.float32)
    hpre = torch.empty((M, N), device=x.device, dtype=torch.float32)
    h_in = torch.empty((M, D), device=x.device, dtype=torch.bfloat16)

    w_launch, NT = _maybe_pad_weight_for_dot(hc_weight, N)

    grid = lambda meta: (triton.cdiv(M, meta["BLOCK_M"]),)
    if gamma is None:
        hc_matmul_pre_only_kernel_no_gamma[grid](
            x_flat_mk,
            w_launch,
            inv_rms,
            hpre,
            bias_pre,
            M=M,
            K=K,
            N=N,
            NT=NT,
            alpha_pre=alpha_pre_val,
            norm_eps=norm_eps,
            hc_eps=hc_eps,
            BLOCK_M=64,
            BLOCK_K=192,
        )
    else:
        hc_matmul_pre_only_kernel_gamma[grid](
            x_flat_mk,
            gamma,
            w_launch,
            inv_rms,
            hpre,
            bias_pre,
            M=M,
            K=K,
            N=N,
            NT=NT,
            alpha_pre=alpha_pre_val,
            norm_eps=norm_eps,
            hc_eps=hc_eps,
            BLOCK_M=64,
            BLOCK_K=192,
        )

    grid = lambda meta: (triton.cdiv(M, meta["BLOCK_M"]), triton.cdiv(D, meta["BLOCK_D"]))
    h_in_kernel_n4[grid](
        x_flat_mnd,
        hpre,
        h_in,
        M=M,
        D=D,
        stride_xm=x_flat_mnd.stride(0),
        stride_xn=x_flat_mnd.stride(1),
        stride_xd=x_flat_mnd.stride(2),
        stride_hm=hpre.stride(0),
        stride_hn=hpre.stride(1),
        stride_om=h_in.stride(0),
        stride_od=h_in.stride(1),
        BLOCK_M=32,
        BLOCK_D=128,
    )

    return h_in.view(B, S, D)
