# 可选 coach：目标设定与 AI 训练计划

> **核心桥接器不提供教练或医疗建议。** `coach` 是可选、本地、默认关闭的扩展。它不诊断、不治疗、不提供饮食处方，也不替代医生或持证教练。

## 1. 能力范围

- 手动设定运动目标，并从本地 `workouts` / `body_measurements` 计算进度。
- 从最近 4–52 周训练记录生成可解释的训练档案（周频率、周时长、距离、最长课、5K 代理值、睡眠/体重上下文、数据质量）。
- 使用本地规则给出目标建议；不配置 LLM 也能使用。
- 生成并校验多周训练计划；LLM 不可用或输出不安全时回退到本地模板。
- 入口：CLI、本地 MCP 工具、Web 目标页。
- 不提供：饮食/热量处方、医疗诊断/治疗、自动每日教练、后台自动 AI、托管/多用户服务、遥测。

## 2. 安装与启用

```bash
pip install -e '.[coach]'          # Anthropic SDK（OpenAI 兼容接口复用 httpx）
pip install -e '.[coach,web]'      # 同时启用 Web 目标页
```

本地目标和本地模板计划不需要 API key。AI 功能需要交互式配置：

```bash
mi-fitness-bridge coach setup
```

`coach setup` 会询问：

1. provider：`anthropic` 或 `openai_compatible`。
2. model：Anthropic 默认 `claude-opus-5-5`；OpenAI 兼容由用户填写。
3. `base_url`：OpenAI 兼容端点，例如 `https://api.deepseek.com/v1`、`https://api.openai.com/v1`、`http://127.0.0.1:11434/v1`（Ollama）。
4. 输出语言、训练档案周数。
5. API key：`getpass` 输入，保存到 OS keyring；不进入 `config.json`。
6. 远程端点的同意：显示将要发送的内容摘要，输入 `yes` 才记录。

重新运行 `coach setup` 会更新配置并保留其他已有设置。`mi-fitness-bridge setup --with-coach` 也可在小米配置完成后进入 coach 配置。

## 3. CLI

```bash
mi-fitness-bridge coach status
mi-fitness-bridge coach profile --weeks 12 --json
mi-fitness-bridge coach profile --weeks 12 --llm-payload   # 预览将发送的精确 payload，不联网
mi-fitness-bridge coach recommend --fallback               # 本地规则建议
mi-fitness-bridge coach recommend --llm                    # 交互确认后调用已配置模型
mi-fitness-bridge coach goals list
mi-fitness-bridge coach goals add --type weekly_frequency --title '每周训练 3 次' \
  --target 3 --unit sessions_per_week --start-date 2026-01-01
mi-fitness-bridge coach goals add --type race --sport running --title '5K 25 分钟' \
  --race-distance 5k --target-time 25:00 --date 2026-06-01
mi-fitness-bridge coach plan --goal <goal_id> --generate --fallback --activate
mi-fitness-bridge coach plan --goal <goal_id> --generate --llm --activate
```

目标类型：

| 类型 | 说明 | 进度来源 |
| --- | --- | --- |
| `weekly_frequency` | 每周训练次数 | 当前周 workouts 数 |
| `weekly_duration` | 每周训练分钟数 | 当前周 `duration_minutes` |
| `race` | 5K / 10K / 半马 / 全马目标成绩 | 近期同距离或更长跑步的配速估算 |
| `distance` | 周/月/目标日累计距离 | workouts `distance_m` |
| `body_composition` | 体重 kg 或体脂 %，支持 `target` 和 `trend` 模式 | `body_measurements` |

体重/体脂目标使用保守上限：≤0.5 kg/周、≤0.5% 体重/周、≤0.25 体脂点/周；可推导 BMI 时拒绝 <18.5；不生成饮食计划。数据不足时只允许 `trend` 模式。每周次数目标可以设到 14 次，但安全计划最多安排每周 6 个训练日；超出部分会保留为目标并在计划校验中提示。

## 4. 训练档案与数据质量

`coach profile` 输出：

- 窗口内每周训练次数、时长、距离、负荷代理。
- 观察到的周频率、活跃周、缺失周。
- 最长课、最佳 5K 代理值。
- 最近 4 周 vs 前 4 周趋势。
- 睡眠均值（至少 3 晚）和体重/体脂趋势（至少 4 次、跨度 ≥21 天）。
- `data_quality`：`ok` / `partial` / `insufficient`，以及缺失指标和注意事项。

缺失的周不会补 0；只统计有记录的周。`best_5k_proxy` 是按近期跑步配速缩放的代理值，不是正式 5K PB：对窗口内距离 ≥5 km 的跑步，用精确的 `start_at`/`end_at` 秒差（而不是截断到分钟的 `duration_minutes`）计算 `用时 × 5000 / 距离`，取最小值。比赛目标的进度使用同一公式，但窗口为 84 天、距离下限为目标距离的 90%。目标卡会显示估算方法和参考记录日期。

## 5. AI 数据边界

发送给远程 LLM 的 payload 只包含：

- 周偏移、训练次数、时长、距离、按运动类型的计数、最长课、硬课次数、负荷代理。
- 观察频率、最长课、5K 代理值、睡眠均值、可选体重趋势。
- 目标类型、目标值/单位、剩余周数、比赛距离、约束。
- `data_quality` 和 `data_gaps`。

**不发送**：

- `user_id`、`device_id`、账号信息。
- GPS、经纬度、原始秒级样本。
- workout/sleep ID、精确时间戳或任何 `YYYY-MM-DD` 日期。
- 备注、标题或其他自由文本。

发送前可运行：

```bash
mi-fitness-bridge coach profile --llm-payload
```

Web 端会在 AI 操作前展示同一份最小化 payload。远程端点没有记录同意时，Web 会提示先运行 `coach setup`。

## 6. 计划生成与校验

计划包含周索引、每周重点、训练日、session 类型（easy/long/tempo/interval/strength/mobility/rest/race）、时长、距离、强度、目的和停止规则。

`PlanValidator` 会检查：

- 每周至少 1 天休息。
- 周时长/距离增幅不超过 10%。
- 6 周以上计划有恢复周；恢复周不超过前一周 80%。
- 不连续 3 天高强度。
- session 时长 10–240 分钟（比赛日可到 600）。
- 比赛计划最后 7 天不安排高强度课，目标日有 race session，之后不再安排训练。
- 首周长课不超过近期最长课的 110%。
- 体重/体脂计划不出现饮食处方、热量缺口、断食等语言。
- 必须有停止规则和非医疗声明。

LLM 输出会先物化为本地日期，再经过校验。失败时最多修复一次，仍失败则使用确定性模板，并在 `validation_warnings` 中写明 `AI_FALLBACK`。

每个目标最多一个 `active` 计划；新计划激活时旧计划变为 `superseded`。

## 7. MCP 工具

可选 coach 工具（默认不启用 AI；本地目标/计划可用）：

- `coach_get_overview`：训练档案、目标进度、active 计划、规则建议、AI 状态。
- `coach_recommend_goals`：`use_llm=false` 时只做本地规则；`use_llm=true` 需要 `consent=true` 和已记录的远程同意。
- `coach_save_goal`：创建/更新本地目标；不接收凭证。
- `coach_get_plan`：按 `plan_id` 或 `goal_id` 读取计划。
- `coach_generate_plan`：默认本地模板；`use_llm=true` 时需 `consent=true` 和已记录的远程同意。

AI 工具标记为 `openWorldHint=true`；只读工具标记 `readOnlyHint=true`。`coach_save_goal` 和 `coach_generate_plan` 会写本地表。

## 8. Web API

所有写操作需要 `X-Mi-Fitness-Confirm: coach`：

| 方法 | 路径 |
| --- | --- |
| GET | `/api/coach/status` |
| GET | `/api/coach/overview` |
| GET | `/api/coach/profile?format=local\|llm` |
| GET | `/api/coach/goals` |
| GET | `/api/coach/goals/{goal_id}` |
| POST | `/api/coach/goals` |
| POST | `/api/coach/goals/{goal_id}` |
| POST | `/api/coach/goals/{goal_id}/archive` |
| POST | `/api/coach/recommendations` |
| GET | `/api/coach/plans` |
| GET | `/api/coach/plans/{plan_id}` |
| POST | `/api/coach/plans/generate` |
| POST | `/api/coach/plans/{plan_id}/activate` |
| POST | `/api/coach/plans/{plan_id}/archive` |

旧的 `/api/goals` 仍返回空列表，作为兼容占位；新页面使用 `/api/coach/*`。API 只监听本机，不接收 `passToken`、`user_id` 或 API key。浏览器不会拿到 key。

## 9. 安全与故障排查

- `coach status` 显示 provider/model/key 是否配置/远程同意/表是否初始化/最近 AI 运行元数据，不调用 LLM。
- `409 COACH_NOT_INITIALIZED`：先运行一次 coach 命令（如 `coach status` 或 `coach profile`）创建 coach 表。
- `409 LLM_CONSENT_REQUIRED`：运行 `coach setup` 重新记录远程同意，或改用本地 Ollama 端点。
- `409 LLM_NOT_CONFIGURED` / `COACH_EXTRA_MISSING`：检查 API key 或安装 `.[coach]`。
- `504 LLM_TIMEOUT` / `502 LLM_UNAVAILABLE`：网络或供应商问题；可加 `--fallback` 使用本地模板。
- 任何 AI 输出都只是运动参考；出现胸痛、异常气短、眩晕、心悸或明显不适时应停止并寻求医疗评估。
