# OpenAI-compatible 模型适配器 v0.1

实现位于 `backend/app/services/llm_adapter.py`，只负责调用兼容 OpenAI Chat Completions 的接口并把返回 JSON 校验为 Pydantic 对象。

配置：

```dotenv
OPENAI_COMPATIBLE_BASE_URL=http://127.0.0.1:11434/v1
OPENAI_COMPATIBLE_API_KEY=
OPENAI_COMPATIBLE_MODEL=qwen2.5:14b
LLM_TIMEOUT_SECONDS=60
LLM_MAX_RETRIES=2
LLM_RETRY_BACKOFF_SECONDS=1
```

调用七阶段：

```python
from backend.app.services.llm_adapter import OpenAICompatibleAdapter
from backend.app.settings import Settings

adapter = OpenAICompatibleAdapter(Settings())
stage_result, metadata = adapter.evaluate_stage(
    "problem_identification",
    paper_context=paper_context,
    evidence_catalog=evidence_catalog,
)
```

适配器会：

- 发送 `response_format: {"type": "json_object"}`；
- 对超时、网络错误、429 和 5xx 做有限重试；
- 清除 Markdown 代码围栏后解析 JSON；
- 用 `StageResult` 或调用方指定的 Pydantic 模型校验；
- 错误信息不包含 API key 或完整模型响应；
- 不启用 tools/function calling，不执行上传代码，不推进 ReviewJob 状态。
