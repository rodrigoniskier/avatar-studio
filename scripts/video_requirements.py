"""Requirements do caminho integrado: retarget não requer SAM2/compilação CUDA."""
import argparse
from pathlib import Path


def prepare(engine, root):
    name = "InfiniteTalk" if engine == "infinitetalk" else "Wan2.2"
    repo = root / "upstreams" / name
    lines = [s for s in (repo / "requirements.txt").read_text().splitlines()
             if not s.strip().startswith(("flash_attn", "torch", "torchaudio", "torchvision"))]
    lines.extend(["setuptools==80.9.0", "ninja>=1.11,<2", "librosa==0.10.2.post1", "soundfile"])
    if engine == "wan-animate":
        for line in (repo / "requirements_animate.txt").read_text().splitlines():
            if "facebookresearch/sam2.git@0e78a118995e66bb27d78518c4bd9a3e95b4e266" in line:
                continue  # The worker defers SAM2 imports to replacement mode, which is disabled.
            if line.strip().startswith("-e "):
                raise ValueError("Dependência editável inesperada: revisão necessária.")
            lines.append(line)
    else:
        lines.extend(["xformers==0.0.28", "einops", "soundfile"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("engine", choices=["infinitetalk", "wan-animate"])
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(prepare(args.engine, Path(__file__).resolve().parents[1]))
