#!/usr/bin/env python3
"""Build, repair, and test the CPython 3.12+ native macOS ADIOS2 wheel."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
WHEEL_NAME = "adios2_compressors"
SUPPORTED_ARCHITECTURES = {"x86_64", "arm64"}
DEFAULT_DEPLOYMENT_TARGET = "11.0"


def run(command: list[str], **kwargs: object) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True, **kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int)
    parser.add_argument(
        "--deployment-target",
        default=DEFAULT_DEPLOYMENT_TARGET,
        help="oldest macOS release encoded in and required by the wheel",
    )
    arguments = parser.parse_args()

    if platform.system() != "Darwin":
        raise RuntimeError("The macOS wheel must be built natively on macOS")
    architecture = platform.machine()
    if architecture not in SUPPORTED_ARCHITECTURES:
        supported = ", ".join(sorted(SUPPORTED_ARCHITECTURES))
        raise RuntimeError(f"Unsupported architecture {architecture!r}; supported: {supported}")
    if importlib.util.find_spec("delocate") is None:
        raise RuntimeError(
            f"Install delocate first: {sys.executable} -m pip install delocate"
        )

    build_root = SCRIPT_DIR / "build" / "macos" / architecture
    raw_wheels = build_root / "raw"
    repaired_wheels = build_root / "repaired"
    for directory in (raw_wheels, repaired_wheels, SCRIPT_DIR / "wheelhouse"):
        directory.mkdir(parents=True, exist_ok=True)

    environment = os.environ.copy()
    environment["MACOSX_DEPLOYMENT_TARGET"] = arguments.deployment_target
    command = [
        sys.executable,
        str(SCRIPT_DIR / "build_wheel.py"),
        "--stable-abi",
        "--work-dir", str(build_root / "work"),
        "--output-dir", str(raw_wheels),
    ]
    if arguments.jobs is not None:
        command.extend(("--jobs", str(arguments.jobs)))
    run(command, env=environment)

    candidates = sorted(raw_wheels.glob(f"{WHEEL_NAME}-*-cp312-abi3-macosx_*.whl"))
    if not candidates:
        raise RuntimeError(f"No cp312-abi3 macOS wheel found in {raw_wheels}")
    raw_wheel = max(candidates, key=lambda path: path.stat().st_mtime)
    for old_wheel in repaired_wheels.glob(f"{WHEEL_NAME}-*.whl"):
        old_wheel.unlink()
    run(
        [
            "delocate-wheel", "--require-archs", architecture,
            "--wheel-dir", str(repaired_wheels), str(raw_wheel),
        ],
        env=environment,
    )

    repaired = sorted(repaired_wheels.glob(f"{WHEEL_NAME}-*-cp312-abi3-macosx_*.whl"))
    if not repaired:
        raise RuntimeError(f"delocate-wheel did not produce a wheel in {repaired_wheels}")
    wheel = max(repaired, key=lambda path: path.stat().st_mtime)
    if architecture not in wheel.name:
        raise RuntimeError(f"Repaired wheel does not identify {architecture}: {wheel.name}")
    destination = SCRIPT_DIR / "wheelhouse" / wheel.name
    shutil.copy2(wheel, destination)

    test_environment = build_root / "test-environment"
    run([sys.executable, "-m", "venv", "--clear", "--system-site-packages", str(test_environment)])
    test_python = test_environment / "bin" / "python"
    run([str(test_python), "-m", "pip", "install", "--no-deps", "--force-reinstall", str(destination)])
    run([str(test_python), str(SCRIPT_DIR / "verify_wheel.py")])
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    checksum = destination.with_suffix(f"{destination.suffix}.sha256")
    checksum.write_text(f"{digest}  {destination.name}\n", encoding="utf-8")
    print(f"Created and verified {destination}", flush=True)
    print(f"Wrote {checksum}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
