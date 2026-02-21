from pathlib import Path
import unittest


class WindowsReleaseWorkflowTests(unittest.TestCase):
    def test_windows_release_workflow_exists_and_uses_v_tag(self) -> None:
        workflow = Path(".github/workflows/windows-release.yml")
        self.assertTrue(workflow.exists(), "expected Windows release workflow file to exist")

        content = workflow.read_text(encoding="utf-8")
        self.assertIn("push:", content)
        self.assertIn("tags:", content)
        self.assertIn("- 'v*'", content)
        self.assertIn("runs-on: windows-latest", content)
        self.assertIn("softprops/action-gh-release", content)
        self.assertIn("shell: bash", content)
        self.assertIn("./scripts/release_windows.spec", content)


if __name__ == "__main__":
    unittest.main()
