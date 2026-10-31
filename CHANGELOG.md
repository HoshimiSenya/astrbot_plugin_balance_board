# 更新日志

本项目所有重要的变更都将记录在此文件中。

本格式基于 [保持更新日志](https://keepachangelog.com/zh-CN/1.1.0/)（Keep a Changelog），
且本项目遵循 [语义化版本规范](https://semver.org/lang/zh-CN)（Semantic Versioning）。

## 1.1.0 - 2026-10-31

### 新增

- 新增 Kimi（Moonshot）余额支持：读取 `GET /v1/users/me/balance`，自动兼容国内站与国际站主机。
- 新增 MiniMax Token Plan 额度支持：读取 `GET /v1/token_plan/remains`，显示 5 小时与周剩余百分比；仅在供应商类型 / ID 明确为 Token Plan 时识别，普通 MiniMax 按量付费供应商会被跳过。
- 新增 Ollama Cloud 余额支持：读取 `GET /api/balance`，支持 `included.balance_usd` + `purchased.balance_usd` 余额以及旧版 `session` / `weekly` 百分比额度；本地 Ollama 地址会被跳过。
- 新增 302.AI 余额支持：读取 `GET /dashboard/balance`。
- 新增 PPIO 余额支持：读取 `GET /openapi/v1/billing/balance/detail`，自动将 1/10000 元换算为人民币。
- 新增额度窗口 UI：当平台同时返回 5 小时与周剩余额度时，在账号行下方追加 `5h: 75% · 周: 40%` 汇总行；单窗口直接显示百分比。
- 新增针对新平台解析、识别、地址归一化和渲染的单元测试。

### 变更

- 扩展 `BalanceSnapshot` / `ParsedBalance`，支持百分比额度、指标文案与附加汇总行，同时保持原有“平台 + 余额”布局。
- 更新 README、README_EN 与元数据，补充新平台配置、识别规则、字段说明和常见问题。
- 版本号更新至 1.1.0。

## 1.0.0 - 2026-10-30

### 新增

- 自动发现 AstrBot 模型提供商：直接从 AstrBot 的服务提供商配置中读取 API 密钥和基础 URL，无需在插件配置中输入或存储密钥；每次查询时动态读取提供商列表，不再暴露固定的 accounts 配置项。
- 多提供商余额看板：覆盖 DeepSeek、智谱 AI 和 ModelScope。
- 基于主机名的提供商检测：针对 `deepseek.com`、`bigmodel.cn` / `zhipuai.cn` 以及 `modelscope.cn` / `modelscope.ai`，在未配置基础 URL 时自动识别并提供提供商类型/ID 提示。
- 安全跳过机制：自动跳过自定义的 OpenAI 兼容代理主机和不支持的平台，确保密钥仅发送至匹配的官方余额查询端点。
- 自动去重：按“API 密钥 + 余额端点”自动去重，共享同一钱包的提供商不会重复显示；多个不同密钥会被保留并编号。
- 使用 Pillow 渲染 PNG 报告：按提供商分组显示，以平台中文名作为标题，详情行包含英文名和端点；包含彩色点缀、右对齐金额、失败原因及更新时间戳。
- 专属计费单位：DeepSeek 和智谱 AI 显示货币余额；ModelScope 显示可用魔搭币。
- 高可用查询机制：支持并发查询、TTL 缓存、单用户冷却时间，以及针对超时、429 和 5xx 响应的指数退避重试。
- 仅限管理员使用的 `/余额` 指令：包含 `/余额查询`、`/查余额`、`/模型余额`、`/余额看板` 和 `/balance` 等别名。
- 文本降级支持：当图像渲染或发送不可用时，自动回退为纯文本输出。
- 隐私保护：在每条消息和日志记录中自动对 API 密钥进行脱敏（打码）处理。
- 平台支持：支持 `aiocqhttp` 和 `qq_official` 平台。
- 精简插件描述：将 `metadata.yaml` 的 `desc` 字段保持为简短单行，以保持 AstrBot 的插件加载日志干净清爽。
- 开发与质量保障：包含单元测试、Ruff 代码检查配置以及 GitHub Actions CI。
