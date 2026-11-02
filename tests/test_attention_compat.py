"""Numerical regression of the actual fallback, independent of the neural model weights."""
import ast
from pathlib import Path

import pytest

torch = pytest.importorskip("torch", reason="Install the CPU torch wheel to run numerical attention verification.")
from studio.engines.attention_compat import sdpa_attention, face_sdpa_attention, inference_dtype
from studio.engines.upstream_compat import patched_source, build_overlay


def explicit(q, k, v, q_sizes, k_sizes, causal=False, window=(-1, -1), scale=None):
    # Direct softmax reference, independently assembled per sample/query/head.
    result = torch.zeros(q.shape[0], q.shape[1], q.shape[2], v.shape[-1], dtype=q.dtype)
    for b, (ql, kl) in enumerate(zip(q_sizes, k_sizes)):
        for i in range(ql):
            for h in range(q.shape[2]):
                scores = (q[b, i, h] @ k[b, :kl, h].T) * (scale if scale is not None else q.shape[-1]**-.5)
                allowed = []
                for j in range(kl):
                    center = i + kl - ql
                    allowed.append((not causal or j <= center) and
                                   (window[0] < 0 or j >= center-window[0]) and
                                   (window[1] < 0 or j <= center+window[1]))
                mask = torch.tensor(allowed)
                if mask.any():
                    result[b, i, h] = scores.masked_fill(~mask, -torch.inf).softmax(-1) @ v[b, :kl, h]
    return result


@pytest.mark.parametrize("ql,kl", [(5, 7), (7, 3), (4, 4)])
@pytest.mark.parametrize("causal,window", [(False,(-1,-1)), (True,(-1,-1)), (False,(1,2)), (True,(2,0))])
def test_varlen_causal_window_and_padding_against_explicit_softmax(ql, kl, causal, window, monkeypatch):
    torch.manual_seed(4)
    monkeypatch.setenv("STUDIO_ATTENTION_CHUNK", "2")
    q = torch.randn(2, ql+2, 3, 4, dtype=torch.float64)
    k = torch.randn(2, kl+3, 3, 4, dtype=torch.float64)
    v = torch.randn(2, kl+3, 3, 6, dtype=torch.float64)
    qs, ks = [ql, max(0,ql-2)], [kl, max(0,kl-1)]
    wanted = explicit(q*.7, k, v, qs, ks, causal, window, .3)
    actual = sdpa_attention(q,k,v,q_lens=torch.tensor(qs),k_lens=torch.tensor(ks),q_scale=.7,
                            softmax_scale=.3,causal=causal,window_size=window)
    torch.testing.assert_close(actual, wanted, atol=1e-10, rtol=1e-10)


def test_padding_never_leaks_into_valid_queries():
    q = torch.randn(1, 5, 2, 4)
    k = torch.randn(1, 8, 2, 4)
    v = torch.randn_like(k)
    before = sdpa_attention(q,k,v,q_lens=[3],k_lens=[4])
    k[:,4:] = 1e6; v[:,4:] = -1e6
    after = sdpa_attention(q,k,v,q_lens=[3],k_lens=[4])
    torch.testing.assert_close(before,after)
    assert (after[:,3:] == 0).all()


@pytest.mark.parametrize("mode", ["flash", "torch", "vanilla"])
def test_face_layout_attends_over_spatial_sequence_not_heads(mode):
    q = torch.randn(2, 5, 3, 4, dtype=torch.float64)
    k = torch.randn(2, 7, 3, 4, dtype=torch.float64)
    v = torch.randn_like(k)
    wanted = explicit(q,k,v,[5,5],[7,7]).reshape(2,5,12)
    torch.testing.assert_close(face_sdpa_attention(q,k,v,mode=mode),wanted)


def test_native_bf16_check_ignores_emulated_support(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "is_bf16_supported", lambda: True)
    monkeypatch.setattr(torch.cuda, "get_device_capability", lambda device=None: (7,5))
    assert inference_dtype("cuda") == torch.float16
    monkeypatch.setattr(torch.cuda, "get_device_capability", lambda device=None: (6,0))
    assert inference_dtype("cuda") == torch.float16
    monkeypatch.setattr(torch.cuda, "get_device_capability", lambda device=None: (8,0))
    assert inference_dtype("cuda") == torch.bfloat16


@pytest.mark.parametrize("engine", ["InfiniteTalk", "Wan2.2"])
def test_patched_actual_upstream_direct_calls_execute_without_flash(engine):
    root = Path(__file__).parents[1] / "upstreams" / engine / "wan"
    assert (root / "modules/attention.py").exists(), "Initialize pinned submodules for contract verification."
    code = patched_source((root / "modules/attention.py").read_text(), "modules/attention.py", True)
    tree = ast.parse(code)
    functions = [x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name in {"attention","flash_attention"}]
    namespace = {"torch":torch}
    exec(compile(ast.Module(body=functions,type_ignores=[]),"actual_upstream","exec"),namespace)
    q=torch.randn(2,5,3,4); k=torch.randn(2,7,3,4); v=torch.randn_like(k)
    expected=sdpa_attention(q,k,v,q_lens=[4,2],k_lens=[5,3])
    for name in ("flash_attention","attention"):
        torch.testing.assert_close(namespace[name](q,k,v,q_lens=[4,2],k_lens=[5,3]),expected)


def test_actual_face_block_function_executes_correct_layout():
    root=Path(__file__).parents[1]/"upstreams/Wan2.2/wan"
    tree=ast.parse(patched_source((root/"modules/animate/face_blocks.py").read_text(),"modules/animate/face_blocks.py",True))
    function=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=="attention")
    namespace={}
    exec(compile(ast.Module(body=[function],type_ignores=[]),"actual_face","exec"),namespace)
    q=torch.randn(2,5,3,4); k=torch.randn(2,7,3,4); v=torch.randn_like(k)
    torch.testing.assert_close(namespace["attention"](q,k,v),face_sdpa_attention(q,k,v))


def test_overlay_does_not_modify_upstream_and_replaces_hardcoded_bf16(tmp_path):
    repo=Path(__file__).parents[1]/"upstreams/Wan2.2"
    original=(repo/"wan/animate.py").read_bytes()
    changed=build_overlay(repo,tmp_path/"overlay",fp16=True)
    assert "animate.py" in changed
    assert (repo/"wan/animate.py").read_bytes()==original
    assert "torch.bfloat16" not in (tmp_path/"overlay/wan/animate.py").read_text()
    assert "sdpa_attention" in (tmp_path/"overlay/wan/modules/attention.py").read_text()


def test_nonfinite_model_activations_are_rejected_not_hidden():
    q=torch.full((1,3,2,4),float('nan'));k=torch.randn_like(q)
    with pytest.raises(FloatingPointError,match="não finitos"):
        sdpa_attention(q,k,k)
