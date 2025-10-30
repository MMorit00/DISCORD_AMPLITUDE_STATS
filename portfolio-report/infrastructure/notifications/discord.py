"""
Discord Webhook 客户端

职责：
- 发送文本消息（可选 embeds）到 Discord Webhook。
"""
import os
import logging
from typing import Optional, Dict, Any, List, TypedDict

import requests

__all__ = [
    "DiscordWebhookClient",
    "get_webhook_url",
    # 轻量模型与构建器
    "EmbedField",
    "Embed",
    "MessagePayload",
    "build_embed",
    "build_message",
]


logger = logging.getLogger(__name__)


class EmbedField(TypedDict, total=False):
    """Discord Embed 字段模型"""
    name: str
    value: str
    inline: bool


class Embed(TypedDict, total=False):
    """Discord Embed 模型"""
    title: str
    description: str
    color: int
    fields: List[EmbedField]


class MessagePayload(TypedDict, total=False):
    """Discord 消息负载模型"""
    content: str
    embeds: List[Embed]


def build_embed(
    title: str,
    description: str = "",
    *,
    color: int = 0x3498db,
    fields: Optional[List[EmbedField]] = None,
) -> Embed:
    """构建一个 Embed 结构（轻量构建器，不改变发送逻辑）"""
    embed: Embed = {"title": title, "description": description, "color": color}
    if fields:
        embed["fields"] = fields
    return embed


def build_message(
    content: str,
    embeds: Optional[List[Embed]] = None,
) -> MessagePayload:
    """构建一个消息负载结构（与 send 接口兼容）"""
    payload: MessagePayload = {"content": content}
    if embeds:
        payload["embeds"] = embeds
    return payload


class DiscordWebhookClient:
    """极简 Discord Webhook 客户端"""

    def __init__(
        self,
        webhook_url: str,
        *,
        timeout: int = 30,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.webhook_url = webhook_url
        self.timeout = timeout
        self.session = session

    def send(self, content: str, embeds: Optional[List[Embed]] = None) -> None:
        """发送消息到 Discord（可选 embeds）"""
        payload: Dict[str, Any] = {"content": content}
        if embeds:
            payload["embeds"] = embeds

        try:
            if self.session is not None:
                r = self.session.post(self.webhook_url, json=payload, timeout=self.timeout)
            else:
                r = requests.post(self.webhook_url, json=payload, timeout=self.timeout)
            r.raise_for_status()
            logger.info("已发送到 Discord")
        except Exception as e:
            logger.error(f"发送到 Discord 失败：{e}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"状态码：{e.response.status_code}，响应：{e.response.text}")
            raise

