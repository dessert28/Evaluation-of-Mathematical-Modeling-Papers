# 会话交接总览

> 更新时间：2026-10-07（Asia/Shanghai；精确时间见 `HANDOFF_LOG.md` 最新条目）  
> 交接用途：供下一会话无需重走已完成工作，直接继续真实模型验证和 v0.1 收尾。  
> 当前项目路径：`D:\project\githubclone\Evaluation-of-Mathematical-Modeling-Papers`

## 1. 项目目标与边界

项目目标是构建一个本地优先的数学建模竞赛论文评审工作台：接收论文和官方评分标准，形成可追溯、证据优先的诊断与改进建议。当前前端参考用户提供的 `ruanzhu` 说明书做成深色工作台，同时保留七阶段建模评审协议。

核心边界：官方评分与通用诊断评分分轨；结论应有可定位证据；缺少证据时降低结论强度并标记待人工核实；默认不执行上传代码；七阶段完成只表示进入待证据审计阶段，不代表最终评审已通过。产品仍是单用户本地应用，不包含账号系统。

## 2. 当前实现状态

- 后端：FastAPI、Pydantic、SQLAlchemy/SQLite，提供模型配置、资产、量表、评审任务、进度、证据、建议修改和报告接口。
- 前端：React 18、Vite、Tailwind/daisyUI，Hash 路由，由 FastAPI 同源提供构建产物。
- 本地存储：论文资产按 SHA-256 管理；模型 API Key 用 Fernet 加密写入 SQLite，密钥文件在 `DATA_DIR/.model-config.key`，密钥不得进入 Git，迁移需手工备份。
- 模型：支持 OpenAI-compatible 配置，含服务提供商、URL、API Key、模型名称、测试连接及激活配置；运行时读取数据库中的激活配置。
- 评审：确定性协调器驱动固定七阶段，阶段结果与进度持久化，失败可降级，允许单阶段重跑及 stale 传播。阶段名称见评审协议。
- 量表：支持 JSON、Markdown、PDF、DOCX 来源导入、草稿编辑、权重校验和人工发布；评分任务绑定已发布量表版本。
- 结果：提供官方/通用评分展示、Finding、Claim/Obligation/Evidence 定位、建议人工编辑与历史、Markdown/JSON 报告下载。
- 安全：请求体显式白名单；不在 API 响应回显密钥；文本按普通 React 文本渲染；不执行用户提交代码。

## 3. 前端页面与本地运行

工作台包括：概览、模型配置、论文资产、官方评分标准、创建评审、任务进度/详情、结果与建议、历史与审计。支持桌面布局、窄屏导航、抽屉与可键盘关闭的弹窗。

当前本机已启动原生工作台：`http://127.0.0.1:8010/#/overview`。如服务停止，可在项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8010
```

如需开发模式，查看 `scripts/dev.ps1` 与 `frontend/RUN.md`。前端构建：

```powershell
npm run build --prefix frontend
```

## 4. 验收证据与其边界

最近一次交接记录的验证结果：

- `npm run build --prefix frontend` 成功，45 个模块；
- `npm run test --prefix frontend` 成功，6 项；
- 后端全量测试：132 passed，1 个既有 Starlette 弃用警告；
- `python -m compileall -q backend` 成功；
- 上游快照校验通过：10 个快照、1411 个哈希；
- 使用本地合成兼容模型和合成数据完成两轮 Edge 无头浏览器闭环验收；运行产物位于被忽略的 `.tmp/browser-acceptance/`。

这些结果证明本地接口/页面交互路径可用，不代表真实云端模型的评价质量。当前模型配置数量为 0；尚未配置或调用用户的云端模型，尚未使用真实论文和真实量表完成端到端评审。

## 5. 已知未完成功能与风险

1. 七阶段运行器目前不自动生成正式官方评分和优化建议；页面展示的是服务端已有数据，不以演示样例填充空结果。
2. 正式 Evidence Audit、冲突仲裁、联网检索/来源保存仍未实现；七阶段全部结束后应显示“待证据审计”。
3. 运行器使用进程内线程池；并发多进程部署需单进程约束或后续改用持久化队列/锁。
4. 主密钥文件需要用户备份；密钥丢失会使已有 API Key 无法解密。
5. Docker 可复现打包尚未完成；Git 尚未初始化，尚无远端或私有 GitHub 仓库，也未推送。
6. 未完成真实云 API 测试；真实服务可能存在兼容性、限流、上下文长度或结构化输出差异。
7. 没有经过真实评审案例校准七阶段评分的稳定性和准确性。

## 6. 下一会话建议顺序

1. 先阅读根目录 `施工必读.md`、`HANDOFF_LOG.md`、本文件、`docs/contracts/review-protocol-v0.1.md` 和 `docs/contracts/frontend-workbench.md`；施工前确认这次范围并追加日志。
2. 启动或确认本地服务 `http://127.0.0.1:8010/#/overview` 可访问。
3. 用户自行在模型配置页填写 OpenAI-compatible 服务商、URL、API Key、模型名并测试连接。不要把 API Key 放入聊天、日志或交接文档。
4. 用无敏感内容的样例论文和已确认量表跑一次真实模型端到端；检查超时/重试、模型结构化输出、证据块定位、阶段失败后的任务状态与报告。清楚区分模拟结果和真实模型结果。
5. 根据真实运行暴露的问题修复，再决定先做 Evidence Audit/建议评分，还是先做 Docker 复现；不应宣称评审闭环已完成，除非证据审计和实际结果路径都落地。
6. GitHub 发布前，先初始化本地 Git并检查忽略文件/密钥/用户数据；再恢复 `gh` 登录，创建目标私有仓库并推送。此前记录提示 GitHub CLI 凭据曾失效，需现场检查状态。
7. 每次施工都更新 `HANDOFF_LOG.md`，并依次执行相关测试、构建、快照核验和交接检查。

## 7. 关键文件索引

- 施工规则：`施工必读.md`
- 追加式逐次记录：`HANDOFF_LOG.md`
- 产品运行说明：`README.md`、`frontend/RUN.md`
- 评审协议：`docs/contracts/review-protocol-v0.1.md`
- 前端交互与接口契约：`docs/contracts/frontend-workbench.md`
- 后端 API：`backend/app/api/`
- 评审阶段编排与运行器：`backend/app/services/automatic_runner.py`、`backend/app/services/stage_orchestrator.py`
- 模型配置与加密：`backend/app/services/model_config.py`、`backend/app/api/model_config.py`
- 前端主应用与 API：`frontend/src/App.jsx`、`frontend/src/api.js`、`frontend/src/pages/`
- 本地浏览器合成验收夹具：`tests/browser_fixture.py`、`frontend/browser-smoke.cjs`（只用于测试，非真实模型）
- 交接检查：`scripts/check_handoff.py`

## 8. 仓库/凭据状态

此目录当前不是 Git 仓库（最近检查 `git status` 返回 `fatal: not a git repository`）。没有创建或推送 GitHub 仓库。模型密钥当前尚未配置；交接文档不保存密钥。不要把 `.env`、`DATA_DIR`、SQLite 数据库、主密钥、论文资产、`node_modules` 或浏览器测试输出提交。

## 9. Windows 桌面端（2026-10-07）

- 已新增 pywebview + FastAPI Windows 桌面启动器、首次新建/迁移工作区流程、每次启动的 API 会话令牌，以及 PyInstaller 打包配置。桌面数据保存在 `%LOCALAPPDATA%\MathModelingPaperReview\data`，服务仅监听 `127.0.0.1`；云模型仍由“模型配置”页面设置，当前没有用户凭据。
- 可分发包：`dist/MathModelingPaperReview-0.1.0-windows-x64.zip`；解压后运行 `MathModelingPaperReview\MathModelingPaperReview.exe`。ZIP 为 51,921,375 字节，SHA-256：`3F939C076C23C658077842D7E8F1908CAFD8488193073C9551C888F1EA022F29`。运行依赖 Microsoft Edge WebView2 Runtime。
- 已完成 Vite 构建、干净隔离 Python 环境下 PyInstaller one-folder 构建、compileall 语法检查及可执行文件进程启动检查。未跑测试、未完成窗口内操作验收、未调用外部云模型。Inno Setup 编译器未安装，所以没有传统安装器；`installer/windows.iss` 是可选源配置。
- 桌面实现和当前限制详见 `HANDOFF_LOG.md` 最新条目、`README.md` 的 Windows 桌面版说明及 `.tmp/windows-desktop-progress.md`。下一步如需真实云端验收，由用户在桌面应用内自行输入自己的模型凭据；不要将 API Key 复制到聊天或交接文档。
