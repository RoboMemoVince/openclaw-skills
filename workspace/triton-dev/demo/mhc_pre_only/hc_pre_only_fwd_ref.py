"""
HC Pre-Only Forward PyTorch Reference Implementation.

This file contains ONLY the PyTorch reference implementation
as accuracy gold standard. NO triton code, NO test code.

Documentation correspondence:
- Input: x [B,S,N,D] BF16, hc_weight [N*D,N] FP32, alpha_pre scalar, bias_pre [N] FP32
- Output: h_in [B,S,D] BF16

Computation flow:
1. x_rs = Cast(x).reshape(B,S,K) where K=N*D  (FP32)
2. H = x_rs @ hc_weight                        (FP32, [B,S,N])
3. inv_rms = rsqrt(mean(x_rs^2, dim=-1) + eps) (FP32)
4. H_pre = sigmoid(alpha * H * inv_rms + bias) + hc_eps (FP32)
5. h_in = sum_n(H_pre * x_reshaped)            (BF16 output)
"""

import torch


def hc_pre_only_reference(
    x: torch.Tensor,
    hc_weight: torch.Tensor,
    alpha_pre: torch.Tensor | float,
    bias_pre: torch.Tensor,
    gamma: torch.Tensor | None = None,
    norm_eps: float = 1e-6,
    hc_eps: float = 1e-6,
):
    """
    HC Pre-Only Forward Reference Implementation.

    Implements the operator exactly as documented, line-by-line.

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
    B, S, N, D = x.shape

    # Step 1: Cast to FP32 and reshape to [B, S, K] where K = N*D
    x_flat = x.view(B, S, N * D).float()

    # Step 3: Compute inv_rms = rsqrt(mean(x^2) + eps)
    # Note: computed before matmul, but used after
    inv_rms = torch.rsqrt(x_flat.square().mean(-1, keepdim=True) + norm_eps)

    # Optional: apply gamma scaling
    if gamma is not None:
        x_flat = x_flat * gamma

    # Step 2: H = x @ hc_weight  -> [B, S, N]
    H = torch.matmul(x_flat, hc_weight)

    # Step 4: H_pre = sigmoid(alpha * H * inv_rms + bias) + hc_eps
    H_tmp = H * inv_rms
    H_pre = torch.sigmoid(alpha_pre * H_tmp + bias_pre) + hc_eps

    # Step 5: h_in = sum over N dimension of (H_pre * x_reshaped)
    # H_pre: [B, S, N] -> unsqueeze to [B, S, N, 1]
    # x: [B, S, N, D]
    # Result: [B, S, D]
    h_in = (H_pre.unsqueeze(-1) * x.float()).sum(dim=2).to(torch.bfloat16)

    return h_in
