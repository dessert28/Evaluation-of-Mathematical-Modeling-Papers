# Windows Desktop App Design

## Goal

Deliver the existing mathematical-modeling paper review workbench as a Windows desktop application. A user should install it, launch it from a desktop shortcut, configure an OpenAI-compatible cloud model in the existing UI, and run reviews through that model without opening a terminal or browser.

The desktop app wraps the existing React workbench and FastAPI review API. It does not change review scoring semantics or claim to implement the unfinished evidence audit, arbitration, or automatic official-score/recommendation generation.

## User flow

1. The installer places a Windows x64 application and desktop/start-menu shortcuts.
2. On launch, the application prepares its per-user data directory, starts the local API, waits for `/health`, then opens the workbench in a native window.
3. The user configures and tests an OpenAI-compatible model using the existing model configuration screen. The configured cloud model is called over HTTPS by the existing backend during review.
4. On first launch, the app offers to select an existing `DATA_DIR` folder with a native folder picker, or start with an empty profile. It copies the selected data into the new per-user location; the source remains intact until the user verifies the migrated workbench.
5. Closing the desktop window shuts down the local API process cleanly. A later launch reuses the same database, assets, and encrypted model configuration.

## Architecture

- Keep React/Vite as the UI and FastAPI as the local service/API.
- Add a small Python desktop launcher using pywebview. The launcher starts Uvicorn on `127.0.0.1` using an OS-assigned available port, waits for readiness, opens the UI, and stops the server when the final window closes.
- Bind only to loopback. The launcher creates a per-run random session token; desktop API requests carry it and the local server rejects requests without it. The desktop window does not navigate to arbitrary remote origins. Cloud traffic is initiated only by the backend to the endpoint configured by the user.
- Add a desktop-aware API base URL so the compiled frontend sends API calls to the selected local port. The server injects the per-run token into the UI bootstrap response; the frontend adds it to API requests. Development browser mode continues to use the existing Vite proxy and does not use the desktop token.
- Package the built frontend and Python backend with PyInstaller in one-folder mode, then wrap that folder in a Windows installer. Store mutable state under `%LOCALAPPDATA%\MathModelingPaperReview\data`, never in the installation directory.
- Resolve packaged resources separately from writable user data. Configuration, database, encryption key, and uploaded assets must continue to work when the working directory is unrelated to the project folder.

## Data migration and secrets

- Existing `DATA_DIR` data may contain the SQLite database, `.model-config.key`, and content-addressed assets. First-run migration copies the selected directory as one unit; a partial copy must not be reported as successful. It must still work when a source directory has no model key because it contains no saved model credentials.
- Migration must not overwrite a non-empty destination. If the destination already contains data, the application starts from that data and offers no destructive merge.
- Keep API keys encrypted with the existing Fernet key. Never place secrets in command-line arguments, logs, installer files, or handoff documentation.
- If the encryption key is absent or cannot decrypt a stored credential, show a recovery message and let the user re-enter the model key.

## Packaging and support boundary

- Initial target: Windows 10/11 x64 on a machine with the Microsoft Edge WebView2 Runtime available. Show an actionable startup message if the runtime is unavailable.
- The application requires an internet connection and a reachable, correctly configured OpenAI-compatible model endpoint to evaluate papers. Parsing, saved history, and reports remain local.
- Produce an installable package, not only a developer command or an unpacked source tree. Code signing and automatic updates are outside this first desktop delivery.

## Failure behavior

- If the local port is unavailable, retry another OS-assigned port; never fall back to listening on a network interface.
- If API startup or `/health` readiness times out, display a desktop error with a safe diagnostic log location and terminate the launcher cleanly.
- If the cloud model is unreachable, retain the existing API error and degraded-review behavior in the workbench; do not report a successful model test or review.
- If the desktop window closes while a review is running, warn that the local process will stop and the review may be marked interrupted; persisted results remain available on the next launch.

## Acceptance criteria

- A clean Windows x64 machine can install and launch the application without Python, Node.js, or a terminal.
- The app opens a native window and serves the existing React workbench through a loopback-only API server.
- First launch without an existing data directory initializes a working database and encryption key under `%LOCALAPPDATA%`.
- First-run migration preserves the existing database, key, and assets together and does not modify the source directory.
- A user can save a model configuration, test it, close/reopen the app, and see the configuration still active with the API key hidden.
- A real configured OpenAI-compatible service can be called by a review started in the desktop UI; failed connectivity remains visible as failure/degraded state.
- Closing the window stops the local server; launching again reuses the persisted review history and assets.
- The installer and packaged resources contain no user database, API key, encryption key, or uploaded paper.

## Out of scope

- macOS/Linux packaging, multi-user accounts, offline/local-model inference, cloud storage, auto-update, and code signing.
- Completing the product's still-missing formal evidence audit, arbitration, or automatic official-score/recommendation generation. Those remain separate product capabilities and retain their current visible status.
