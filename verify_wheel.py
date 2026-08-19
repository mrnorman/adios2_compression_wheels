#!/usr/bin/env python3
"""Verify the native compression operators included in the ADIOS2 wheel."""

from __future__ import annotations

import tempfile
from pathlib import Path

import adios2_compressors as adios2
import numpy as np


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="adios2-compressors-wheel-") as temporary:
        expected = np.arange(65536, dtype=np.float32).reshape(256, 256) % 31
        compressors = (
            ("blosc-lz4", "blosc", {"compressor": "lz4", "clevel": "5"}, 0.0),
            ("blosc-lz4hc", "blosc", {"compressor": "lz4hc", "clevel": "5"}, 0.0),
            ("blosc-zstd", "blosc", {"compressor": "zstd", "clevel": "5"}, 0.0),
            ("sz", "sz", {"accuracy": "0.001"}, 0.0011),
            ("sz3", "sz3", {"accuracy": "0.001"}, 0.0011),
            ("zfp", "zfp", {"accuracy": "0.001"}, 0.0011),
        )
        for name, operator_type, parameters, tolerance in compressors:
            output = Path(temporary) / f"native-{name}.bp"
            adios = adios2.Adios()
            io = adios.declare_io(f"native_{name.replace('-', '_')}_write")
            io.set_engine("BP5")
            if operator_type == "blosc":
                parameters["doshuffle"] = "BLOSC_BITSHUFFLE"
            operator = adios.define_operator(name, operator_type, parameters)
            variable = io.define_variable(
                "field", expected, expected.shape, [0, 0], expected.shape, True
            )
            variable.add_operation(operator, {})
            writer = io.open(str(output), adios2.Mode.Write)
            writer.put(variable, expected, adios2.Mode.Sync)
            writer.close()

            with adios2.FileReader(str(output)) as reader:
                actual = reader.read("field")
            if tolerance == 0.0:
                np.testing.assert_array_equal(actual, expected)
            else:
                np.testing.assert_allclose(actual, expected, rtol=0.0, atol=tolerance)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
