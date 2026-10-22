# PyInstaller one-folder bundle for Windows. Run from the repository root.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

ROOT = Path(SPECPATH).resolve().parent
webview_datas = collect_data_files("webview", subdir="lib")
webview_binaries = collect_dynamic_libs("webview")

datas = [
    (str(ROOT / "frontend" / "dist"), "frontend/dist"),
    (str(ROOT / "desktop" / "welcome.html"), "desktop"),
    (str(ROOT / "config"), "config"),
] + webview_datas

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.lifespan.on",
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
    "webview.platforms.win32",
    "webview.guilib",
    "clr",
    "clr_loader",
    "pymupdf",
    "multipart",
    "cryptography.fernet",
]

a = Analysis(
    [str(ROOT / "desktop" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=webview_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # The app uses the Windows Edge WebView backend. Other GUI engines and
    # scientific packages are optional and must not be pulled from host Python.
    excludes=["pytest", "numpy", "scipy", "pandas", "dask", "numba", "llvmlite", "torch", "tkinter.test", "PyQt5", "PyQt6", "PySide2", "PySide6"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MathModelingPaperReview",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MathModelingPaperReview",
)
