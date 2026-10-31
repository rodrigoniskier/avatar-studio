"""Bootstrap dos upstreams com todas as chamadas diretas de atenção corrigidas."""
import sys
import tempfile
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP_ROOT))
from studio.engines.attention_compat import native_bf16
from studio.engines.upstream_compat import build_overlay


def main():
    repo = Path.cwd().resolve()
    engine = sys.argv[1]
    script = "generate_infinitetalk.py" if engine == "infinitetalk" else "generate.py"
    with tempfile.TemporaryDirectory(prefix="avatar-runtime-") as folder:
        overlay = Path(folder)
        changed = build_overlay(repo, overlay, fp16=not native_bf16())
        sys.path[:0] = [str(overlay), str(repo)]
        if "--check-only" in sys.argv:
            import importlib
            import json
            import torch
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA indisponível neste ambiente de inferência.")
            module = importlib.import_module("wan.modules.attention")
            from studio.engines.attention_compat import inference_dtype
            dtype = inference_dtype()
            q = torch.randn(1, 5, 2, 8, device="cuda", dtype=dtype)
            k = torch.randn(1, 7, 2, 8, device="cuda", dtype=dtype)
            result = module.flash_attention(q, k, k, q_lens=[3], k_lens=[4])
            if not torch.isfinite(result).all() or result.shape != q.shape:
                raise RuntimeError("O ensaio SDPA mínimo falhou.")
            if engine == "wan-animate":
                face = importlib.import_module("wan.modules.animate.face_blocks")
                if face.attention(q,k,k).shape != (1,5,16):
                    raise RuntimeError("O ensaio de atenção facial falhou.")
            print(json.dumps({"cuda": True, "native_bf16": native_bf16(), "dtype": str(dtype),
                              "sdpa_smoke_passed": True, "note": "Sem carregamento de pesos; não certifica inferência 14B."}))
            return
        sys.argv = [str(repo / script), *sys.argv[2:]]
        print("Runtime SDPA; arquivos em overlay:", ", ".join(changed), flush=True)
        # Patch dtypes in the entry script too, before its eager `import wan`.
        from studio.engines.upstream_compat import patched_source
        code = patched_source((repo / script).read_text(), script, fp16=not native_bf16())
        exec(compile(code, str(repo / script), "exec"), {"__name__": "__main__", "__file__": str(repo / script)})


if __name__ == "__main__":
    main()
