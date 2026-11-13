# 文档索引

> 本仓库是 [`shkyyy18/mi_fitness_data_bridge`](https://github.com/shkyyy18/mi_fitness_data_bridge) 的 fork，在其基础上继续开发。来源、本 fork 的改动、免责声明与许可证见根 README 的 [Fork 说明与免责声明](../README.md#fork-说明与免责声明)。

本仓库的文档按「现行指南 / 设计与参考 / 维护与发布 / 项目级文件 / 历史记录」分类。部署步骤和常用命令优先看根目录 [README.md](../README.md)；本页用于查具体主题。

## 现行指南

| 文档 | 内容 | 何时看 |
| --- | --- | --- |
| [compatibility.md](compatibility.md) | 兼容性证据边界、安全上手、真实账户前提、问题反馈方式 | 首次连接账号前；同步为空或失败时 |
| [web-api.md](web-api.md) | 本地 API 启动、接口、状态码、错误信封、账号选择、同步历史 | 启动 Web 看板或调试前端连接时 |
| [coach.md](coach.md) | 可选 coach：目标、训练档案、计划、AI 数据边界与安全规则 | 使用目标/计划或配置远程 LLM 时 |
| [export-format.md](export-format.md) | JSON 信封、CSV 布局、日期过滤、身体成分单位、睡眠评分来源 | 消费导出文件或排查导出差异时 |
| [mcp-tool-contracts.md](mcp-tool-contracts.md) | MCP 工具契约、副作用、分页、日期/限制/错误语义 | 接入本地 MCP 客户端或新增工具时 |
| [workout-detail-feasibility.md](workout-detail-feasibility.md) | FDS 秒级运动明细协议、支持范围、已知限制 | 使用 `workout_detail` / GPS 轨迹时 |
| [设计手稿.md](设计手稿.md) | 前端三个页面的设计与范围 | 修改 `frontend/` 页面时 |

## 维护与发布

| 文档 | 内容 |
| --- | --- |
| [release-checklist.md](release-checklist.md) | 发布前验证、真实账户试点门槛、发布记录 |

## 设计与参考

| 文档 | 内容 |
| --- | --- |
| [health-assistant/README.md](health-assistant/README.md) | 原 health-assistant 仓库能力的迁移说明；`analytics.py` 与教练/营养方法论文档作为下游参考保留 |
| [assets/README.md](assets/README.md) | 文档截图与演示页资源说明（全部为合成数据） |

## 项目级文件

- [README.md](../README.md) / [README.en.md](../README.en.md)：部署方案与常用命令。
- [AGENTS.md](../AGENTS.md)：仓库工作规则（agent/维护者）。
- [PROJECT_GUIDE.md](../PROJECT_GUIDE.md)：项目范围与工作规则。
- [SECURITY.md](../SECURITY.md)：敏感数据、漏洞上报、coach/LLM 出口边界。
- [CONTRIBUTING.md](../CONTRIBUTING.md)：贡献方式、测试要求、许可。
- [CHANGELOG.md](../CHANGELOG.md)：版本变更记录。
- [LICENSE](../LICENSE)：本 fork 的 AGPL-3.0-only 许可证与上游 MIT 版权声明。
- [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)：Fork 来源链路、上游许可证历史与第三方归属。

## 历史记录

以下文档保留当时的排查过程或决策依据，**不代表当前行为**。现行行为以本页「现行指南」和代码为准。

| 文档 | 内容 |
| --- | --- |
| [issue-14-sleep-score-investigation.md](issue-14-sleep-score-investigation.md) | 睡眠评分缺失排查与本地修复候选（2026-09-21） |
| [mcp-2x-migration-assessment.md](mcp-2x-migration-assessment.md) | MCP 2.x 迁移评估（issue #4） |
| [tdqs-remediation-2026-09-21.md](tdqs-remediation-2026-09-21.md) | TDQS 整改记录与验证证据（2026-09-21） |

## 维护约定

- 新增现行文档时，在上表补一行，并从根 README 的「文档地图」链接过来。
- 历史/一次性排查文档放在「历史记录」区，并在文首加历史提示。
- 文档中的命令必须能从仓库根目录直接执行；示例只使用合成数据。
- 修改许可证或来源说明时，同步更新 `LICENSE`、`THIRD_PARTY_NOTICES.md`、根 README 的 Fork 说明和 `pyproject.toml`。
- 不写入真实凭证、账户标识符、健康数值、数据库路径或个人截图。
