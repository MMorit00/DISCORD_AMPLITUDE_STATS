# Cron 定时任务配置指南

> 使用 cron-job.org 或本机 cron 触发 GitHub Actions

---

## 🎯 为什么不用 GitHub Actions Schedule？

参考 `amplitude-report` 的经验：
- ❌ GitHub Actions schedule 延迟严重（有时延迟数小时）
- ❌ 有时完全不触发
- ✅ 改用外部 cron 触发 `workflow_dispatch` **可靠性高**

---

## 方案 A：cron-job.org（推荐，免费）

### 1. 注册并创建任务

访问：https://cron-job.org

### 2. 获取 GitHub Token

1. 访问：https://github.com/settings/tokens
2. 生成 Fine-grained Token
3. 权限：`actions: write`（触发 workflow）
4. 仓库：`MMorit00/DISCORD_AMPLITUDE_STATS`

### 3. 配置 Cron Jobs

创建以下任务（URL 格式）：

```
https://api.github.com/repos/MMorit00/DISCORD_AMPLITUDE_STATS/actions/workflows/portfolio-daily.yml/dispatches
```

**Headers:**
```
Authorization: token ghp_YOUR_GITHUB_TOKEN
Accept: application/vnd.github.v3+json
Content-Type: application/json
```

**Body (POST):**
```json
{"ref":"main"}
```

### 4. 定时配置

| 任务 | 时间（中国） | cron-job.org 表达式 |
|------|-------------|---------------------|
| 日报 | 08:30 | `30 8 * * *` (Asia/Shanghai) |
| 周报 | 周一 08:45 | `45 8 * * 1` |
| 月报 | 每天 09:45 | `45 9 * * *` |
| 确认轮询（上午） | 10:30 | `30 10 * * *` |
| 确认轮询（下午） | 18:30 | `30 18 * * *` |

**注意：** cron-job.org 支持时区选择，直接选择 `Asia/Shanghai` 即可，无需转换 UTC。

---

## 方案 B：本机 Mac Cron

### 1. 创建触发脚本

创建 `~/scripts/trigger-portfolio.sh`：

```bash
#!/bin/bash

# GitHub 配置
GITHUB_TOKEN="ghp_YOUR_GITHUB_TOKEN"
REPO="MMorit00/DISCORD_AMPLITUDE_STATS"

# 触发函数
trigger_workflow() {
    local workflow=$1
    echo "$(date): Triggering $workflow..."
    
    curl -X POST \
        -H "Authorization: token $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github.v3+json" \
        "https://api.github.com/repos/$REPO/actions/workflows/$workflow/dispatches" \
        -d '{"ref":"main"}'
    
    echo "Done"
}

# 根据参数触发不同的 workflow
case "$1" in
    daily)
        trigger_workflow "portfolio-daily.yml"
        ;;
    weekly)
        trigger_workflow "portfolio-weekly.yml"
        ;;
    monthly)
        trigger_workflow "portfolio-monthly.yml"
        ;;
    confirm)
        trigger_workflow "portfolio-confirm-poll.yml"
        ;;
    *)
        echo "Usage: $0 {daily|weekly|monthly|confirm}"
        exit 1
        ;;
esac
```

赋予执行权限：
```bash
chmod +x ~/scripts/trigger-portfolio.sh
```

### 2. 配置 Crontab

编辑 crontab：
```bash
crontab -e
```

添加以下任务：
```cron
# Portfolio Report Triggers
30 8 * * * ~/scripts/trigger-portfolio.sh daily      # 每天 08:30
45 8 * * 1 ~/scripts/trigger-portfolio.sh weekly     # 周一 08:45
45 9 * * * ~/scripts/trigger-portfolio.sh monthly    # 每天 09:45
30 10 * * * ~/scripts/trigger-portfolio.sh confirm   # 每天 10:30
30 18 * * * ~/scripts/trigger-portfolio.sh confirm   # 每天 18:30
```

### 3. 验证

查看 cron 日志：
```bash
tail -f /var/log/system.log | grep trigger-portfolio
```

---

## 方案 C：混合方案（推荐）

- **主要**：cron-job.org（免费、可靠、Web 管理界面）
- **备用**：本机 cron（Mac 开机时运行）

这样即使 cron-job.org 临时故障，本机 cron 也能兜底。

---

## 📝 触发 URL 列表

方便你配置 cron-job.org：

### 日报（每天 08:30）
```
POST https://api.github.com/repos/MMorit00/DISCORD_AMPLITUDE_STATS/actions/workflows/portfolio-daily.yml/dispatches
Body: {"ref":"main"}
```

### 周报（周一 08:45）
```
POST https://api.github.com/repos/MMorit00/DISCORD_AMPLITUDE_STATS/actions/workflows/portfolio-weekly.yml/dispatches
Body: {"ref":"main"}
```

### 月报（每天 09:45，脚本内判定）
```
POST https://api.github.com/repos/MMorit00/DISCORD_AMPLITUDE_STATS/actions/workflows/portfolio-monthly.yml/dispatches
Body: {"ref":"main"}
```

### 确认轮询（10:30 和 18:30）
```
POST https://api.github.com/repos/MMorit00/DISCORD_AMPLITUDE_STATS/actions/workflows/portfolio-confirm-poll.yml/dispatches
Body: {"ref":"main"}
```

---

## 🧪 手动测试

测试 workflow 是否正常：

```bash
# 方式1：GitHub 网页
# 访问 Actions 标签，点击对应 workflow，点击 "Run workflow"

# 方式2：命令行
export GITHUB_TOKEN="ghp_YOUR_TOKEN"
export REPO="MMorit00/DISCORD_AMPLITUDE_STATS"

curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  "https://api.github.com/repos/$REPO/actions/workflows/portfolio-daily.yml/dispatches" \
  -d '{"ref":"main"}'
```

---

## 📊 完整调度表

| 任务 | 中国时间 | cron 表达式 | Workflow |
|------|----------|-------------|----------|
| 日报 | 每天 08:30 | `30 8 * * *` | portfolio-daily.yml |
| 周报 | 周一 08:45 | `45 8 * * 1` | portfolio-weekly.yml |
| 月报 | 每天 09:45 | `45 9 * * *` | portfolio-monthly.yml |
| 确认（上午） | 每天 10:30 | `30 10 * * *` | portfolio-confirm-poll.yml |
| 确认（下午） | 每天 18:30 | `30 18 * * *` | portfolio-confirm-poll.yml |

---

## 📮 环境变量配置

在 GitHub 仓库设置中添加 Secret：

1. 访问：https://github.com/MMorit00/DISCORD_AMPLITUDE_STATS/settings/secrets/actions
2. 添加 `DISCORD_WEBHOOK_URL`

---

## ✅ 验证成功

成功的 workflow 运行会：
1. ✅ 出现在 Actions 标签
2. ✅ Discord 收到报告消息
3. ✅ 确认轮询会自动 commit 更新

失败时会在 Discord 收到错误通知。

