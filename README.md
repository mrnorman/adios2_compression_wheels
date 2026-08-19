# ADIOS2 compression wheels for portUrb

This repository builds the unofficial `adios2-compressors` Python distribution
with Blosc2, SZ2, SZ3, and ZFP compiled into ADIOS2's native compression
operators. It installs as the separate `adios2_compressors` Python package and
uses suffixed native-library names, so it can safely coexist with the upstream
`adios2` distribution in one environment. This project is not affiliated with
or endorsed by the ADIOS2 project or Oak Ridge National Laboratory.

The primary purpose of this wheel is to support
[portUrb](https://github.com/ORNL/portUrb) Python analysis, post-processing,
and visualization workflows. ADIOS2 is portUrb's default file backend, and
portUrb currently compresses sufficiently large BP5 arrays with ADIOS2's
native Blosc2 operator using LZ4 and bit-shuffle. This wheel provides a
portable Python reader with that operator enabled. SZ2, SZ3, ZFP, and Blosc2's
LZ4HC and Zstd compressors are included for portUrb experiments and related
ADIOS2 datasets that select them.

The compressor libraries are linked statically and require no separate
runtime installation.

The release artifacts use the CPython 3.12 stable ABI (`cp312-abi3`). Separate
wheels support x86-64 and ARM64 Linux under the manylinux2014 /
`manylinux_2_17` policy, and Intel and Apple Silicon Macs with macOS 11 or
newer. Each architecture-specific wheel supports CPython 3.12 and newer.

## Build Linux wheels

The host needs Python 3.10 or newer, Git, and Docker or Podman. Run:

```bash
python3 build_manylinux.py
```

Use `--engine docker` or `--engine podman` to select a container engine, and
`--jobs N` to limit native compilation parallelism. The builder fetches the
pinned compressor and ADIOS2 sources under `sources/` when they do not exist.
Rootless Podman accounts without a subordinate UID/GID range can additionally
pass `--podman-ignore-chown-errors`.

The build runs in the pinned PyPA manylinux2014 image, compiles the compressor
libraries as CPU-only static PIC libraries, creates an ABI3 wheel with CPython
3.12, runs `auditwheel repair`, and installs and exercises the repaired wheel.
The distributable result is an architecture-specific wheel and checksum, for
example:

```text
wheelhouse/adios2_compressors-2.12.1.1-cp312-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl
wheelhouse/adios2_compressors-2.12.1.1-cp312-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl.sha256
```

Native x86-64 and AArch64 hosts are supported. The builder selects the pinned
PyPA manylinux2014 image for the host architecture; it does not use CPU
emulation.

## Build macOS wheels

On an Intel or Apple Silicon Mac with Python 3.12 or newer, install the build
requirements and run:

```bash
python3 -m pip install \
  build cmake delocate ninja numpy scikit-build-core setuptools-scm
python3 build_macos.py
```

This natively builds the wheel for the host architecture, repairs its dynamic
library references with `delocate`, installs the repaired wheel in a clean
environment, exercises every compressor, and writes the wheel and SHA-256
checksum under `wheelhouse/`. The default deployment target is macOS 11.0.

## Build all four wheels with GitHub Actions

The manually triggered `Build wheels` workflow builds and verifies Linux
x86-64, Linux ARM64, macOS Intel, and macOS Apple Silicon wheels. It has no
push, pull-request, or scheduled trigger.

After the workflow file is present on the repository's default branch, open
the repository's **Actions** tab, choose **Build wheels**, and click
**Run workflow**. Each platform's wheel and checksum is uploaded as a separate
artifact and retained for seven days. A failed platform can be re-run by
opening the workflow run and choosing **Re-run failed jobs**.

Install it on a target machine with:

```bash
python3 -m pip install wheelhouse/adios2_compressors-*.whl
```

Import the compression-enabled build with its distinct namespace:

```python
import adios2_compressors as adios2
```

It may be loaded alongside the upstream package without either distribution
owning or overwriting the other's files:

```python
import adios2
import adios2_compressors
```

## What is included

The distribution version is `2.12.1.1`: the first three components identify
the embedded ADIOS2 release and the final component identifies this downstream
build revision.
ADIOS2 v2.12.1, c-blosc2 v2.15.1, ZFP v1.0.1, SZ2 v2.1.12.5, SZ3 v3.1.8,
zstd v1.5.7, and zlib v1.3.1 are pinned to exact commits. SZ2 is included for
compatibility with existing data; SZ3 is the current SZ implementation. MPI,
CUDA, OpenMP, Fortran, HDF5, SST, SysV shared memory, other compression
operators, examples, and native tests are disabled to keep the wheel portable
and self-contained.

`verify_wheel.py` round-trips BP5 data independently with Blosc2 `lz4`,
`lz4hc`, and `zstd`, and with the native `sz`, `sz3`, and `zfp` operators. Run
it against an installed wheel with:

```bash
python3 verify_wheel.py
```

To test same-process coexistence after installing both distributions, run:

```bash
python3 verify_coexistence.py
```

Compressed data use the ordinary ADIOS2 API through the `adios2_compressors`
namespace; ADIOS2 detects and decompresses the native operator automatically.
Native applications such as ParaView must
independently contain an ADIOS2 build with the corresponding compressor
enabled. Installing this Python wheel does not replace an application's private
ADIOS2 library.

For a host-specific developer build, install `build`, `cmake`, `ninja`,
`numpy`, `scikit-build-core`, and `setuptools-scm`, then run
`python3 build_wheel.py`. Such a wheel is not a distribution artifact until it
has been built inside the manylinux image and processed by `auditwheel` on
Linux, or repaired with `delocate` on macOS.
