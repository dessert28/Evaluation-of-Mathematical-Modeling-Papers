# Windows Desktop App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the existing paper review workbench as a Windows 10/11 x64 desktop installer that starts its local API and calls the OpenAI-compatible cloud model configured in the existing UI.

**Architecture:** Keep React/Vite and FastAPI, add a pywebview launcher that serves the UI in a native window and starts Uvicorn on an OS-assigned loopback port. Put mutable state under `%LOCALAPPDATA%`, protect desktop API requests with a per-run token, and package the application in one-folder form with a Windows installer.

**Tech Stack:** Python, FastAPI, Uvicorn, React, Vite, pywebview, PyInstaller, Windows WebView2, Windows installer tool.

**Spec:** `docs/superpowers/specs/2026-10-07-windows-desktop-app-design.md`

## Global Constraints

- Initial target is Windows 10/11 x64 with Microsoft Edge WebView2 Runtime available.
- The app binds only to `127.0.0.1`; a per-run random token protects desktop API calls.
- Mutable data lives under `%LOCALAPPDATA%\MathModelingPaperReview\data`, never in the install directory.
- API keys remain encrypted with the existing Fernet key and are excluded from logs and packaged files.
- First-run migration copies a selected existing `DATA_DIR` as a unit, leaves the source untouched, and never overwrites a non-empty destination.
- Cloud model calls use the existing OpenAI-compatible configuration and backend adapter over HTTPS.
- Linux/macOS installers, auto-update, code signing, offline models, and completing evidence audit/arbiter/official-score generation are out of scope.

## Review Focus

- Missing or partial legacy data: the destination must not be marked migrated unless the copy completed and the source remains unchanged.
- Invalid or already-populated data destination: preserve current destination and explain recovery without overwriting it.
- Port collision or slow API startup: choose another loopback port or show a desktop startup error.
- Missing WebView2 or packaged frontend assets: show an actionable startup message and stop the backend.
- Closing the app during a review: warn before shutdown and preserve already-persisted state.

## File Map

- Create `desktop/launcher.py`: application entry point, first-run welcome flow, window lifetime, and orchestration.
- Create `desktop/runtime.py`: packaged resource discovery, per-user paths, migration, and log location.
- Create `desktop/server.py`: loopback port selection, Uvicorn lifecycle, and health readiness.
- Create `desktop/welcome.html`: first-run choice to migrate a selected data folder or start a clean profile.
- Create `desktop/desktop.spec`: PyInstaller one-folder bundle definition and resource collection.
- Create `installer/windows.iss`: Windows installer configuration and shortcuts.
- Modify `backend/app/settings.py`: desktop data/resource settings.
- Modify `backend/app/main.py`: packaged frontend routing and optional per-run desktop session guard.
- Modify `frontend/src/api.js` and `frontend/index.html`: configurable API base and desktop session-token bootstrap.
- Modify `pyproject.toml`: desktop runtime/build dependencies and entry-point packaging metadata.
- Modify `README.md` and `frontend/RUN.md`: development and installed desktop launch instructions.
- Modify `HANDOFF_LOG.md`: required dated implementation and verification record.

---

### Task 1: Per-user data directory and safe legacy migration

**Files:**
- Create: `desktop/runtime.py`
- Create: `desktop/launcher.py`
- Modify: `backend/app/settings.py`

**Interfaces:**
- `desktop.runtime.user_data_dir() -> Path` returns `%LOCALAPPDATA%\MathModelingPaperReview\data` and creates its parent.
- `desktop.runtime.migrate_data(source: Path, destination: Path) -> None` copies a selected legacy data directory atomically enough to detect partial failure, refuses a non-empty destination, and never changes the source.
- `desktop.runtime.startup_profile(mode: Literal["fresh", "migrate"], source_dir: Path | None, destination: Path | None = None) -> Path` creates a fresh profile or migrates the selected folder before importing the FastAPI application.
- `Settings.data_dir` continues to accept `DATA_DIR`; the desktop launcher sets it to the user data path before importing backend modules.

- [ ] Implement writable path resolution and verify paths are outside the install/resource directory.
- [ ] Implement safe migration, including rollback/removal of an incomplete destination copy, existing-destination refusal, missing model key support, and source preservation.
- [ ] Add first-run welcome choices for selecting a source folder or starting fresh; skip the choice when a valid profile already exists.

### Task 2: Desktop API origin, session guard, and UI bootstrap

**Files:**
- Modify: `backend/app/main.py`
- Modify: `frontend/src/api.js`
- Modify: `frontend/index.html`
- Create or modify: focused desktop settings in `backend/app/settings.py`

**Interfaces:**
- Desktop server mode accepts a configured `frontend_dist_dir: Path` and `desktop_session_token: str | None`.
- `frontend/src/api.js` resolves API requests from `window.__DESKTOP_API_BASE__` when present; otherwise it uses same-origin requests as today.
- The desktop UI bootstrap exposes `window.__DESKTOP_SESSION_TOKEN__`; API requests send it as `X-Desktop-Token`.
- When desktop token mode is enabled, middleware rejects `/api/*` requests with a missing or invalid token. Normal development mode remains token-free.

- [ ] Add the desktop API base and token header without changing the existing Vite proxy flow.
- [ ] Add server-side token enforcement limited to desktop mode and a UI bootstrap that does not expose tokens in logs or persisted responses.
- [ ] Route `/` to the packaged frontend and static assets to the packaged `dist` directory while keeping the current development/fallback behavior.

### Task 3: Native window and local server lifecycle

**Files:**
- Create: `desktop/server.py`
- Create: `desktop/welcome.html`
- Modify: `desktop/launcher.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- `desktop.server.LocalApiServer.start(*, session_token: str, data_dir: Path, frontend_dist_dir: Path) -> str` starts the module-level FastAPI app after setting desktop environment configuration, binds Uvicorn to a selected OS-assigned loopback port, and returns the ready base URL.
- `LocalApiServer.stop(timeout_seconds: float = 5.0) -> None` requests graceful shutdown and waits for the server thread.
- The launcher owns the pywebview window, calls the bridge for fresh/migrated profile startup, loads the React UI only after `/health` succeeds, and stops the API on final window close.

- [ ] Start the app with the configured data directory and per-run token; select only loopback sockets and retry port collisions.
- [ ] Wait for `/health` with a bounded timeout and provide a safe local log path on startup failure.
- [ ] Add native window close confirmation while a run is active, with clean shutdown after confirmation.
- [ ] Handle a missing WebView2 runtime with a clear startup message.

### Task 4: Windows packaging and installer

**Files:**
- Create: `desktop/desktop.spec`
- Create: `installer/windows.iss`
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `frontend/RUN.md`

**Interfaces:**
- `python -m PyInstaller desktop/desktop.spec --noconfirm` builds the one-folder desktop distribution from the current Windows environment.
- The installer consumes that distribution, installs the app, and creates Start Menu and optional desktop shortcuts.
- Runtime data remains external under `%LOCALAPPDATA%` and is not included in the build input or installer payload.

- [ ] Add pinned/compatible desktop build dependencies and collect FastAPI, Uvicorn, SQLAlchemy, cryptography, PDF parsing, prompts/configuration, and frontend `dist` resources.
- [ ] Configure an onedir build that excludes project `data`, `.env`, `.model-config.key`, `.db` files, uploaded papers, test outputs, `.venv`, and `node_modules`.
- [ ] Add installer entries, shortcuts, uninstall behavior, and WebView2 prerequisite messaging.
- [ ] Document separate developer and installed-app launch paths.

### Task 5: Desktop delivery review and handoff

**Files:**
- Modify: `HANDOFF_LOG.md`
- Modify: `HANDOFF_CURRENT.md`

**Interfaces:**
- The final handoff records the generated installer path, build command, profile/migration behavior, and unresolved requirements without recording credentials or user paper contents.

- [ ] Review the installer payload for excluded local data and credentials.
- [ ] Build the frontend and Windows package from the clean documented commands.
- [ ] Perform a manual desktop acceptance pass for launch, model configuration persistence/key masking, local API shutdown, and review request routing to the configured cloud endpoint; record unavailable external credentials as an explicit unverified item.
- [ ] Update the current handoff snapshot and append the dated implementation record.

## Self-review

- Spec coverage: native window and launch/shutdown (Tasks 2–3); cloud model configuration/API flow (Tasks 2 and 5); data directory and migration (Task 1); Windows installer and clean-machine boundary (Task 4); secrets and loopback protection (Tasks 1–2 and 4); handoff (Task 5). The unfinished evidence audit and score/recommendation generation remain explicitly out of scope.
- Step scan: each step maps to one coherent component or delivery check; no step introduces an unspecified scoring behavior.
- Type consistency: `user_data_dir`, `migrate_data`, `startup_profile`, and `LocalApiServer` interfaces are used consistently by their later tasks.
- Review focus: all five identified failure classes are assigned to the task that owns their behavior.
- Proportion: five tasks cover the five dependent work areas without duplicating the broader review product roadmap.
