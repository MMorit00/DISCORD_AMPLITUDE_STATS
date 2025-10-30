"""
Discord Bot 适配器
职责：处理 Discord 事件，收发消息
依赖：config.Settings, presentation.MessageRouter
"""
import logging
import discord
from discord.ext import commands

from config.settings import Settings
from discord_bot.presentation.message_router import MessageRouter

logger = logging.getLogger(__name__)


class DiscordBotAdapter:
    """Discord Bot 适配器"""
    
    def __init__(self, settings: Settings, message_router: MessageRouter):
        """
        初始化
        
        Args:
            settings: 配置对象
            message_router: 消息路由器
        """
        self.settings = settings
        self.message_router = message_router
        
        # 创建 Bot 实例
        intents = discord.Intents.default()
        intents.message_content = True
        
        self.bot = commands.Bot(
            command_prefix="!",
            intents=intents,
            proxy=settings.proxy if settings.proxy else None
        )
        
        # 注册事件处理器
        self._register_handlers()
    
    # ==================== 事件注册 ====================
    
    def _register_handlers(self):
        """注册事件处理器"""
        
        @self.bot.event
        async def on_ready():
            """Bot 启动事件"""
            logger.info(f"Bot 已登录: {self.bot.user.name} (ID: {self.bot.user.id})")
            logger.info(f"允许的用户 ID: {self.settings.allowed_user_ids}")
        
        @self.bot.event
        async def on_message(message: discord.Message):
            """消息事件"""
            # 忽略 Bot 自己的消息
            if message.author == self.bot.user:
                return
            
            # 权限校验
            if message.author.id not in self.settings.allowed_user_ids:
                logger.warning(f"未授权用户尝试操作: {message.author.id}")
                return
            
            # 处理命令
            if message.content.startswith("!"):
                await self.bot.process_commands(message)
                return
            
            # 处理自然语言
            await self._handle_natural_language(message)
        
        @self.bot.command(name="status")
        async def status_command(ctx):
            """查询持仓状态命令"""
            logger.info(f"命令调用: !status by {ctx.author.name}")
            reply = self.message_router.route_message("", is_command=True)
            await ctx.reply(reply)
        
        @self.bot.command(name="guide")
        async def guide_command(ctx):
            """使用指南命令"""
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
    
    # ==================== 私有方法 ====================
    
    async def _handle_natural_language(self, message: discord.Message):
        """处理自然语言消息"""
        try:
            logger.info(f"收到消息: {message.author.name}: {message.content}")
            
            # 发送"处理中"提示
            async with message.channel.typing():
                reply = self.message_router.route_message(message.content)
                await message.reply(reply)
        
        except Exception as e:
            logger.exception(f"处理消息失败: {e}")
            await message.reply(f"❌ 处理失败: {str(e)}")
    
    # ==================== 公开接口 ====================
    
    def run(self):
        """启动 Bot"""
        logger.info("启动 Discord Bot...")
        try:
            self.bot.run(self.settings.discord_token)
        except KeyboardInterrupt:
            logger.info("Bot 停止")
        except Exception as e:
            logger.exception(f"Bot 运行失败: {e}")
            raise

