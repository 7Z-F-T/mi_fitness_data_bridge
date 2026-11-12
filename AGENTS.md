# AGENTS.md — 小米设备数据导出skill（mi_fitness_data_bridge）

> 本文件在原有 9 行工作规则基础上扩展。原有规则仍然有效，保留在「既有工作规则」一节。

## 项目定位

本地优先（local-first）的小米运动健康（Mi Fitness）数据桥接工具：通过非官方/实验性的小米云端适配器读取**用户本人**的健康数据，落本地 SQLite，导出 JSON/CSV 或暴露为 MCP 查询工具。明确不做医疗建议、托管账号访问、多用户云服务。

## 技术栈

- Python ≥ 3.11，hatchling 构建，src 布局 `src/mi_fitness_mcp/`
- 依赖：`mcp>=1.12,<2.0`、`pydantic>=2`、`httpx>=0.27`、`platformdirs`、`keyring>=25`（CLI 用 argparse 实现，无 click/rich）
- 测试：pytest + pytest-asyncio + respx（HTTP mock）；lint：ruff（line-length 100，select E/F/I/N/W/UP/B/C4/SIM，忽略 E501）

## 常用命令

```bash
pip install -e '.[dev]'
pip install -e '.[web]'
python -m pytest -q -p no:cacheprovider
python -m ruff check src tests
mi-fitness-bridge web --host 127.0.0.1 --port 8765
```

## 前端项目（frontend/）

- 技术栈：Vue 3 + TypeScript + Vite，使用 pnpm 管理依赖；命令：`cd frontend && pnpm install && pnpm build`。
- 前端只读本地缓存或导出结果；**不得在浏览器中接收、存储或回传 passToken/user_id 凭证**。账户入口只说明 `mi-fitness-bridge setup` 并链接官方登录页，不抓取登录结果。
- 默认使用合成演示数据并显示“演示数据”标识；连接真实数据需本地 API（查询只读，同步入口为显式 POST；仅监听 `127.0.0.1`），禁止公网部署，且不得引入遥测或第三方分析。

## 本地 Web API（src/mi_fitness_mcp/web/）

- API 只用于本机数据看板：默认 `127.0.0.1:8765`。查询接口仅 GET；同步入口仅 `POST /api/sync`，必须带 `X-Mi-Fitness-Confirm: sync`；PUT/PATCH/DELETE 一律 405，OPTIONS 仅用于本地 CORS 预检。禁止公网部署、托管代理或多用户服务。
- 查询服务必须以 `Database(..., read_only=True)` / `mode=ro` 打开，不得调用写方法或修改缓存。唯一的例外是显式同步动作：它可以创建可写 `Database` 并调用 `SyncService`，但必须使用钥匙串中已有的凭证，不得在 HTTP 请求/响应/日志中接收或回显 passToken。
- 异常类型集中在 `web/exceptions.py`；所有错误返回统一 JSON 信封（`code`/`message`/`requestId`/`details`）并使用标准 HTTP 状态码；不要向客户端泄露 SQL、路径或凭证。
- 同步历史写入 `sync_runs`（分类、开始/结束、状态、计数、来源、error_code）；不得写入异常原文、解密数据或健康数值。
- 响应字段使用 Pydantic camelCase alias，与 `frontend/src/api/types.ts` 对齐；新增/修改字段时同步前端类型、`docs/web-api.md` 和测试。
- API 测试一律使用临时 SQLite + 合成记录（`tests/test_web_api.py`），不得读取真实数据库或发出真实网络请求；同步流程用 fake coordinator/monkeypatch 验证，禁止触发真实小米同步。

## 既有工作规则（原文保留）

- Read `PROJECT_GUIDE.md` and `README.md` before work.
- Use `D:\AIWork\projects\mi_fitness_data_bridge` as the stable path.
- Keep credentials, databases, exports, logs, caches, and personal health data out of Git.
- Do not duplicate this connector inside downstream projects.
- Preserve the experimental/unofficial status and upstream MIT attribution.
- Run `python -m pytest -q -p no:cacheprovider` after changes.

## Text encoding

- Pure Python project: pass `encoding="utf-8"` on every text file read/write and explicit `encoding` on `subprocess` text capture; user health data may contain Chinese.
- Export convention: JSON is UTF-8, CSV is `utf-8-sig` (BOM, so Excel opens Chinese correctly); SQLite stores text natively.

## 本仓库 agent 的搜索范围与要求

- 只允许改动本仓库；**严禁读取、复制、传输任何真实凭证与健康数据**：passToken、SQLite 库、导出文件、日志均不得入库、不得进报告、不得上传到任何第三方（.gitignore 已覆盖 `.env*`、`*.db`、`exports/`、`logs/` 等，不得绕过）。
- 适配器（`adapters/mi_fitness_cloud.py`）只访问用户本人有权访问的账号；任何测试/调试一律用合成数据（`examples/synthetic_demo.py`）或 respx mock，不得对真实小米端点发起探测性请求。
- 保持非官方/实验性定位声明与上游 MIT 归属（THIRD_PARTY_NOTICES.md），不得在 README/文档中弱化这些声明。
- `setup` 只走交互式（getpass 不回显）；`--user-id` / `--pass-token` 命令行旗标已于 2026-08-17 移除（会进 shell 历史），不得在文档/脚本中重新引入。

## 升级建议有效性 / 采纳规则（本仓定制）

1. 凡涉及凭证处理、隐私数据流、MCP 工具暴露面的建议：默认从严，凡扩大凭证/数据暴露面的（如托管代理、共享 token、公网部署）一律**记录不做**（SECURITY.md 已明确超出安全模型）。
2. 适配器协议变更（登录、加密、分页）：必须用 respx mock 补测试，禁止以真实账号请求作为验证手段。
3. 任何引入遥测/上报/联网分析的建议：一律**记录不做**（local-first 定位）。
4. 上游 API 变动导致的修复：属"立即做"（工具会实际失效），修复后同步 README 的实验性声明和 KNOWN_REGIONS。
5. 导出格式/查询能力增强：有效即可排期做，但导出内容不得包含 passToken 等凭证字段。

## 升级建议 backlog

（暂无。近期问题已修复；后续发现按全局规则 `github-project-evaluation/docs/agent-collab-rules.md` 收录。）
