import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "cicd_setup.py"


class CiCdSetupCliTests(unittest.TestCase):
    def run_tool(self, *args, input_text=None):
        return subprocess.run(
            [sys.executable, str(TOOL), *args],
            input=input_text,
            text=True,
            capture_output=True,
            check=True,
        )

    def test_list_options_includes_key_supported_tools(self):
        result = self.run_tool("--list-options")

        self.assertIn("drone", result.stdout)
        self.assertIn("kubernetes", result.stdout)
        self.assertIn("GitHub Actions", result.stdout)

    def test_non_interactive_plan_includes_selected_stack(self):
        result = self.run_tool(
            "--ci",
            "drone",
            "--build",
            "docker",
            "--deploy",
            "kubernetes",
            "--non-interactive",
        )

        self.assertIn("Drone (`drone`)", result.stdout)
        self.assertIn("Docker (`docker`)", result.stdout)
        self.assertIn("Kubernetes (`kubernetes`)", result.stdout)
        self.assertIn("self-hosted control", result.stdout)

    def test_interactive_selection_accepts_numbered_choices(self):
        result = self.run_tool(input_text="2\n1\n2\n")

        self.assertIn("Drone (`drone`)", result.stdout)
        self.assertIn("Docker (`docker`)", result.stdout)
        self.assertIn("SSH host deployments (`ssh-host`)", result.stdout)


if __name__ == "__main__":
    unittest.main()
