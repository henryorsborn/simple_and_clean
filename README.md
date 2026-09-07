# simple_and_clean

Tooling to create a simple CI/CD setup for an application.

## What it does

This repository provides a small starter CLI that helps a user choose a basic
CI/CD stack for:

- integration / CI
- builds
- deployments

The tool explains the trade-offs and advantages of each option before producing
a recommended plan. Current guided options include:

- **GitHub Actions** and **Drone** for CI / integration
- **Docker** and **language-native builds** for build tooling
- **Kubernetes** and **SSH host deployments** for deployment tooling

## CLI entry points

- Bash: `./setup-cicd.sh`
- CMD: `.\setup-cicd.cmd`
- PowerShell: `.\setup-cicd.ps1`

All three entry points use the same Python-based planner so they stay in sync.

## Usage

List the available options:

```bash
python ./cicd_setup.py --list-options
```

Create a plan non-interactively:

```bash
python ./cicd_setup.py \
  --ci drone \
  --build docker \
  --deploy kubernetes
```

Run the interactive Bash wrapper:

```bash
./setup-cicd.sh
```

Save the plan to a file:

```bash
python ./cicd_setup.py \
  --ci github-actions \
  --build language-native \
  --deploy ssh-host \
  --output /tmp/basic-cicd-plan.md
```

## Agent skills

Repository skills are included in:

- `.github/skills/setup-basic-ci-cd/SKILL.md`
- `.github/skills/compare-ci-cd-options/SKILL.md`

These skills help agents compare supported toolchains and use the CLI to produce
an initial CI/CD recommendation.
