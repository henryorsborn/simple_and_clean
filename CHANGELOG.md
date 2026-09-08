# Changelog

All notable changes to `servicectl` are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-09-07

### Added
- Initial release.
- Three service templates: `node-express`, `python-flask`, `dotnet-webapi`.
- Two CI providers: GitHub Actions and Azure DevOps.
- One deploy target: `azure` (Azure App Service Linux + ACR + Postgres Flexible Server, Bicep).
- Placeholder for `azure-container-apps` deploy target (CLI Choice + hint only).
- Flags for `--template`, `--ci`, `--deploy`, `--azure-region`, `--coverage`,
  `--registry`, `--output-dir`, `--no-git`, `--no-readme`.
- Filename Jinja substitution (so `dotnet-webapi` can produce
  `MyService.csproj` from `{{ service_name_pascal }}.csproj`).
- Jinja `{% raw %}` blocks for GitHub Actions `${{ }}` expressions.
- Windows console UTF-8 fix for Rich Unicode glyphs.
- Smoke test suite: 9 tests covering template registration, all three
  templates, dashed/dotted names, dotnet PascalCase filenames, custom
  coverage, error paths, and the Azure overlay emit/skip behavior.
- GitHub Actions CI workflow for `servicectl` itself: tests across Python
  3.10-3.13 on Ubuntu and Windows, plus Bicep validation in CI.
