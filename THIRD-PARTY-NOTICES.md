# 第三方内容声明

本仓库以 MIT 许可证发布（见 [`LICENSE`](LICENSE)）。本文件列出仓库内**不属于**上述 MIT 授权范围的第三方内容，以及它们各自的许可证。

这些内容的共同性质：都是**未修改的只读参考快照**，用于设计核对、协议提取和离线评测。它们不是运行时依赖，应用代码不 import、不执行其中的任何文件。快照的抓取时间、提交哈希和逐文件 SHA-256 见 `references/SOURCES.json` 与各目录下的 `SOURCE_MANIFEST.json`；相关策略见 [`references/REFERENCE_POLICY.md`](references/REFERENCE_POLICY.md)。

## 一、`references/upstream/` 中的上游仓库快照

| 目录 | 上游仓库 | 提交 | 许可证 | 快照状态 |
|---|---|---|---|---|
| `chengziyue1222--math-model-agent` | chengziyue1222/math-model-agent | `e7a426008506` | MIT | 完整 |
| `erezweinstein5--eval-layer` | erezweinstein5/eval-layer | `d742197453d8` | **无许可证文件** | 完整 |
| `khoj-ai--openpaper` | khoj-ai/openpaper | `93ad62ffc639` | **AGPL-3.0** | 完整 |
| `ngstcf--agentic-paper-review` | ngstcf/agentic-paper-review | `c117aba2dbb2` | MIT | 完整 |
| `pavelgolikov--arxiv-research-agent` | pavelgolikov/arxiv-research-agent | `3e2b837a5ffd` | MIT | 完整 |
| `ShaishavMaisuria--research-paper-lifecycle-skills` | ShaishavMaisuria/research-paper-lifecycle-skills | `f9a0ed8f0f17` | Apache-2.0 | 完整 |
| `Y-love-han--math-modeling-skill` | Y-love-han/math-modeling-skill | `0a19b18e0345` | MIT | 完整 |
| `YiFraternity--LLM-MM-Agent` | YiFraternity/LLM-MM-Agent | `63fa0abd635d` | **GPL-3.0** | 稀疏（README、许可证、提示词、解析器、基准量表） |
| `yohanchen1--MathModelingAgent` | yohanchen1/MathModelingAgent | `04035453dcab` | MIT | 完整 |
| `zhnnky329--MathModeling-skills` | zhnnky329/MathModeling-skills | `0b46e9c78335` | MIT | 完整 |

各目录内保留了上游原始的 `LICENSE` / `LICENSE.md` 文件，以其为准。

### 需要特别注意的三项

- **`khoj-ai--openpaper`**：AGPL-3.0。AGPL 要求以同许可证分发衍生作品；本仓库将其作为独立、未修改的参考快照收录，并未将其代码并入本项目任何可执行路径。
- **`YiFraternity--LLM-MM-Agent`**：GPL-3.0，同样属于 copyleft，情形同上。
- **`erezweinstein5--eval-layer`**：上游未提供任何许可证文件，按默认规则视为保留所有权利。

以上三点是仓库所有者知情后作出的收录决定。若其中任何一项的许可证要求无法满足，删除 `references/upstream/<目录>` 即可移除对应内容，不影响应用代码（提交历史中该部分与产品代码分离，便于单独回退）。

## 二、`skills/` 中的 skill 包

`skills/` 下是本项目自有的评审与研发 skill 副本，与 `references/` 的外部快照分离（见 [`skills/README.md`](skills/README.md)）。

其中 `skills/upstream-audit/` 的四个子目录同样来自上游，它们的许可证全文不重复存放，直接引用本仓库内已发布的上游快照：

| 目录 | 上游仓库 | 许可证 | 许可证全文位置 |
|---|---|---|---|
| `skills/upstream-audit/MathModelingAgent` | yohanchen1/MathModelingAgent | MIT | `references/upstream/yohanchen1--MathModelingAgent/LICENSE` |
| `skills/upstream-audit/MathModeling-skills` | zhnnky329/MathModeling-skills | MIT | `references/upstream/zhnnky329--MathModeling-skills/LICENSE` |
| `skills/upstream-audit/research-paper-lifecycle-skills` | ShaishavMaisuria/research-paper-lifecycle-skills | Apache-2.0 | `references/upstream/ShaishavMaisuria--research-paper-lifecycle-skills/LICENSE` |
| `skills/upstream-audit/math-model-agent` | chengziyue1222/math-model-agent | MIT | `references/upstream/chengziyue1222--math-model-agent/LICENSE` |

## 三、字体

`skills/shared-scripts/NotoSansSC-Regular.ttf`（10.5MB）是 Noto Sans SC 字体，由 Google / Adobe 的 Noto 项目发布，采用 SIL Open Font License 1.1。

该字体的许可证标识、获取地址和许可要点见 `skills/shared-scripts/LICENSE-NotoSansSC.txt`。

> ⚠️ 已知缺口：`LICENSE-NotoSansSC.txt` 目前是许可证标识与获取途径说明，**不是 SIL OFL 1.1 的全文**。OFL 要求再分发字体时随附许可证全文，正式分发前需从 <https://github.com/notofonts/noto-cjk> 取得 `LICENSE` 并用全文替换该文件。

## 四、量表来源

`rubrics/CUMCM-general-four-dimensions-2026.10-v1.0.json` 的四维评分框架来自 anticipate218/math-modeling-skill 的 `scoring-rubric.md`（MIT），来源提交与哈希记录在该 JSON 的 `provenance` 字段中。四维权重（各 25%）是本项目的本地假设，CUMCM 官方只公布维度、不公布权重，详见该文件内的 `weight_policy` 说明。
