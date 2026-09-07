---
name: compare-ci-cd-options
description: Compare supported CI/CD options in this repository. Use this when a user wants the differences, trade-offs, or advantages of GitHub Actions vs Drone, Docker vs language-native builds, or Kubernetes vs SSH host deployments.
---

# Compare CI/CD Options

Use this skill when the user is still deciding which tooling to use.

## Steps

1. Run the repository tool with:

   ```bash
   python ./cicd_setup.py --list-options
   ```

2. Summarize the supported choices under the three categories:
   - CI / integration
   - Build
   - Deployment
3. Explain the main advantages and trade-offs for each option.
4. Recommend a simple starting combination based on the user's team size,
   hosting model, and operational maturity.

## Rules

- Keep comparisons grounded in the options shipped by this repository.
- Present both a lightweight path and a scalable path when possible.
- If the user has already chosen a stack, switch to the `setup-basic-ci-cd`
  skill instead of continuing generic comparison.
