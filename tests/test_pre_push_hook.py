"""Tests for the human approval push checkpoint."""

from pathlib import Path
import subprocess
import unittest


class TestPrePushHook(unittest.TestCase):
    """Verify pushes require explicit human approval."""

    def test_pre_push_hook_blocks_a_declined_push(self) -> None:
        """Verify declining the checkpoint stops the push."""
        hook = Path(__file__).parents[1] / ".githooks" / "pre-push"
        result = subprocess.run(
            ["script", "-qefc", f"{hook} origin example", "/dev/null"],
            input="no\n",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Push blocked: human approval is required.", result.stdout)


if __name__ == "__main__":
    unittest.main()
