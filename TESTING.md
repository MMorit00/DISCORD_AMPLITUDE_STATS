# 测试指南

> 如何测试系统的可行性

## 🎯 测试路线图

### ✅ 阶段 1：本地核心功能测试（无需外部服务）

#### 1.1 交易日历测试
```bash
cd /Users/panlingchuan/Downloads/My_Project/Discord_amplitude_Stats/amplitude-discord-report
uv run python portfolio-report/core/test_calendar.py
```

**预期结果：**
- ✅ 15:00 cutoff 判定正确
- ✅ 中国交易日判定正确
- ✅ QDII T+2 确认推演正确

---

#### 1.2 数据抓取测试（需要网络）
```bash
uv run python portfolio-report/sources/test_eastmoney.py
```

**预期结果：**
- ✅ 获取真实基金净值
- ✅ 获取盘中估值
- ✅ 缓存机制工作
- ✅ 显示实际数据（如 000051: 1.7645）

---

#### 1.3 持仓管理测试
```bash
uv run python portfolio-report/core/test_portfolio.py
```

**预期结果：**
- ✅ 读取 11 笔交易记录
- ✅ 构建 5 个持仓
- ✅ 计算总市值 ~¥8,144
- ✅ 权重偏离分析（CSI300 超标 63%）

---

#### 1.4 信号引擎测试
```bash
uv run python portfolio-report/core/test_signals.py
```

**预期结果：**
- ✅ 触发再平衡信号（CSI300 强制再平衡）
- ✅ 冷却机制工作
- ✅ 信号优先级排序

---

#### 1.5 报告生成测试
```bash
uv run python portfolio-report/core/test_report.py
```

**预期结果：**
- ✅ 日报格式正确
- ✅ 周报格式正确
- ✅ 月报包含操作建议
- ✅ 显示权重偏离（🔴/🟢 emoji）

---

### 🚧 阶段 2：GitHub Actions 测试（需要推送代码）

#### 2.1 推送代码到 GitHub
```bash
cd /Users/panlingchuan/Downloads/My_Project/Discord_amplitude_Stats/amplitude-discord-report
git push origin main
```

**当前状态：**
- 领先远程 7 个提交
- 需要推送到 https://github.com/MMorit00/DISCORD_AMPLITUDE_STATS

---

#### 2.2 配置 GitHub Secrets

访问：https://github.com/MMorit00/DISCORD_AMPLITUDE_STATS/settings/secrets/actions

添加 Secret：
- `DISCORD_WEBHOOK_URL`: 你的 Discord Webhook URL

**如何获取 Webhook URL：**
1. 进入 Discord 频道
2. 设置 → 集成 → Webhooks
3. 创建 Webhook
4. 复制 Webhook URL

---

#### 2.3 手动触发 Workflow 测试

访问：https://github.com/MMorit00/DISCORD_AMPLITUDE_STATS/actions

**测试步骤：**

1. **测试日报：**
   - 点击 `portfolio-daily-report`
   - 点击 "Run workflow"
   - 等待运行完成
   - 检查 Discord 是否收到消息

2. **测试周报：**
   - 点击 `portfolio-weekly-report`
   - 点击 "Run workflow"
   - 检查 Discord

3. **测试月报：**
   - 点击 `portfolio-monthly-report`
   - 点击 "Run workflow"
   - 检查 Discord

4. **测试确认轮询：**
   - 点击 `portfolio-confirm-poller`
   - 点击 "Run workflow"
   - 检查是否有新的 commit（如果有待确认交易）

**预期结果：**
- ✅ Workflow 运行成功（绿色勾）
- ✅ Discord 收到格式化消息
- ✅ 数据正确（市值、权重、信号）

---

### 🚧 阶段 3：Cron 定时测试

#### 3.1 配置 cron-job.org

访问：https://cron-job.org

**创建任务 1：日报（测试用，每5分钟）**
- Title: `Portfolio Daily Test`
- URL: `https://api.github.com/repos/MMorit00/DISCORD_AMPLITUDE_STATS/actions/workflows/portfolio-daily.yml/dispatches`
- Method: `POST`
- Schedule: `*/5 * * * *`（每5分钟，测试用）
- Headers:
  ```
  Authorization: token ghp_YOUR_GITHUB_TOKEN
  Accept: application/vnd.github.v3+json
  Content-Type: application/json
  ```
- Body:
  ```json
  {"ref":"main"}
  ```

**获取 GitHub Token：**
1. https://github.com/settings/tokens
2. Generate new token (classic)
3. 勾选 `repo` 和 `workflow`
4. 生成并复制

**测试步骤：**
1. 创建任务后，等待 5 分钟
2. 检查 cron-job.org 的执行历史（应该是 200 OK）
3. 检查 GitHub Actions（应该有新的运行）
4. 检查 Discord（应该收到消息）

**验证成功后：**
- 修改为正式时间（每天 08:30）
- 创建其他任务（周报、月报、确认轮询）

---

### 🚧 阶段 4：Discord Bot 测试（需要 Render 部署）

#### 4.1 注册 Discord Bot

访问：https://discord.com/developers/applications

**步骤：**
1. **创建应用**
   - New Application
   - 名称：Portfolio Bot

2. **获取 Token**
   - Bot → Reset Token
   - 复制 Token（保存到安全位置）

3. **开启 Intents**
   - Bot → Privileged Gateway Intents
   - 勾选 `Message Content Intent`

4. **邀请 Bot**
   - OAuth2 → URL Generator
   - 勾选 `bot`
   - Bot Permissions: `Send Messages`, `Read Message History`
   - 复制 URL 并打开，选择你的服务器

5. **获取你的 User ID**
   - Discord 设置 → 高级 → 开发者模式
   - 右键你的用户名 → 复制 ID

---

#### 4.2 本地测试 Bot（推荐先本地测试）

创建 `discord-bot/.env`：
```bash
cd discord-bot
cp .env.example .env
```

编辑 `.env`：
```bash
DISCORD_TOKEN=你的_Bot_Token
ALLOWED_USER_IDS=你的_User_ID
GITHUB_TOKEN=你的_GitHub_Token
GITHUB_REPO=MMorit00/DISCORD_AMPLITUDE_STATS
DASHSCOPE_API_KEY=你的_Qwen_API_Key  # 或其他 LLM
```

**运行 Bot：**
```bash
cd discord-bot
uv sync
uv run python bot.py
```

**测试交互：**
在 Discord 频道发送：
1. `!help` → 查看帮助
2. `!status` → 查询持仓
3. `今天没定投 018043` → 测试自然语言

**预期结果：**
- ✅ Bot 在线（显示在线状态）
- ✅ 命令有回复
- ✅ 自然语言能识别
- ✅ GitHub 有新 commit（[bot] skip_investment）

---

#### 4.3 部署到 Render

**步骤：**
1. 推送代码到 GitHub（包含 discord-bot/）
2. 访问：https://render.com
3. 创建 New → Background Worker
4. 连接 GitHub 仓库
5. 配置：
   - Name: `portfolio-discord-bot`
   - Region: `Singapore`
   - Branch: `main`
   - Root Directory: `discord-bot`
   - Build Command: `pip install -e .`
   - Start Command: `python bot.py`
6. 添加环境变量（从 .env 复制）
7. Deploy

**验证：**
- ✅ Render 显示 "Live"
- ✅ 日志无错误
- ✅ Discord Bot 在线
- ✅ 消息能正常交互

---

## 📋 测试检查清单

### 立即可测试（本地）
- [ ] 交易日历功能
- [ ] 数据抓取（真实 API）
- [ ] 持仓计算与权重
- [ ] 信号生成
- [ ] 报告生成

### 需要推送代码
- [ ] GitHub Actions 手动触发
- [ ] Discord Webhook 推送
- [ ] 确认轮询 commit

### 需要配置外部服务
- [ ] cron-job.org 定时触发
- [ ] Discord Bot 注册
- [ ] Bot 本地运行测试
- [ ] Render 部署

---

## 🚀 推荐测试顺序

### 第一步：立即测试本地功能（5分钟）
```bash
cd /Users/panlingchuan/Downloads/My_Project/Discord_amplitude_Stats/amplitude-discord-report

# 测试所有核心功能
uv run python portfolio-report/core/test_calendar.py
uv run python portfolio-report/sources/test_eastmoney.py
uv run python portfolio-report/core/test_portfolio.py
uv run python portfolio-report/core/test_report.py
```

### 第二步：推送并测试 Actions（10分钟）
```bash
# 推送代码
git push origin main

# 然后在 GitHub 网页手动触发测试
# 需要先配置 DISCORD_WEBHOOK_URL Secret
```

### 第三步：配置 cron-job.org（15分钟）
- 注册账号
- 配置 GitHub Token
- 创建测试任务（每5分钟）
- 验证成功后改为正式时间

### 第四步：Discord Bot（30分钟）
- 注册 Bot
- 本地测试
- Render 部署

---

## ⚠️ 常见问题

### Q1: Actions 运行失败？
检查：
- Secret 是否正确配置
- Webhook URL 是否有效
- uv 是否安装成功

### Q2: Bot 无法连接？
检查：
- DISCORD_TOKEN 是否正确
- Message Content Intent 是否开启
- 网络是否畅通

### Q3: LLM 调用失败？
检查：
- API Key 是否有效
- 是否有余额
- 降级到 OpenAI 测试

---

你想从哪一步开始测试？我建议先运行本地测试确认核心功能！

