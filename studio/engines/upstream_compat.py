"""Overlay temporário e verificável: fontes fixadas permanecem intactas."""
import ast
import os
import shutil
from pathlib import Path


ATTENTION_ARGUMENTS = {"q", "k", "v", "q_lens", "k_lens", "dropout_p", "softmax_scale",
                       "q_scale", "causal", "window_size", "deterministic", "dtype"}


def patched_source(source: str, path: str, fp16: bool) -> str:
    tree = ast.parse(source)
    if path == "modules/attention.py":
        count = 0
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in {"flash_attention", "attention"}:
                names = {arg.arg for arg in node.args.args}
                if not ATTENTION_ARGUMENTS <= names:
                    raise RuntimeError("Contrato de atenção do upstream mudou; revisão necessária.")
                node.body = ast.parse(
                    "from studio.engines.attention_compat import sdpa_attention\n"
                    "return sdpa_attention(q,k,v,q_lens=q_lens,k_lens=k_lens,dropout_p=dropout_p,"
                    "softmax_scale=softmax_scale,q_scale=q_scale,causal=causal,window_size=window_size,"
                    "deterministic=deterministic,dtype=dtype)\n").body
                count += 1
        if count != 2:
            raise RuntimeError("Funções de atenção esperadas ausentes no upstream.")
        class Xformers(ast.NodeTransformer):
            def visit_Call(self, node):
                self.generic_visit(node)
                if ast.unparse(node.func) == "xformers.ops.memory_efficient_attention":
                    node.func = ast.Name(id="avatar_xformers_sdpa", ctx=ast.Load())
                return node
        tree = Xformers().visit(tree)
        tree.body.insert(0, ast.parse("from studio.engines.attention_compat import xformers_sdpa as avatar_xformers_sdpa").body[0])
    if path == "modules/animate/face_blocks.py":
        count = 0
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "attention":
                expected = {"q", "k", "v", "mode", "drop_rate", "attn_mask", "causal", "max_seqlen_q", "batch_size"}
                if {arg.arg for arg in node.args.args} != expected:
                    raise RuntimeError("Contrato de atenção facial mudou; revisão necessária.")
                node.body = ast.parse(
                    "from studio.engines.attention_compat import face_sdpa_attention\n"
                    "return face_sdpa_attention(q,k,v,mode=mode,drop_rate=drop_rate,attn_mask=attn_mask,"
                    "causal=causal,max_seqlen_q=max_seqlen_q,batch_size=batch_size)\n").body
                count += 1
        if count != 1:
            raise RuntimeError("Função de atenção facial ausente no upstream.")
    if fp16:
        class Dtype(ast.NodeTransformer):
            def visit_Attribute(self, node):
                if isinstance(node.value, ast.Name) and node.value.id == "torch" and node.attr == "bfloat16":
                    node.attr = "float16"
                return self.generic_visit(node)
        tree = Dtype().visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n"


def build_overlay(repo: Path, destination: Path, fp16: bool):
    source = repo / "wan"
    if not (source / "modules/attention.py").exists():
        raise RuntimeError("Upstream incompleto: falta wan/modules/attention.py.")
    shutil.copytree(source, destination / "wan", copy_function=os.symlink,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    changed = []
    for path in (destination / "wan").rglob("*.py"):
        relative = path.relative_to(destination / "wan").as_posix()
        original = path.read_text()
        attention = relative in {"modules/attention.py", "modules/animate/face_blocks.py"}
        if attention or (fp16 and "torch.bfloat16" in original):
            code = patched_source(original, relative, fp16)
            path.unlink()  # remove only the overlay symlink, never write into the upstream
            path.write_text(code)
            changed.append(relative)
    return changed
