"""Windows desktop entry point for the review workbench."""

from __future__ import annotations

import secrets
import sys
import threading
from pathlib import Path
from typing import Any

from desktop.runtime import ProfileError, profile_state, startup_profile, user_data_dir
from desktop.server import DesktopServerError, LocalApiServer


def resource_dir() -> Path:
    """Return the source or PyInstaller resource root."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root)
    return Path(__file__).resolve().parents[1]


class DesktopBridge:
    def __init__(self, server: LocalApiServer) -> None:
        self.window: Any = None
        self.server = server
        self._starting = threading.Lock()
        self._started = False

    def startup(self, mode: str) -> dict[str, Any]:
        """Initialize a profile, start the API, and navigate the native window."""
        if not self._starting.acquire(blocking=False):
            return {"ok": False, "message": "应用正在启动，请稍候。"}
        try:
            if self._started:
                return {"ok": True}
            data_dir = user_data_dir()
            if mode == "fresh":
                startup_profile("fresh", destination=data_dir)
            elif mode == "migrate":
                import webview
                selected = self.window.create_file_dialog(webview.FileDialog.FOLDER, allow_multiple=False)
                if not selected:
                    return {"ok": False, "message": "已取消选择，原数据未修改。"}
                startup_profile("migrate", Path(selected[0]), data_dir)
            else:
                return {"ok": False, "message": "未知的数据初始化方式。"}

            token = secrets.token_urlsafe(32)
            base_url = self.server.start(
                session_token=token,
                data_dir=data_dir,
                frontend_dist_dir=resource_dir() / "frontend" / "dist",
            )
            self._started = True
            import webview
            self.window.events.closing += lambda: close_confirmation(self.server)
            self.window.load_url(base_url)
            return {"ok": True}
        except (ProfileError, DesktopServerError, OSError) as exc:
            return {"ok": False, "message": str(exc)}
        except Exception:
            return {"ok": False, "message": "桌面工作台启动失败，请重新打开应用。"}
        finally:
            self._starting.release()


def show_error(message: str) -> None:
    """Show a native Windows error if the desktop webview cannot start."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, "数学建模论文评审工作台", 0x10)
            return
        except Exception:
            pass
    print(message, file=sys.stderr)


def close_confirmation(server: LocalApiServer) -> bool:
    """Warn before stopping the local service while a review is still running."""
    if not server.has_active_review():
        return True
    if sys.platform == "win32":
        import ctypes
        return ctypes.windll.user32.MessageBoxW(
            None,
            "关闭工作台会停止本地服务，当前评审可能中断。已保存的结果会保留。是否继续关闭？",
            "评审仍在运行",
            0x24,
        ) == 6
    return False


def main() -> int:
    try:
        import webview
    except Exception as exc:
        show_error(f"无法初始化桌面窗口，请安装或修复 Microsoft Edge WebView2 Runtime。\n{exc}")
        return 1

    server = LocalApiServer()
    try:
        webview.settings["ALLOW_DOWNLOADS"] = True
        data_dir = user_data_dir()
        state = profile_state(data_dir)
        if state == "partial":
            show_error(f"数据目录内容不完整或不可读取，应用不会覆盖它：\n{data_dir}")
            return 1

        if state == "ready":
            token = secrets.token_urlsafe(32)
            url = server.start(
                session_token=token,
                data_dir=data_dir,
                frontend_dist_dir=resource_dir() / "frontend" / "dist",
            )
            window = webview.create_window("数学建模论文评审工作台", url, width=1360, height=900, min_size=(960, 640))
            window.events.closing += lambda: close_confirmation(server)
        else:
            bridge = DesktopBridge(server)
            welcome = (resource_dir() / "desktop" / "welcome.html").read_text(encoding="utf-8")
            window = webview.create_window("数学建模论文评审工作台", html=welcome, js_api=bridge, width=760, height=520, min_size=(640, 460))
            bridge.window = window

        window.events.closed += lambda: server.stop()
        webview.start(gui="edgechromium")
        server.stop()
        return 0
    except Exception as exc:
        server.stop()
        show_error(f"桌面工作台无法启动：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
