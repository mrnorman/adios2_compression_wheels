#!/usr/bin/env python3
"""Build and install the wheel's minimal static Blosc2 dependency."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--prefix", required=True, type=Path)
    parser.add_argument("--jobs", type=int)
    arguments = parser.parse_args()

    if shutil.which("cmake") is None:
        raise RuntimeError("CMake 3.18 or newer is required to build Blosc2")

    configure = [
        "cmake",
        "-S", str(arguments.source.resolve()),
        "-B", str(arguments.build_dir.resolve()),
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_INSTALL_PREFIX={arguments.prefix.resolve()}",
        "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
        "-DBUILD_STATIC=ON",
        "-DBUILD_SHARED=OFF",
        "-DBUILD_TESTS=OFF",
        "-DBUILD_FUZZERS=OFF",
        "-DBUILD_BENCHMARKS=OFF",
        "-DBUILD_EXAMPLES=OFF",
        "-DBUILD_PLUGINS=OFF",
        "-DBUILD_LITE=OFF",
        "-DDEACTIVATE_ZLIB=ON",
        "-DDEACTIVATE_ZSTD=OFF",
        "-DPREFER_EXTERNAL_ZSTD=ON",
        "-DBLOSC_INSTALL=ON",
    ]
    subprocess.run(configure, check=True)

    build = ["cmake", "--build", str(arguments.build_dir.resolve()), "--target", "install", "--parallel"]
    if arguments.jobs is not None:
        build.append(str(arguments.jobs))
    subprocess.run(build, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
