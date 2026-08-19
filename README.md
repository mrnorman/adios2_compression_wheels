# ADIOS2 compression manylinux wheel

This repository builds an ADIOS2 Python wheel with Blosc2, SZ2, SZ3, and ZFP
compiled into ADIOS2's native compression operators. Blosc2 contains its
standard LZ4, LZ4HC, and Zstd compressors (sometimes mistyped as "l4z" and
"l4zhc"). The compressor libraries are linked statically and require no
separate runtime installation.

The release artifact uses the CPython 3.12 stable ABI (`cp312-abi3`) and the
manylinux2014 / `manylinux_2_17` platform policy. One wheel therefore supports
CPython 3.12 and newer on glibc-based x86-64 Linux distributions whose glibc is
2.17 or newer.

## Build

Docker or Podman is the only host build dependency. Run:

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
The distributable result is:

```text
wheelhouse/adios2-2.12.1-cp312-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl
```

Install it on a target machine with:

```bash
python3 -m pip install wheelhouse/adios2-*.whl
```

## What is included

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

Compressed data use the ordinary ADIOS2 API; ADIOS2 detects and decompresses
the native operator automatically. Native applications such as ParaView must
independently contain an ADIOS2 build with the corresponding compressor
enabled. Installing this Python wheel does not replace an application's private
ADIOS2 library.

For a host-specific developer build, install `build`, `cmake`, `ninja`,
`numpy`, `scikit-build-core`, and `setuptools-scm`, then run
`python3 build_wheel.py`. Such a wheel is not a distribution artifact until it
has been built inside the manylinux image and processed by `auditwheel`.
