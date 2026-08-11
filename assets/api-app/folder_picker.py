#!/usr/bin/env python3
"""Open the operating system's folder picker and print the selected path."""

from __future__ import annotations

import sys
from pathlib import Path


def enable_windows_dpi_awareness() -> None:
    """Match the native folder dialog to the active monitor's Windows scaling."""
    if sys.platform != "win32":
        return
    import ctypes

    try:
        per_monitor_v2 = ctypes.c_void_p(-4)
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(per_monitor_v2):
            return
    except (AttributeError, OSError):
        pass
    try:
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def main() -> int:
    enable_windows_dpi_awareness()
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise SystemExit(f"Tk folder dialog is unavailable: {exc}") from exc

    initial = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 and sys.argv[1] else None
    initial_dir = str(initial) if initial and initial.is_dir() else None
    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except tk.TclError:
        pass
    root.update_idletasks()
    selected = filedialog.askdirectory(
        parent=root,
        title="选择本地文献库文件夹",
        initialdir=initial_dir,
        mustexist=True,
    )
    root.destroy()
    if selected:
        sys.stdout.write(str(Path(selected).resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
