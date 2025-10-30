"""
Portfolio 输出格式化
职责：将业务结果格式化为 Discord 消息文本
依赖：shared.types, shared.utils
"""
from shared.types import Result, HoldingsSnapshot
from shared.utils import format_amount, format_percentage


# ==================== 格式化函数 ====================

def format_skip_investment(result: Result[None], fund_code: str, date: str) -> str:
    """格式化跳过定投结果"""
    if result.success:
        return f"✅ 已标记 {date} 的 {fund_code} 为'未定投'"
    else:
        return f"❌ 操作失败: {result.error}"


def format_update_position(result: Result[str], fund_code: str, amount: float) -> str:
    """格式化调整持仓结果"""
    if result.success:
        action = "买入" if amount > 0 else "赎回"
        return f"✅ 已记录 {fund_code} {action} {format_amount(abs(amount))}"
    else:
        return f"❌ 操作失败: {result.error}"


def format_confirm_shares(result: Result[None], fund_code: str, trade_date: str, shares: float) -> str:
    """格式化确认份额结果"""
    if result.success:
        return f"✅ 已确认 {fund_code} {trade_date} 的份额: {shares:.2f}"
    else:
        return f"❌ 操作失败: {result.error}"


def format_query_status(result: Result[HoldingsSnapshot]) -> str:
    """格式化查询持仓结果"""
    if not result.success:
        return f"❌ 查询失败: {result.error}"
    
    holdings = result.data
    if not holdings:
        return "❌ 无持仓数据"
    
    lines = []
    lines.append(f"💰 总市值: {format_amount(holdings.total_value_net)}")
    lines.append("\n📊 权重分布:")
    
    for asset, weight in holdings.weights_net.items():
        lines.append(f"  • {asset}: {format_percentage(weight)}")
    
    return "\n".join(lines)


def format_delete_transaction(result: Result[None], tx_id: str) -> str:
    """格式化删除交易结果"""
    if result.success:
        return f"✅ 已删除交易 {tx_id}"
    else:
        return f"❌ 操作失败: {result.error}"


def format_text_reply(content: str) -> str:
    """格式化纯文本回复"""
    return content


def format_error(error_msg: str) -> str:
    """格式化错误消息"""
    return f"❌ {error_msg}"

