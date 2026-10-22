# 外部参考快照策略

本目录的 `upstream/` 保存联网检索得到的公开项目快照，仅用于设计核对、协议提取和离线评测，不作为运行时依赖，也不执行其中的代码。

## 固定规则

1. 每个项目必须有 `SOURCE_MANIFEST.json`，记录仓库 URL、提交、抓取时间、文件哈希、状态和许可证文件。
2. 参考快照与 `skills/` 下的运行时 skill 副本分离。只有经过本项目适配、许可证核查和测试的内容，才能进入运行时 registry。
3. 不把外部项目的 API 密钥、用户论文、机器绝对路径或运行时缓存复制进本项目。
4. 许可证文本随快照保留；在产品化复用前必须再次核对上游许可证、依赖许可证和本项目的分发方式。
5. 不能完整获取的仓库要记录失败原因；可复用的稀疏文件必须标记为 `downloaded_sparse`，不能伪装成完整快照。

## 本次快照

候选项目清单和每个文件的 SHA-256 位于 [`SOURCES.json`](SOURCES.json)。本次包括 MathModelingAgent、MathModeling-skills、LLM-MM-Agent、Agentic Paper Review、arxiv-research-agent、OpenPaper、verify-claims、eval-layer、math-modeling-skill 和 math-model-agent。

LLM-MM-Agent 的完整压缩包超过抓取工具的 100 MB 上限，因此只保存了 README、许可证、评测提示词、解析器和基准量表；详见其 `SOURCE_MANIFEST.json`。

