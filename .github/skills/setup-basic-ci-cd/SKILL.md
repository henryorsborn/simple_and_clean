---
name: setup-basic-ci-cd
description: Guide for setting up a basic CI/CD recommendation. Use this when asked to compare CI/CD tooling, choose between GitHub Actions and Drone, choose between Docker and language-native builds, or choose between Kubernetes and lightweight host deployments.
---

# Setup a Basic CI/CD System

Use this skill when a user wants an agent to help choose and set up a starter
CI/CD workflow for a repository.

## When to use

- The user wants a lightweight CI/CD starting point.
- The user wants help choosing between **GitHub Actions** and **Drone**.
- The user wants help choosing between **Docker** builds and **language-native**
  builds.
- The user wants help choosing between **Kubernetes** and **SSH host**
  deployments.

## Steps

1. Gather the user's preferences for CI, build, and deployment tooling.
2. If the user needs help deciding, run the CLI with `--list-options` and use
   the built-in summaries, advantages, and trade-offs to explain the choices.
3. Generate a recommendation with one of these entry points:
   - Bash: `./setup-cicd.sh`
   - PowerShell: `.\setup-cicd.ps1`
   - CMD: `.\setup-cicd.cmd`
   - Direct Python: `./cicd_setup.py`
4. Prefer non-interactive execution when the user's selections are already
   known, for example:

   ```bash
   python ./cicd_setup.py \
     --ci drone \
     --build docker \
     --deploy kubernetes \
     --non-interactive
   ```

5. Share the generated plan and translate it into the repository's actual CI/CD
   files only after confirming the stack the user wants.

## Rules

- Do not assume the user wants the heaviest platform by default.
- Always explain both advantages and trade-offs before recommending a stack.
- Keep the first implementation minimal: focus on lint, build, test, and one
  deployment path.
- Prefer the repository CLI output as the source of truth for supported options.
