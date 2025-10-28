"""
Discord Bot 工具函数定义
供 LLM Function Calling 使用
"""
import logging
from typing import Dict, Any, List
from datetime import datetime, date

logger = logging.getLogger(__name__)


# ============================================================
# 工具函数定义（OpenAI Function Calling 格式）
# ============================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "skip_investment",
            "description": "标记某日某基金为未定投，从统计中移除",
            "parameters": {
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
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_position",
            "description": "调整持仓，正数为买入，负数为赎回",
            "parameters": {
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
        }
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_shares",
            "description": "确认份额（净值公布后回填）",
            "parameters": {
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
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_status",
            "description": "查询当前持仓与权重",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_transaction",
            "description": "删除指定交易记录",
            "parameters": {
                "type": "object",
                "properties": {
                    "tx_id": {
                        "type": "string",
                        "description": "交易 ID"
                    }
                },
                "required": ["tx_id"]
            }
        }
    }
]


# ============================================================
# 工具函数实现
# ============================================================

class FunctionExecutor:
    """工具函数执行器"""
    
    def __init__(self, github_sync):
        """
        Args:
            github_sync: GitHubSync 实例
        """
        self.github_sync = github_sync
    
    def execute(self, function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具函数
        
        Args:
            function_name: 函数名
            arguments: 参数字典
        
        Returns:
            执行结果
        """
        logger.info(f"执行函数: {function_name}, 参数: {arguments}")
        
        if function_name == "skip_investment":
            return self.skip_investment(**arguments)
        
        elif function_name == "update_position":
            return self.update_position(**arguments)
        
        elif function_name == "confirm_shares":
            return self.confirm_shares(**arguments)
        
        elif function_name == "query_status":
            return self.query_status(**arguments)
        
        elif function_name == "delete_transaction":
            return self.delete_transaction(**arguments)
        
        else:
            return {
                "success": False,
                "error": f"未知函数: {function_name}"
            }
    
    def skip_investment(self, date: str, fund_code: str) -> Dict[str, Any]:
        """跳过定投"""
        try:
            # 解析日期
            if date.lower() == "today":
                target_date = datetime.now().date()
            else:
                target_date = datetime.strptime(date, "%Y-%m-%d").date()
            
            # 通过 GitHub API 更新
            result = self.github_sync.skip_transaction(fund_code, target_date)
            
            if result["success"]:
                return {
                    "success": True,
                    "message": f"✅ 已标记 {target_date} 的 {fund_code} 为'未定投'"
                }
            else:
                return result
        
        except Exception as e:
            logger.error(f"skip_investment 失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def update_position(
        self,
        fund_code: str,
        amount: float,
        trade_time: str = None
    ) -> Dict[str, Any]:
        """更新持仓"""
        try:
            # 解析交易时间
            if trade_time:
                trade_dt = datetime.strptime(trade_time, "%Y-%m-%d %H:%M")
            else:
                trade_dt = datetime.now()
            
            # 通过 GitHub API 添加交易
            tx_type = "buy" if amount > 0 else "sell"
            result = self.github_sync.add_transaction(
                fund_code=fund_code,
                amount=abs(amount),
                trade_time=trade_dt,
                tx_type=tx_type
            )
            
            if result["success"]:
                action = "买入" if amount > 0 else "赎回"
                return {
                    "success": True,
                    "message": f"✅ 已记录 {fund_code} {action} ¥{abs(amount):.0f}"
                }
            else:
                return result
        
        except Exception as e:
            logger.error(f"update_position 失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def confirm_shares(
        self,
        fund_code: str,
        trade_date: str,
        shares: float
    ) -> Dict[str, Any]:
        """确认份额"""
        try:
            target_date = datetime.strptime(trade_date, "%Y-%m-%d").date()
            
            result = self.github_sync.confirm_transaction(
                fund_code=fund_code,
                trade_date=target_date,
                shares=shares
            )
            
            if result["success"]:
                return {
                    "success": True,
                    "message": f"✅ 已确认 {fund_code} {trade_date} 的份额: {shares:.2f}"
                }
            else:
                return result
        
        except Exception as e:
            logger.error(f"confirm_shares 失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def query_status(self) -> Dict[str, Any]:
        """查询持仓状态"""
        try:
            # 读取最新的 holdings.json
            holdings = self.github_sync.read_holdings()
            
            if not holdings:
                return {
                    "success": False,
                    "error": "无法读取持仓数据"
                }
            
            # 格式化输出
            lines = []
            lines.append(f"💰 总市值: ¥{holdings.get('total_value_net', 0):,.2f}")
            lines.append("\n📊 权重分布:")
            
            weights = holdings.get('weights_net', {})
            for asset, weight in weights.items():
                lines.append(f"  • {asset}: {weight*100:.2f}%")
            
            return {
                "success": True,
                "message": "\n".join(lines),
                "data": holdings
            }
        
        except Exception as e:
            logger.error(f"query_status 失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def delete_transaction(self, tx_id: str) -> Dict[str, Any]:
        """删除交易"""
        try:
            result = self.github_sync.delete_transaction(tx_id)
            
            if result["success"]:
                return {
                    "success": True,
                    "message": f"✅ 已删除交易 {tx_id}"
                }
            else:
                return result
        
        except Exception as e:
            logger.error(f"delete_transaction 失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

