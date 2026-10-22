# 评审提示词 v0.1

提示词是项目内可审查、可版本化的资产，位于 `config/prompts/v0.1/`。

## 文件结构

- `system.md`：所有评审调用共用的证据、结论、评分和安全约束；
- `stage_common.md`：七阶段公共输入和 `StageResult` JSON 输出格式；
- `stages/*.md`：问题识别、问题表述、假设、模型构造、求解、代码、结果分析七个阶段；
- `evidence_audit.md`：Claim → Obligation → Evidence 审计；
- `arbitration.md`：冲突、反例和证据不足裁决；
- `recommendations.md`：把 finding 转为带验收条件的修改建议。

## 本地渲染

```python
from backend.app.services.prompt_templates import PromptTemplateStore

bundle = PromptTemplateStore().stage_prompt(
    "model_construction",
    paper_context="论文块和题目摘要",
    evidence_catalog="可定位的文档块目录",
    rubric_context="已发布官方量表摘要",
    prior_results="前置阶段 JSON 结果",
)

# bundle.system 作为 system message，bundle.user 作为 user message。
```

渲染器只负责读取和填充模板，不调用模型。模型返回内容必须再经过 `StageResult`、`ReviewResult` 和证据门禁校验；提示词本身不能推进 ReviewJob 状态。
