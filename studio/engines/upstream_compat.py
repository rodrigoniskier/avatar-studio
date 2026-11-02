"""Overlay temporário e verificável: fontes fixadas permanecem intactas."""
import ast
import os
import shutil
from pathlib import Path


ATTENTION_ARGUMENTS = {"q", "k", "v", "q_lens", "k_lens", "dropout_p", "softmax_scale",
                       "q_scale", "causal", "window_size", "deterministic", "dtype"}


def patched_source(source: str, path: str, fp16: bool) -> str:
    tree = ast.parse(source)
    if path == "multitalk.py":
        init = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "__init__")
        branch = next(n for n in ast.walk(init) if isinstance(n, ast.If) and ast.unparse(n.test) == "dit_path is None")
        if "merged_state_dict" not in ast.unparse(branch):
            raise RuntimeError("Contrato de carregamento InfiniteTalk mudou.")
        branch.body = ast.parse('''
from studio.engines.checkpoint_loading import assign_shards
wan_config = json.load(open(os.path.join(checkpoint_dir, "config.json")))
with torch.device("meta"):
    self.model = WanModel(weight_init=False, **wan_config).to(dtype=self.param_dtype)
self.model.init_freqs()
weight_files = [os.path.join(checkpoint_dir, f"diffusion_pytorch_model-{i:05d}-of-00007.safetensors") for i in range(1, 8)]
assign_shards(self.model, weight_files + [infinitetalk_dir])
''').body
        # Only the first temporal condition changes; CLIP and y retain the original identity.
        candidates = [n for n in ast.walk(tree) if isinstance(n, ast.If)
                      and ast.unparse(n.test) == "is_first_clip"
                      and "latent_motion_frames = self.vae.encode(cond_image)[0]" in ast.unparse(n)]
        if len(candidates) != 1:
            raise RuntimeError("Contrato de continuidade InfiniteTalk mudou.")
        candidates[0].body = ast.parse('''
if input_data.get("initial_frame"):
    first_image = extract_specific_frames(input_data["initial_frame"], 0)
    first_image = resize_and_centercrop(first_image, (target_h, target_w))
    first_image = ((first_image / 255 - 0.5) * 2).to(self.device)
    latent_motion_frames = self.vae.encode(first_image)[0]
else:
    latent_motion_frames = self.vae.encode(cond_image)[0]
''').body
    if path == "generate_infinitetalk.py":
        kokoro = [n for n in tree.body if isinstance(n, ast.ImportFrom) and n.module == "kokoro"]
        if len(kokoro) != 1:
            raise RuntimeError("Contrato de importação Kokoro mudou.")
        tree.body = [n for n in tree.body if n not in kokoro]
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in {"process_tts_single", "process_tts_multi"}:
                node.body[:0] = ast.parse("from kokoro import KPipeline").body
        candidates = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                      and ast.unparse(n) == "input_clip['cond_video'] = items[0]"]
        if len(candidates) != 1:
            raise RuntimeError("Contrato de entrada InfiniteTalk mudou.")
        # Expand the assignment as a statement group using a transformer.
        target = candidates[0]
        class InitialFrame(ast.NodeTransformer):
            def visit_Assign(self, node):
                if node is target:
                    return [node, *ast.parse('input_clip["initial_frame"] = input_data.get("initial_frame")').body]
                return self.generic_visit(node)
        tree = InitialFrame().visit(tree)
    if path == "modules/t5.py":
        init = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "T5EncoderModel")
        count = 0
        for node in ast.walk(init):
            if isinstance(node, ast.Call) and ast.unparse(node.func) == "umt5_xxl":
                for arg in node.keywords:
                    if arg.arg == "device":
                        arg.value = ast.Constant(value="meta")
            if (isinstance(node, ast.Call) and ast.unparse(node.func) == "model.load_state_dict"
                    and node.args and isinstance(node.args[0], ast.Call)
                    and ast.unparse(node.args[0].func) == "torch.load"):
                node.func = ast.Name(id="avatar_assign_checkpoint", ctx=ast.Load())
                node.args = [ast.Name(id="model", ctx=ast.Load()), ast.Name(id="checkpoint_path", ctx=ast.Load())]
                node.keywords = []
                count += 1
        if count != 1:
            raise RuntimeError("Contrato T5 mudou; carregamento por mmap não aplicado.")
        tree.body.insert(0, ast.parse("from studio.engines.checkpoint_loading import assign_torch_checkpoint as avatar_assign_checkpoint").body[0])
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
        attention = relative in {"modules/attention.py", "modules/animate/face_blocks.py", "modules/t5.py", "multitalk.py"}
        if attention or (fp16 and "torch.bfloat16" in original):
            code = patched_source(original, relative, fp16)
            path.unlink()  # remove only the overlay symlink, never write into the upstream
            path.write_text(code)
            changed.append(relative)
    return changed


def build_preprocess_overlay(repo: Path, destination: Path):
    """Retarget não usa SAM2/FLUX. Imports opcionais ficam nos seus ramos reais."""
    source = repo / "wan/modules/animate/preprocess"
    shutil.copytree(source, destination, copy_function=os.symlink,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"), dirs_exist_ok=True)
    path = destination / "process_pipepline.py"
    tree = ast.parse(path.read_text())
    optional = []
    for node in tree.body:
        code = ast.unparse(node)
        if (code.startswith(("import sam2.", "from sam_utils import", "transformer."))
                or code == "from diffusers import FluxKontextPipeline"):
            optional.append(node)
    if len(optional) != 6:
        raise RuntimeError("Contrato de pré-processamento mudou; revisão necessária.")
    tree.body = [n for n in tree.body if n not in optional]
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and ast.unparse(node.test) == "sam_checkpoint_path is not None":
            node.body[:0] = [n for n in optional if "FluxKontextPipeline" not in ast.unparse(n)]
        if isinstance(node, ast.If) and ast.unparse(node.test) == "flux_kontext_path is not None":
            node.body[:0] = [n for n in optional if "FluxKontextPipeline" in ast.unparse(n)]
    ast.fix_missing_locations(tree)
    path.unlink()
    path.write_text(ast.unparse(tree) + "\n")
