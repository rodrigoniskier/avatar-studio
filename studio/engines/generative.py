"""Inferência local nos upstreams fixados; nenhuma API de geração."""
import json
import math
from pathlib import Path

from .. import config, media
from ..runner import run_logged
from .. import resources

WORKER = Path(__file__).with_name("_video_worker.py")


def require_paths(*paths):
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"Falta {path}. Consulte docs/FREE_GENERATION.md.")


class InfiniteTalk:
    def render(self, identity, motion, audio, prompt, out, seed, *, initial_frame=None):
        resources.require("infinitetalk")
        repo = config.UPSTREAMS / "InfiniteTalk"
        root = config.MODELS / "infinitetalk"
        checkpoint = root / "Wan2.1-I2V-14B-480P"
        wav2vec = root / "chinese-wav2vec2-base"
        weights = root / "InfiniteTalk/single/infinitetalk.safetensors"
        if config.INFINITETALK_QUANT not in {"none", "fp8"}:
            raise ValueError("STUDIO_INFINITETALK_QUANT deve ser none ou fp8 (experimental).")
        quant_args = []
        if config.INFINITETALK_QUANT == "fp8":
            quant = root / "InfiniteTalk/quant_models"
            require_paths(*(quant / name for name in ("infinitetalk_single_fp8.safetensors",
                          "infinitetalk_single_fp8.json", "t5_fp8.safetensors", "t5_map_fp8.json")))
            quant_args = ["--quant", "fp8", "--quant_dir", str(quant / "infinitetalk_single_fp8.safetensors")]
        else:
            require_paths(weights)
        require_paths(repo / "generate_infinitetalk.py", checkpoint, wav2vec, identity, audio)
        if config.VIDEO_SIZE not in {"480", "720"}:
            raise ValueError("InfiniteTalk suporta STUDIO_VIDEO_SIZE=480 ou 720.")
        task = out.with_suffix(".json")
        prepared_audio = media.inference_audio(audio, out.with_suffix(".inference.wav"))
        payload = {"prompt": prompt, "cond_video": str(identity.resolve()),
                   "cond_audio": {"person1": str(prepared_audio.resolve())}}
        if initial_frame is not None:
            require_paths(initial_frame)
            payload["initial_frame"] = str(initial_frame.resolve())
        task.write_text(json.dumps(payload))
        run_logged([
            config.venv_python("infinitetalk"), str(WORKER), "infinitetalk",
            "--ckpt_dir", str(checkpoint), "--wav2vec_dir", str(wav2vec),
            "--infinitetalk_dir", str(weights), "--input_json", str(task.resolve()),
            "--audio_mode", "localfile",
            "--size", f"infinitetalk-{config.VIDEO_SIZE}", "--mode", "streaming",
            "--max_frame_num", str(math.ceil(media.duration(prepared_audio) * 25) + 25),
            "--sample_steps", "40", "--motion_frame", "9", "--sample_text_guide_scale", "5",
            "--frame_num", "81", "--t5_cpu",
            "--sample_audio_guide_scale", "4", "--num_persistent_param_in_dit", "0",
            "--base_seed", str(seed),
            "--audio_save_dir", str((out.parent / (out.stem + "_audio")).resolve()),
            "--save_file", str(out.resolve().with_suffix("")), *quant_args,
        ], cwd=repo)
        require_paths(out)
        return out


class WanAnimate:
    def render(self, identity, motion, audio, prompt, out, seed):
        resources.require("wan-animate")
        repo = config.UPSTREAMS / "Wan2.2"
        ckpt = config.MODELS / "wan-animate"
        if motion is None:
            raise ValueError("Wan-Animate requer vídeo de movimento separado da identidade.")
        require_paths(repo / "generate.py", ckpt / "process_checkpoint/pose2d/vitpose_h_wholebody.onnx",
                      ckpt / "process_checkpoint/det/yolov10m.onnx", identity, motion)
        prepared = out.parent / (out.stem + "_poses")
        prepared.mkdir(exist_ok=True)
        # FLUX and external prompt extension are deliberately not enabled.
        run_logged([
            config.venv_python("wan-animate"), str(WORKER.with_name("_preprocess_worker.py")),
            "--ckpt_path", str(ckpt / "process_checkpoint"), "--video_path", str(motion.resolve()),
            "--refer_path", str(identity.resolve()), "--save_path", str(prepared.resolve()),
            "--resolution_area", "1280", "720", "--fps", "30", "--retarget_flag",
        ], cwd=repo)
        run_logged([
            config.venv_python("wan-animate"), str(WORKER), "wan-animate", "--task", "animate-14B",
            "--ckpt_dir", str(ckpt), "--src_root_path", str(prepared.resolve()),
            "--refert_num", "1", "--offload_model", "True", "--convert_model_dtype", "--t5_cpu",
            "--frame_num", "77", "--base_seed", str(seed), "--save_file", str(out.resolve()),
        ], cwd=repo)
        require_paths(out)
        return out
