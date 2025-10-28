# Portfolio Report - 投资组合自动化报告系统

> 基于支付宝/QDII 口径的基金投资组合管理与 Discord 自动化报告系统

## 📊 项目概述

本项目提供基金投资组合的自动化管理与报告功能，支持：
- ✅ **净值/估值抓取**：自动获取基金净值与盘中估值
- ✅ **估/净并行计算**：同时维护净值口径和估值口径
- ✅ **15:00 Cutoff**：符合支付宝未知价原则的交易时间判定
- ✅ **T+N 确认推演**：A股 T+1、QDII T+2（含海外节假日）
- ✅ **权重分析**：实时计算资产权重与偏离度
- 🚧 **再平衡信号**：智能提示再平衡与战术操作（TODO）
- 🚧 **Discord 交互**：自然语言修改数据、查询持仓（TODO）
- 🚧 **定时报告**：日/周/月/半年/年自动推送（TODO）

---

## 🎯 投资策略

### 目标配比
- **美股 QDII**：75%
  - 天弘纳斯达克100(QDII)A（018043）
  - 天弘纳斯达克100(QDII)C（018044）
  - 摩根标普500指数(QDII)C（019305）
  - 每日各定投 100 元（支付宝自动执行）

- **A股沪深300**：20%
  - 沪深300联接A（000051）
  - 一次性买入 + 持续月投

- **中债3-5年**：5%
  - 易方达中债3-5年期国债指数A（001512）
  - 一次性买入 + 持续月投

### 再平衡策略
- **轻度再平衡**：绝对偏离 ≥ 5%，建议调仓，冷却 60 天
- **强制再平衡**：相对偏离 ≥ 20%，优先执行，冷却 90 天

### 战术操作（低频）
- **加仓**：90日回撤 ≥ 10% 且不超重，建议加码 100-300，冷却 30 天
- **减仓**：超额收益 > 15% 且超重，建议减码 100-300，冷却 30 天

---

## 📁 项目结构

```
portfolio-report/
├── config/
│   └── config.yaml              # 配置中心（目标权重、阈值、LLM路由）
├── data/
│   ├── transactions.csv         # 交易台账（支持15:00 cutoff、T+N确认）
│   ├── holdings.json           # 持仓快照（自动生成）
│   ├── state.json              # 信号状态与冷却
│   └── cache/                  # 净值缓存（gitignore）
├── core/
│   ├── trading_calendar.py     # ✅ 交易日历（340行）
│   ├── portfolio.py            # ✅ 持仓管理（361行）
│   ├── metrics.py              # 🚧 TODO: 收益/XIRR/回撤
│   ├── signals.py              # 🚧 TODO: 再平衡/战术信号
│   └── confirm.py              # 🚧 TODO: 确认轮询器
├── sources/
│   └── eastmoney.py            # ✅ 东方财富数据源（376行）
├── report/
│   └── builder.py              # 🚧 TODO: 报告生成器
├── utils/
│   ├── config_loader.py        # ✅ 配置加载（93行）
│   └── discord.py              # ✅ Discord推送（69行）
├── Flow/
│   ├── current-architecture.puml    # 当前架构图
│   ├── portfolio-architecture.puml  # 完整架构图
│   └── signal-workflow.puml         # 信号工作流
└── main.py                     # 🚧 TODO: CLI 入口
```

---

## ✅ 已实现功能（v0.1）

### 1. 交易日历管理（`core/trading_calendar.py`）
- ✅ 15:00 cutoff 判定（未知价原则）
- ✅ 中国交易日判定（基于 `chinesecalendar`，自动处理调休）
- ✅ 美国交易日判定（主要联邦假日）
- ✅ A股 T+1 确认日推演
- ✅ QDII T+2 确认日推演（中美市场对齐）
- ✅ 下一交易日查找

**测试结果：** 全部通过 ✅
```bash
uv run python portfolio-report/core/test_calendar.py
```

### 2. 基金数据抓取（`sources/eastmoney.py`）
- ✅ 实时估值获取（盘中，天天基金 API）
- ✅ 最新净值获取（已公布，东方财富 API）
- ✅ 智能选择净值/估值（根据时间和数据新鲜度）
- ✅ 历史净值序列查询
- ✅ 本地文件缓存（5分钟 TTL）

**测试结果：** 全部通过 ✅
```bash
uv run python portfolio-report/sources/test_eastmoney.py
```

**实际数据示例（2025-10-28）：**
- A股基金（000051）：估值 1.7555（-0.51%），净值 1.7645（2025-10-27）
- QDII 基金（018043）：净值 1.8424（2025-10-24，T+2 滞后）

### 3. 持仓管理（`core/portfolio.py`）
- ✅ 从交易台账构建持仓（聚合份额）
- ✅ 估/净并行计算（双轨道市值）
- ✅ 权重分析（按资产类别汇总）
- ✅ 权重偏离计算（绝对偏离、相对偏离）
- ✅ 持仓快照保存（JSON 格式）

**测试结果：** 全部通过 ✅
```bash
uv run python portfolio-report/core/test_portfolio.py
```

**实际持仓示例：**
```
总市值(净): ¥8,144.31
- CSI300: ¥6,793.62 (83.42%)  目标 20% → 偏离 +63.42%
- US_QDII: ¥897.27 (11.02%)   目标 75% → 偏离 -63.98%
- CGB_3_5Y: ¥453.41 (5.57%)   目标 5% → 偏离 +0.57%
```

### 4. 配置管理（`utils/config_loader.py`）
- ✅ YAML 配置加载
- ✅ 目标权重、基金映射、阈值配置
- ✅ LLM 路由配置（Qwen/GLM/豆包）
- ✅ 信号时间配置（07:30/14:40/15:00）

### 5. Discord 推送（`utils/discord.py`）
- ✅ Webhook 消息发送
- ✅ Embed 美化支持
- ✅ 复用 amplitude-report 逻辑

---

## 🚧 待实现功能（TODO）

### 高优先级

#### TODO 5: 确认轮询器（`core/confirm.py`）
**功能：**
- 10:30/18:30 定时轮询基金净值
- 自动回填 `confirm_date` 和 `shares`
- Discord 轻提醒（"✅ 已确认份额"）

**调度：**
- GitHub Actions: `portfolio-confirm-cron.yml`
- Cron: `30 2,10 * * *`（UTC）= 10:30/18:30 CST

#### TODO 6: 信号引擎（`core/signals.py`）
**功能：**
- 再平衡信号（轻度/强制）
- 战术信号（加仓/减仓）
- 冷却机制（60/90/30 天）
- 信号优先级与冲突处理

**输出：**
```python
{
  "signal_type": "rebalance_light",
  "asset_class": "US_QDII",
  "action": "buy",
  "amount": 5000,
  "reason": "权重偏离 -63.98%，建议调至目标 75%",
  "urgency": "medium"
}
```

#### TODO 7: 报告生成器（`report/builder.py` + `main.py`）
**功能：**
- 日报（08:30）：涨跌、持仓、权重、信号提示
- 周报（周一 08:45）：本周收益、权重热力图
- 月报（次一交易日 09:45）：月度收益、XIRR、再平衡建议
- 半年/年报：累计收益、回撤、策略复盘

**CLI：**
```bash
uv run python portfolio-report/main.py --freq daily
uv run python portfolio-report/main.py --freq weekly
```

### 中优先级

#### TODO 8: Discord Bot（`discord-bot/`）
**功能：**
- 常驻监听 Discord Gateway（Render Background Worker）
- LLM 自然语言解析（Qwen/GLM/豆包函数调用）
- 交互命令：
  - "今天没定投 018043" → `skip_investment()`
  - "调整 000051 +500" → `update_position()`
  - "确认份额 018043 100份 2025-10-25" → `confirm_shares()`
  - "查询持仓" → `query_status()`

**部署：**
- Render Background Worker（新加坡区域）
- 环境变量：`DISCORD_TOKEN`, `OPENAI_API_KEY`, `GITHUB_TOKEN`

#### TODO 9: GitHub 幂等写入（`discord-bot/github_sync.py`）
**功能：**
- If-Match 并发控制
- 事务 ID 幂等性
- 软删除策略（`status=skipped`）
- 自动 commit 与推送

#### TODO 10: GitHub Actions 工作流
**文件：**
- `.github/workflows/portfolio-daily.yml`
- `.github/workflows/portfolio-weekly.yml`
- `.github/workflows/portfolio-monthly.yml`
- `.github/workflows/portfolio-confirm-cron.yml`

**时间（UTC 对齐 CST）：**
- 日报：`0 30 0 * * *`（00:30 UTC = 08:30 CST）
- 周报：`0 45 0 * * 1`（周一 00:45 UTC = 08:45 CST）
- 确认：`0 30 2,10 * * *`（02:30/10:30 UTC = 10:30/18:30 CST）

### 低优先级

#### TODO 11: 文档与示例
- 🚧 部署指南（Render/GitHub Actions 配置）
- 🚧 LLM 供应商配置（Qwen/GLM/豆包）
- 🚧 常见问答（FAQ）
- 🚧 环境变量说明（`.env.example`）

---

## 🚀 快速开始

### 1. 安装依赖

```bash
# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install -r requirements.txt
```

### 2. 配置文件

编辑 `config/config.yaml`：
- 设置目标权重
- 配置基金代码
- 调整阈值和时间

### 3. 准备交易数据

编辑 `data/transactions.csv`，记录你的交易：
```csv
tx_id,date,fund_code,amount,shares,type,status,...
tx001,2025-10-20,000051,6800,3850.17,buy,confirmed,...
```

或使用样例数据：
```bash
cp data/transactions_sample.csv data/transactions.csv
```

### 4. 运行测试

```bash
# 测试交易日历
uv run python portfolio-report/core/test_calendar.py

# 测试数据抓取
uv run python portfolio-report/sources/test_eastmoney.py

# 测试持仓管理
uv run python portfolio-report/core/test_portfolio.py
```

### 5. 查看持仓（当前可用）

```bash
# 刷新持仓并查看快照
uv run python -c "
from core.portfolio import Portfolio
p = Portfolio()
p.refresh()
print(f'总市值: ¥{p.total_value_net:.2f}')
"
```

---

## 📊 当前进度

### ✅ 已完成（v0.1）

| 模块 | 文件 | 行数 | 状态 | 测试 |
|------|------|------|------|------|
| 交易日历 | `core/trading_calendar.py` | 340 | ✅ | ✅ |
| 持仓管理 | `core/portfolio.py` | 361 | ✅ | ✅ |
| 数据抓取 | `sources/eastmoney.py` | 376 | ✅ | ✅ |
| 配置加载 | `utils/config_loader.py` | 93 | ✅ | ✅ |
| Discord推送 | `utils/discord.py` | 69 | ✅ | - |

**代码统计：** ~1,239 行核心代码 + ~330 行测试代码

### 🚧 进行中

| 序号 | 任务 | 优先级 | 预计行数 | 依赖模块 |
|------|------|--------|----------|----------|
| 5 | 确认轮询器 | 高 | ~150 | Portfolio |
| 6 | 信号引擎 | 高 | ~200 | Portfolio, Metrics |
| 7 | 报告生成 + CLI | 高 | ~300 | Signals |
| 8 | Discord Bot | 中 | ~400 | All |
| 9 | GitHub 幂等写入 | 中 | ~150 | - |
| 10 | GitHub Actions | 中 | ~200 | CLI |
| 11 | 文档完善 | 低 | - | - |

---

## 🔧 技术栈

### 后端
- **Python**: 3.11+
- **依赖管理**: uv + pyproject.toml
- **交易日历**: chinesecalendar（自动处理调休）
- **数据抓取**: requests（天天基金/东方财富 API）
- **精度保证**: Decimal（金融计算）

### Discord 交互（TODO）
- **Bot 框架**: discord.py
- **LLM**: OpenAI GPT-4o-mini（或 Qwen/GLM/豆包）
- **GitHub API**: PyGithub

### 部署（TODO）
- **定时任务**: GitHub Actions（免费）
- **常驻 Bot**: Render Background Worker（免费层）
- **时区**: Asia/Shanghai（UTC+8）

---

## 📐 架构图

查看 `Flow/` 目录下的 PlantUML 图表：

- **`current-architecture.puml`** - 当前已实现架构（简洁版）✨
- **`portfolio-architecture.puml`** - 完整系统架构（含 TODO）
- **`signal-workflow.puml`** - 信号触发工作流

在 Cursor/VSCode 中打开 `.puml` 文件，按 `Opt + D`（Mac）预览。

---

## 🎯 核心概念

### 未知价原则
支付宝基金交易采用"未知价原则"：
- **15:00 前提交**：按当日收盘净值（T日）成交
- **15:00 后提交**：按次日收盘净值（T+1日）成交

### 估/净并行
- **净值口径**：已公布的单位净值（权威，滞后）
- **估值口径**：盘中实时估算（及时，有偏差）
- **策略**：信号以"净"为主，"估"作为参考

### T+N 确认
- **A股基金**：T 日净值，T+1 确认，T+2 可查
- **QDII 基金**：T+1 计算净值，T+2 内公告并确认，遇境外节假日顺延

---

## 📝 使用说明

### 记录交易

手动编辑 `data/transactions.csv`，或通过 Discord Bot（TODO）：

```csv
tx_id,date,fund_code,amount,shares,type,status
tx001,2025-10-20,000051,6800,3850.17,buy,confirmed
tx002,2025-10-22,018043,100,54.29,buy,confirmed
```

**字段说明：**
- `tx_id`：唯一交易ID
- `date`：交易日期
- `fund_code`：基金代码
- `amount`：金额（元）
- `shares`：份额（可后续回填）
- `type`：buy/sell/skip
- `status`：pending/confirmed/skipped

### 查询持仓

```python
from core.portfolio import Portfolio

# 刷新持仓
portfolio = Portfolio()
portfolio.refresh()

# 查看权重
for asset, weight in portfolio.weights_net.items():
    print(f"{asset}: {weight*100:.2f}%")

# 查看偏离
deviations = portfolio.get_weight_deviation()
```

---

## 🔐 环境变量

### 必需（报告功能）
```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
TIMEZONE=Asia/Shanghai
```

### 可选（Bot 功能，TODO）
```bash
DISCORD_TOKEN=your_bot_token
OPENAI_API_KEY=sk-...
GITHUB_TOKEN=ghp_...
GITHUB_REPO=username/repo
ALLOWED_USER_IDS=123456789,987654321
```

---

## 📅 时间编排（未知价原则）

### A股信号（000051, 001512）
- **14:40** - 最终确认提醒（基于盘中/收盘数据）
- **15:00** - 交易截止（之后顺延至下一交易日）

### QDII 信号（018043, 018044, 019305）
- **07:30** - 昨夜收盘信号推送
- **14:40** - 复核提醒（今晚未知价成交）
- **15:00** - 交易截止（T+2 确认，遇节假日顺延）

### 定时报告（TODO）
- **08:30** - 日报
- **周一 08:45** - 周报
- **月初次一交易日 09:45** - 月报
- **1月1日/7月1日次一交易日 10:00** - 半年/年报

### 确认轮询（TODO）
- **10:30** - 上午轮询（QDII 净值公告）
- **18:30** - 下午轮询（补充检查）

---

## 🧪 测试覆盖

### 已测试 ✅
- ✅ 15:00 前后 cutoff 判定
- ✅ 中国/美国交易日判定
- ✅ A股/QDII 确认日推演
- ✅ 实时估值/最新净值获取
- ✅ 持仓构建与份额聚合
- ✅ 估/净并行计算
- ✅ 权重与偏离分析

### 待测试 🚧
- 🚧 收益/XIRR/回撤计算
- 🚧 再平衡/战术信号生成
- 🚧 冷却机制
- 🚧 Discord Bot 交互
- 🚧 GitHub API 写入

---

## 📚 参考文档

- [PlantUML 使用指南](Prompt/PlantUML-Guide.md)
- [chinesecalendar 库](https://pypi.org/project/chinesecalendar/)
- [Discord.py 文档](https://discordpy.readthedocs.io/)
- [天天基金](https://fund.eastmoney.com/)

---

## 📄 许可证

MIT License

---

## 📮 联系方式

如有问题或建议，请通过 Discord 频道反馈。

