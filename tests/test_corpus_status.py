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
