"""Pré-processamento retarget sem importar/instalar SAM2 ou FLUX desnecessariamente."""
import runpy
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from studio.engines.upstream_compat import build_preprocess_overlay


def main():
    if any(arg.split("=")[0] in {"--use_flux", "--replace_flag"} for arg in sys.argv[1:]):
        raise ValueError("Esta integração suporta apenas retarget, sem SAM2/FLUX.")
    with tempfile.TemporaryDirectory(prefix="avatar-preprocess-") as folder:
        build_preprocess_overlay(Path.cwd(), Path(folder))
        sys.path.insert(0, folder)
        script = str(Path(folder) / "preprocess_data.py")
        sys.argv[0] = script
        runpy.run_path(script, run_name="__main__")


if __name__ == "__main__":
    main()
