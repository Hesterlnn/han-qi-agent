import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


APP_DIR = Path(__file__).resolve().parents[1] / "assets" / "api-app"
sys.path.insert(0, str(APP_DIR))

import folder_picker  # noqa: E402


class FolderPickerTests(unittest.TestCase):
    def test_windows_prefers_per_monitor_v2_dpi_awareness(self):
        calls = []
        fake_ctypes = SimpleNamespace(
            c_void_p=lambda value: value,
            windll=SimpleNamespace(
                user32=SimpleNamespace(
                    SetProcessDpiAwarenessContext=lambda value: calls.append(value) or True,
                    SetProcessDPIAware=lambda: calls.append("legacy") or True,
                ),
                shcore=SimpleNamespace(
                    SetProcessDpiAwareness=lambda value: calls.append(("shcore", value)) or 0
                ),
            ),
        )

        with patch.object(folder_picker.sys, "platform", "win32"):
            with patch.dict(sys.modules, {"ctypes": fake_ctypes}):
                folder_picker.enable_windows_dpi_awareness()

        self.assertEqual(calls, [-4])

    def test_non_windows_does_not_load_windows_dpi_api(self):
        with patch.object(folder_picker.sys, "platform", "linux"):
            with patch.dict(sys.modules, {"ctypes": None}):
                folder_picker.enable_windows_dpi_awareness()


if __name__ == "__main__":
    unittest.main()
