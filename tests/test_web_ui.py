import unittest
from pathlib import Path


HTML = (Path(__file__).resolve().parents[1] / "assets" / "api-app" / "index.html").read_text(encoding="utf-8")


class WebUiStructureTests(unittest.TestCase):
    def test_rich_text_is_sanitized_before_rendering(self):
        self.assertIn("function markdownToHtml", HTML)
        self.assertIn("function sanitizedRichFragment", HTML)
        self.assertIn("const blocked = new Set", HTML)
        self.assertIn("renderRichText(bubble", HTML)

    def test_file_list_and_thinking_summary_are_present(self):
        self.assertIn('id="toggle-corpus-list"', HTML)
        self.assertIn('id="corpus-list"', HTML)
        self.assertIn("思考了 ${", HTML)
        self.assertIn("message.reasoning.summary", HTML)

    def test_reference_display_uses_unique_file_names_without_locators(self):
        self.assertIn("参考文献：${summary.local.map(item => item.name || item.path)", HTML)
        self.assertNotIn("item.locator", HTML)


if __name__ == "__main__":
    unittest.main()
