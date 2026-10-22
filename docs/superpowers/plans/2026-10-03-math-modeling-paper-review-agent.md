# 数学建模论文评价与优化建议智能体 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个本地优先的数学建模竞赛论文评价系统，支持官方量表、通用诊断、证据化建议、联网检索、阶段重跑和强制交接记录。

**Architecture:** FastAPI 后端负责文件解析、量表版本、评审流水线和报告导出；React/Vite 前端负责上传、进度、双评分和建议展示；SQLite 保存任务元数据，本地目录保存文件。模型通过 OpenAI-compatible adapter 调用，外部 skill 通过环境变量加载并建立 registry。

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLModel/SQLite, PyMuPDF, python-docx, React, Vite, TypeScript, Tailwind/daisyUI, pytest, Docker Compose。

**Spec:** `docs/superpowers/specs/2026-10-03-math-modeling-paper-review-agent-design.md`

## Global Constraints

- 首版只面向数学建模竞赛论文。
- 官方评分与通用诊断必须并列输出。
- 所有外部结论必须保存 URL、标题、摘要、检索时间和用途。
- 没有证据定位的结论必须标记为“待人工核实”。
- 默认不执行用户上传代码。
- 每次施工前阅读 `施工必读.md`，每次施工后追加 `HANDOFF_LOG.md`。
- 不得提交 API key、上传论文、用户数据或机器专属绝对路径。
- 本地原生运行优先，Docker 作为可复现打包方式。

## Review Focus

- 评分标准解析错误：导入的官方量表必须在发布前可编辑确认；测试覆盖 PDF/DOCX/Markdown/JSON。
- 证据漂移：页码、段落和代码行定位不能因报告重排而丢失；测试空证据和越界定位。
- 双评分混算：官方评分与通用诊断必须有不同字段和不同展示；测试量表切换。
- 模型输出失控：非法 JSON、缺字段、无证据结论必须进入失败或人工核实状态。
- 交接缺失：变更检查脚本必须能拒绝没有完整交接条目的提交。

---

### Task 1: 项目治理、设计资料与 skill registry

**Files:**
- Create: `施工必读.md`, `HANDOFF_LOG.md`, `CONTRIBUTING.md`
- Create: `docs/skill-inventory.md`, `config/skill_registry.yaml`
- Create: `scripts/build_skill_registry.py`, `scripts/check_handoff.py`

**Interfaces:**
- `build_skill_registry.py --root PATH --output config/skill_registry.yaml` 扫描所有 `SKILL.md`，输出路径、名称、SHA-256、类别和变体。
- `check_handoff.py --base REF` 检查工作树变更和最新交接条目，缺少时间、目标、文件、验证、风险或下一步时退出码为 1。

- [ ] 写 registry 单元测试：扫描临时目录中的两个 skill，验证名称、哈希和变体字段。
- [ ] 写 handoff 检查测试：完整记录通过；缺少验证字段失败；仅修改日志文件时仍要求时间和目标。
- [ ] 运行 `python -m pytest tests/test_governance.py -q`，预期初始失败。
- [ ] 实现扫描和检查脚本，再运行同一命令，预期通过。
- [ ] 从 `E:\Modex-MH-Agent-Portable\OpenAgent-skills-plain` 生成 127 个源条目的 registry，并记录外部路径为配置值。

### Task 2: 后端骨架与配置

**Files:**
- Create: `backend/app/main.py`, `backend/app/settings.py`, `backend/app/db.py`
- Create: `backend/requirements.txt`, `pyproject.toml`, `.env.example`
- Create: `tests/test_health.py`

**Interfaces:**
- `GET /health` 返回 `{"status":"ok","timezone":"Asia/Shanghai"}`。
- `Settings` 暴露 `openai_compatible_base_url`, `openai_compatible_api_key`, `openai_compatible_model`, `openagent_skills_root`, `search_base_url`, `data_dir`, `app_timezone`。

- [ ] 先写健康检查和默认配置测试并确认失败。
- [ ] 实现 FastAPI 应用、环境配置、SQLite 初始化和 `/health`。
- [ ] 运行 `python -m pytest tests/test_health.py -q`，预期通过。

### Task 3: 资产解析与证据定位

**Files:**
- Create: `backend/app/domain/assets.py`, `backend/app/services/asset_inventory.py`
- Create: `backend/app/services/parsers/pdf_parser.py`, `docx_parser.py`, `markdown_parser.py`
- Create: `tests/fixtures/sample.md`, `tests/test_asset_inventory.py`

**Interfaces:**
- `AssetInventory.inspect(path: Path) -> Asset`。
- `ParsedDocument.blocks: list[DocumentBlock]`；每个 block 包含 `block_id`, `text`, `page`, `paragraph`, `line_start`, `line_end`。
- 解析失败返回 `status="failed"` 和可读错误，不抛出未处理异常。

- [ ] 写 Markdown 解析、未知扩展名和空文件测试并确认失败。
- [ ] 实现 SHA-256、MIME 判断、PDF/DOCX/Markdown 解析和证据块编号。
- [ ] 运行 `python -m pytest tests/test_asset_inventory.py -q`，预期通过。

### Task 4: 官方评分标准导入与版本化

**Files:**
- Create: `backend/app/domain/rubrics.py`
- Create: `backend/app/services/rubric_importer.py`
- Create: `backend/app/api/rubrics.py`
- Create: `tests/test_rubric_import.py`

**Interfaces:**
- `import_rubric(asset: Asset) -> RubricDraft`。
- `publish_rubric(draft_id: str) -> RubricProfile`。
- `POST /api/v1/rubrics/import` 接受 multipart 文件并返回草稿。
- `POST /api/v1/rubrics/{id}/publish` 返回已发布版本。
- `GET /api/v1/rubrics` 返回版本列表。

- [ ] 写 JSON 直读、Markdown 表格、缺失权重和发布前不可用测试并确认失败。
- [ ] 实现四类文件解析、字段校验、解析警告、预览草稿和发布版本。
- [ ] 运行 `python -m pytest tests/test_rubric_import.py -q`，预期通过。

### Task 5: OpenAI-compatible 模型与联网检索适配器

**Files:**
- Create: `backend/app/services/llm_client.py`, `backend/app/services/search_provider.py`
- Create: `backend/app/domain/model_outputs.py`
- Create: `tests/test_llm_schema.py`, `tests/test_search_provider.py`

**Interfaces:**
- `LLMClient.complete_json(prompt: str, schema: dict) -> dict`。
- `SearchProvider.search(query: str, limit: int) -> list[SearchResult]`。
- `SearchResult` 必须包含 `url`, `title`, `snippet`, `retrieved_at`, `purpose`。

- [ ] 写非法 JSON、缺字段、搜索端点超时和空结果测试并确认失败。
- [ ] 实现 schema 校验、有限重试、超时、脱敏日志和可选搜索端点。
- [ ] 运行 `python -m pytest tests/test_llm_schema.py tests/test_search_provider.py -q`，预期通过。

### Task 6: 阶段化评审流水线

**Files:**
- Create: `backend/app/domain/reviews.py`, `backend/app/domain/evaluations.py`
- Create: `backend/app/services/pipeline/asset_inventory.py`
- Create: `backend/app/services/pipeline/problem_parser.py`
- Create: `backend/app/services/pipeline/stage_evaluators.py`
- Create: `backend/app/services/pipeline/code_data_auditor.py`
- Create: `backend/app/services/pipeline/logic_adversarial_review.py`
- Create: `backend/app/services/pipeline/evidence_mapper.py`
- Create: `backend/app/services/pipeline/recommendation_generator.py`
- Create: `backend/app/services/pipeline/report_builder.py`
- Create: `tests/test_evaluation_pipeline.py`

**Interfaces:**
- `run_review(job: ReviewJob) -> ReviewResult`。
- `run_stage(job_id: str, stage: str) -> StageResult`。
- `diagnostic_score(scores: list[CriterionScore]) -> float` 使用规格中的七维权重。
- `readiness_status(findings: list[Finding]) -> Literal["blocked","needs_major_fixes","reviewable"]`。

- [ ] 写固定样例论文的阶段覆盖、证据缺失、严重度和分数计算测试并确认失败。
- [ ] 实现七阶段评价、可选静态代码/数据审计、逻辑复核、证据绑定和建议生成。
- [ ] 实现 `fatal`/`major`/`minor` 状态规则，保证分数与状态独立。
- [ ] 运行 `python -m pytest tests/test_evaluation_pipeline.py -q`，预期通过。

### Task 7: Review API 与报告导出

**Files:**
- Create: `backend/app/api/reviews.py`, `backend/app/api/reports.py`
- Modify: `backend/app/main.py`
- Create: `tests/test_review_api.py`

**Interfaces:**
- `POST /api/v1/reviews` 创建任务并绑定资产与 `rubric_profile_id`。
- `GET /api/v1/reviews/{id}` 返回阶段状态、官方评分、诊断评分和建议。
- `POST /api/v1/reviews/{id}/rerun` 只重跑指定阶段。
- `GET /api/v1/reviews/{id}/report?format=md|json` 导出报告。

- [ ] 写创建、查询、重跑、Markdown 导出和 JSON 导出测试并确认失败。
- [ ] 实现 API、任务持久化、后台任务状态和报告导出。
- [ ] 运行 `python -m pytest tests/test_review_api.py -q`，预期通过。

### Task 8: React/Vite 前端

**Files:**
- Create: `frontend/package.json`, `frontend/index.html`
- Create: `frontend/src/App.tsx`, `frontend/src/api.ts`, `frontend/src/types.ts`
- Create: `frontend/src/components/UploadPanel.tsx`, `RubricPanel.tsx`, `ReviewProgress.tsx`, `ScorePanels.tsx`, `FindingsList.tsx`

**Interfaces:**
- 前端只调用后端公共 API，不复制评审逻辑。
- `ReviewProgress` 展示阶段状态；`ScorePanels` 并列展示官方评分和通用诊断；`FindingsList` 展示证据和建议。

- [ ] 写 API client 类型和基础页面渲染测试。
- [ ] 实现上传、量表预览、任务进度、双评分、证据和建议页面。
- [ ] 运行 `npm run build`，预期成功。

### Task 9: 原生启动、Docker 与完整测试

**Files:**
- Create: `scripts/dev.ps1`, `docker-compose.yml`, `Dockerfile.backend`, `Dockerfile.frontend`
- Create: `tests/test_end_to_end.py`, `RUN.md`, `TEST_REPORT.md`

- [ ] 添加原生启动说明和 Docker Compose 健康检查。
- [ ] 用固定样例跑导入→发布→评审→双报告→阶段重跑。
- [ ] 运行后端 pytest、前端 `npm run build`、短时 uvicorn 探活和 Docker 配置检查。
- [ ] 将每项结果如实写入 `TEST_REPORT.md`，不得伪造通过。
- [ ] 追加交接日志并运行 `python scripts/check_handoff.py`。

### Task 10: Git 初始化与私有 GitHub 仓库

**Files:**
- Modify: `.gitignore`, `README.md`, `HANDOFF_LOG.md`

- [ ] 确认没有密钥、用户文件、数据库和构建产物进入 Git。
- [ ] 运行 `gh auth status`；若 token 无效，执行 `gh auth login -h github.com`。
- [ ] 初始化 Git，提交设计、代码、测试和文档。
- [ ] 执行 `gh repo create dessert28/math-modeling-paper-review-agent --private --source . --remote origin --push`。
- [ ] 用 `git remote -v`、`gh repo view --json name,isPrivate,url` 验证私有仓库和远程地址。
- [ ] 将仓库 URL、提交哈希和推送结果追加到 `HANDOFF_LOG.md`。

## 验收标准

- 能上传 PDF、DOCX、Markdown 并获得稳定的证据块定位。
- 能导入官方评分标准，编辑预览后发布版本并绑定评审任务。
- 官方评分和通用诊断始终分开保存、分开展示、分开导出。
- 至少一个固定样例能完成全流程并输出 Markdown 与 JSON。
- 非法模型输出、检索失败、证据缺失和解析失败均有可读状态。
- 原生启动、Docker 配置、后端测试和前端构建均有可复现命令。
- 交接检查能阻止缺少必填字段的施工记录。
- GitHub 仓库为私有，且提交不包含任何凭据或用户材料。
