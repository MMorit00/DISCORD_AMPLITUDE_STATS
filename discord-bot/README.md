# Portfolio Discord Bot

> 投资组合 Discord 交互式机器人

## 功能

- ✅ 自然语言交互（中文）
- ✅ LLM 函数调用（Qwen/GLM/OpenAI）
- ✅ GitHub 幂等写入（自动 commit）
- ✅ 权限校验（用户白名单）
- ✅ 24/7 常驻监听

## 快速开始

### 1. 安装依赖

```bash
cd discord-bot
uv sync
```

### 2. 配置环境变量

复制 `.env.example` 到 `.env`：
```bash
cp .env.example .env
```

编辑 `.env` 填入：
- `DISCORD_TOKEN`: Bot Token
- `ALLOWED_USER_IDS`: 你的 Discord User ID
- `GITHUB_TOKEN`: Personal Access Token
- `DASHSCOPE_API_KEY`: Qwen API Key

### 3. 本地运行

```bash
uv run python bot.py
```

### 4. 部署到 Render

```bash
# 推送代码到 GitHub
git push

# 在 Render 创建 Background Worker
# 使用 render.yaml 配置
# 添加环境变量
```

## 使用示例

### 自然语言

在 Discord 频道直接发送：

```
今天没定投 018043
```

Bot 回复：
```
✅ 已标记 2025-10-28 的 018043 为'未定投'
```

```
调整 000051 +500
```

Bot 回复：
```
✅ 已记录 000051 买入 ¥500
```

### 命令模式

```
!status
```

Bot 回复：
```
💰 总市值: ¥8,144.31

📊 权重分布:
  • CSI300: 83.42%
  • US_QDII: 11.02%
  • CGB_3_5Y: 5.57%
```

## 架构

```
用户消息 → Discord Gateway → LLM 解析 → 函数执行 → GitHub API → Commit
```

## 支持的操作

| 操作 | 自然语言示例 | 函数 |
|------|--------------|------|
| 跳过定投 | "今天没定投 018043" | `skip_investment` |
| 调整持仓 | "调整 000051 +500" | `update_position` |
| 确认份额 | "确认 018043 100份" | `confirm_shares` |
| 查询状态 | "查询持仓" | `query_status` |
| 删除交易 | "删除 tx001" | `delete_transaction` |

## 技术细节

- **LLM 路由**: Qwen → GLM → OpenAI（自动降级）
- **幂等性**: 每次 commit 带唯一事务 ID
- **并发控制**: If-Match（SHA 校验）
- **软删除**: 标记为 skip/void，保留历史

