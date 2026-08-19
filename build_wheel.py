#!/usr/bin/env python3
"""Build a local ADIOS2 wheel with native scientific compression operators."""

from __future__ import annotations

import argparse
import importlib.util
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_DIR = SCRIPT_DIR / "sources"
DEFAULT_ADIOS2_SOURCE = SOURCE_DIR / "ADIOS2"
DEFAULT_BLOSC2_SOURCE = SOURCE_DIR / "c-blosc2"
DEFAULT_ZFP_SOURCE = SOURCE_DIR / "zfp"
DEFAULT_SZ3_SOURCE = SOURCE_DIR / "SZ3"
DEFAULT_SZ_SOURCE = SOURCE_DIR / "SZ"
DEFAULT_ZSTD_SOURCE = SOURCE_DIR / "zstd"
DEFAULT_ZLIB_SOURCE = SOURCE_DIR / "zlib"
ADIOS2_REPOSITORY = "https://github.com/ornladios/ADIOS2.git"
BLOSC2_REPOSITORY = "https://github.com/Blosc/c-blosc2.git"
ZFP_REPOSITORY = "https://github.com/LLNL/zfp.git"
SZ3_REPOSITORY = "https://github.com/szcompressor/SZ3.git"
SZ_REPOSITORY = "https://github.com/szcompressor/sz2.git"
ZSTD_REPOSITORY = "https://github.com/facebook/zstd.git"
ZLIB_REPOSITORY = "https://github.com/madler/zlib.git"
ADIOS2_REF = "v2.12.1"
BLOSC2_REF = "v2.15.1"
ZFP_REF = "1.0.1"
SZ3_REF = "v3.1.8"
SZ_REF = "v2.1.12.5"
ZSTD_REF = "v1.5.7"
ZLIB_REF = "v1.3.1"
ADIOS2_REVISION = "f5267290f06980acaecaf54688d0980958eb86bf"
BLOSC2_REVISION = "841c6ae7200c88f73b2825da27fed2a83360ad4c"
ZFP_REVISION = "f40868a6a1c190c802e7d8b5987064f044bf7812"
SZ3_REVISION = "be68d645b2e1350adfbd61851c0886b38b876aa5"
SZ_REVISION = "5857c6ed1f7a8ca1c2822a88e2f614e466dc4d34"
ZSTD_REVISION = "f8745da6ff1ad1e7bab384bd1f9d742439278e99"
ZLIB_REVISION = "51b7f2abdade71cd9bb0e7a373ef2610ec6f9daf"
UPSTREAM_VERSION = "2.12.1"
PACKAGE_VERSION = f"{UPSTREAM_VERSION}.1"
PYTHON_PACKAGE = "adios2_compressors"
DISTRIBUTION_NAME = "adios2-compressors"
WHEEL_NAME = DISTRIBUTION_NAME.replace("-", "_")
LIBRARY_SUFFIX = "_compressors"
PROJECT_URL = "https://github.com/mrnorman/adios2_compression_wheels"

SOURCES = (
    (
        "adios2_source", DEFAULT_ADIOS2_SOURCE, ADIOS2_REPOSITORY, ADIOS2_REF,
        ADIOS2_REVISION, "pyproject.toml",
    ),
    (
        "blosc2_source", DEFAULT_BLOSC2_SOURCE, BLOSC2_REPOSITORY, BLOSC2_REF,
        BLOSC2_REVISION, "CMakeLists.txt",
    ),
    (
        "zfp_source", DEFAULT_ZFP_SOURCE, ZFP_REPOSITORY, ZFP_REF,
        ZFP_REVISION, "CMakeLists.txt",
    ),
    (
        "sz3_source", DEFAULT_SZ3_SOURCE, SZ3_REPOSITORY, SZ3_REF,
        SZ3_REVISION, "CMakeLists.txt",
    ),
    (
        "sz_source", DEFAULT_SZ_SOURCE, SZ_REPOSITORY, SZ_REF,
        SZ_REVISION, "CMakeLists.txt",
    ),
    (
        "zstd_source", DEFAULT_ZSTD_SOURCE, ZSTD_REPOSITORY, ZSTD_REF,
        ZSTD_REVISION, "build/cmake/CMakeLists.txt",
    ),
    (
        "zlib_source", DEFAULT_ZLIB_SOURCE, ZLIB_REPOSITORY, ZLIB_REF,
        ZLIB_REVISION, "CMakeLists.txt",
    ),
)

DISABLED_ADIOS2_FEATURES = (
    "AWSSDK", "BigWhoop", "BZip2", "CUDA", "Caliper", "Campaign", "Catalyst", "CURL", "DAOS",
    "DataMan", "DataSpaces", "Derived_Variable", "Fortran", "HDF5", "HDF5_VOL", "IME", "Kokkos",
    "KVCACHE", "LIBPRESSIO", "MGARD", "MHS", "OpenSSL", "PNG", "PRODM", "Profiling", "SST",
    "SealKeygen", "Sodium", "SysVShMem", "UCX", "XRootD", "ZeroMQ",
)


def prepare_checkout(
    source: Path, repository: str, reference: str, revision: str, sentinel: str
) -> None:
    if (source / sentinel).is_file():
        actual = subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
        ).strip()
        if actual != revision:
            raise RuntimeError(f"Expected {source} at {revision}, found {actual}")
    else:
        if source.exists():
            raise RuntimeError(f"Source directory exists but is incomplete: {source}")
        source.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "git", "clone", "--depth", "1", "--branch", reference,
                "--recurse-submodules", repository, str(source),
            ],
            check=True,
        )
        actual = subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
        ).strip()
        if actual != revision:
            raise RuntimeError(f"Expected {repository} at {revision}, cloned {actual}")


def source_paths(arguments: argparse.Namespace) -> dict[str, Path]:
    paths = {}
    for name, default, repository, reference, revision, sentinel in SOURCES:
        requested = getattr(arguments, name)
        path = (requested or default).resolve()
        if requested is None:
            prepare_checkout(path, repository, reference, revision, sentinel)
        if not (path / sentinel).is_file():
            raise RuntimeError(f"Invalid source tree: {path}")
        paths[name] = path
    return paths


def adios2_version(adios2_source: Path) -> str:
    version_file = adios2_source / "VERSION.TXT"
    if version_file.is_file():
        return version_file.read_text(encoding="utf-8").strip()
    description = subprocess.check_output(
        ["git", "-C", str(adios2_source), "describe"], text=True
    ).strip()
    tagged = re.fullmatch(r"v([^-]+)", description)
    if tagged:
        return tagged.group(1)
    committed = re.fullmatch(r"v([^-]+)-([0-9]+)-g[0-9a-f]+", description)
    if committed:
        return f"{committed.group(1)}.{100000 + int(committed.group(2))}"
    release_candidate = re.fullmatch(r"v([^-]+)-rc([0-9]+)(?:-([0-9]+)-g[0-9a-f]+)?", description)
    if release_candidate:
        commits = int(release_candidate.group(3) or 0)
        return f"{release_candidate.group(1)}.{1000 * int(release_candidate.group(2)) + commits}"
    raise RuntimeError(f"Cannot translate ADIOS2 git description into a wheel version: {description}")


def replace_required(path: Path, old: str, new: str, count: int = -1) -> None:
    contents = path.read_text(encoding="utf-8")
    occurrences = contents.count(old)
    if occurrences == 0:
        raise RuntimeError(f"Cannot find {old!r} in {path}")
    if count >= 0 and occurrences != count:
        raise RuntimeError(
            f"Expected {count} occurrences of {old!r} in {path}, found {occurrences}"
        )
    path.write_text(contents.replace(old, new), encoding="utf-8")


def namespace_python_package(stage: Path) -> Path:
    package = stage / "python" / "adios2"
    namespaced_package = package.with_name(PYTHON_PACKAGE)
    package.rename(namespaced_package)
    for source in namespaced_package.rglob("*.py"):
        contents = source.read_text(encoding="utf-8")
        source.write_text(re.sub(r"\badios2\b", PYTHON_PACKAGE, contents), encoding="utf-8")
    for source in (stage / "bindings" / "Python" / "test").rglob("*.py"):
        contents = source.read_text(encoding="utf-8")
        source.write_text(re.sub(r"\badios2\b", PYTHON_PACKAGE, contents), encoding="utf-8")

    replace_required(
        stage / "python" / "CMakeLists.txt",
        "adios2",
        PYTHON_PACKAGE,
    )
    replace_required(
        stage / "bindings" / "Python" / "CMakeLists.txt",
        "adios2/bindings",
        f"{PYTHON_PACKAGE}/bindings",
    )
    replace_required(
        stage / "bindings" / "Python" / "CMakeLists.txt",
        "  NB_STATIC\n",
        f"  NB_STATIC\n  NB_DOMAIN {PYTHON_PACKAGE}\n",
        count=1,
    )
    replace_required(
        stage / "bindings" / "Python" / "CMakeLists.txt",
        "set(install_location adios2)",
        f"set(install_location {PYTHON_PACKAGE})",
        count=1,
    )
    replace_required(
        stage / "CMakeLists.txt",
        'set(CMAKE_INSTALL_LIBDIR "adios2")',
        f'set(CMAKE_INSTALL_LIBDIR "{PYTHON_PACKAGE}")',
        count=1,
    )
    replace_required(
        stage / "CMakeLists.txt",
        'set(CMAKE_INSTALL_INCLUDEDIR "adios2/include")',
        f'set(CMAKE_INSTALL_INCLUDEDIR "{PYTHON_PACKAGE}/include")',
        count=1,
    )
    replace_required(
        stage / "CMakeLists.txt",
        'set(CMAKE_INSTALL_BINDIR "adios2/bindings")',
        f'set(CMAKE_INSTALL_BINDIR "{PYTHON_PACKAGE}/bindings")',
        count=1,
    )
    return namespaced_package


def customize_metadata(stage: Path, python_minimum: str | None) -> None:
    pyproject = stage / "pyproject.toml"
    contents = pyproject.read_text(encoding="utf-8")
    operating_system_classifier = (
        "Operating System :: MacOS :: MacOS X"
        if platform.system() == "Darwin"
        else "Operating System :: POSIX :: Linux"
    )
    replacements = {
        'name = "adios2"': f'name = "{DISTRIBUTION_NAME}"',
        'description = "The Adaptable Input Output System version 2"': (
            'description = "ADIOS2 compression build supporting portUrb Python workflows"'
        ),
        'readme = "ReadMe.md"': 'readme = "ReadMe.compression-wheel.md"',
        'keywords = [\n    "Python",\n    "Web",\n    "Application",\n    "Framework",\n]': (
            'keywords = ["portUrb", "ADIOS2", "compression", "scientific computing"]'
        ),
        '"Operating System :: OS Independent",': f'"{operating_system_classifier}",',
        'wheel.packages = ["python/adios2"]': f'wheel.packages = ["python/{PYTHON_PACKAGE}"]',
        'test-command = "python -m unittest adios2.test.simple_read_write.TestSimpleReadWrite"': (
            f'test-command = "python -m unittest '
            f'{PYTHON_PACKAGE}.test.simple_read_write.TestSimpleReadWrite"'
        ),
    }
    for old, new in replacements.items():
        if contents.count(old) != 1:
            raise RuntimeError(f"Expected one occurrence of {old!r} in {pyproject}")
        contents = contents.replace(old, new)
    contents, substitutions = re.subn(
        r"(?ms)^authors = \[.*?^\]\n",
        'authors = [{ name="ADIOS2 contributors" }]\n'
        'maintainers = [{ name="Matt Norman" }]\n',
        contents,
        count=1,
    )
    if substitutions != 1:
        raise RuntimeError(f"Cannot replace project authors in {pyproject}")
    contents, substitutions = re.subn(
        r"(?ms)^\[project\.urls\]\n.*?(?=^\[tool\.cibuildwheel\])",
        (
            "[project.urls]\n"
            f'Homepage = "{PROJECT_URL}"\n'
            f'Repository = "{PROJECT_URL}"\n'
            f'"Issue Tracker" = "{PROJECT_URL}/issues"\n'
            'portUrb = "https://github.com/ORNL/portUrb"\n'
            '"Upstream ADIOS2" = "https://github.com/ornladios/ADIOS2"\n'
            '"ADIOS2 Documentation" = "https://adios2.readthedocs.io/"\n\n'
        ),
        contents,
        count=1,
    )
    if substitutions != 1:
        raise RuntimeError(f"Cannot replace project URLs in {pyproject}")
    if python_minimum is not None:
        contents, substitutions = re.subn(
            r'(?m)^requires-python\s*=\s*"[^"]+"$',
            f'requires-python = ">={python_minimum}"',
            contents,
            count=1,
        )
        if substitutions != 1:
            raise RuntimeError(f"Cannot set requires-python in {pyproject}")
    pyproject.write_text(contents, encoding="utf-8")


def prepare_source(
    work_dir: Path,
    sources: dict[str, Path],
    python_minimum: str | None = None,
) -> Path:
    adios2_source = sources["adios2_source"]
    stage = work_dir / "source"
    if stage.exists():
        shutil.rmtree(stage)
    shutil.copytree(
        adios2_source,
        stage,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".git", "_skbuild", "build", "__pycache__"),
    )
    upstream_version = adios2_version(adios2_source)
    if upstream_version != UPSTREAM_VERSION:
        raise RuntimeError(f"Expected ADIOS2 {UPSTREAM_VERSION}, found {upstream_version}")
    (stage / "VERSION.TXT").write_text(PACKAGE_VERSION, encoding="utf-8")
    shutil.copy2(SCRIPT_DIR / "README.md", stage / "ReadMe.compression-wheel.md")
    package = namespace_python_package(stage)
    licenses = package / "third_party_licenses"
    licenses.mkdir(parents=True, exist_ok=True)
    license_files = {
        "Blosc2-LICENSE.txt": sources["blosc2_source"] / "LICENSE.txt",
        "SZ2-LICENSE.txt": sources["sz_source"] / "copyright-and-BSD-license.txt",
        "SZ3-LICENSE.txt": sources["sz3_source"] / "copyright-and-BSD-license.txt",
        "ZFP-LICENSE.txt": sources["zfp_source"] / "LICENSE",
        "ZFP-NOTICE.txt": sources["zfp_source"] / "NOTICE",
        "zlib-LICENSE.txt": sources["zlib_source"] / "LICENSE",
        "zstd-LICENSE.txt": sources["zstd_source"] / "LICENSE",
        "Wheel-build-BSD-2-Clause.txt": SCRIPT_DIR / "LICENSE",
    }
    for name, source in license_files.items():
        shutil.copy2(source, licenses / name)
    for source in (sources["blosc2_source"] / "LICENSES").glob("*.txt"):
        shutil.copy2(source, licenses / f"Blosc2-{source.name}")
    customize_metadata(stage, python_minimum)
    return stage


def cmake_settings(prefix: Path, build_dir: Path, stable_abi: bool) -> list[str]:
    settings = {
        "build-dir": str(build_dir.resolve()),
        "cmake.define.CMAKE_PREFIX_PATH": str(prefix.resolve()),
        "cmake.define.ADIOS2_USE_Blosc2": "ON",
        "cmake.define.ADIOS2_Blosc2_PREFER_SHARED": "OFF",
        "cmake.define.ADIOS2_USE_SZ": "ON",
        "cmake.define.ADIOS2_USE_SZ3": "ON",
        "cmake.define.ADIOS2_USE_ZFP": "ON",
        "cmake.define.ADIOS2_USE_MPI": "OFF",
        "cmake.define.ADIOS2_USE_PIP": "ON",
        "cmake.define.ADIOS2_USE_Python": "ON",
        "cmake.define.ADIOS2_LIBRARY_SUFFIX": LIBRARY_SUFFIX,
        "cmake.define.CMAKE_DISABLE_FIND_PACKAGE_OpenMP": "ON",
        "cmake.define.HAVE_shmget": "OFF",
        "cmake.define.SZ_ROOT": str(prefix.resolve()),
    }
    settings.update({f"cmake.define.ADIOS2_USE_{feature}": "OFF" for feature in DISABLED_ADIOS2_FEATURES})
    if stable_abi:
        settings["wheel.py-api"] = "cp312"
        settings["cmake.define.ADIOS2_USE_PythonStableABI"] = "ON"
    return [item for key, value in settings.items() for item in ("--config-setting", f"{key}={value}")]


def cmake_supports_stable_abi() -> bool:
    output = subprocess.check_output(["cmake", "--version"], text=True).splitlines()[0]
    match = re.search(r"([0-9]+)\.([0-9]+)", output)
    return match is not None and tuple(map(int, match.groups())) >= (3, 26)


def build_wheel(
    arguments: argparse.Namespace,
    adios2_source: Path,
    work_dir: Path,
    output_dir: Path,
    sources: dict[str, Path],
) -> None:
    build_requirements = ("build", "ninja", "numpy", "scikit_build_core", "setuptools_scm")
    missing = [name for name in build_requirements if importlib.util.find_spec(name) is None]
    if missing:
        packages = " ".join(name.replace("_", "-") for name in missing)
        raise RuntimeError(
            f"Install the missing build dependencies first: "
            f"{sys.executable} -m pip install {packages}"
        )
    architecture = platform.machine() or "unknown"
    python_tag = sys.implementation.cache_tag or f"py{sys.version_info.major}{sys.version_info.minor}"
    prefix = work_dir / f"compression-prefix-{architecture}"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / "build_dependencies.py"),
            "--blosc2-source", str(sources["blosc2_source"]),
            "--zfp-source", str(sources["zfp_source"]),
            "--sz3-source", str(sources["sz3_source"]),
            "--sz-source", str(sources["sz_source"]),
            "--zstd-source", str(sources["zstd_source"]),
            "--zlib-source", str(sources["zlib_source"]),
            "--work-dir", str(work_dir / f"compression-build-{architecture}"),
            "--prefix", str(prefix),
            *(["--jobs", str(arguments.jobs)] if arguments.jobs is not None else []),
        ],
        check=True,
    )

    stable_abi_available = (
        sys.implementation.name == "cpython"
        and sys.version_info >= (3, 12)
        and cmake_supports_stable_abi()
    )
    if arguments.stable_abi and not stable_abi_available:
        raise RuntimeError(
            "--stable-abi requires CPython 3.12 or newer and CMake 3.26 or newer"
        )
    stable_abi = arguments.stable_abi or stable_abi_available
    output_dir.mkdir(parents=True, exist_ok=True)
    adios2_build_dir = work_dir / f"adios2-build-{python_tag}-{architecture}"
    if adios2_build_dir.exists():
        shutil.rmtree(adios2_build_dir)
    environment = os.environ.copy()
    existing_prefix = environment.get("CMAKE_PREFIX_PATH")
    environment["CMAKE_PREFIX_PATH"] = os.pathsep.join(
        entry for entry in (str(prefix.resolve()), existing_prefix) if entry
    )
    pkg_config_paths = [prefix / "lib64" / "pkgconfig", prefix / "lib" / "pkgconfig"]
    existing_pkg_config = environment.get("PKG_CONFIG_PATH")
    pkg_config_entries = [str(path) for path in pkg_config_paths]
    if existing_pkg_config:
        pkg_config_entries.append(existing_pkg_config)
    environment["PKG_CONFIG_PATH"] = os.pathsep.join(pkg_config_entries)
    subprocess.run(
        [
            sys.executable, "-m", "build", "--wheel", "--no-isolation",
            "--outdir", str(output_dir),
            *cmake_settings(prefix, adios2_build_dir, stable_abi),
            str(adios2_source),
        ],
        check=True,
        env=environment,
    )
    if arguments.install:
        wheel = max(output_dir.glob(f"{WHEEL_NAME}-*.whl"), key=lambda path: path.stat().st_mtime)
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--force-reinstall", str(wheel)],
            check=True,
        )
        subprocess.run([sys.executable, str(SCRIPT_DIR / "verify_wheel.py")], check=True)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=SCRIPT_DIR / "build")
    parser.add_argument("--output-dir", type=Path, default=SCRIPT_DIR / "wheelhouse")
    parser.add_argument("--jobs", type=int, help="parallel native build jobs")
    parser.add_argument("--install", action="store_true", help="install and verify the new wheel")
    parser.add_argument(
        "--stable-abi",
        action="store_true",
        help="require a CPython 3.12 abi3 wheel instead of silently falling back",
    )
    parser.add_argument("--adios2-source", type=Path, help="use an existing ADIOS2 source tree")
    parser.add_argument("--blosc2-source", type=Path, help="use an existing c-blosc2 source tree")
    parser.add_argument("--zfp-source", type=Path, help="use an existing ZFP source tree")
    parser.add_argument("--sz3-source", type=Path, help="use an existing SZ3 source tree")
    parser.add_argument("--sz-source", type=Path, help="use an existing SZ2 source tree")
    parser.add_argument("--zstd-source", type=Path, help="use an existing zstd source tree")
    parser.add_argument("--zlib-source", type=Path, help="use an existing zlib source tree")
    parser.add_argument("--prepare-sources-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    sources = source_paths(arguments)
    if arguments.prepare_sources_only:
        return 0
    work_dir = arguments.work_dir.resolve()
    output_dir = arguments.output_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    stage = prepare_source(
        work_dir,
        sources,
        "3.12" if arguments.stable_abi else None,
    )
    build_wheel(arguments, stage, work_dir, output_dir, sources)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
