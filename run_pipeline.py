import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

PIPELINE_STEPS = [
    ("1. EXTRACT DATA", "scripts/extract.py"),
    ("2. LOAD RAW DATA", "scripts/load.py"),
    ("3. TRANSFORM & CLEAN DATA", "scripts/transform.py"),
    ("4. GENERATE ANALYTICS TABLES", "scripts/run_analytics.py"),
    ("5. EXECUTE QUALITY CHECKS", "scripts/checks.py"),
]


def run_pipeline():
    print("=" * 60)
    print("STARTING NYC YELLOW TAXI DATA PIPELINE")
    print("=" * 60)

    for step_title, script_path in PIPELINE_STEPS:
        print(f"\n>>> {step_title}")
        print(f"Executing: {script_path}")
        print("-" * 40)

        result = subprocess.run(
            [sys.executable, "-u", script_path],
            cwd=REPO_ROOT,
        )

        if result.returncode != 0:
            print("\n" + "=" * 60)
            print(f"PIPELINE EXECUTION FAILED AT STEP: {step_title}")
            print(f"Script {script_path} exited with code {result.returncode}.")
            print("=" * 60)
            sys.exit(result.returncode)

    print("\n" + "=" * 60)
    print("SUCCESS: ALL PIPELINE STEPS AND QUALITY CHECKS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    run_pipeline()
