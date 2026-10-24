# 会话交接总览

> 更新时间：2026-10-24（Asia/Shanghai；精确时间见 `HANDOFF_LOG.md` 最新条目）  
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

## 3. 技术栈

- 运行时：Python ≥ 3.11（本机开发用仓库内 `.venv`，隔离虚拟环境打包桌面版）；Node.js（前端 Vite 构建与 `node --test` 测试）。
- 后端：FastAPI（≥0.115，同步路由）+ Pydantic v2 + pydantic-settings + SQLAlchemy 2.0（SQLite，同步，NullPool）+ Uvicorn；无迁移工具，`db.py` 的 `init_db` 直接建表。
- 文档解析：PyMuPDF（PDF）、python-docx（DOCX）、内置 Markdown 解析器（保留标题/段落/表格/代码围栏行号）。
- 模型接入：任意 OpenAI-compatible 端点（httpx，超时/重试可配）；API Key 用 Fernet（cryptography）加密入库，主密钥在 `DATA_DIR/.model-config.key`，不得进入 Git。
- 配置与协议：PyYAML 读取 `config/default_rubric.yaml`（七阶段与权重）、`config/state_machine.yaml`（生命周期与门禁）、`config/agent_roles.yaml`、`config/skill_registry.yaml`；提示词模板在 `config/prompts/`。
- 前端：React 18.3.1 + Vite 5.4.10 + Tailwind CSS 3.4.14 + daisyUI 4.12.24，Hash 路由，无其他 UI 框架；`npm run build` 后由 FastAPI 同源托管 `frontend/dist`，无 `dist` 时回退 `frontend/static/index.html`。
- 桌面端：pywebview（依赖 Windows Edge WebView2 Runtime）+ PyInstaller 6 one-folder 打包；可选 Inno Setup 安装器（`installer/windows.iss`）；数据存 `%LOCALAPPDATA%\MathModelingPaperReview\data`，服务仅监听 127.0.0.1，每次启动生成 API 会话令牌。
- 测试：pytest（`tests/` 24 个后端测试文件）+ `node --test`（`frontend/tests/*.test.mjs`）；浏览器闭环验收用 Edge 无头 + `tests/browser_fixture.py` 合成夹具（非真实模型）。
- 环境变量：见 `.env.example`（`DATA_DIR`、`OPENAI_COMPATIBLE_*`、`OPENAGENT_SKILLS_ROOT`、`LLM_TIMEOUT_SECONDS`、`MAX_UPLOAD_BYTES` 等）。
- 第三方只读参考：`references/upstream/` 10 个上游项目快照（不 import、不执行，`references/_tools/verify_snapshots.py` 核 1411 个哈希）；`skills/` 34 个 skill 副本，经 `OPENAGENT_SKILLS_ROOT` 读取。

## 4. 前端页面与本地运行

工作台包括：概览、模型配置、论文资产、官方评分标准、创建评审、任务进度/详情、结果与建议、历史与审计。支持桌面布局、窄屏导航、抽屉与可键盘关闭的弹窗。

当前本机已启动原生工作台：`http://127.0.0.1:8010/#/overview`。如服务停止，可在项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8010
```

如需开发模式，查看 `scripts/dev.ps1` 与 `frontend/RUN.md`。前端构建：

```powershell
npm run build --prefix frontend
```

一键启动（推荐）：双击/命令行运行根目录 `start-workbench.cmd`（支持 `/port <n>`、`/dev`、`/rebuild` 参数；自动拉起前后端并打开浏览器 `/#/overview`；2026-10-24 实测通过）。

## 5. 验收证据与其边界

最近一次交接记录的验证结果：

- `npm run build --prefix frontend` 成功，46 个模块；
- `npm run test --prefix frontend` 成功，8 项；
- 后端全量测试：232 passed（含 2026-10-24 真实模型调试新增 2 例 reasoning 回退用例 + 失败诊断断言增强），仅 1 个既有 Starlette 弃用警告（及 .pytest_cache ACL 写入警告，属环境问题非测试失败）；
- `python -m compileall -q backend` 成功；
- 上游快照校验通过：10 个快照、1411 个哈希；
- 多智能体辩论评审验收：迭代 1–4 专项测试全绿（领域模型、聚合、面板、提示词、debate_snapshot 持久化、引擎 20 例、API 15 例、运行器集成 10 例），已并入上述全量；
- 使用本地合成兼容模型和合成数据完成两轮 Edge 无头浏览器闭环验收；运行产物位于被忽略的 `.tmp/browser-acceptance/`。
- 真实模型（用户端点 `zjsru-DeepSeek-V4-flash-0731`）已配置并实测：模型在线时成功按 12 万字符论文上下文输出结构化意见（3 条 MAJOR，引用真实证据 ID）；模型下线后端点返回 `404 model_not_found`（用户侧推理服务状态）。

这些结果证明本地接口/页面交互路径可用。真实模型侧：用户的 OpenAI-compatible 端点已配置进数据库（custom 服务商，`zjsru-DeepSeek-V4-flash-0731`，测试连接通过），且真实论文（`review-26c257991fc042a7807c53882e4eadd6`）上完成了端到端调试；2026-10-24 已修复真实模型暴露的全部 4 个代码缺陷（上下文接线、证据 ID 空间对齐、dict 形态 stage_results、reasoning 字段读取），但用户端点模型当前离线，尚缺一次辩论 COMPLETED 快照。

## 6. 已知未完成功能与风险

1. 七阶段运行器目前不自动生成正式官方评分和优化建议；页面展示的是服务端已有数据，不以演示样例填充空结果。
2. 正式 Evidence Audit、冲突仲裁、联网检索/来源保存仍未实现；七阶段全部结束后应显示“待证据审计”。
3. 运行器使用进程内线程池；并发多进程部署需单进程约束或后续改用持久化队列/锁。
4. 主密钥文件需要用户备份；密钥丢失会使已有 API Key 无法解密。
5. Docker 可复现打包尚未完成。Git 已初始化，仓库已公开推送到 `https://github.com/dessert28/Evaluation-of-Mathematical-Modeling-Papers`（`main` 分支，MIT 许可证）。
6. 真实云 API 已实测（用户端点，2026-10-24）：该模型为 reasoning 型（最终答案常放 `message.reasoning`、`content` 为空，已兼容）；大上下文（≈12 万字符论文）单次生成需数分钟，`.env` 已把 `LLM_TIMEOUT_SECONDS` 提到 300；端点稳定性取决于用户主机（曾 502/断连/404 model_not_found）。
7. 没有经过真实评审案例校准七阶段评分的稳定性和准确性。
8. 多智能体辩论（v0.1）代码侧已用真实论文完成调试（2026-10-24，修复 4 个缺陷，见 `HANDOFF_LOG.md` 最新条目），待用户模型恢复在线后跑一次 COMPLETED 辩论完成端到端验收；面板权重、阈值与轮数仍为 v0.1 默认值，需真实辩论校准。
9. 环境：`.pytest_tmp`、`.pytest-local`、`.pytest_cache`、`.tmp\pytest-of-*` 为 NTFS ACL 锁定目录（Everyone DENY，当前用户亦不可读写删），修复需管理员 PowerShell（`takeown /f <路径> /r /d Y` + icacls 授权后删除）；期间跑测试一律用独立 basetemp（如 `--basetemp .pytest_tmp_lead`），详见 `.acl-reports/`。

## 7. 下一会话建议顺序

1. 先阅读根目录 `施工必读.md`、`HANDOFF_LOG.md`、本文件、`docs/contracts/review-protocol-v0.1.md` 和 `docs/contracts/frontend-workbench.md`；施工前确认这次范围并追加日志。
2. 启动或确认本地服务 `http://127.0.0.1:8010/#/overview` 可访问。
3. 用户自行在模型配置页填写 OpenAI-compatible 服务商、URL、API Key、模型名并测试连接。不要把 API Key 放入聊天、日志或交接文档。
4. 用无敏感内容的样例论文和已确认量表跑一次真实模型端到端；检查超时/重试、模型结构化输出、证据块定位、阶段失败后的任务状态与报告。清楚区分模拟结果和真实模型结果。
5. 根据真实运行暴露的问题修复，再决定先做 Evidence Audit/建议评分，还是先做 Docker 复现；不应宣称评审闭环已完成，除非证据审计和实际结果路径都落地。
6. GitHub 发布已完成（2026-10-22）：本地 Git 已初始化，公开仓库 `dessert28/Evaluation-of-Mathematical-Modeling-Papers` 已推送。后续提交前仍需检查忽略文件/密钥/用户数据；注意本机 ssh 在当前宿主环境不可用，推送走 HTTPS + gh token。
7. 每次施工都更新 `HANDOFF_LOG.md`，并依次执行相关测试、构建、快照核验和交接检查。

## 8. 关键文件索引

- 施工规则：`施工必读.md`
- 追加式逐次记录：`HANDOFF_LOG.md`
- 产品运行说明：`README.md`、`frontend/RUN.md`
- 评审协议：`docs/contracts/review-protocol-v0.1.md`
- 前端交互与接口契约：`docs/contracts/frontend-workbench.md`
- 一键启动脚本：`start-workbench.cmd`
- 后端 API：`backend/app/api/`
- 评审阶段编排与运行器：`backend/app/services/automatic_runner.py`、`backend/app/services/stage_orchestrator.py`
- 模型配置与加密：`backend/app/services/model_config.py`、`backend/app/api/model_config.py`
- 前端主应用与 API：`frontend/src/App.jsx`、`frontend/src/api.js`、`frontend/src/pages/`
- 本地浏览器合成验收夹具：`tests/browser_fixture.py`、`frontend/browser-smoke.cjs`（只用于测试，非真实模型）
- 交接检查：`scripts/check_handoff.py`

## 9. 仓库/凭据状态

- 本地已是 Git 仓库，分支 `main`，仓库级身份为 `dessert28 <dessert28@users.noreply.github.com>`。
- 公开远端：`https://github.com/dessert28/Evaluation-of-Mathematical-Modeling-Papers`（PUBLIC，MIT 许可证）。
- 本机全局 git 配置有 `url.git@github.com:.insteadOf=https://github.com/` 改写，仓库内实际可达的推送方式是 HTTPS + gh token；直接 `git push` 会走 ssh 并在当前宿主环境失败，详见 `HANDOFF_LOG.md` 最新条目。
- `.gitignore` 把应用目录锚定到仓库根（`/dist/`、`/build/`、`/reports/` 等），以便 `references/upstream/` 下的同名目录能正常入库。
- 入库内容：产品代码与文档 133 个文件，上游参考快照与 skill 包 1563 个文件，合计 1700 个文件、约 26 MB。`references/` 与 `skills/` 单独成一次提交，便于按许可证要求整体移除。
- 未入库内容：`data/`（含真实论文、`app.db`、加密 API Key 与本地主密钥）、`ruanzhu/`、`ruanzhu.zip`、`.env`、`.venv/`、`node_modules/`、`dist/`、`build/`、`.tmp/`、测试临时目录。
- 模型密钥仍未配置进 Git，交接文档不保存密钥。不要把 `.env`、`DATA_DIR`、SQLite 数据库、主密钥、论文资产、`node_modules` 或浏览器测试输出提交。

## 10. Windows 桌面端（2026-10-07）

- 已新增 pywebview + FastAPI Windows 桌面启动器、首次新建/迁移工作区流程、每次启动的 API 会话令牌，以及 PyInstaller 打包配置。桌面数据保存在 `%LOCALAPPDATA%\MathModelingPaperReview\data`，服务仅监听 `127.0.0.1`；云模型仍由“模型配置”页面设置，当前没有用户凭据。
- 可分发包：`dist/MathModelingPaperReview-0.1.0-windows-x64.zip`；解压后运行 `MathModelingPaperReview\MathModelingPaperReview.exe`。ZIP 为 51,921,375 字节，SHA-256：`3F939C076C23C658077842D7E8F1908CAFD8488193073C9551C888F1EA022F29`。运行依赖 Microsoft Edge WebView2 Runtime。
- 已完成 Vite 构建、干净隔离 Python 环境下 PyInstaller one-folder 构建、compileall 语法检查及可执行文件进程启动检查。未跑测试、未完成窗口内操作验收、未调用外部云模型。Inno Setup 编译器未安装，所以没有传统安装器；`installer/windows.iss` 是可选源配置。
- 桌面实现和当前限制详见 `HANDOFF_LOG.md` 最新条目、`README.md` 的 Windows 桌面版说明及 `.tmp/windows-desktop-progress.md`。下一步如需真实云端验收，由用户在桌面应用内自行输入自己的模型凭据；不要将 API Key 复制到聊天或交接文档。

## 11. 多智能体辩论评审（已完成，2026-10-22）

- 目标：在七阶段确定性评审之上增加“评审委员会”——每轮多位专家独立出意见 → 结构化辩论（AGREE/QUALIFY/DISAGREE/REFUTE/WITHDRAW）→ 多轮收敛 → 确定性加权投票；保留证据锚定与状态机门禁。
- 设计文档：`docs/superpowers/specs/2026-10-22-multi-agent-debate-review-design.md`；协议：`docs/contracts/debate-protocol-v0.1.md`；面板配置：`config/debate.yaml`（默认 5 专家、2 轮、收敛阈值 0.8）。
- 迭代进度（0–5 全部完成）：迭代 0 文档与契约；迭代 1 `backend/app/domain/debate.py`（领域模型 + 聚合纯函数）；迭代 2a `backend/app/db.py` 的 `review_jobs.debate_snapshot` JSON 列、`PromptTemplateStore.debate_prompt`、`config/prompts/v0.1/debate/*.md`、`backend/app/services/debate_panel.py`；迭代 2b `backend/app/services/debate_engine.py`（DebateService + DebateRunManager）；迭代 3 API（`reviews.py` 三个 debate endpoint）+ 运行器集成（`review_run_manager.py`，七阶段后、EVIDENCE_AUDIT 前）+ `main.py` 接线 + `stage_orchestrator.py` stage 重跑置 stale；迭代 4 `frontend/src/components/DebateTimeline.jsx` + `api.js` + `ReviewDetail.jsx` 挂载；迭代 5 全量验证与交接。
- 运行方式：辩论在七阶段全部完成后自动触发（`job.options["debate"]["enabled"]` 默认 true，可置 false 关闭）；也可在任务详情页“运行辩论”手动触发；失败不阻塞评审（run 标 DEGRADED 但继续进入 EVIDENCE_AUDIT）。
- 关键边界（v0.1）：辩论只产出意见与投票，不新增证据、不改七阶段分数与双轨；无 LLM 主席（纯确定性聚合）；辩论数据存 `review_jobs.debate_snapshot`，不进 3 秒轮询响应；匿名专家 id；错误用安全短语、不泄露模型端点/密钥/论文全文。
- 验收：后端全量 232 passed（含辩论模块 98 例 + 2026-10-24 调试新增 2 例）；前端测试 8/8、构建 46 modules；`compileall` 通过。
- 真实模型调试（2026-10-24，用户端点 `zjsru-DeepSeek-V4-flash-0731`）：定位并修复 4 个代码缺陷——① `main.py` 未给 `DebateService` 接 `context_builder`（辩论上下文全为占位符）；② 证据目录误用资产 block ID（与引擎 `known` 证据 ID 空间不一致，全部意见 `invalid_evidence`），已改为该任务 `stage_results` 的 153 个真实证据 ID，双向对齐验证通过；③ `stage_results` 真实 DB 为 dict 形态导致 `_collect_evidence_ids` 崩溃被吞（「202 后永远 404」），已做 list/dict 归一；④ reasoning 模型把答案放 `message.reasoning` 而 `content` 为空，适配器已回退读取。另加 `.env`（gitignored）把 LLM 超时提到 300 秒，并为失败快照增加 `last_error.details.rejected_codes` 分诊字段（单测覆盖）。模型在线时已验证能产出结构化意见（3 条 MAJOR，真实证据 ID）；模型离线时端点 `404 model_not_found`。
- 尚未完成：用户模型恢复在线后的端到端 COMPLETED 辩论验收（预期 round0 意见 → 消息轮 → 加权投票 → `outcome.converged`）；阈值与轮数未经真实论文校准（为 v0.1 默认值）。
- 环境注意：`.pytest_tmp`、`.pytest-local`、`.pytest_cache`、`.tmp\pytest-of-*` 为 NTFS ACL 锁定目录（Everyone DENY），跑测试请用独立 basetemp（如 `--basetemp .pytest_tmp_lead`）；修复需管理员 PowerShell（`takeown /f <路径> /r /d Y` + icacls 授权后删除），详见 `.acl-reports/`。
