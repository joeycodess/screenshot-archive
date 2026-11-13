"""Measure CLI wall time on fresh archives and verify the output."""
import argparse
import csv
import platform
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path
from time import perf_counter

from make_fixtures import generate
from screenshot_archive import fingerprint


def invoke(source, archive, manifest):
    started = perf_counter()
    subprocess.run([sys.executable, str(Path(__file__).with_name("screenshot_archive.py")),
                    str(source), str(archive), "--manifest", str(manifest)], check=True, capture_output=True)
    elapsed = perf_counter() - started
    with manifest.open(newline="", encoding="utf-8") as stream:
        return elapsed, list(csv.DictReader(stream))


def benchmark(count, repeats):
    times = []
    with tempfile.TemporaryDirectory() as workspace:
        root = Path(workspace)
        source = root / "input"
        generate(source, count)
        for index in range(repeats):
            archive = root / f"archive-{index}"
            elapsed, rows = invoke(source, archive, root / f"apply-{index}.csv")
            assert len(rows) == count and all(row["status"] == "archived" for row in rows)
            assert all(fingerprint(source / row["source"]) == fingerprint(archive / row["destination"]) for row in rows)
            existing = {path: path.stat().st_mtime_ns for path in archive.rglob("*") if path.is_file()}
            _, second = invoke(source, archive, root / f"repeat-{index}.csv")
            assert len(second) == count and all(row["status"] == "already_archived" for row in second)
            assert existing == {path: path.stat().st_mtime_ns for path in archive.rglob("*") if path.is_file()}
            times.append(elapsed)
    print(f"{platform.system()} {platform.release()} {platform.machine()}, Python {platform.python_version()}")
    print("Runs (seconds):", ", ".join(f"{value:.3f}" for value in times))
    print(f"Median: {statistics.median(times):.3f}s for {count} synthetic PNGs; 0 additional copies per rerun")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if min(args.count, args.repeats) < 1:
        parser.error("count and repeats must be positive")
    benchmark(args.count, args.repeats)
