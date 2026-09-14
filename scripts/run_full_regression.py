"""Run every repository pytest test, including integration tests, and archive the result."""
from __future__ import annotations

from datetime import datetime, timezone
import platform
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = ROOT / "artifacts" / "full_regression" / timestamp
    output_dir.mkdir(parents=True, exist_ok=False)
    junit_path = output_dir / "junit.xml"
    pytest_output = output_dir / "pytest-output.txt"
    command = [
        sys.executable, "-m", "pytest", "backend/tests", "-o", "addopts=",
        "--tb=short", f"--junitxml={junit_path}",
        f"--basetemp={output_dir / 'pytest-tmp'}",
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, check=False)
    pytest_output.write_text(completed.stdout, encoding="utf-8")

    report = f"""# Full regression test report

- Run time (UTC): {timestamp}
- Python: {sys.version.splitlines()[0]}
- Platform: {platform.platform()}
- Command: `{' '.join(command)}`
- Exit code: {completed.returncode}
- Scope: all tests under `backend/tests`, including tests marked `integration`.

Artifacts:

- `pytest-output.txt`: full pytest terminal output.
- `junit.xml`: machine-readable per-test result.

Interpretation: this is a full regression result for this repository snapshot. It does not by itself establish that every real academic policy has been modelled or that the research hypotheses are proven.
"""
    (output_dir / "REPORT.md").write_text(report, encoding="utf-8")
    print(output_dir.relative_to(ROOT))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
