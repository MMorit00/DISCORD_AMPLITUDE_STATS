"""
LLM 工具定义（与 TransactionService 的用例对应）
"""
from typing import List, Dict, Any
from discord_bot.shared.types import ToolSpec


def _object(properties: Dict[str, Any], required: List[str] | None = None) -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
    }


all_tools: List[ToolSpec] = [
    ToolSpec(
        name="skip_investment",
        description="标记某天某基金未进行定投",
        parameters=_object(
            {
                "fund_code": {"type": "string", "description": "基金代码(6位数字)"},
                "date": {"type": "string", "description": "日期，如 2025-10-25 或 today"},
            },
            required=["fund_code", "date"],
        ),
    ),
    ToolSpec(
        name="update_position",
        description="调整持仓金额，正数买入，负数赎回",
        parameters=_object(
            {
                "fund_code": {"type": "string", "description": "基金代码(6位数字)"},
                "amount": {"type": "number", "description": "变动金额，正买负卖"},
                "trade_time": {"type": "string", "description": "可选，交易时间 HH:MM", "nullable": True},
            },
            required=["fund_code", "amount"],
        ),
    ),
    ToolSpec(
        name="confirm_shares",
        description="确认某日的成交份额",
        parameters=_object(
            {
                "fund_code": {"type": "string"},
                "trade_date": {"type": "string"},
                "shares": {"type": "number"},
            },
            required=["fund_code", "trade_date", "shares"],
        ),
    ),
    ToolSpec(
        name="query_status",
        description="查询当前持仓状态",
        parameters=_object({}, required=[]),
    ),
    ToolSpec(
        name="delete_transaction",
        description="删除一条交易记录",
        parameters=_object(
            {
                "tx_id": {"type": "string", "description": "交易ID"},
            },
            required=["tx_id"],
        ),
    ),
]


