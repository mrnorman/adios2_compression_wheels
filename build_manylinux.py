#!/usr/bin/env python3
"""Build, repair, and test the CPython 3.12+ manylinux ADIOS2 wheel."""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
IMAGE = "adios2-compressors-manylinux2014:local"
WHEEL_NAME = "adios2_compressors"
PLATFORM_TAGS = {
    "x86_64": "manylinux_2_17_x86_64",
    "aarch64": "manylinux_2_17_aarch64",
}
MANYLINUX_IMAGES = {
    "x86_64": (
        "quay.io/pypa/manylinux2014_x86_64@"
        "sha256:95440e0e72dd3a81dc8d2cf59a84d57af661456620f5bc821ff92048d0e54ff9"
    ),
    "aarch64": (
        "quay.io/pypa/manylinux2014_aarch64@"
        "sha256:b63ff749fee6f3f2a6b67ed3101a073db3211df1791da19e9acf96f43c0dd6ff"
    ),
}


def run(command: list[str], **kwargs: object) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True, **kwargs)


def container_engine(requested: str | None) -> str:
    if requested:
        executable = shutil.which(requested)
        if executable is None:
            raise RuntimeError(f"Container engine not found: {requested}")
        return executable
    for candidate in ("docker", "podman"):
        executable = shutil.which(candidate)
        if executable is not None:
            return executable
    raise RuntimeError("Docker or Podman is required for the manylinux build")


def build_in_container(jobs: int | None) -> None:
    architecture = platform.machine()
    try:
        platform_tag = PLATFORM_TAGS[architecture]
    except KeyError as error:
        supported = ", ".join(sorted(PLATFORM_TAGS))
        raise RuntimeError(f"Unsupported architecture {architecture!r}; supported: {supported}") from error

    build_root = SCRIPT_DIR / "build" / "manylinux"
    raw_wheels = build_root / "raw"
    repaired_wheels = build_root / "repaired"
    for directory in (raw_wheels, repaired_wheels, SCRIPT_DIR / "wheelhouse"):
        directory.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        str(SCRIPT_DIR / "build_wheel.py"),
        "--stable-abi",
        "--work-dir", str(build_root / "work"),
        "--output-dir", str(raw_wheels),
        "--adios2-source", str(SCRIPT_DIR / "sources" / "ADIOS2"),
        "--blosc2-source", str(SCRIPT_DIR / "sources" / "c-blosc2"),
        "--zfp-source", str(SCRIPT_DIR / "sources" / "zfp"),
        "--sz3-source", str(SCRIPT_DIR / "sources" / "SZ3"),
        "--sz-source", str(SCRIPT_DIR / "sources" / "SZ"),
        "--zstd-source", str(SCRIPT_DIR / "sources" / "zstd"),
        "--zlib-source", str(SCRIPT_DIR / "sources" / "zlib"),
    ]
    if jobs is not None:
        command.extend(("--jobs", str(jobs)))
    run(command)

    candidates = sorted(raw_wheels.glob(f"{WHEEL_NAME}-*-cp312-abi3-linux_*.whl"))
    if not candidates:
        raise RuntimeError(f"No cp312-abi3 Linux wheel found in {raw_wheels}")
    raw_wheel = max(candidates, key=lambda path: path.stat().st_mtime)
    run(["auditwheel", "show", str(raw_wheel)])
    for old_wheel in repaired_wheels.glob(f"{WHEEL_NAME}-*.whl"):
        old_wheel.unlink()
    run(
        [
            "auditwheel", "repair", "--plat", platform_tag,
            "--wheel-dir", str(repaired_wheels), str(raw_wheel),
        ]
    )

    repaired = sorted(
        path
        for path in repaired_wheels.glob(f"{WHEEL_NAME}-*-cp312-abi3-*.whl")
        if platform_tag in path.name
    )
    if not repaired:
        raise RuntimeError(f"auditwheel did not produce a {platform_tag} wheel")
    wheel = max(repaired, key=lambda path: path.stat().st_mtime)
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


def run_container(engine: str, jobs: int | None, ignore_chown_errors: bool) -> None:
    architecture = platform.machine()
    try:
        manylinux_image = MANYLINUX_IMAGES[architecture]
    except KeyError as error:
        supported = ", ".join(sorted(MANYLINUX_IMAGES))
        raise RuntimeError(
            f"Unsupported architecture {architecture!r}; supported: {supported}"
        ) from error
    run([sys.executable, str(SCRIPT_DIR / "build_wheel.py"), "--prepare-sources-only"])
    engine_options = []
    if ignore_chown_errors:
        if Path(engine).name != "podman":
            raise RuntimeError("--podman-ignore-chown-errors can only be used with Podman")
        engine_options = ["--storage-opt", "overlay.ignore_chown_errors=true"]
    run(
        [
            engine, *engine_options, "build",
            "--file", str(SCRIPT_DIR / "Dockerfile.manylinux"),
            "--build-arg", f"MANYLINUX_IMAGE={manylinux_image}",
            "--tag", IMAGE,
            str(SCRIPT_DIR),
        ]
    )
    container_user = "0:0" if ignore_chown_errors else f"{os.getuid()}:{os.getgid()}"
    command = [
        engine, *engine_options, "run", "--rm",
        "--user", container_user,
        "--env", "HOME=/tmp/adios2-wheel-home",
        "--volume", f"{SCRIPT_DIR}:/project:rw",
        IMAGE,
        "python", "/project/build_manylinux.py", "--inside-container",
    ]
    if jobs is not None:
        command.extend(("--jobs", str(jobs)))
    run(command)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("docker", "podman"))
    parser.add_argument("--jobs", type=int)
    parser.add_argument(
        "--podman-ignore-chown-errors",
        action="store_true",
        help="support rootless Podman accounts that have no subordinate UID/GID range",
    )
    parser.add_argument("--inside-container", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    if arguments.inside_container:
        build_in_container(arguments.jobs)
    else:
        run_container(
            container_engine(arguments.engine),
            arguments.jobs,
            arguments.podman_ignore_chown_errors,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
