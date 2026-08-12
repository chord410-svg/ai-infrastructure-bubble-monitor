import unittest
from pathlib import Path


class DocumentationTests(unittest.TestCase):
    def test_readme_covers_operation_limits_sources_and_extension(self):
        text = Path("README.md").read_text(encoding="utf-8")
        for heading in (
            "## What it measures", "## What it does not measure", "## Weekly operation",
            "## Manual recovery", "## Add an indicator", "## Data sources", "## Disclaimer",
        ):
            self.assertIn(heading, text)
        self.assertIn("SEC_USER_AGENT", text)
        self.assertIn("GitHub Pages", text)


if __name__ == "__main__":
    unittest.main()
