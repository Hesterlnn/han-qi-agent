import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


APP_DIR = Path(__file__).resolve().parents[1] / "assets" / "api-app"
sys.path.insert(0, str(APP_DIR))

import server  # noqa: E402


class CorpusFolderTests(unittest.TestCase):
    def test_document_upload_size_limits(self):
        self.assertEqual(server.MAX_IMPORTED_FILE_BYTES, 50 * 1024 * 1024)
        self.assertEqual(server.MAX_IMPORTED_TOTAL_BYTES, 200 * 1024 * 1024)
        self.assertGreaterEqual(
            server.MAX_IMPORT_REQUEST_BYTES,
            (server.MAX_IMPORTED_TOTAL_BYTES * 4 + 2) // 3,
        )

    def make_handler(self, corpus_root: Path, allow_local: bool = True):
        handler = server.Handler.__new__(server.Handler)
        upload_root = corpus_root / "uploads"
        upload_root.mkdir(parents=True)
        handler.server = SimpleNamespace(
            allow_local_folder_selection=allow_local,
            corpus_root=corpus_root,
            corpus_source=upload_root,
            corpus_source_mode="uploads",
            corpus_lock=threading.Lock(),
        )
        return handler

    def test_external_folder_is_indexed_without_copying_files(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            root = Path(temporary)
            corpus_root = root / "app-data"
            library = root / "library"
            library.mkdir()
            (library / "论文.md").write_text("一篇用于测试的论文", encoding="utf-8")
            handler = self.make_handler(corpus_root)

            report = handler.use_corpus_folder({"path": str(library.resolve())})

            self.assertEqual(report["source_mode"], "folder")
            self.assertEqual(report["source_path"], str(library.resolve()))
            self.assertEqual(report["file_count"], 1)
            self.assertFalse((corpus_root / "uploads" / "论文.md").exists())
            self.assertEqual(server.saved_corpus_folder(corpus_root), library.resolve())

    def test_folder_dialog_selection_can_be_processed_automatically(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            root = Path(temporary)
            corpus_root = root / "app-data"
            library = root / "library"
            library.mkdir()
            (library / "材料.txt").write_text("材料内容", encoding="utf-8")
            handler = self.make_handler(corpus_root)

            with patch.object(server, "choose_local_folder", return_value=library.resolve()):
                selection = handler.browse_corpus_folder()

            self.assertFalse(selection["cancelled"])
            self.assertEqual(selection["selected_path"], str(library.resolve()))
            self.assertEqual(handler.server.corpus_source_mode, "uploads")

            report = handler.use_corpus_folder({"path": selection["selected_path"]})

            self.assertEqual(report["source_mode"], "folder")
            self.assertEqual(report["file_count"], 1)

    def test_removing_external_library_does_not_delete_original_files(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            root = Path(temporary)
            corpus_root = root / "app-data"
            library = root / "library"
            library.mkdir()
            original = library / "原文.txt"
            original.write_text("原文内容", encoding="utf-8")
            handler = self.make_handler(corpus_root)
            uploaded = corpus_root / "uploads" / "原先上传.txt"
            uploaded.write_text("上传副本", encoding="utf-8")
            handler.use_corpus_folder({"path": str(library.resolve())})

            report = handler.clear_corpus()

            self.assertTrue(original.is_file())
            self.assertEqual(original.read_text(encoding="utf-8"), "原文内容")
            self.assertEqual(report["source_mode"], "uploads")
            self.assertTrue(uploaded.is_file())
            self.assertEqual(report["file_count"], 1)
            self.assertIsNone(server.saved_corpus_folder(corpus_root))

    def test_remote_binding_cannot_select_arbitrary_server_folder(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            root = Path(temporary)
            corpus_root = root / "app-data"
            library = root / "library"
            library.mkdir()
            handler = self.make_handler(corpus_root, allow_local=False)

            with self.assertRaisesRegex(ValueError, "只有本机访问"):
                handler.use_corpus_folder({"path": str(library.resolve())})

    def test_clearing_uploaded_library_deletes_only_managed_copies(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            root = Path(temporary)
            corpus_root = root / "app-data"
            handler = self.make_handler(corpus_root)
            uploaded = corpus_root / "uploads" / "上传文献.txt"
            uploaded.write_text("上传内容", encoding="utf-8")

            report = handler.clear_corpus()

            self.assertFalse(uploaded.exists())
            self.assertEqual(report["file_count"], 0)


if __name__ == "__main__":
    unittest.main()
