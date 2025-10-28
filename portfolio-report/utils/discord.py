"""
Discord Webhook 发送工具（复用 amplitude-discord-report 的逻辑）
"""
import os
import logging
import requests
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


def post_to_discord(webhook_url: str, content: str, embeds: Optional[List[Dict[str, Any]]] = None):
    """
    发送消息到 Discord
    
    Args:
        webhook_url: Discord Webhook URL
        content: 消息文本内容
        embeds: 可选的 Embed 列表（用于美化报告）
    """
    payload = {"content": content}
    if embeds:
        payload["embeds"] = embeds
    
    try:
        r = requests.post(webhook_url, json=payload, timeout=30)
        r.raise_for_status()
        logger.info("已发送到 Discord")
    except Exception as e:
        logger.error(f"发送到 Discord 失败：{e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"状态码：{e.response.status_code}，响应：{e.response.text}")
        raise


def create_embed(title: str, description: str = "", color: int = 0x3498db, 
                 fields: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    创建 Discord Embed 对象
    
    Args:
        title: 标题
        description: 描述
        color: 颜色（十六进制，默认蓝色）
        fields: 字段列表，格式 [{"name": "字段名", "value": "值", "inline": True/False}]
    
    Returns:
        Embed 字典
    """
    embed = {
        "title": title,
        "description": description,
        "color": color
    }
    
    if fields:
        embed["fields"] = fields
    
    return embed


def get_webhook_url() -> str:
    """从环境变量获取 Discord Webhook URL"""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        raise ValueError("缺少环境变量：DISCORD_WEBHOOK_URL")
    return webhook_url

