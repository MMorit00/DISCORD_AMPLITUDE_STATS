# Portfolio Report - 投资组合自动化报告系统

> 基于支付宝/QDII 口径的基金投资组合管理与 Discord 自动化报告系统

## 📊 项目概述

功能：
- ✅ 净值/估值抓取（东方财富/天天基金）
- ✅ 估/净并行计算与权重分析
- ✅ 15:00 Cutoff（未知价原则）与 T+N 确认推演（A股 T+1 / QDII T+2）
- ✅ 报告生成（日/周/月 等）
- ✅ Discord Webhook 推送（可选）
- 🚧 Discord Bot 交互（命令/自然语言）

---

## 📁 项目结构（已扁平化，src 布局）

```
amplitude-discord-report/
├── pyproject.toml                 # uv 项目定义（含入口：portfolio-report / discord-bot）
├── src/
│   ├── portfolio_report/
│   │   ├── application/
│   │   │   ├── portfolio_service.py
│   │   │   └── report_builder.py
│   │   ├── config/
│   │   │   ├── config.yaml
│   │   │   ├── loader.py
│   │   │   └── settings.py
│   │   ├── domain/
│   │   │   ├── models.py
│   │   │   └── services/
│   │   │       ├── confirm.py
│   │   │       ├── metrics.py
│   │   │       ├── portfolio.py
│   │   │       ├── signals.py
│   │   │       └── trading_calendar.py
│   │   ├── infrastructure/
│   │   │   ├── github/repository.py
│   │   │   ├── market_data/eastmoney.py
│   │   │   └── notifications/discord.py
│   │   ├── presentation/
│   │   │   └── report_text.py
│   │   └── data/
│   │       ├── transactions.csv
│   │       ├── holdings.json
│   │       ├── state.json
│   │       └── cache/
│   └── discord_bot/
│       ├── business/
│       ├── infrastructure/llm/clients.py
│       ├── presentation/
│       │   ├── bot_adapter.py
│       │   └── message_router.py
│       └── shared/
│           ├── types.py
│           └── utils.py
└── docs/
    └── architecture/              # 架构/流程文档（puml / 指南）
```

说明：
- 已移除 sys.path 注入与过度聚合的 `__init__.py` 再导出；统一使用标准导入。
- 文档（Flow/Prompt）已迁移至 `docs/architecture/`，不再混入包内。

---

## 🚀 快速开始

安装依赖（uv）：
```bash
uv sync
```

运行报告（入口脚本由 pyproject 提供）：
```bash
# 生成日报/周报/月报
uv run portfolio-report --freq daily
uv run portfolio-report --freq weekly
uv run portfolio-report --freq monthly
```

运行 Bot（可选，需 extras）：
```bash
uv sync --extra bot
uv run discord-bot
```

配置文件：编辑 `src/portfolio_report/config/config.yaml`；环境变量通过 `.env`/系统环境加载（参见 `settings.py`）。

数据文件：`src/portfolio_report/data/`（交易台账/持仓快照/状态与缓存）。

---

## 🧩 关键模块

- 应用层：`application/portfolio_service.py`, `application/report_builder.py`
- 领域层：`domain/models.py`, `domain/services/*`
- 基础设施层：`infrastructure/*`（GitHub 仓储/市场数据/通知）
- 表现层：`presentation/report_text.py`
- 配置：`config/loader.py`, `config/settings.py`, `config/config.yaml`

示例：刷新并查看持仓（Python 交互）
```python
from portfolio_report.domain.services.portfolio import Portfolio
from portfolio_report.config.loader import ConfigLoader
from portfolio_report.infrastructure.github.repository import GitHubRepository
from portfolio_report.infrastructure.market_data.eastmoney import EastMoneyFundAPI

# 依赖注入（示例）
config = ConfigLoader()
repo = GitHubRepository(settings=None)  # 生产中通过 portfolio_service 注入
fund_api = EastMoneyFundAPI()

portfolio = Portfolio(repository=repo, fund_api=fund_api, config=config)
portfolio.refresh()
print(portfolio.weights_net)
```

---

## 🔐 环境变量（摘）

报告：
```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
TZ=Asia/Shanghai
```

Bot（可选）：
```bash
DISCORD_TOKEN=your_bot_token
OPENAI_API_KEY=sk-...
GITHUB_TOKEN=ghp_...
GITHUB_REPO=username/repo
ALLOWED_USER_IDS=123456789,987654321
```

---

## 📐 架构文档

参见 `docs/architecture/` 下的 PlantUML 图与指南（含 Portfolio 与 Bot 的 4 层架构图）。

---

## 备注

- 构建产物与历史文件已清理：`__pycache__/`、`requirements.txt`、`PLANNING.md` 等。
- 推荐仅使用 uv 进行依赖与脚本管理。

