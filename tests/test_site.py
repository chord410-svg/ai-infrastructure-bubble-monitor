import json
import unittest
from pathlib import Path


class SiteTests(unittest.TestCase):
    def test_required_sections_and_accessibility_hooks_exist(self):
        html = Path("site/index.html").read_text(encoding="utf-8")
        for marker in ("state-title","structural-score","trigger-score","confidence","indicator-list","missing-evidence","last-updated","source-list"):
            self.assertIn('id="{}"'.format(marker), html)
        self.assertIn("<details", html)
        self.assertIn("<noscript", html)
        self.assertIn('<meta charset="utf-8">', html)
        self.assertIn('class="skip-link"', html)
        self.assertIn('aria-label="核心監測結果"', html)
        self.assertIn('role="status"', html)
        self.assertTrue(Path("site/favicon.svg").exists())

    def test_mobile_breakpoint_and_native_expand_controls_exist(self):
        html = Path("site/index.html").read_text(encoding="utf-8")
        css = Path("site/styles.css").read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 720px)", css)
        self.assertGreaterEqual(html.count("<details"), 4)
        self.assertGreaterEqual(html.count("<summary"), 4)

    def test_site_uses_local_assets_and_no_fabricated_scores(self):
        html = Path("site/index.html").read_text(encoding="utf-8")
        self.assertNotIn("https://cdn.", html)
        self.assertNotIn("64 /100", html)
        self.assertNotIn("27 /100", html)
        self.assertIn("正式資料尚未接入", html)

    def test_javascript_handles_stale_and_fetch_failures(self):
        script = Path("site/app.js").read_text(encoding="utf-8")
        self.assertIn("isStale", script)
        self.assertIn("資料載入失敗", script)
        self.assertIn("資料過期，暫停判讀", script)
        self.assertIn('cache: "no-store"', script)
        self.assertIn("textContent", script)

    def test_published_data_is_honest_and_parseable(self):
        packet = json.loads(Path("site/data/latest.json").read_text(encoding="utf-8"))
        from src.validate import validate_packet
        validate_packet(packet)
        if packet["structural_pressure"] is None or packet["financial_break_trigger"] is None:
            self.assertEqual(packet["state"], "INSUFFICIENT_EVIDENCE")
        else:
            self.assertNotEqual(packet["state"], "INSUFFICIENT_EVIDENCE")

    def test_method_link_is_not_a_placeholder_repository(self):
        html = Path("site/index.html").read_text(encoding="utf-8")
        self.assertNotIn('href="https://github.com/"', html)


if __name__ == "__main__":
    unittest.main()
