# 数模论文评审工作台前端

React + Vite + Tailwind/daisyUI。开发时默认通过 Vite 代理访问本地 FastAPI `/api`，生产构建由 FastAPI 托管 `frontend/dist`。

界面参考 ruanzhu 用户说明书的深色侧栏、分区面板、详情抽屉与编辑弹窗；业务保留七阶段证据评审。

入口：工作台概览、论文资产、官方评分标准、模型配置、创建评审、评审任务、历史与审计。任务详情并列展示官方评分和通用诊断，并支持证据与建议查看、人工修改和报告下载。

七阶段运行完成停在 EVIDENCE_AUDIT。当前运行器不会自动生成正式官方分数或优化建议；界面显示服务端已有结果和人工结果，缺失时明确显示为空。联网检索、证据审计与仲裁不在本轮实现范围。

模型 URL 为无用户名、密码、查询参数或片段的兼容服务地址。密钥只填写在 API Key 字段。

## 可重复浏览器验收

先构建前端，然后在项目根目录启动隔离夹具：

```powershell
.venv\Scripts\python.exe -m uvicorn tests.browser_fixture:create_fixture --factory --host 127.0.0.1 --port 8027
```

安装或使用已有 Playwright（环境变量 `PLAYWRIGHT_MODULE` 可指定模块路径），运行：

```powershell
node frontend/tests/browser-smoke.cjs
```

默认使用本机 Edge，无头浏览器与合成论文只写入 `.tmp/`。`BROWSER_TEST_URL` 可覆盖夹具地址，`BROWSER_TEST_CHANNEL` 可切换浏览器通道。夹具使用真实 API/SQLite/评审协调器/兼容适配器，云端响应和一条建议为明确的测试数据；不能作为真实模型效果验证。勿在生产运行夹具。
