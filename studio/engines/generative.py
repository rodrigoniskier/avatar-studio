"""Inferência local nos upstreams fixados; nenhuma API de geração."""
import json
import math

from .. import config, media
from ..runner import run_logged


def require_paths(*paths):
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Falta {path}. Consulte docs/FREE_GENERATION.md.")


class InfiniteTalk:
    def render(self, identity, motion, audio, prompt, out, seed):
        repo = config.UPSTREAMS / "InfiniteTalk"
        root = config.MODELS / "infinitetalk"
        checkpoint = root / "Wan2.1-I2V-14B-480P"
        wav2vec = root / "chinese-wav2vec2-base"
        weights = root / "InfiniteTalk/single/infinitetalk.safetensors"
        require_paths(repo / "generate_infinitetalk.py", checkpoint, wav2vec, weights, identity, audio)
        if config.VIDEO_SIZE not in {"480", "720"}:
            raise ValueError("InfiniteTalk suporta STUDIO_VIDEO_SIZE=480 ou 720.")
        task = out.with_suffix(".json")
        task.write_text(json.dumps({"prompt": prompt, "cond_video": str(identity.resolve()),
                                    "cond_audio": {"person1": str(audio.resolve())}}))
        run_logged([
            config.venv_python("infinitetalk"), "generate_infinitetalk.py",
            "--ckpt_dir", str(checkpoint), "--wav2vec_dir", str(wav2vec),
            "--infinitetalk_dir", str(weights), "--input_json", str(task.resolve()),
            "--size", f"infinitetalk-{config.VIDEO_SIZE}", "--mode", "streaming",
            "--max_frame_num", str(math.ceil(media.duration(audio) * 25) + 25),
            "--sample_steps", "40", "--motion_frame", "9", "--sample_text_guide_scale", "5",
            "--sample_audio_guide_scale", "4", "--num_persistent_param_in_dit", "0",
            "--base_seed", str(seed),
            "--audio_save_dir", str((out.parent / (out.stem + "_audio")).resolve()),
            "--save_file", str(out.resolve().with_suffix("")),
        ], cwd=repo)
        require_paths(out)
        return out


class WanAnimate:
    def render(self, identity, motion, audio, prompt, out, seed):
        repo = config.UPSTREAMS / "Wan2.2"
        ckpt = config.MODELS / "wan-animate"
        if motion is None:
            raise ValueError("Wan-Animate requer vídeo de movimento separado da identidade.")
        require_paths(repo / "generate.py", ckpt / "process_checkpoint", identity, motion)
        prepared = out.parent / (out.stem + "_poses")
        prepared.mkdir(exist_ok=True)
        # FLUX and external prompt extension are deliberately not enabled.
        run_logged([
            config.venv_python("wan-animate"), "wan/modules/animate/preprocess/preprocess_data.py",
            "--ckpt_path", str(ckpt / "process_checkpoint"), "--video_path", str(motion.resolve()),
            "--refer_path", str(identity.resolve()), "--save_path", str(prepared.resolve()),
            "--resolution_area", "1280", "720", "--fps", "30", "--retarget_flag",
        ], cwd=repo)
        run_logged([
            config.venv_python("wan-animate"), "generate.py", "--task", "animate-14B",
            "--ckpt_dir", str(ckpt), "--src_root_path", str(prepared.resolve()),
            "--refert_num", "1", "--offload_model", "True", "--convert_model_dtype", "--t5_cpu",
            "--prompt", prompt, "--base_seed", str(seed), "--save_file", str(out.resolve()),
        ], cwd=repo)
        require_paths(out)
        return out
