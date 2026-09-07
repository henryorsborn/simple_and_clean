#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


CATALOG = {
    "ci": {
        "label": "Integration / CI",
        "options": {
            "github-actions": {
                "title": "GitHub Actions",
                "summary": "Integrated CI that works especially well when your code already lives on GitHub.",
                "advantages": [
                    "Native GitHub pull request and branch integration",
                    "Large marketplace of reusable actions",
                    "Simple path for small teams starting from zero",
                ],
                "tradeoffs": [
                    "Tied closely to GitHub as the source platform",
                    "Complex workflows can become verbose YAML",
                ],
            },
            "drone": {
                "title": "Drone",
                "summary": "Container-first CI for teams that want a portable pipeline engine they can host themselves.",
                "advantages": [
                    "Good fit for self-hosted and container-centric workflows",
                    "Portable pipeline model across environments",
                    "Clear separation between source hosting and CI execution",
                ],
                "tradeoffs": [
                    "Requires additional platform setup and maintenance",
                    "Smaller plugin ecosystem than GitHub Actions",
                ],
            },
        },
    },
    "build": {
        "label": "Build",
        "options": {
            "docker": {
                "title": "Docker",
                "summary": "Package the application into a repeatable container image for CI, testing, and deployment.",
                "advantages": [
                    "Consistent build output across developer, CI, and deployment environments",
                    "Pairs well with Kubernetes and container registries",
                    "Simplifies dependency management inside builds",
                ],
                "tradeoffs": [
                    "Adds container image maintenance and registry concerns",
                    "Can slow feedback loops for very small projects",
                ],
            },
            "language-native": {
                "title": "Language-native builds",
                "summary": "Use ecosystem tooling such as npm, dotnet, cargo, go, or python build commands directly.",
                "advantages": [
                    "Lower setup cost for simple applications",
                    "Fast feedback when the language toolchain is already established",
                    "Keeps build steps close to the application's native tooling",
                ],
                "tradeoffs": [
                    "Environment drift is more likely without containerization",
                    "Deployment packaging usually needs an extra step later",
                ],
            },
        },
    },
    "deploy": {
        "label": "Deployment",
        "options": {
            "kubernetes": {
                "title": "Kubernetes",
                "summary": "Orchestrated deployments for teams that need scaling, service discovery, and rollout control.",
                "advantages": [
                    "Strong support for scaling, self-healing, and progressive rollout strategies",
                    "Works well for microservices and containerized platforms",
                    "Rich ecosystem for secrets, ingress, and observability",
                ],
                "tradeoffs": [
                    "Operationally heavier than simpler deployment targets",
                    "Requires cluster management and platform expertise",
                ],
            },
            "ssh-host": {
                "title": "SSH host deployments",
                "summary": "Push artifacts or containers to a VM or small server over SSH for a lightweight starting point.",
                "advantages": [
                    "Very small operational footprint",
                    "Good fit for prototypes and small single-service deployments",
                    "Easy to understand and debug end to end",
                ],
                "tradeoffs": [
                    "Less scalable and less standardized than orchestration platforms",
                    "Rollbacks and zero-downtime releases usually need extra scripting",
                ],
            },
        },
    },
}

PROMPT_ORDER = ("ci", "build", "deploy")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Guide a user through choosing a simple CI/CD stack."
    )
    parser.add_argument("--ci", choices=sorted(CATALOG["ci"]["options"].keys()))
    parser.add_argument("--build", choices=sorted(CATALOG["build"]["options"].keys()))
    parser.add_argument(
        "--deploy", choices=sorted(CATALOG["deploy"]["options"].keys())
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional file path to write the generated markdown plan to.",
    )
    parser.add_argument(
        "--list-options",
        action="store_true",
        help="Print supported CI/CD options and exit.",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Fail if any selection is missing instead of prompting.",
    )
    return parser.parse_args()


def option_details(category: str, option_key: str) -> dict[str, object]:
    return CATALOG[category]["options"][option_key]


def render_catalog() -> str:
    lines: list[str] = []
    for category in PROMPT_ORDER:
        definition = CATALOG[category]
        lines.append(f"{definition['label']}:")
        for key, option in definition["options"].items():
            lines.append(f"  - {key}: {option['title']}")
            lines.append(f"    {option['summary']}")
            lines.append(
                f"    Advantages: {', '.join(option['advantages'])}"
            )
            lines.append(
                f"    Trade-offs: {', '.join(option['tradeoffs'])}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def prompt_for_choice(category: str) -> str:
    definition = CATALOG[category]
    options = list(definition["options"].items())

    print(f"\n{definition['label']}")
    print("-" * len(definition["label"]))
    for index, (_, option) in enumerate(options, start=1):
        print(f"{index}. {option['title']}")
        print(f"   {option['summary']}")
        print(f"   Advantages: {', '.join(option['advantages'])}")
        print(f"   Trade-offs: {', '.join(option['tradeoffs'])}")

    while True:
        raw = input(f"Choose {definition['label']} option [1-{len(options)}]: ").strip()
        if raw.isdigit():
            numeric_choice = int(raw)
            if 1 <= numeric_choice <= len(options):
                return options[numeric_choice - 1][0]
        print("Please enter a valid number from the menu.")


def collect_selections(args: argparse.Namespace) -> dict[str, str]:
    selections = {
        "ci": args.ci,
        "build": args.build,
        "deploy": args.deploy,
    }

    missing = [category for category, value in selections.items() if not value]
    if missing and args.non_interactive:
        raise SystemExit(
            "--non-interactive requires --ci, --build, and --deploy to all be set."
        )

    for category in missing:
        selections[category] = prompt_for_choice(category)

    return selections


def recommendation_summary(selections: dict[str, str]) -> str:
    if selections["ci"] == "drone" and selections["deploy"] == "kubernetes":
        return (
            "This stack favors self-hosted control with a container-first path into "
            "orchestrated deployments."
        )
    if selections["ci"] == "github-actions" and selections["deploy"] == "ssh-host":
        return (
            "This stack favors a fast, low-ceremony setup that is easy to adopt for "
            "small repositories and straightforward deployments."
        )
    return (
        "This stack balances simplicity with a clear upgrade path as the application "
        "and team grow."
    )


def render_plan(selections: dict[str, str]) -> str:
    ci = option_details("ci", selections["ci"])
    build = option_details("build", selections["build"])
    deploy = option_details("deploy", selections["deploy"])

    lines = [
        "# Basic CI/CD Recommendation",
        "",
        recommendation_summary(selections),
        "",
        "## Selected stack",
        "",
        f"- **CI / integration:** {ci['title']} (`{selections['ci']}`)",
        f"- **Build:** {build['title']} (`{selections['build']}`)",
        f"- **Deployment:** {deploy['title']} (`{selections['deploy']}`)",
        "",
        "## Why these choices fit",
        "",
        f"### {ci['title']}",
        ci["summary"],
        "",
        f"Advantages: {', '.join(ci['advantages'])}.",
        f"Trade-offs: {', '.join(ci['tradeoffs'])}.",
        "",
        f"### {build['title']}",
        build["summary"],
        "",
        f"Advantages: {', '.join(build['advantages'])}.",
        f"Trade-offs: {', '.join(build['tradeoffs'])}.",
        "",
        f"### {deploy['title']}",
        deploy["summary"],
        "",
        f"Advantages: {', '.join(deploy['advantages'])}.",
        f"Trade-offs: {', '.join(deploy['tradeoffs'])}.",
        "",
        "## Suggested next steps",
        "",
        "1. Create the first pipeline around lint, build, and test steps.",
        "2. Add artifact packaging that matches the selected build tooling.",
        "3. Add environment-specific deployment credentials and rollout checks.",
        "4. Revisit the deployment target once reliability and scale requirements are clearer.",
        "",
    ]
    return "\n".join(lines)


def write_output(plan: str, output_path: Path | None) -> None:
    if output_path is None:
        sys.stdout.write(plan)
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(plan, encoding="utf-8")
    print(f"Wrote CI/CD plan to {output_path}")


def main() -> int:
    args = parse_args()
    if args.list_options:
        sys.stdout.write(render_catalog())
        return 0

    selections = collect_selections(args)
    plan = render_plan(selections)
    write_output(plan, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
