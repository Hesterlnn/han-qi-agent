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
        self.assertIn('id="browse-corpus-folder"', HTML)
        self.assertIn('aria-label="选择文献库文件夹"', HTML)
        self.assertNotIn('id="corpus-path"', HTML)
        self.assertNotIn('id="use-corpus-folder"', HTML)
        self.assertNotIn('id="corpus-folder"', HTML)
        self.assertNotIn("备用：", HTML)
        self.assertIn("/api/corpus/browse", HTML)
        self.assertIn("正在处理文件夹，文件较多时可能需要一些时间", HTML)
        self.assertIn("/api/corpus/reindex", HTML)
        self.assertIn("默认整篇阅读", HTML)
        self.assertIn("默认按需阅读", HTML)
        self.assertIn("请阅读全文《文件名》", HTML)
        self.assertIn("只查相关部分", HTML)
        self.assertIn("单个文件上限50 MB，单次上传总量上限200 MB", HTML)
        self.assertIn("思考了 ${", HTML)
        self.assertIn("message.reasoning.summary", HTML)

    def test_reference_display_uses_unique_file_names_without_locators(self):
        self.assertIn("message.mode === '考据'", HTML)
        self.assertIn("new Map((retrieval?.local || [])", HTML)
        self.assertIn("meta.open = referenceCount <= 3", HTML)
        self.assertIn("referenceSummary.local.map(item => item.name || item.path)", HTML)
        self.assertNotIn("item.locator", HTML)


if __name__ == "__main__":
    unittest.main()
