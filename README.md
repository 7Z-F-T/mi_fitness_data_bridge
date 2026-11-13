> English: [README.en.md](README.en.md)

# 小米设备数据导出skill（Mi Fitness Data Bridge）

[![Glama score（上游条目）](https://glama.ai/mcp/servers/shkyyy18/mi_fitness_data_bridge/badges/score.svg)](https://glama.ai/mcp/servers/shkyyy18/mi_fitness_data_bridge)

**把本人小米运动健康（Mi Fitness）数据同步到本机 SQLite，导出 JSON/CSV，或通过本地 MCP / Web 看板查询。** 仅用于个人备份与分析；实际可用数据取决于设备、账户地区和上游服务。

> **非官方、实验性。** 本项目与小米没有隶属、背书或支持关系。适配器依赖非公开上游接口，登录、连接或某些数据类型可能随小米服务、账户地区、设备、固件或认证方式变化而失效。仅可用于你有权访问的账户和数据。

> **Fork 说明：** 本仓库是 [`shkyyy18/mi_fitness_data_bridge`](https://github.com/shkyyy18/mi_fitness_data_bridge) 的 fork，在其基础上继续开发，不是上游官方版本。来源链路、本 fork 的改动、免责声明与许可证见 [Fork 说明与免责声明](#fork-说明与免责声明)。

不想连接账号？打开[上游项目的合成数据演示](https://shkyyy18.github.io/mi_fitness_data_bridge/)，或安装后运行 `python examples/synthetic_demo.py`；两者都不需要账号或凭证，本地脚本也不访问网络。

## 部署方案

本项目只支持**本机、单用户**部署，不支持公网部署、托管账号、共享凭证或多用户服务。按用途选择：

| 形态 | 安装 | 入口 | 适用 |
| --- | --- | --- | --- |
| CLI 同步与导出 | `pip install -e .` | `mi-fitness-bridge sync/export` | 备份、CSV/JSON、脚本 |
| 本地 MCP | `pip install -e .` | `mi-fitness-bridge serve` | 本机 MCP / AI 客户端 |
| 本地 Web 看板 | `pip install -e '.[web]'` + 前端 | `mi-fitness-bridge web` + `pnpm dev` | 浏览器分析 |
| 可选 coach | `pip install -e '.[coach]'`；同时用 Web 时装 `'.[coach,web]'` | `mi-fitness-bridge coach ...` | 目标、训练档案、计划 |

### 最短路径（CLI + Web 看板）

```bash
# 1. 安装（在仓库根目录）
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS / Linux:      source .venv/bin/activate
pip install -e '.[web]'

# 2. 配置账号并首次同步
mi-fitness-bridge setup
mi-fitness-bridge doctor
mi-fitness-bridge sync --start-date 2026-07-01 --end-date 2026-07-15

# 3. 启动本地 API（保持运行）
mi-fitness-bridge web --host 127.0.0.1 --port 8765

# 4. 另开一个终端启动前端
cd frontend
corepack enable        # 首次使用 pnpm 时
pnpm install
cp .env.example .env.local
pnpm dev               # http://127.0.0.1:5173
```

`.env.example` 已指向 `http://127.0.0.1:8765/api`。改完 `.env.local` 后必须重启 `pnpm dev`，否则前端仍使用合成演示数据。

## 从零部署

### 1. 环境要求

- Python **3.11+**
- Git
- 仅 Web 看板需要：Node.js **20.19+**（或 22.12+）、pnpm（推荐 `corepack enable`）

### 2. 安装

```bash
git clone https://github.com/7Z-F-T/mi_fitness_data_bridge.git
cd mi_fitness_data_bridge
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e .
```

macOS / Linux：

```bash
source .venv/bin/activate
pip install -e .
```

按用途选择 extras：

```bash
pip install -e '.[web]'          # 本地 API（FastAPI + uvicorn）
pip install -e '.[coach]'        # coach；不装 AI SDK 也可用本地目标与模板计划
pip install -e '.[coach,web]'    # coach + 本地 API
pip install -e '.[dev]'          # 开发、测试、构建
```

主命令为 `mi-fitness-bridge`；旧命令 `mi-fitness-mcp` 保留为兼容别名。

### 3. 配置账号（一次性）

```bash
mi-fitness-bridge setup    # 交互输入 user_id、passToken、region（默认 cn）
mi-fitness-bridge doctor   # 检查配置、凭证、数据库；有凭证时测试云端连通
```

- `passToken` 只在交互式提示中读取，**不接受命令行参数**；凭证保存到操作系统钥匙串。
- 默认云端地区为 `cn`；这只是默认路由，不是设备或地区兼容性保证。
- `doctor` 的云端检查可能因网络或上游变化失败；本地数据、导出和 Web 查询仍可离线使用。
- 数据库路径优先级：`--db` > `MI_FITNESS_DB_PATH` > 配置/默认路径。`sync`、`export`、`serve`、`doctor`、`web` 都支持 `--db`。
- 还没有可用的 `user_id` / `passToken`，或不确定设备/地区是否可用？先读[兼容性与安全上手](docs/compatibility.md)。

### 4. 首次同步与导出

```bash
# 推荐首次使用显式日期范围
mi-fitness-bridge sync --start-date 2026-07-01 --end-date 2026-07-15

# 只同步一种类型
mi-fitness-bridge sync --type sleep --start-date 2026-07-01 --end-date 2026-07-15

# 之后不写日期：按上次同步水位增量同步（无水位时使用默认回看窗口）
mi-fitness-bridge sync

# 忽略水位完整重拉；仍受显式日期或默认回看窗口限制
mi-fitness-bridge sync --full
```

`--type` 可选：`daily_activity`、`heart_rate`、`body_measurements`、`sleep`、`workouts`、`workout_detail`、`spo2`、`stress`、`abnormal_heart_beat`。重复同步同一范围是幂等的，不会复制已有记录。

**升级代码后**：先重新同步受影响的数据类型，再导出；重启已有的 MCP 和 Web API 进程。初始化会自动补列，**不要删除数据库**。睡眠评分补取的细节见[兼容性说明](docs/compatibility.md)。

导出：

```bash
# 一个 JSON 文件
mi-fitness-bridge export --format json --output exports/mi_fitness.json

# 每个数据集一个 CSV 文件
mi-fitness-bridge export --format csv --output exports/csv

# 按数据集和日期筛选
mi-fitness-bridge export --format json --type sleep \
  --start-date 2026-07-01 --end-date 2026-07-15 \
  --output exports/sleep.json
```

日期使用 `YYYY-MM-DD`，开始日期不得晚于结束日期。JSON 为 UTF-8；CSV 为 `utf-8-sig`（带 BOM，Excel 可直接打开中文）。导出文件**不含 `passToken`**，但可能含明文 `user_id` 和完整健康记录，必须妥善保管。字段与筛选规则见[导出格式](docs/export-format.md)。

不连接账号验证本地流程：

```bash
python examples/synthetic_demo.py
python examples/coach_synthetic_demo.py
```

### 5. 本地 Web 看板（可选）

后端：

```bash
pip install -e '.[web]'
mi-fitness-bridge web --host 127.0.0.1 --port 8765

# 健康检查
curl http://127.0.0.1:8765/api/health

# Swagger UI: http://127.0.0.1:8765/docs
# OpenAPI:    http://127.0.0.1:8765/openapi.json
```

前端：

```bash
cd frontend
corepack enable
pnpm install
cp .env.example .env.local
pnpm dev        # http://127.0.0.1:5173
pnpm build      # 类型检查 + 生产构建
```

- 查询接口只读（SQLite `mode=ro`）；`POST /api/sync` 使用钥匙串中的凭证写入本地缓存，必须带 `X-Mi-Fitness-Confirm: sync`。
- 可选的 coach 写操作必须带 `X-Mi-Fitness-Confirm: coach`；AI 调用还需要单独同意。
- API **不在 HTTP 中接收凭证**，默认只监听 `127.0.0.1`。不要部署到公网。
- 接口、错误信封、状态码、账号选择和同步历史见[本地 Web API](docs/web-api.md)；前端契约见[frontend/README.md](frontend/README.md)。

### 6. 本地 MCP（可选）

```bash
mi-fitness-bridge serve
# 兼容别名
mi-fitness-mcp serve
```

本机 MCP 客户端配置示例：

```json
{
  "mcpServers": {
    "mi-bridge": {
      "command": "mi-fitness-bridge",
      "args": ["serve"]
    }
  }
}
```

- 服务通过标准输入/输出通信，由本机 MCP 客户端启动；直接在终端运行会看似“卡住”，因为它在等待 MCP 消息。
- 启动时不连接小米；只有状态检查或同步操作才按需建立云端连接。
- 同一数据库同时只允许一个 MCP 服务进程使用。
- 工具列表、分页、错误语义和副作用见[MCP 工具契约](docs/mcp-tool-contracts.md)；秒级运动明细与 GPS 见[运动明细可行性说明](docs/workout-detail-feasibility.md)。

### 7. 可选 coach（目标与训练计划）

```bash
mi-fitness-bridge coach status                     # 初始化/检查本地 coach 表
mi-fitness-bridge coach profile --weeks 12 --json
mi-fitness-bridge coach recommend                  # 本地规则建议
mi-fitness-bridge coach goals add --type weekly_frequency \
  --title '每周训练 3 次' --target 3 --unit sessions_per_week --start-date 2026-01-01
mi-fitness-bridge coach plan --goal <goal_id> --generate --fallback --activate

# 可选：配置远程 AI（交互式，密钥只写入系统钥匙串）
mi-fitness-bridge coach setup
```

不配置 LLM 也能使用本地目标、训练档案和确定性模板计划。远程 AI 只在显式配置、记录同意并显式触发后调用，只发送最小化周聚合；API key 不进入 `config.json`、命令行、MCP 参数或 HTTP。完整说明见[coach 文档](docs/coach.md)。

## 常用命令与文档位置

| 场景 | 命令 | 文档 |
| --- | --- | --- |
| 配置账号 | `mi-fitness-bridge setup` | [兼容性与安全上手](docs/compatibility.md) |
| 诊断配置/数据库/连通性 | `mi-fitness-bridge doctor` | [兼容性与安全上手](docs/compatibility.md) |
| 增量同步（无需日期） | `mi-fitness-bridge sync` | [README 同步章节](#4-首次同步与导出) |
| 指定日期/类型同步 | `mi-fitness-bridge sync --type ... --start-date ... --end-date ...` | [README 同步章节](#4-首次同步与导出) |
| 忽略水位完整重拉 | `mi-fitness-bridge sync --full` | [README 同步章节](#4-首次同步与导出) |
| JSON/CSV 导出 | `mi-fitness-bridge export ...` | [导出格式](docs/export-format.md) |
| 本地 MCP | `mi-fitness-bridge serve` | [MCP 工具契约](docs/mcp-tool-contracts.md) |
| 本地 Web API | `mi-fitness-bridge web --host 127.0.0.1 --port 8765` | [本地 Web API](docs/web-api.md) |
| 前端开发/构建 | `cd frontend && pnpm dev` / `pnpm build` | [frontend/README.md](frontend/README.md) |
| coach 目标/计划 | `mi-fitness-bridge coach ...` | [coach](docs/coach.md) |
| 不联网验证 | `python examples/synthetic_demo.py` | [兼容性与安全上手](docs/compatibility.md) |
| 测试与 lint | `python -m pytest -q -p no:cacheprovider` / `python -m ruff check src tests scripts` | [CONTRIBUTING.md](CONTRIBUTING.md) |
| 发版 | 按检查表执行 | [发布检查表](docs/release-checklist.md) |

## 文档地图

| 文档 | 内容 |
| --- | --- |
| [docs/README.md](docs/README.md) | 完整文档索引：现行指南、设计参考、维护、历史记录 |
| [docs/compatibility.md](docs/compatibility.md) | 兼容性证据、凭证前提、安全上手、问题反馈 |
| [docs/web-api.md](docs/web-api.md) | 本地 API 接口、错误信封、账号选择、同步记录 |
| [docs/coach.md](docs/coach.md) | 目标、训练档案、计划、AI 数据边界 |
| [docs/export-format.md](docs/export-format.md) | JSON/CSV 格式、日期过滤、字段口径 |
| [docs/mcp-tool-contracts.md](docs/mcp-tool-contracts.md) | MCP 工具契约与分页语义 |
| [docs/workout-detail-feasibility.md](docs/workout-detail-feasibility.md) | FDS 秒级明细协议、支持范围与限制 |
| [docs/设计手稿.md](docs/设计手稿.md) | 前端页面设计 |
| [docs/release-checklist.md](docs/release-checklist.md) | 发布与真实账户试点检查 |
| [SECURITY.md](SECURITY.md) | 敏感数据、漏洞上报、LLM 出口边界 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 贡献、测试、许可 |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更记录 |
| [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) | Fork 来源链路、上游许可证历史与第三方归属 |

## 支持的数据

日常活动、睡眠会话与阶段、运动记录、身体测量、心率样本（含可用时的静息心率）、血氧、压力、异常心跳事件，以及可用的秒级运动明细与 GPS 轨迹。

日常活动步数按本地“分钟切片”汇总：手机、手环或手表对同一分钟上报重叠记录时，保留较大的单条记录而不是相加，以避免双设备重复计步。该规则是对非公开上游格式的兼容处理，最终数值仍可能与 App 的服务端修正结果不同。

## Fork 说明与免责声明

- **来源链路：** 本仓库 `7Z-F-T/mi_fitness_data_bridge` 是 [`shkyyy18/mi_fitness_data_bridge`](https://github.com/shkyyy18/mi_fitness_data_bridge) 的 fork；上游项目源自 [`binglua/mi-fitness-mcp-cn`](https://github.com/binglua/mi-fitness-mcp-cn)，后者基于 [`kubulashvili/mi-fitness-mcp`](https://github.com/kubulashvili/mi-fitness-mcp)。
- **非官方版本：** 本 fork 不是上游官方发行版，上游作者不对本 fork 的修改、发布、支持或数据行为负责；本 fork 的维护者也不代表 Xiaomi。
- **本 fork 的主要改动：** 本地 Web 看板与 API、按分类同步历史与增量同步、可选 coach、FDS 秒级运动明细解析修复，以及文档和前端页面。
- **免责声明：** 本项目为个人、非官方、实验性项目，按“现状”提供，不提供任何明示或暗示的担保（包括但不限于适销性、特定用途适用性和不侵权）。使用本项目可能因上游接口变化、设备或地区差异、账户权限或数据错误而失败；使用者应自行备份数据、核对结果，并自行承担使用风险。本项目不构成医疗建议，不用于诊断或治疗。请遵守 Xiaomi 的服务条款、当地法律及你所在账户的授权范围。
- **许可证：** 本 fork 以 **AGPL-3.0-only** 许可证发布；上游版权、原始 MIT 声明和第三方归属见 [LICENSE](LICENSE) 与 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 项目边界与隐私

- **核心桥接器不提供教练或医疗建议**，不做诊断、治疗、处方或减重建议。
- 不提供托管账户、共享凭证、公开 Token 代理、公网服务或多用户看板，也不引入遥测或第三方分析。
- 可选 coach 默认关闭；它只提供本地目标、训练档案和训练计划，不改变核心同步/导出/查询行为。
- 可选的本地 Web 看板与 API 只服务本人本机缓存，不属于托管服务。
- MCP 查询结果会流入你使用的 MCP 客户端/模型；仅限本机 stdio 客户端，不要接入远程或托管代理。
- 下游项目应安装本包或消费本地导出，而不是复制连接器源码。

本软件仅用于个人数据访问和工程研究，不用于诊断或治疗。安全问题请遵循 [SECURITY.md](SECURITY.md)；贡献与测试约定见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## Python 集成

兼容包名保持为 `mi_fitness_mcp`：

```python
from mi_fitness_mcp.adapters.mi_fitness_cloud import MiFitnessCloudAdapter
```

不要硬编码或提交真实凭证。下游项目应安装本包，而不是复制连接器源码。

## 许可证与反馈

本 fork 采用 **AGPL-3.0-only** 许可证，详见 [LICENSE](LICENSE)。上游来源、原始 MIT 版权声明、上游许可证历史和第三方归属见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

如果这个工具对你有用，欢迎给[本 fork](https://github.com/7Z-F-T/mi_fitness_data_bridge)点一个 **Star**，或提交[不泄露隐私的兼容性反馈](https://github.com/7Z-F-T/mi_fitness_data_bridge/issues/new?template=compatibility_report.yml)。请勿上传凭证、真实健康数据、数据库或日志。
