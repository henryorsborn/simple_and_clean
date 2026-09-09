"""Smoke tests for the doctor subcommand.

Runs against the scaffolded services in sample-scaffolds/ — exercises the
real checks (file presence, Dockerfile multi-stage, USER directive,
Azure overlay files) end-to-end.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from servicectl.doctor import (
    DoctorReport,
    render_json,
    render_text,
    run_checks,
)


# Real scaffolded services — point at one of the Azure-deployed demos.
SAMPLE_AZURE_SERVICE = (
    Path("C:/Users/henry/source/repos/simple_and_clean_test_samples")
    / "sample-scaffolds"
    / "surfside_icecream_rewards"
    / "surfside_icecream_rewards"
)
SAMPLE_LOCAL_SERVICE = (
    Path("C:/Users/henry/source/repos/simple_and_clean_test_samples")
    / "sample-scaffolds"
    / "surfside_icecream_rewards"
    / "surfside_icecream_rewards"
)


def test_azure_service_passes_baseline_checks():
    """A freshly scaffolded Azure-deployed service should pass all hard checks."""
    if not SAMPLE_AZURE_SERVICE.exists():
        pass  # sample not present, skipping
    report = run_checks(SAMPLE_AZURE_SERVICE)
    # No errors on a fresh scaffold (warnings/info may be present).
    assert not report.has_errors, (
        f"Expected no errors on fresh Azure scaffold, got: "
        f"{[(c.name, c.message) for c in report.checks if not c.passed and c.severity == 'error']}"
    )
    assert report.deploy_target == "azure"


def test_report_summary_includes_counts():
    """The render functions should include a summary line."""
    if not SAMPLE_AZURE_SERVICE.exists():
        pass  # sample not present, skipping
    report = run_checks(SAMPLE_AZURE_SERVICE)
    text = render_text(report)
    assert "summary:" in text
    assert "passed" in text


def test_json_output_is_valid():
    """--json should produce parseable JSON with the expected keys."""
    if not SAMPLE_AZURE_SERVICE.exists():
        pass  # sample not present, skipping
    report = run_checks(SAMPLE_AZURE_SERVICE)
    out = json.loads(render_json(report))
    assert "path" in out
    assert "deploy_target" in out
    assert "exit_code" in out
    assert "summary" in out
    assert "checks" in out
    assert isinstance(out["checks"], list)


def test_missing_dockerfile_is_error():
    """A directory without a Dockerfile should produce an error-level check."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Create the minimum to avoid being a totally empty dir, but no Dockerfile.
        (tmp_path / "README.md").write_text("# test\n")
        (tmp_path / ".gitleaks.toml").write_text("title = \"empty\"\n")
        report = run_checks(tmp_path)
        dockerfile_checks = [c for c in report.checks if c.name == "file:Dockerfile"]
        assert len(dockerfile_checks) == 1
        assert not dockerfile_checks[0].passed
        assert dockerfile_checks[0].severity == "error"


def test_single_stage_dockerfile_is_error():
    """A Dockerfile with only one FROM instruction should fail multi-stage check."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text(
            "FROM python:3.12-slim\n"
            "WORKDIR /app\n"
            "COPY . .\n"
            "CMD [\"python\", \"app.py\"]\n"
        )
        report = run_checks(tmp_path)
        ms_checks = [c for c in report.checks if c.name == "dockerfile:multi-stage"]
        assert len(ms_checks) == 1
        assert not ms_checks[0].passed
        assert ms_checks[0].severity == "error"


def test_root_user_dockerfile_is_warning():
    """A Dockerfile that runs as root should fail the non-root-user check."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "Dockerfile").write_text(
            "FROM python:3.12-slim AS builder\n"
            "FROM python:3.12-slim\n"
            "WORKDIR /app\n"
            "COPY . .\n"
            "USER root\n"
            "CMD [\"python\", \"app.py\"]\n"
        )
        report = run_checks(tmp_path)
        user_checks = [c for c in report.checks if c.name == "dockerfile:non-root-user"]
        assert len(user_checks) == 1
        assert not user_checks[0].passed
        assert user_checks[0].severity == "warn"


def test_multistage_nonroot_dockerfile_passes():
    """A well-formed multi-stage Dockerfile should pass both Docker checks."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "Dockerfile").write_text(
            "FROM python:3.12-slim AS builder\n"
            "WORKDIR /app\n"
            "COPY . .\n"
            "RUN pip install --user /app\n"
            "\n"
            "FROM python:3.12-slim\n"
            "WORKDIR /app\n"
            "COPY --from=builder /root/.local /root/.local\n"
            "USER appuser\n"
            "CMD [\"python\", \"app.py\"]\n"
        )
        report = run_checks(tmp_path)
        for name in ("dockerfile:multi-stage", "dockerfile:non-root-user"):
            check = next((c for c in report.checks if c.name == name), None)
            assert check is not None, f"missing check: {name}"
            assert check.passed, f"check {name} should pass: {check.message}"


def test_exit_code_for_clean_report():
    """A report with no failures should have exit_code 0."""
    report = DoctorReport(path="/tmp/fake", checks=[])
    assert report.exit_code() == 0
    assert not report.has_errors
    assert not report.has_warnings


def test_exit_code_for_errors():
    """A report with errors should have exit_code 2."""
    report = DoctorReport(
        path="/tmp/fake",
        checks=[
            # One passed, one errored.
        ],
    )
    from servicectl.doctor import Check, SEVERITY_ERROR
    report.checks.append(Check(
        name="test:foo",
        severity=SEVERITY_ERROR,
        passed=False,
        message="broken",
    ))
    report.checks.append(Check(
        name="test:bar",
        severity=SEVERITY_ERROR,
        passed=True,
        message="ok",
    ))
    assert report.exit_code() == 2
    assert report.has_errors


def test_pause_skips_when_not_tty():
    """The --pause logic should only engage when stdin AND stdout are TTYs.

    When invoked from a piped/captured context (CI, test harness), the
    pause prompt must be skipped so the command doesn't hang.
    """
    import subprocess
    # `python -m servicectl doctor --pause` with stdin closed should exit
    # cleanly without waiting for a keypress.
    result = subprocess.run(
        ["python", "-m", "servicectl", "doctor", ".", "--pause"],
        cwd=str(Path(__file__).resolve().parent.parent),
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=15,
    )
    # Should exit with 0 or 1 (warnings) since the servicectl repo itself
    # isn't a scaffolded service. The point: it didn't hang waiting for input.
    assert result.returncode in (0, 1, 2)
    # The 'Press any key' message should NOT appear in piped output.
    assert "Press any key" not in result.stdout


if __name__ == "__main__":
    # Allow running without pytest: `python tests/test_doctor.py`
    failures = 0
    for name in dir():
        if name.startswith("test_") and callable(locals()[name]):
            try:
                locals()[name]()
                print(f"PASS  {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL  {name}: {e}")
            except Exception as e:
                failures += 1
                print(f"ERROR {name}: {type(e).__name__}: {e}")
    if failures:
        sys.exit(1)
    print(f"\nAll tests passed.")

