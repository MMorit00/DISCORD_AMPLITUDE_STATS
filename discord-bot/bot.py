"""
Discord Bot 主程序
常驻监听 Gateway，处理用户自然语言交互
"""
import os
import sys
import logging
from dotenv import load_dotenv
import discord
from discord.ext import commands
import aiohttp

from llm_handler import get_llm_handler
from github_sync import GitHubSync
from functions import TOOLS, FunctionExecutor

# 加载环境变量
load_dotenv()

# 配置代理（如果环境变量中有）
PROXY = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
if PROXY:
    logger = logging.getLogger(__name__)
    logger.info(f"使用代理: {PROXY}")

# 日志配置
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)


# Discord Bot 配置
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ALLOWED_USER_IDS = [
    int(uid.strip())
    for uid in os.getenv("ALLOWED_USER_IDS", "").split(",")
    if uid.strip()
]

if not DISCORD_TOKEN:
    logger.error("缺少 DISCORD_TOKEN 环境变量")
    sys.exit(1)

if not ALLOWED_USER_IDS:
    logger.error("缺少 ALLOWED_USER_IDS 环境变量")
    sys.exit(1)


# 创建 Bot 实例
intents = discord.Intents.default()
intents.message_content = True  # 需要 Message Content Intent

# Bot 实例（代理通过环境变量传递，discord.py 会自动使用）
bot = commands.Bot(command_prefix="!", intents=intents, proxy=PROXY if PROXY else None)


# 初始化组件
llm_handler = get_llm_handler()
github_sync = GitHubSync()
function_executor = FunctionExecutor(github_sync)


@bot.event
async def on_ready():
    """Bot 启动事件"""
    logger.info(f"Bot 已登录: {bot.user.name} (ID: {bot.user.id})")
    logger.info(f"允许的用户 ID: {ALLOWED_USER_IDS}")


@bot.event
async def on_message(message: discord.Message):
    """消息事件处理"""
    # 忽略 Bot 自己的消息
    if message.author == bot.user:
        return
    
    # 权限校验
    if message.author.id not in ALLOWED_USER_IDS:
        logger.warning(f"未授权用户尝试操作: {message.author.id}")
        return
    
    # 处理命令
    if message.content.startswith("!"):
        await bot.process_commands(message)
        return
    
    # 自然语言处理
    try:
        logger.info(f"收到消息: {message.author.name}: {message.content}")
        
        # 发送"处理中"提示
        async with message.channel.typing():
            # 调用 LLM 解析
            result = llm_handler.parse_message(message.content, TOOLS)
            
            if not result:
                await message.reply("❌ 抱歉，我无法理解你的意思。请重新描述。")
                return
            
            # 如果是纯文本回复
            if result.get("function_name") is None:
                await message.reply(result.get("text_response", "我理解了。"))
                return
            
            # 执行函数
            function_name = result["function_name"]
            arguments = result["arguments"]
            
            logger.info(f"执行函数: {function_name}({arguments})")
            
            exec_result = function_executor.execute(function_name, arguments)
            
            if exec_result.get("success"):
                await message.reply(exec_result.get("message", "✅ 操作成功"))
            else:
                error_msg = exec_result.get("error", "未知错误")
                await message.reply(f"❌ 操作失败: {error_msg}")
    
    except Exception as e:
        logger.exception(f"处理消息失败: {e}")
        await message.reply(f"❌ 处理失败: {str(e)}")


@bot.command(name="status")
async def status_command(ctx):
    """查询持仓状态（命令版）"""
    logger.info(f"命令调用: !status by {ctx.author.name}")
    
    try:
        result = function_executor.query_status()
        
        if result.get("success"):
            await ctx.reply(result.get("message"))
        else:
            await ctx.reply(f"❌ {result.get('error')}")
    
    except Exception as e:
        logger.error(f"status 命令失败: {e}")
        await ctx.reply(f"❌ 查询失败: {str(e)}")


@bot.command(name="guide")
async def guide_command(ctx):
    """使用指南"""
    help_text = """
📋 **Portfolio Bot 使用指南**

**自然语言示例：**
• "今天没定投 018043" → 跳过定投
• "调整 000051 +500" → 买入 500 元
• "确认份额 018043 100份 2025-10-25" → 回填份额
• "查询持仓" → 查看当前状态
• "删除交易 tx001" → 删除记录

**命令模式：**
• `!status` - 查询持仓
• `!guide` - 使用指南

**支持的操作：**
✅ 跳过定投
✅ 调整持仓
✅ 确认份额
✅ 查询状态
✅ 删除交易
"""
    await ctx.reply(help_text)


def main():
    """主函数"""
    logger.info("启动 Discord Bot...")
    
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot 停止")
    except Exception as e:
        logger.exception(f"Bot 运行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

