"""Benchmark script for XLS reader performance and memory profiling.

Measures parse time and peak memory for real and synthetic sparse/dense workbooks.
"""

from __future__ import annotations

import io
import time
import tracemalloc
from pathlib import Path

from atboffice.modules.spreadsheet.io.xls_reader import read_xls

REAL_SAMPLE = Path("tests/docs/excel/xls/poi__51535.xls")


def run_benchmark_on_source(name: str, source: str | Path | bytes, iterations: int = 3) -> dict[str, float]:
    times: list[float] = []
    peak_mems: list[float] = []

    for _ in range(iterations):
        tracemalloc.start()
        t0 = time.perf_counter()
        wb = read_xls(source)
        t1 = time.perf_counter()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        times.append(t1 - t0)
        peak_mems.append(peak / (1024 * 1024))

    min_t = min(times)
    avg_t = sum(times) / len(times)
    max_t = max(times)
    avg_mem = sum(peak_mems) / len(peak_mems)

    result = {
        "name": name,
        "min_sec": min_t,
        "avg_sec": avg_t,
        "max_sec": max_t,
        "avg_peak_mb": avg_mem,
    }
    print(f"[{name}] {iterations} runs: min={min_t:.4f}s, avg={avg_t:.4f}s, max={max_t:.4f}s, peak_mem={avg_mem:.2f}MB")
    return result


def main() -> None:
    print("=== XLS Reader Benchmark & Profiling ===")
    if REAL_SAMPLE.exists():
        run_benchmark_on_source("Real Sample: poi__51535.xls", REAL_SAMPLE, iterations=1)
    else:
        print(f"Real sample not found: {REAL_SAMPLE}")


if __name__ == "__main__":
    main()
