"""Smoke tests for servicectl generator + template registry.

Run with: pytest tests/ (or just `python tests/test_smoke.py`).
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

# Make the installed package importable when running this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from servicectl.generator import ServiceGenerator, ScaffoldError  # noqa: E402
from servicectl.templates import list_templates  # noqa: E402


def _scaffold(tmp: Path, name: str, template: str, **overrides) -> Path:
    gen = ServiceGenerator(
        name=name,
        template=template,
        ci_provider=overrides.get("ci_provider", "github-actions"),
        deploy_target=overrides.get("deploy_target", "local"),
        azure_region=overrides.get("azure_region", "eastus"),
        coverage_threshold=overrides.get("coverage_threshold", 80),
        registry=overrides.get("registry", "ghcr"),
        output_dir=tmp,
        with_git=False,
        with_readme=True,
    )
    return gen.run()


def test_all_templates_registered():
    expected = {"node-express", "python-flask", "dotnet-webapi"}
    assert set(list_templates()) == expected


def test_node_express_scaffolds():
    with tempfile.TemporaryDirectory() as td:
        target = _scaffold(Path(td), "demo-node", "node-express")
        assert (target / "package.json").exists()
        assert (target / "Dockerfile").exists()
        assert (target / "docker-compose.dev.yml").exists()
        assert (target / ".github" / "workflows" / "ci.yml").exists()
        assert (target / "azure-pipelines.yml").exists()
        assert (target / ".env.example").exists()
        assert (target / "README.md").exists()
        pkg = (target / "package.json").read_text()
        assert '"name": "demo-node"' in pkg
        assert '"lines": 80' in pkg


def test_python_flask_scaffolds_with_custom_coverage():
    with tempfile.TemporaryDirectory() as td:
        target = _scaffold(Path(td), "demo-py", "python-flask", coverage_threshold=90)
        pyproject = (target / "pyproject.toml").read_text()
        assert "--cov-fail-under=90" in pyproject
        assert 'name = "demo-py"' in pyproject


def test_dotnet_pascal_cases_filename():
    with tempfile.TemporaryDirectory() as td:
        target = _scaffold(Path(td), "demo-dotnet", "dotnet-webapi")
        # Jinja-substituted filenames should land as PascalCase.
        assert (target / "DemoDotnet.csproj").exists()
        assert (target / "tests" / "DemoDotnet.Tests" / "DemoDotnet.Tests.csproj").exists()
        assert (target / "tests" / "DemoDotnet.Tests" / "UnitTest1.cs").exists()


def test_dashed_name_renders_correctly():
    with tempfile.TemporaryDirectory() as td:
        target = _scaffold(Path(td), "my-cool.api", "python-flask", ci_provider="azure-devops")
        # Filenames should be exactly the supplied name.
        assert target.name == "my-cool.api"
        # ADO pipeline should be generated and contain the name.
        yml = (target / "azure-pipelines.yml").read_text()
        assert "my-cool.api" in yml
        # ADO pipeline should NOT have a GH-Actions-only file extension leak.
        assert ".github" not in yml


def test_duplicate_directory_is_rejected():
    with tempfile.TemporaryDirectory() as td:
        _scaffold(Path(td), "dup-test", "node-express")
        try:
            _scaffold(Path(td), "dup-test", "node-express")
        except ScaffoldError as e:
            assert "already exists" in str(e)
        else:
            raise AssertionError("expected ScaffoldError on duplicate directory")


def test_invalid_name_is_rejected():
    with tempfile.TemporaryDirectory() as td:
        try:
            _scaffold(Path(td), "bad/name", "node-express")
        except ScaffoldError as e:
            assert "invalid character" in str(e)
        else:
            raise AssertionError("expected ScaffoldError on invalid name")


def test_azure_overlay_emits_infra_files():
    with tempfile.TemporaryDirectory() as td:
        target = _scaffold(
            Path(td),
            "demo-azure",
            "python-flask",
            deploy_target="azure",
            azure_region="westus2",
        )
        assert (target / "infra" / "main.bicep").exists()
        assert (target / "infra" / "dev.bicepparam").exists()
        assert (target / "infra" / "staging.bicepparam").exists()
        assert (target / "infra" / "prod.bicepparam").exists()
        assert (target / "deploy.yml").exists()
        # Make sure Jinja placeholders didn't leak through.
        for p in [target / "infra" / "main.bicep", target / "infra" / "dev.bicepparam"]:
            content = p.read_text()
            assert "{{" not in content, f"unrendered Jinja in {p}"
        # Substitutions should reflect service name + region.
        bicep = (target / "infra" / "main.bicep").read_text()
        assert "demo-azure" in bicep
        assert "westus2" in bicep
        params = (target / "infra" / "dev.bicepparam").read_text()
        assert "demo-azure" in params
        assert "westus2" in params


def test_azure_overlay_skipped_for_local():
    with tempfile.TemporaryDirectory() as td:
        target = _scaffold(Path(td), "demo-local", "node-express")
        assert not (target / "infra").exists()
        assert not (target / "deploy.yml").exists()


def test_azure_bicepparam_no_secure_decorator():
    """Regression: Bicepparam files do not support decorators.

    The BCP130 error breaks `bicep build-params` if `@secure()` is used inside
    a .bicepparam file. The @secure() decorator belongs on the corresponding
    param in main.bicep, not in the bicepparam file.
    """
    with tempfile.TemporaryDirectory() as td:
        target = _scaffold(
            Path(td),
            "demo-bicep",
            "python-flask",
            deploy_target="azure",
            azure_region="eastus",
        )
        for env in ("dev", "staging", "prod"):
            content = (target / "infra" / f"{env}.bicepparam").read_text()
            assert "@secure" not in content, (
                f"{env}.bicepparam contains @secure() decorator; "
                "bicepparam files do not support decorators (BCP130)"
            )


if __name__ == "__main__":
    # Allow running without pytest: `python tests/test_smoke.py`
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
