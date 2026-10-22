# 前端运行

```powershell
npm install --prefix frontend
npm run dev --prefix frontend
```

后端另开终端运行：

```powershell
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000
```

以上命令在项目根目录执行。生产构建：`npm run build --prefix frontend`。构建后重启 FastAPI，由其提供 `frontend/dist`。Hash 路由支持直接进入评审详情。

未构建时 `frontend/static/index.html` 仅显示启动说明，不提供第二套工作台。

## Windows 桌面版

桌面启动器由 pywebview 承载已构建的 React 工作台，并启动只监听 `127.0.0.1` 的 FastAPI 服务。安装版将工作数据保存在 `%LOCALAPPDATA%\MathModelingPaperReview\data`，首次启动可以迁移现有 `DATA_DIR`。桌面开发和 Windows 安装包命令见仓库根目录 `README.md` 的“Windows 桌面版”部分。

关键 API 契约测试：`npm run test --prefix frontend`。
