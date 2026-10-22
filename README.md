# 数学建模论文评审智能体 v0.1

这是一个本地优先的数学建模竞赛论文评审工作台。后端使用 FastAPI、SQLite 和可配置的 OpenAI-compatible 云端模型接口；前端使用 React、Vite、Tailwind 和 daisyUI。系统不执行上传的代码或数据。

## 本地运行

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000
```

另开终端启动前端开发服务器：

```powershell
npm install --prefix frontend
npm run dev --prefix frontend
```

打开 `http://127.0.0.1:5173`，在“模型配置”页填写提供商、OpenAI-compatible URL、API Key 和模型名称。API Key 使用 `DATA_DIR/.model-config.key` 生成的本地主密钥加密保存，只返回是否已配置。

## Windows 桌面版

Windows 10/11 x64 桌面包需要 Microsoft Edge WebView2 Runtime、Node.js/npm。建议用隔离虚拟环境打包，避免宿主 Anaconda 中无关的科学计算库进入应用：

```powershell
python -m venv .tmp/desktop-build-venv
$tmpPython = ".tmp/desktop-build-venv/Scripts/python.exe"
& $tmpPython -m pip install -e ".[desktop]"
npm run build --prefix frontend
& $tmpPython -m PyInstaller desktop/desktop.spec --noconfirm
Compress-Archive -Path dist/MathModelingPaperReview -DestinationPath dist/MathModelingPaperReview-0.1.0-windows-x64.zip -Force
```

解压 ZIP 后运行 `MathModelingPaperReview.exe`。如需安装器，可使用 Inno Setup 编译 `installer/windows.iss`；安装器工具需另行安装。

开发模式可安装桌面依赖并从项目根目录运行：

```powershell
python -m pip install -e ".[desktop]"
npm run build --prefix frontend
python -m desktop.launcher
```

安装后的程序从桌面或开始菜单快捷方式启动。首次启动可选迁移现有 `DATA_DIR`，或创建新工作区；数据保存在 `%LOCALAPPDATA%\MathModelingPaperReview\data`。在工作台“模型配置”页设置 OpenAI-compatible URL、API Key 和模型名并测试连接。评审由本机服务通过互联网调用所配置的云模型。

前端构建后，FastAPI 会同源托管 `frontend/dist`：

```powershell
npm run build --prefix frontend
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8000
```

尚未构建前端时，FastAPI 根页面显示启动说明。执行前端构建后重启服务，即可使用完整深色工作台；不再维护另一套静态备用工作台。

工作流是：上传论文 → 导入并发布量表 → 创建评审 → 启动七阶段后台评审 → 查看进度、双轨评分、证据与建议 → 导出 Markdown/JSON 报告。每次运行只使用冻结的资产和已发布量表；单阶段重跑会标记下游结果过期。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest tests -q --basetemp .pytest_tmp
.venv\Scripts\python.exe -m compileall -q backend
python scripts/check_handoff.py
python references/_tools/verify_snapshots.py
npm run test --prefix frontend
npm run build --prefix frontend
```

构建前端需要 Node.js/npm 网络可用；依赖安装不应把 `frontend/node_modules` 或 `frontend/dist` 提交到仓库。

## 第三方参考快照

`references/upstream/` 保存了 10 个公开项目的只读快照，用于设计核对、协议提取和离线评测；它们不是运行时依赖，应用不会 import 或执行其中任何文件。`skills/` 是项目自有的评审与研发 skill 包。这些内容的来源、提交和许可证见 [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md) 与 [`references/REFERENCE_POLICY.md`](references/REFERENCE_POLICY.md)。

核验快照完整性：

```powershell
python references/_tools/verify_snapshots.py
```

## 许可证

本项目以 [MIT 许可证](LICENSE)发布。`references/`、`skills/` 中的第三方内容不属于该授权范围，各自保留原许可证，详见 [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md)。
