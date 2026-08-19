#!/usr/bin/env python3
"""Build and install the wheel's compression dependencies as static PIC libraries."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def run(command: list[str], **kwargs: object) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True, **kwargs)


def cmake_install(
    source: Path,
    build_dir: Path,
    prefix: Path,
    definitions: dict[str, str],
    jobs: int | None,
    environment: dict[str, str] | None = None,
) -> None:
    configure = [
        "cmake",
        "-S", str(source.resolve()),
        "-B", str(build_dir.resolve()),
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_INSTALL_PREFIX={prefix.resolve()}",
        "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
        *[f"-D{key}={value}" for key, value in definitions.items()],
    ]
    run(configure, env=environment)
    build = ["cmake", "--build", str(build_dir.resolve()), "--target", "install", "--parallel"]
    if jobs is not None:
        build.append(str(jobs))
    run(build, env=environment)


def pkg_config_environment(prefix: Path) -> dict[str, str]:
    environment = os.environ.copy()
    paths = [prefix / "lib64" / "pkgconfig", prefix / "lib" / "pkgconfig"]
    existing = environment.get("PKG_CONFIG_PATH")
    if existing:
        paths.append(Path(existing))
    environment["PKG_CONFIG_PATH"] = os.pathsep.join(str(path) for path in paths)
    return environment


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blosc2-source", required=True, type=Path)
    parser.add_argument("--zfp-source", required=True, type=Path)
    parser.add_argument("--sz3-source", required=True, type=Path)
    parser.add_argument("--sz-source", required=True, type=Path)
    parser.add_argument("--zstd-source", required=True, type=Path)
    parser.add_argument("--zlib-source", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--prefix", required=True, type=Path)
    parser.add_argument("--jobs", type=int)
    arguments = parser.parse_args()

    if shutil.which("cmake") is None:
        raise RuntimeError("CMake is required to build the compression libraries")

    prefix = arguments.prefix.resolve()
    prefix.mkdir(parents=True, exist_ok=True)
    work_dir = arguments.work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    # SZ2 requires zlib and zstd, SZ3 requires zstd, and Blosc2 can reuse the
    # same zstd. Building one copy avoids duplicate codec symbols in ADIOS2.
    zlib_build = work_dir / "zlib"
    if zlib_build.exists():
        shutil.rmtree(zlib_build)
    zlib_build.mkdir(parents=True, exist_ok=True)
    zlib_environment = os.environ.copy()
    zlib_environment["CFLAGS"] = "-O3 -fPIC"
    run(
        [str(arguments.zlib_source.resolve() / "configure"), "--static", f"--prefix={prefix}"],
        cwd=zlib_build,
        env=zlib_environment,
    )
    make = ["make", *([f"-j{arguments.jobs}"] if arguments.jobs is not None else [])]
    run(make, cwd=zlib_build, env=zlib_environment)
    run(["make", "install"], cwd=zlib_build, env=zlib_environment)

    cmake_install(
        arguments.zstd_source / "build" / "cmake",
        work_dir / "zstd",
        prefix,
        {
            "BUILD_SHARED_LIBS": "OFF",
            "BUILD_TESTING": "OFF",
            "ZSTD_BUILD_SHARED": "OFF",
            "ZSTD_BUILD_STATIC": "ON",
            "ZSTD_BUILD_PROGRAMS": "OFF",
            "ZSTD_BUILD_TESTS": "OFF",
            "ZSTD_LEGACY_SUPPORT": "OFF",
            "ZSTD_MULTITHREAD_SUPPORT": "OFF",
        },
        arguments.jobs,
    )
    environment = pkg_config_environment(prefix)
    environment["CMAKE_PREFIX_PATH"] = str(prefix)

    run(
        [
            sys.executable,
            str(SCRIPT_DIR / "build_blosc2.py"),
            "--source", str(arguments.blosc2_source.resolve()),
            "--build-dir", str(work_dir / "blosc2"),
            "--prefix", str(prefix),
            *(["--jobs", str(arguments.jobs)] if arguments.jobs is not None else []),
        ],
        env=environment,
    )
    cmake_install(
        arguments.zfp_source,
        work_dir / "zfp",
        prefix,
        {
            "BUILD_SHARED_LIBS": "OFF",
            "BUILD_TESTING": "OFF",
            "BUILD_UTILITIES": "OFF",
            "ZFP_WITH_CUDA": "OFF",
            "ZFP_WITH_OPENMP": "OFF",
        },
        arguments.jobs,
        environment,
    )
    cmake_install(
        arguments.sz3_source,
        work_dir / "sz3",
        prefix,
        {
            "BUILD_SHARED_LIBS": "OFF",
            "BUILD_TESTING": "OFF",
            "BUILD_H5Z_FILTER": "OFF",
            "BUILD_MDZ": "OFF",
            "CMAKE_DISABLE_FIND_PACKAGE_GSL": "ON",
            "CMAKE_DISABLE_FIND_PACKAGE_OpenMP": "ON",
            "SZ3_USE_BUNDLED_ZSTD": "OFF",
        },
        arguments.jobs,
        environment,
    )
    cmake_install(
        arguments.sz_source,
        work_dir / "sz",
        prefix,
        {
            "BUILD_SHARED_LIBS": "OFF",
            "BUILD_TESTING": "OFF",
            "BUILD_FORTRAN": "OFF",
            "BUILD_HDF5_FILTER": "OFF",
            "BUILD_OPENMP": "OFF",
            "BUILD_PYTHON_WRAPPER": "OFF",
            "CMAKE_DISABLE_FIND_PACKAGE_OpenMP": "ON",
            "SZ_FIND_DEPS": "ON",
        },
        arguments.jobs,
        environment,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
