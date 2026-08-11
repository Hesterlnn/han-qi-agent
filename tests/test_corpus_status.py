import json
import sys
import tempfile
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "assets" / "api-app"
sys.path.insert(0, str(APP_DIR))

import corpus  # noqa: E402


class CorpusStatusTests(unittest.TestCase):
    def test_build_index_reports_files_for_the_web_list(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            root = Path(temporary)
            uploads = root / "uploads"
            index = root / "index"
            uploads.mkdir()
            (uploads / "甲.md").write_text("第一条材料", encoding="utf-8")
            (uploads / "子目录").mkdir()
            (uploads / "子目录" / "乙.txt").write_text("第二条材料", encoding="utf-8")

            report = corpus.build_index(uploads, index, 1024 * 1024)

            self.assertEqual(report["file_count"], 2)
            self.assertEqual([item["path"] for item in report["files"]], ["子目录/乙.txt", "甲.md"])
            self.assertTrue(all(item["status"] == "extracted" for item in report["files"]))
            self.assertTrue(all(item["character_count"] > 0 for item in report["files"]))
            self.assertTrue((index / "documents.jsonl").is_file())

    def test_short_relevant_document_is_returned_in_full(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            root = Path(temporary)
            uploads = root / "uploads"
            index = root / "index"
            uploads.mkdir()
            (uploads / "短论文.md").write_text("开头背景\n目标材料\n结尾结论", encoding="utf-8")
            corpus.build_index(uploads, index, 1024 * 1024)

            results = corpus.search_index(
                index,
                "目标材料",
                top=8,
                full_text_max_chars=100,
                full_text_total_chars=1000,
            )

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["content_mode"], "full")
            self.assertEqual(results[0]["chunk"], 0)
            self.assertIn("开头背景", results[0]["text"])
            self.assertIn("结尾结论", results[0]["text"])

    def test_long_document_still_uses_relevant_excerpts(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            root = Path(temporary)
            uploads = root / "uploads"
            index = root / "index"
            uploads.mkdir()
            long_text = "目标材料\n" + "\n".join(f"其他内容{i}" for i in range(1000))
            (uploads / "长论文.md").write_text(long_text, encoding="utf-8")
            corpus.build_index(uploads, index, 1024 * 1024)

            results = corpus.search_index(
                index,
                "目标材料",
                top=8,
                full_text_max_chars=100,
                full_text_total_chars=1000,
            )

            self.assertGreaterEqual(len(results), 1)
            self.assertTrue(all(item["content_mode"] == "excerpt" for item in results))
            self.assertTrue(all(len(item["text"]) <= 2200 for item in results))

    def test_user_can_request_a_long_document_in_full(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            root = Path(temporary)
            uploads = root / "uploads"
            index = root / "index"
            uploads.mkdir()
            long_text = "开头背景\n目标材料\n" + "较长正文" * 1000 + "\n结尾结论"
            (uploads / "长论文.md").write_text(long_text, encoding="utf-8")
            corpus.build_index(uploads, index, 1024 * 1024)

            paths = corpus.match_requested_documents(index, "请阅读全文《长论文》后回答")
            results = corpus.search_index(
                index,
                "请阅读全文《长论文》后回答",
                full_text_max_chars=100,
                force_full_paths=paths,
            )

            self.assertEqual(paths, ["长论文.md"])
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["content_mode"], "full")
            self.assertIn("开头背景", results[0]["text"])
            self.assertIn("结尾结论", results[0]["text"])

    def test_user_can_require_excerpts_for_a_short_document(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            root = Path(temporary)
            uploads = root / "uploads"
            index = root / "index"
            uploads.mkdir()
            (uploads / "短论文.md").write_text("目标材料\n简短正文", encoding="utf-8")
            corpus.build_index(uploads, index, 1024 * 1024)

            results = corpus.search_index(index, "目标材料", excerpts_only=True)

            self.assertGreaterEqual(len(results), 1)
            self.assertTrue(all(item["content_mode"] == "excerpt" for item in results))

    def test_named_documents_restrict_search_and_each_gets_a_result(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            root = Path(temporary)
            uploads = root / "uploads"
            index = root / "index"
            uploads.mkdir()
            (uploads / "甲论文.md").write_text("共同问题\n甲方观点", encoding="utf-8")
            (uploads / "乙论文.md").write_text("共同问题\n乙方观点", encoding="utf-8")
            (uploads / "无关论文.md").write_text("共同问题\n无关观点", encoding="utf-8")
            corpus.build_index(uploads, index, 1024 * 1024)

            query = "请比较《甲论文.md》和《乙论文.md》对共同问题的判断"
            paths = corpus.match_requested_documents(index, query)
            results = corpus.search_index(index, query, restrict_paths=paths)

            self.assertEqual(paths, ["乙论文.md", "甲论文.md"])
            self.assertEqual({item["path"] for item in results}, {"甲论文.md", "乙论文.md"})

    def test_nested_book_title_filename_is_matched_directly(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            root = Path(temporary)
            uploads = root / "uploads"
            index = root / "index"
            uploads.mkdir()
            name = "从《安阳集》看韩琦.md"
            (uploads / name).write_text("论文内容", encoding="utf-8")
            corpus.build_index(uploads, index, 1024 * 1024)

            paths = corpus.match_requested_documents(index, f"请只根据文件“{name}”回答")

            self.assertEqual(paths, [name])

    def test_unnamed_full_text_request_only_selects_a_single_document(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            root = Path(temporary)
            uploads = root / "uploads"
            index = root / "index"
            uploads.mkdir()
            (uploads / "甲.md").write_text("甲文", encoding="utf-8")
            corpus.build_index(uploads, index, 1024 * 1024)

            self.assertEqual(corpus.match_requested_documents(index, "请阅读全文后回答"), ["甲.md"])

            (uploads / "乙.md").write_text("乙文", encoding="utf-8")
            corpus.build_index(uploads, index, 1024 * 1024)
            self.assertEqual(corpus.match_requested_documents(index, "请阅读全文后回答"), [])

    def test_requested_full_text_reports_capacity_limit(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            root = Path(temporary)
            uploads = root / "uploads"
            index = root / "index"
            uploads.mkdir()
            (uploads / "超长论文.md").write_text("正文" * 100, encoding="utf-8")
            corpus.build_index(uploads, index, 1024 * 1024)

            with self.assertRaisesRegex(ValueError, "全文超出本次可处理范围"):
                corpus.search_index(
                    index,
                    "阅读全文",
                    force_full_paths=["超长论文.md"],
                    requested_full_document_max_chars=50,
                )

    def test_old_index_can_recover_file_list_from_manifest(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            index = Path(temporary)
            (index / "report.json").write_text(
                json.dumps({"file_count": 1, "extracted_files": 1, "chunk_count": 2, "issues": []}),
                encoding="utf-8",
            )
            manifest = {
                "path": "旧文献.pdf",
                "extension": ".pdf",
                "size": 2048,
                "status": "extracted",
                "chunk_count": 2,
                "error": None,
            }
            (index / "manifest.jsonl").write_text(json.dumps(manifest, ensure_ascii=False) + "\n", encoding="utf-8")

            status = corpus.index_status(index)

            self.assertEqual(status["files"][0]["path"], "旧文献.pdf")
            self.assertEqual(status["files"][0]["size"], 2048)


if __name__ == "__main__":
    unittest.main()
