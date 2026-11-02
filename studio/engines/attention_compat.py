"""Atenção SDPA com contrato BLHD/varlen do Wan, sem FlashAttention externo.

Imports de torch ficam apenas nos ambientes de inferência e nos testes numéricos CPU.
"""
import os

import torch
import torch.nn.functional as F


def native_bf16(device=None):
    if not torch.cuda.is_available():
        return False
    return torch.cuda.get_device_capability(device)[0] >= 8


def inference_dtype(device="cuda"):
    if str(device).startswith("cuda"):
        return torch.bfloat16 if native_bf16(device) else torch.float16
    return torch.float32


def _lengths(lengths, batch, maximum):
    values = [maximum] * batch if lengths is None else [int(x) for x in lengths]
    if len(values) != batch or any(x < 0 or x > maximum for x in values):
        raise ValueError("Comprimentos de atenção incompatíveis com o tensor.")
    return values


def sdpa_attention(q, k, v, q_lens=None, k_lens=None, dropout_p=0., softmax_scale=None,
                   q_scale=None, causal=False, window_size=(-1, -1), deterministic=False,
                   dtype=None, version=None, fa_version=None):
    """Recorta padding por exemplo e limita memória por blocos de queries.

    Máscara causal/janela segue alinhamento inferior direito do FlashAttention 2.1+.
    Posições de query fora de q_lens recebem zero, em vez de valores indefinidos.
    """
    if q.ndim != 4 or k.ndim != 4 or v.ndim != 4:
        raise ValueError("A atenção requer tensores [batch, sequence, heads, channels].")
    batch, nq, heads, _ = q.shape
    if k.shape[:3] != v.shape[:3] or k.shape[0] != batch or heads % k.shape[2]:
        raise ValueError("Shapes Q/K/V incompatíveis.")
    q_sizes = _lengths(q_lens, batch, nq)
    k_sizes = _lengths(k_lens, batch, k.shape[1])
    out_dtype = q.dtype
    target = q.dtype
    if q.is_cuda:
        target = inference_dtype(q.device)
        if dtype in {torch.float16, torch.bfloat16}:
            target = dtype if dtype != torch.bfloat16 or native_bf16(q.device) else torch.float16
    q, k, v = (x.to(target) for x in (q, k, v))
    if q_scale is not None:
        q = q * q_scale
    repeats = heads // k.shape[2]
    if repeats != 1:
        k, v = (x.repeat_interleave(repeats, dim=2) for x in (k, v))
    out = q.new_zeros(batch, nq, heads, v.shape[-1])
    chunk = max(1, int(os.getenv("STUDIO_ATTENTION_CHUNK", "128")))
    left, right = window_size
    for b, (ql, kl) in enumerate(zip(q_sizes, k_sizes)):
        if not ql or not kl:
            continue
        key = k[b:b+1, :kl].transpose(1, 2)
        value = v[b:b+1, :kl].transpose(1, 2)
        for start in range(0, ql, chunk):
            end = min(start + chunk, ql)
            mask = None
            if causal or left >= 0 or right >= 0:
                center = torch.arange(start, end, device=q.device)[:, None] + kl - ql
                positions = torch.arange(kl, device=q.device)[None, :]
                mask = torch.ones(end-start, kl, dtype=torch.bool, device=q.device)
                if causal:
                    mask &= positions <= center
                if left >= 0:
                    mask &= positions >= center - left
                if right >= 0:
                    mask &= positions <= center + right
            query = q[b:b+1, start:end].transpose(1, 2)
            if deterministic:
                from torch.nn.attention import SDPBackend, sdpa_kernel
                with sdpa_kernel(SDPBackend.MATH):
                    result = F.scaled_dot_product_attention(query, key, value, attn_mask=mask,
                                                            dropout_p=dropout_p, scale=softmax_scale)
            else:
                result = F.scaled_dot_product_attention(query, key, value, attn_mask=mask,
                                                        dropout_p=dropout_p, scale=softmax_scale)
            # Only mathematically empty rows are zeroed. Never hide model overflow/NaN.
            if mask is not None:
                allowed = mask.any(dim=-1)[None, None, :, None]
                result = torch.where(allowed, result, torch.zeros_like(result))
            out[b:b+1, start:end] = result.transpose(1, 2)
    if not torch.isfinite(out).all():
        raise FloatingPointError("A atenção produziu valores não finitos. Confira precisão/modelo; o resultado não será mascarado.")
    return out.to(out_dtype)


def face_sdpa_attention(q, k, v, mode="flash", drop_rate=0, attn_mask=None, causal=False,
                        max_seqlen_q=None, batch_size=1):
    # FaceBlock passes [B*temporal, spatial, heads, channels]. Do not attend over heads.
    if q.ndim == 3:
        if not max_seqlen_q:
            raise ValueError("max_seqlen_q ausente para atenção facial empacotada.")
        q = q.reshape(batch_size, max_seqlen_q, *q.shape[-2:])
        k = k.reshape(batch_size, -1, *k.shape[-2:])
        v = v.reshape(batch_size, -1, *v.shape[-2:])
    if mode not in {"flash", "torch", "vanilla"}:
        raise ValueError("Modo de atenção facial inválido.")
    if attn_mask is None:
        result = sdpa_attention(q, k, v, dropout_p=drop_rate, causal=causal)
    else:
        if attn_mask.ndim == 2 and attn_mask.shape == (q.shape[0], k.shape[1]):
            attn_mask = attn_mask[:, None, None, :]
        if attn_mask.dtype != torch.bool:
            attn_mask = attn_mask.to(q.dtype)
        result = F.scaled_dot_product_attention(q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2),
                                                attn_mask=attn_mask, dropout_p=drop_rate,
                                                is_causal=causal).transpose(1, 2)
    return result.reshape(result.shape[0], result.shape[1], -1)


def xformers_sdpa(q, k, v, attn_bias=None, op=None):
    if attn_bias is not None:
        raise ValueError("A integração local suporta uma GPU; máscara de paralelismo não suportada.")
    return sdpa_attention(q, k, v)
