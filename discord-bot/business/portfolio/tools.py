"""
Portfolio 工具定义
职责：定义投资组合相关的 LLM 工具规范
依赖：shared.ToolSpec
"""
from shared import ToolSpec


# ==================== 工具定义 ====================

skip_investment = ToolSpec(
    name="skip_investment",
    description="标记某日某基金为未定投，从统计中移除",
    parameters={
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "日期，格式 YYYY-MM-DD 或 'today'"
            },
            "fund_code": {
                "type": "string",
                "description": "基金代码（如 018043）"
            }
        },
        "required": ["date", "fund_code"]
    }
)

update_position = ToolSpec(
    name="update_position",
    description="调整持仓，正数为买入，负数为赎回",
    parameters={
        "type": "object",
        "properties": {
            "fund_code": {
                "type": "string",
                "description": "基金代码"
            },
            "amount": {
                "type": "number",
                "description": "金额（元），正数买入负数赎回"
            },
            "trade_time": {
                "type": "string",
                "description": "交易时间（可选），格式 YYYY-MM-DD HH:MM，默认为当前时间"
            }
        },
        "required": ["fund_code", "amount"]
    }
)

confirm_shares = ToolSpec(
    name="confirm_shares",
    description="确认份额（净值公布后回填）",
    parameters={
        "type": "object",
        "properties": {
            "fund_code": {
                "type": "string",
                "description": "基金代码"
            },
            "trade_date": {
                "type": "string",
                "description": "交易日期，格式 YYYY-MM-DD"
            },
            "shares": {
                "type": "number",
                "description": "确认的份额"
            }
        },
        "required": ["fund_code", "trade_date", "shares"]
    }
)

query_status = ToolSpec(
    name="query_status",
    description="查询当前持仓与权重",
    parameters={
        "type": "object",
        "properties": {},
        "required": []
    }
)

delete_transaction = ToolSpec(
    name="delete_transaction",
    description="删除指定交易记录",
    parameters={
        "type": "object",
        "properties": {
            "tx_id": {
                "type": "string",
                "description": "交易 ID"
            }
        },
        "required": ["tx_id"]
    }
)


# ==================== 工具集合 ====================

all_tools = [
    skip_investment,
    update_position,
    confirm_shares,
    query_status,
    delete_transaction,
]

