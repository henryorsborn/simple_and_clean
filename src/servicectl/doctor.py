"""Doctor — validate an existing scaffolded service against servicectl standards.

Catches drift from the generated baseline: missing files, single-stage
Dockerfiles, removed gitleaks config, dropped bicepparam files, etc.

Designed to run locally as a one-shot check, or in CI as a gate.

Usage:
    servicectl doctor [PATH]
    servicectl doctor my-service --strict
    servicectl doctor my-service --json
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable


# Severity levels: error = must-fix, warn = should-fix, info = nice-to-have.
SEVERITY_ERROR = "error"
SEVERITY_WARN = "warn"
SEVERITY_INFO = "info"

# Exit codes: 0 = clean, 1 = warnings only, 2 = errors.
EXIT_OK = 0
EXIT_WARN = 1
EXIT_ERROR = 2


@dataclass
class Check:
    """One rule result. `passed=False` means the rule fired."""
    name: str
    severity: str
    passed: bool
    message: str
    fix: str = ""  # Short hint on how to remediate if not passed.


@dataclass
class DoctorReport:
    """Aggregate of all checks against one service directory."""
    path: str
    checks: list[Check] = field(default_factory=list)
    deploy_target: str = "unknown"  # Best-effort inference from files present.

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks if c.severity == SEVERITY_ERROR)

    @property
    def has_warnings(self) -> bool:
        return any(not c.passed for c in self.checks if c.severity == SEVERITY_WARN)

    @property
    def has_errors(self) -> bool:
        return any(not c.passed for c in self.checks if c.severity == SEVERITY_ERROR)

    def exit_code(self) -> int:
        if self.has_errors:
            return EXIT_ERROR
        if self.has_warnings:
            return EXIT_WARN
        return EXIT_OK

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "deploy_target": self.deploy_target,
            "exit_code": self.exit_code(),
            "summary": {
                "passed": sum(1 for c in self.checks if c.passed),
                "errors": sum(1 for c in self.checks if not c.passed and c.severity == SEVERITY_ERROR),
                "warnings": sum(1 for c in self.checks if not c.passed and c.severity == SEVERITY_WARN),
                "info": sum(1 for c in self.checks if not c.passed and c.severity == SEVERITY_INFO),
            },
            "checks": [asdict(c) for c in self.checks],
        }


def _infer_deploy_target(path: Path) -> str:
    """Best-effort guess of which deploy target the service was scaffolded with."""
    if (path / "infra" / "main.bicep").exists():
        return "azure"
    if (path / "Dockerfile").exists():
        return "local"
    return "unknown"


def _file_text(path: Path) -> str:
    """Read a file as text, returning empty string on any failure."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _dockerfile_is_multistage(path: Path) -> tuple[bool, str]:
    """A multi-stage Dockerfile has more than one `FROM` instruction."""
    if not path.exists():
        return False, "Dockerfile missing"
    text = _file_text(path)
    from_count = len(re.findall(r"^\s*FROM\s+", text, flags=re.MULTILINE | re.IGNORECASE))
    if from_count < 2:
        return False, f"only {from_count} FROM instruction(s); need ≥2 for multi-stage build"
    return True, f"{from_count} FROM instructions (multi-stage confirmed)"


def _dockerfile_runs_nonroot(path: Path) -> tuple[bool, str]:
    """A secure-by-default Dockerfile sets USER to a non-root user."""
    if not path.exists():
        return False, "Dockerfile missing"
    text = _file_text(path)
    if not re.search(r"^\s*USER\s+\S+", text, flags=re.MULTILINE | re.IGNORECASE):
        return False, "no USER directive — container will run as root"
    if re.search(r"^\s*USER\s+root\s*$", text, flags=re.MULTILINE | re.IGNORECASE):
        return False, "USER is set to 'root' — should be a non-root user"
    return True, "USER directive present and non-root"


def _coverage_threshold(path: Path) -> tuple[bool, int | None, str]:
    """Try to read the coverage threshold from the generated project.

    Where we look depends on the template, because each tool stack has a
    different idiomatic place to declare a coverage gate:

      - python-flask:  `pyproject.toml` -> `tool.pytest.ini_options.addopts`
                       containing `--cov-fail-under=NN` (set via {{ coverage_threshold }}).
      - node-express:  `package.json` -> `jest.coverageThreshold.global.lines`
                       (set via {{ coverage_threshold }}).
      - dotnet-webapi: dotnet has no project-level threshold config; the gate
                       lives in the CI workflow as `/p:Threshold=NN`.

    Returns (found, value, message).
    """
    pyproject = path / "pyproject.toml"
    if pyproject.exists():
        text = _file_text(pyproject)
        m = re.search(r"--cov-fail-under=(\d+)", text)
        if m:
            return True, int(m.group(1)), f"coverage threshold = {m.group(1)}% (from pyproject.toml)"

    pkg_json = path / "package.json"
    if pkg_json.exists():
        try:
            import json as _json
            data = _json.loads(_file_text(pkg_json))
            threshold = (
                data.get("jest", {})
                    .get("coverageThreshold", {})
                    .get("global", {})
                    .get("lines")
            )
            if isinstance(threshold, (int, float)):
                return True, int(threshold), f"coverage threshold = {int(threshold)}% (from package.json)"
        except (ValueError, KeyError):
            pass

    # Fallback: look in the CI workflow. This is the only place dotnet-webapi
    # stores the gate (via `/p:Threshold=NN`).
    candidates = [
        path / ".github" / "workflows" / "ci.yml",
        path / "azure-pipelines.yml",
    ]
    patterns = [
        r"coverage[_-]?threshold[:\s=]+(\d+)",
        r"--cov-fail-under=(\d+)",
        r"--coverage=(\d+)",
        r"/p:Threshold=(\d+)",
        r"--code-coverage[_-]?(?:threshold|minimum)?[:\s=]+(\d+)",
    ]
    for c in candidates:
        if not c.exists():
            continue
        text = _file_text(c)
        for p in patterns:
            m = re.search(p, text, flags=re.IGNORECASE)
            if m:
                return True, int(m.group(1)), f"coverage threshold = {m.group(1)}% (from {c.name})"
    return False, None, "no coverage threshold detected (checked pyproject.toml, package.json, CI workflow)"


def run_checks(service_path: Path) -> DoctorReport:
    """Run all doctor checks against a service directory."""
    report = DoctorReport(
        path=str(service_path.resolve()),
        deploy_target=_infer_deploy_target(service_path),
    )

    # Always-required files.
    required_files = [
        ("Dockerfile", "Dockerfile missing", "rerun `servicectl init` to regenerate"),
        (".gitleaks.toml", "gitleaks baseline missing", "add a `.gitleaks.toml` to enable secrets scanning in CI"),
        ("docker-compose.dev.yml", "local dev compose missing", "add a `docker-compose.dev.yml` for one-command local dev"),
        (".env.example", "env example missing", "add a `.env.example` listing required environment variables"),
        ("README.md", "README missing", "add a README.md describing how to run/test/deploy the service"),
    ]
    for rel, msg, fix in required_files:
        p = service_path / rel
        report.checks.append(Check(
            name=f"file:{rel}",
            severity=SEVERITY_ERROR if rel == "Dockerfile" else SEVERITY_WARN,
            passed=p.exists(),
            message="present" if p.exists() else msg,
            fix="" if p.exists() else fix,
        ))

    # Dockerfile quality.
    df = service_path / "Dockerfile"
    is_ms, ms_msg = _dockerfile_is_multistage(df)
    report.checks.append(Check(
        name="dockerfile:multi-stage",
        severity=SEVERITY_ERROR,
        passed=is_ms,
        message=ms_msg,
        fix="convert to multi-stage: separate build stage from runtime stage" if not is_ms else "",
    ))
    nr, nr_msg = _dockerfile_runs_nonroot(df)
    report.checks.append(Check(
        name="dockerfile:non-root-user",
        severity=SEVERITY_WARN,
        passed=nr,
        message=nr_msg,
        fix="add `USER <non-root-user>` to the runtime stage" if not nr else "",
    ))

    # CI: at least one of the supported CI configs should exist.
    has_gh = (service_path / ".github" / "workflows" / "ci.yml").exists()
    has_az = (service_path / "azure-pipelines.yml").exists()
    if not (has_gh or has_az):
        report.checks.append(Check(
            name="ci:any-config",
            severity=SEVERITY_ERROR,
            passed=False,
            message="no CI configuration found (.github/workflows/ci.yml or azure-pipelines.yml)",
            fix="rerun `servicectl init` with --ci=github-actions or --ci=azure-devops",
        ))
    else:
        report.checks.append(Check(
            name="ci:any-config",
            severity=SEVERITY_INFO,
            passed=True,
            message="github-actions" if has_gh else "azure-devops",
        ))

    # Devcontainer.
    devcontainer = service_path / ".devcontainer" / "devcontainer.json"
    report.checks.append(Check(
        name="devcontainer:present",
        severity=SEVERITY_INFO,
        passed=devcontainer.exists(),
        message="present" if devcontainer.exists() else "missing (optional but recommended)",
        fix="" if devcontainer.exists() else "add `.devcontainer/devcontainer.json` for VS Code remote dev",
    ))

    # Source + tests non-empty.
    src = service_path / "src"
    tests = service_path / "tests"
    src_ok = src.exists() and any(src.rglob("*"))
    tests_ok = tests.exists() and any(tests.rglob("*"))
    report.checks.append(Check(
        name="src:non-empty",
        severity=SEVERITY_WARN,
        passed=src_ok,
        message="present with content" if src_ok else "src/ missing or empty",
        fix="" if src_ok else "add a `src/` directory with your service code",
    ))
    report.checks.append(Check(
        name="tests:non-empty",
        severity=SEVERITY_WARN,
        passed=tests_ok,
        message="present with content" if tests_ok else "tests/ missing or empty",
        fix="" if tests_ok else "add a `tests/` directory with at least one test",
    ))

    # Coverage threshold (only meaningful if a CI workflow exists).
    cov_ok, cov_val, cov_msg = _coverage_threshold(service_path)
    report.checks.append(Check(
        name="ci:coverage-threshold",
        severity=SEVERITY_INFO,
        passed=cov_ok,
        message=cov_msg,
        fix="" if cov_ok else "no `coverage_threshold:` value found in pyproject.toml / package.json / CI workflow — servicectl defaults to 80%",
    ))

    # Azure overlay (only if infra/main.bicep exists — i.e. was scaffolded with --deploy=azure).
    if report.deploy_target == "azure":
        required_azure = [
            ("infra/main.bicep", "main Bicep file missing", "regenerate with --deploy=azure"),
            ("infra/dev.bicepparam", "dev bicepparam missing", "regenerate with --deploy=azure"),
            ("infra/staging.bicepparam", "staging bicepparam missing", "regenerate with --deploy=azure"),
            ("infra/prod.bicepparam", "prod bicepparam missing", "regenerate with --deploy=azure"),
            ("deploy.yml", "CD workflow missing", "regenerate with --deploy=azure"),
        ]
        for rel, msg, fix in required_azure:
            p = service_path / rel
            report.checks.append(Check(
                name=f"azure:{rel}",
                severity=SEVERITY_ERROR,
                passed=p.exists(),
                message="present" if p.exists() else msg,
                fix="" if p.exists() else fix,
            ))

    return report


def render_text(report: DoctorReport) -> str:
    """Render the report as a human-readable text block."""
    lines = []
    sym = {True: "✓", False: "✗"}
    color = {True: "green", False: "red"}

    header = f"doctor: {report.path}"
    if report.deploy_target != "unknown":
        header += f"  (deploy: {report.deploy_target})"
    lines.append(header)
    lines.append("=" * len(header))

    if not report.checks:
        lines.append("  (no checks ran)")
        return "\n".join(lines)

    # Group by severity for readable output.
    for severity in (SEVERITY_ERROR, SEVERITY_WARN, SEVERITY_INFO):
        items = [c for c in report.checks if c.severity == severity]
        if not items:
            continue
        lines.append("")
        lines.append(f"{severity.upper()}S:")
        for c in items:
            mark = sym[c.passed]
            status = "PASS" if c.passed else "FAIL"
            line = f"  [{mark}] {status:<4}  {c.name}"
            if not c.passed:
                line += f" — {c.message}"
                if c.fix:
                    line += f"\n          fix: {c.fix}"
            else:
                line += f" — {c.message}"
            lines.append(line)

    summary = (
        f"\nsummary: {sum(1 for c in report.checks if c.passed)}/{len(report.checks)} passed; "
        f"{sum(1 for c in report.checks if not c.passed and c.severity == SEVERITY_ERROR)} errors, "
        f"{sum(1 for c in report.checks if not c.passed and c.severity == SEVERITY_WARN)} warnings, "
        f"{sum(1 for c in report.checks if not c.passed and c.severity == SEVERITY_INFO)} info"
    )
    lines.append(summary)
    return "\n".join(lines)


def render_json(report: DoctorReport) -> str:
    return json.dumps(report.to_dict(), indent=2)


__all__ = [
    "DoctorReport",
    "Check",
    "run_checks",
    "render_text",
    "render_json",
    "EXIT_OK",
    "EXIT_WARN",
    "EXIT_ERROR",
]
