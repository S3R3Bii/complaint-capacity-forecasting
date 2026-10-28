"""Replay the saved study in a disposable directory and compare released results."""
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def compare(expected, actual, path="summary"):
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or expected.keys() != actual.keys():
            raise AssertionError(f"{path}: fields differ")
        for key, value in expected.items():
            compare(value, actual[key], f"{path}.{key}")
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            raise AssertionError(f"{path}: lengths differ")
        for index, value in enumerate(expected):
            compare(value, actual[index], f"{path}[{index}]")
    elif isinstance(expected, float):
        # Permit numerical-library rounding, not a material change in a result.
        if not isinstance(actual, (int, float)) or not math.isclose(
            expected, actual, rel_tol=1e-7, abs_tol=1e-9
        ):
            raise AssertionError(f"{path}: released and reproduced values differ")
    elif expected != actual:
        raise AssertionError(f"{path}: released and reproduced values differ")


def main():
    expected = {
        delay: json.loads((ROOT/f"results/lag{delay}_summary.json").read_text())
        for delay in (2, 3)
    }
    with TemporaryDirectory(prefix="complaint-replay-") as temporary:
        replay = Path(temporary)
        for folder in ("data", "src", "sql", "results"):
            shutil.copytree(ROOT/folder, replay/folder, ignore=shutil.ignore_patterns("__pycache__", "*.sqlite"))
        (replay/"figures").mkdir()
        for script in ("analyze.py", "verify.py", "verify_intervals.py", "figures.py"):
            result = subprocess.run(
                [sys.executable, str(replay/"src"/script)], cwd=replay,
                capture_output=True, text=True, timeout=300, check=False,
            )
            if result.returncode:
                print(result.stdout)
                print(result.stderr, file=sys.stderr)
                raise RuntimeError(f"{script}: reproduction failed")
            print(f"PASS: {script}", flush=True)
        for delay, released in expected.items():
            reproduced = json.loads((replay/f"results/lag{delay}_summary.json").read_text())
            compare(released, reproduced, f"lag{delay}")
            print(f"PASS: lag {delay} summary matches the released result", flush=True)
        for name in ("forecast-and-decision", "tuning-comparison", "product-forecast-traces"):
            for extension in ("png", "pdf"):
                figure = replay/f"figures/{name}.{extension}"
                if not figure.is_file() or figure.stat().st_size == 0:
                    raise AssertionError(f"Figure not generated: {name}.{extension}")
        print("PASS: all three figures generated; visual interpretation still requires review")
    print("Offline reproduction completed without modifying the released artifacts.")


if __name__ == "__main__":
    main()
