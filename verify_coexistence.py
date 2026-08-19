#!/usr/bin/env python3
"""Verify that upstream ADIOS2 and the compression build load side by side."""

from __future__ import annotations

import adios2
import adios2_compressors

from verify_wheel import main as verify_compressors


def main() -> int:
    if adios2.__file__ == adios2_compressors.__file__:
        raise RuntimeError("The two distributions resolved to the same Python package")
    upstream_version = adios2.__version__
    compressors_version = adios2_compressors.__version__
    upstream = adios2.Adios()
    compressors = adios2_compressors.Adios()
    if upstream is None or compressors is None:
        raise RuntimeError("Could not construct both ADIOS objects")
    print(f"Loaded adios2 {upstream_version} from {adios2.__file__}")
    print(
        f"Loaded adios2_compressors {compressors_version} "
        f"from {adios2_compressors.__file__}"
    )
    return verify_compressors()


if __name__ == "__main__":
    raise SystemExit(main())
