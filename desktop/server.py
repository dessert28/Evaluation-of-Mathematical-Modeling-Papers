"""Start and stop the embedded loopback-only FastAPI service."""

from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


class DesktopServerError(RuntimeError):
    """Raised when the desktop API cannot be started safely."""


class LocalApiServer:
    def __init__(self) -> None:
        self._server = None
        self._app = None
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self.base_url: str | None = None

    def start(self, *, session_token: str, data_dir: Path, frontend_dist_dir: Path) -> str:
        """Start the packaged application and return its ready loopback URL."""
        data_dir.mkdir(parents=True, exist_ok=True)
        if not (frontend_dist_dir / "index.html").is_file():
            raise DesktopServerError("未找到前端构建文件，请重新安装应用。")

        sock: socket.socket | None = None
        last_error: OSError | None = None
        for _ in range(8):
            candidate = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                    candidate.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                candidate.bind(("127.0.0.1", 0))
                candidate.listen(128)
                candidate.setblocking(False)
                sock = candidate
                break
            except OSError as exc:
                last_error = exc
                candidate.close()
        if sock is None:
            raise DesktopServerError("无法分配本机服务端口，请关闭占用本地网络的程序后重试。") from last_error

        port = sock.getsockname()[1]
        base_url = f"http://127.0.0.1:{port}"
        os.environ["DATA_DIR"] = str(data_dir)
        os.environ["DESKTOP_SESSION_TOKEN"] = session_token
        os.environ["FRONTEND_DIST_DIR"] = str(frontend_dist_dir)
        os.environ["DESKTOP_API_BASE"] = base_url

        try:
            import uvicorn
            from backend.app.main import app
        except Exception as exc:
            sock.close()
            raise DesktopServerError("本地评审服务加载失败。") from exc

        try:
            config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
            server = uvicorn.Server(config)
            thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, name="review-api", daemon=True)
            self._socket, self._server, self._thread, self._app = sock, server, thread, app
            self.base_url = base_url
            thread.start()
        except Exception as exc:
            sock.close()
            raise DesktopServerError("本地评审服务无法启动。") from exc

        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self._thread is None or not self._thread.is_alive():
                self.stop()
                raise DesktopServerError("本地评审服务意外退出，请查看桌面应用日志。")
            try:
                with urlopen(f"{self.base_url}/health", timeout=1) as response:
                    if response.status == 200:
                        return self.base_url
            except (OSError, URLError, TimeoutError):
                time.sleep(0.15)
        self.stop()
        raise DesktopServerError("本地评审服务启动超时，请重新启动应用。")

    def has_active_review(self) -> bool:
        """Return whether a persisted review is queued or currently running."""
        repository = getattr(getattr(self._app, "state", None), "review_job_repository", None)
        if repository is None:
            return False
        try:
            for job in repository.list():
                if (job.state_snapshot or {}).get("run_status") in {"QUEUED", "RUNNING"}:
                    return True
        except Exception:
            return True
        return False

    def stop(self, timeout_seconds: float = 5.0) -> None:
        server, thread, sock = self._server, self._thread, self._socket
        if server is not None:
            server.should_exit = True
        if thread is not None and thread.is_alive():
            thread.join(timeout_seconds)
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        self._server = self._thread = self._socket = self._app = None
        self.base_url = None


__all__ = ["DesktopServerError", "LocalApiServer"]
