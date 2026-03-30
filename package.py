from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)


def ensure_pyinstaller() -> None:
    if shutil.which("pyinstaller"):
        return
    raise SystemExit(
        "PyInstaller not found. Install with: pip install pyinstaller"
    )


def build_cli(onefile: bool) -> None:
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--name",
        "recolor-cli",
        "--collect-all",
        "PIL",
        "--collect-all",
        "numpy",
    ]
    cmd += ["--onefile"] if onefile else []
    cmd += [str(ROOT / "main.py")]
    run(cmd)


def build_gui(onefile: bool) -> None:
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        "recolor-gui",
        "--collect-all",
        "PIL",
        "--collect-all",
        "numpy",
    ]
    cmd += ["--onefile"] if onefile else []
    cmd += [str(ROOT / "gui.py")]
    run(cmd)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build standalone executables via PyInstaller")
    parser.add_argument(
        "--target",
        choices=["all", "cli", "gui"],
        default="all",
        help="Which binary target to build",
    )
    parser.add_argument(
        "--onedir",
        action="store_true",
        help="Build as onedir instead of onefile",
    )
    parser.add_argument(
        "--clean-artifacts",
        action="store_true",
        help="Delete ./build and ./dist before building",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_pyinstaller()

    if args.clean_artifacts:
        shutil.rmtree(BUILD_DIR, ignore_errors=True)
        shutil.rmtree(DIST_DIR, ignore_errors=True)

    onefile = not args.onedir

    try:
        if args.target in {"all", "cli"}:
            build_cli(onefile=onefile)
        if args.target in {"all", "gui"}:
            build_gui(onefile=onefile)
    except subprocess.CalledProcessError as exc:
        print(f"Build failed with exit code {exc.returncode}", file=sys.stderr)
        return exc.returncode

    print("Build complete.")
    print("Artifacts in ./dist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
