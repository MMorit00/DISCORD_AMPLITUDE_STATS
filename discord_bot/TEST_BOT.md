# Discord Bot 测试指南

> 专注测试 Discord Bot 的交互功能

## 🎯 测试目标

验证 Bot 的核心功能：
1. ✅ Discord Gateway 连接
2. ✅ 消息监听与权限校验
3. ✅ LLM 自然语言解析
4. ✅ 函数执行
5. ✅ GitHub 数据读写
6. ✅ Discord 回复

---

## 🚀 快速测试（本地运行）

### 步骤 1：配置环境变量

创建 `.env` 文件：
```bash
cd discord-bot
cp .env.example .env
```

编辑 `.env`，填入以下信息：

```bash
# Discord Bot Token（必需）
DISCORD_TOKEN=YOUR_BOT_TOKEN

# 你的 Discord User ID（必需）
ALLOWED_USER_IDS=YOUR_USER_ID

# GitHub Token（必需）
GITHUB_TOKEN=ghp_YOUR_TOKEN
GITHUB_REPO=MMorit00/DISCORD_AMPLITUDE_STATS

# LLM API Key（任选其一）
DASHSCOPE_API_KEY=sk-YOUR_QWEN_KEY
# 或
OPENAI_API_KEY=sk-YOUR_OPENAI_KEY

# 时区
TZ=Asia/Shanghai
LOG_LEVEL=INFO
```

---

### 步骤 2：获取必需的 Token 和 ID

#### 2.1 Discord Bot Token

1. 访问：https://discord.com/developers/applications
2. 点击 "New Application"
3. 名称：`Portfolio Bot`
4. 进入 Bot 标签
5. 点击 "Reset Token"，复制 Token
6. **重要：** 勾选 `Privileged Gateway Intents` → `Message Content Intent`

#### 2.2 你的 Discord User ID

1. Discord 设置 → 高级 → 开启"开发者模式"
2. 右键你的用户名 → 复制 ID
3. 填入 `ALLOWED_USER_IDS`

#### 2.3 GitHub Token

1. 访问：https://github.com/settings/tokens
2. Generate new token (classic)
3. 勾选：
   - `repo`（全部）
   - `workflow`
4. 生成并复制

#### 2.4 Qwen API Key（推荐）

1. 访问：https://dashscope.console.aliyun.com/
2. 注册/登录阿里云
3. 创建 API Key
4. 复制到 `DASHSCOPE_API_KEY`

**或使用 OpenAI：**
1. 访问：https://platform.openai.com/api-keys
2. 创建 API Key

---

### 步骤 3：邀请 Bot 到服务器

1. 在 Discord Developer Portal → OAuth2 → URL Generator
2. 勾选：
   - `bot`
   - `applications.commands`
3. Bot Permissions 勾选：
   - `Send Messages`
   - `Read Message History`
4. 复制生成的 URL
5. 在浏览器打开，选择你的服务器

---

### 步骤 4：安装依赖

```bash
cd discord-bot
uv sync
```

---

### 步骤 5：运行 Bot

```bash
uv run python bot.py
```

**预期输出：**
```
2025-10-28 18:00:00,000 INFO __main__ 启动 Discord Bot...
2025-10-28 18:00:01,234 INFO __main__ 主 LLM: Qwen-Turbo (新加坡端点)
2025-10-28 18:00:02,345 INFO __main__ GitHub 同步器初始化: MMorit00/DISCORD_AMPLITUDE_STATS
2025-10-28 18:00:03,456 INFO discord Bot 已登录: Portfolio Bot (ID: 123456789)
2025-10-28 18:00:03,456 INFO discord 允许的用户 ID: [你的ID]
```

---

## 🧪 测试用例

Bot 运行后，在 Discord 频道测试：

### 测试 1：命令模式

**输入：**
```
!help
```

**预期回复：**
```
📋 Portfolio Bot 使用指南
...（帮助信息）
```

---

**输入：**
```
!status
```

**预期回复：**
```
💰 总市值: ¥8,144.31

📊 权重分布:
  • CSI300: 83.42%
  • US_QDII: 11.02%
  • CGB_3_5Y: 5.57%
```

---

### 测试 2：自然语言（跳过定投）

**输入：**
```
今天没定投 018043
```

**Bot 处理流程：**
1. 收到消息
2. 调用 Qwen LLM 解析
3. 识别为 `skip_investment(date="today", fund_code="018043")`
4. 执行函数
5. GitHub API 修改 transactions.csv
6. Commit: `[bot] skip_investment 018043 2025-10-28 [tx:abc123]`

**预期回复：**
```
✅ 已标记 2025-10-28 的 018043 为'未定投'
```

**验证：**
- GitHub 仓库有新 commit
- transactions.csv 中对应记录 type=skip, status=skipped

---

### 测试 3：自然语言（调整持仓）

**输入：**
```
调整 000051 +500
```

**预期回复：**
```
✅ 已记录 000051 买入 ¥500
```

**验证：**
- GitHub 有新 commit
- transactions.csv 新增一行

---

### 测试 4：自然语言（确认份额）

**输入：**
```
确认 018043 100份 2025-10-25
```

**预期回复：**
```
✅ 已确认 018043 2025-10-25 的份额: 100.00
```

**验证：**
- transactions.csv 对应记录 shares=100, status=confirmed

---

### 测试 5：查询持仓

**输入：**
```
查询持仓
```

**预期回复：**
```
💰 总市值: ¥8,144.31

📊 权重分布:
  • CSI300: 83.42%
  • US_QDII: 11.02%
  • CGB_3_5Y: 5.57%
```

---

## ⚠️ 常见问题

### Q1: Bot 无法启动？

**检查：**
```bash
# 验证环境变量
uv run python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('DISCORD_TOKEN:', 'OK' if os.getenv('DISCORD_TOKEN') else 'MISSING')
print('GITHUB_TOKEN:', 'OK' if os.getenv('GITHUB_TOKEN') else 'MISSING')
print('ALLOWED_USER_IDS:', os.getenv('ALLOWED_USER_IDS'))
"
```

---

### Q2: Message Content Intent 错误？

**错误信息：**
```
discord.errors.PrivilegedIntentsRequired: Shard ID None is requesting privileged intents...
```

**解决：**
1. Discord Developer Portal → Bot
2. 勾选 `Message Content Intent`
3. 保存
4. 重启 Bot

---

### Q3: LLM 调用失败？

**测试 LLM 连接：**
```bash
uv run python -c "
from llm_handler import get_llm_handler
handler = get_llm_handler()
print('LLM 初始化成功')
"
```

**如果失败：**
- 检查 API Key 是否有效
- 检查是否有余额
- 尝试切换到 OpenAI 测试

---

### Q4: GitHub API 权限错误？

**错误信息：**
```
403 Forbidden: Resource not accessible by integration
```

**解决：**
- 确认 Token 有 `repo` 和 `workflow` 权限
- 确认仓库名正确（`username/repo`）
- 重新生成 Token

---

### Q5: Bot 不回复我的消息？

**检查：**
1. 你的 User ID 是否在 `ALLOWED_USER_IDS` 中
2. Bot 是否有 `Send Messages` 权限
3. 查看 Bot 日志是否有权限警告

---

## 📝 测试检查清单

### 环境配置
- [ ] Discord Bot Token 已获取
- [ ] 你的 User ID 已获取
- [ ] GitHub Token 已获取（repo + workflow 权限）
- [ ] LLM API Key 已获取（Qwen 或 OpenAI）
- [ ] .env 文件已创建并填写
- [ ] Message Content Intent 已开启
- [ ] Bot 已邀请到服务器

### 功能测试
- [ ] Bot 成功启动（日志显示"已登录"）
- [ ] `!help` 命令有回复
- [ ] `!status` 显示持仓
- [ ] "今天没定投 018043" 能识别
- [ ] GitHub 有自动 commit
- [ ] "查询持仓" 返回数据

### 验证
- [ ] GitHub 仓库有 Bot 的 commit
- [ ] transactions.csv 被正确修改
- [ ] 软删除（type=skip）生效
- [ ] 冲突重试机制工作

---

## 🎯 最简测试流程（10分钟）

```bash
# 1. 进入目录
cd discord-bot

# 2. 创建 .env（手动填写）
cp .env.example .env

# 3. 安装依赖
uv sync

# 4. 运行 Bot
uv run python bot.py

# 5. 在 Discord 测试
# - 发送：!status
# - 发送：今天没定投 018043

# 6. 检查 GitHub 是否有新 commit
```

---

准备好了吗？需要我帮你准备什么？

