"""
再平衡与战术信号引擎
支持：净口径信号、冷却机制、优先级处理
"""
import json
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from pathlib import Path

from utils.config_loader import ConfigLoader
from core.metrics import get_metrics

logger = logging.getLogger(__name__)


class Signal:
    """信号对象"""
    
    def __init__(
        self,
        signal_type: str,
        asset_class: str,
        action: str,
        amount: Optional[Decimal] = None,
        reason: str = "",
        urgency: str = "medium",
        risk_note: str = ""
    ):
        self.signal_type = signal_type  # rebalance_light, rebalance_strong, tactical_add, tactical_reduce
        self.asset_class = asset_class
        self.action = action            # buy, sell, rebalance
        self.amount = amount
        self.reason = reason
        self.urgency = urgency          # low, medium, high
        self.risk_note = risk_note
        self.triggered_at = datetime.now().date()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "signal_type": self.signal_type,
            "asset_class": self.asset_class,
            "action": self.action,
            "amount": float(self.amount) if self.amount else None,
            "reason": self.reason,
            "urgency": self.urgency,
            "risk_note": self.risk_note,
            "triggered_at": self.triggered_at.isoformat()
        }
    
    def __repr__(self) -> str:
        return (f"Signal({self.signal_type}, {self.asset_class}, "
                f"{self.action}, ¥{self.amount}, {self.urgency})")


class SignalEngine:
    """信号引擎"""
    
    def __init__(
        self,
        config: Optional[ConfigLoader] = None,
        state_file: Optional[str] = None
    ):
        self.config = config or ConfigLoader()
        
        if state_file is None:
            base_dir = Path(__file__).parent.parent
            state_file = base_dir / "data" / "state.json"
        
        self.state_file = Path(state_file)
        self.state = self._load_state()
        self.metrics = get_metrics()
    
    def _load_state(self) -> Dict[str, Any]:
        """加载信号状态"""
        if not self.state_file.exists():
            return {
                "last_signals": {},
                "signal_history": [],
                "last_rebalance": None,
                "cooldown_tracker": {}
            }
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载状态文件失败: {e}")
            return {
                "last_signals": {},
                "signal_history": [],
                "last_rebalance": None,
                "cooldown_tracker": {}
            }
    
    def _save_state(self):
        """保存信号状态"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
            logger.info(f"保存信号状态: {self.state_file}")
        except Exception as e:
            logger.error(f"保存状态文件失败: {e}")
    
    def check_cooldown(self, asset_class: str, signal_type: str) -> bool:
        """
        检查是否在冷却期
        
        Args:
            asset_class: 资产类别
            signal_type: 信号类型
        
        Returns:
            True 表示在冷却期，False 表示可以触发
        """
        cooldown_tracker = self.state.get("cooldown_tracker", {})
        key = f"{asset_class}_{signal_type}"
        
        if key not in cooldown_tracker:
            return False
        
        cooldown_until_str = cooldown_tracker[key].get("cooldown_until")
        if not cooldown_until_str:
            return False
        
        try:
            cooldown_until = datetime.fromisoformat(cooldown_until_str).date()
            today = date.today()
            
            if today < cooldown_until:
                days_left = (cooldown_until - today).days
                logger.info(f"{asset_class} {signal_type} 冷却中，剩余 {days_left} 天")
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"冷却期检查失败: {e}")
            return False
    
    def set_cooldown(self, asset_class: str, signal_type: str, days: int):
        """
        设置冷却期
        
        Args:
            asset_class: 资产类别
            signal_type: 信号类型
            days: 冷却天数
        """
        cooldown_until = date.today() + timedelta(days=days)
        
        cooldown_tracker = self.state.setdefault("cooldown_tracker", {})
        key = f"{asset_class}_{signal_type}"
        
        cooldown_tracker[key] = {
            "triggered_at": date.today().isoformat(),
            "cooldown_until": cooldown_until.isoformat(),
            "days": days
        }
        
        logger.info(f"设置冷却：{asset_class} {signal_type} → {cooldown_until}")
    
    def generate_rebalance_signals(
        self,
        weights_net: Dict[str, Decimal],
        target_weights: Dict[str, float],
        total_value: Decimal
    ) -> List[Signal]:
        """
        生成再平衡信号
        
        Args:
            weights_net: 实际权重（净口径）
            target_weights: 目标权重
            total_value: 总市值
        
        Returns:
            信号列表
        """
        signals = []
        thresholds = self.config.get_thresholds()
        
        light_threshold = Decimal(str(thresholds.get("rebalance_light_absolute", 0.05)))
        strong_threshold = Decimal(str(thresholds.get("rebalance_strong_relative", 0.20)))
        
        cooldown_days = thresholds.get("cooldown_days", {})
        
        for asset_class, target in target_weights.items():
            target_decimal = Decimal(str(target))
            actual = weights_net.get(asset_class, Decimal("0"))
            
            # 绝对偏离
            abs_deviation = abs(actual - target_decimal)
            
            # 相对偏离
            if target_decimal > 0:
                rel_deviation = abs(actual / target_decimal - Decimal("1"))
            else:
                rel_deviation = Decimal("0")
            
            # 强制再平衡（优先级高）
            if rel_deviation >= strong_threshold:
                if self.check_cooldown(asset_class, "rebalance_strong"):
                    continue
                
                # 计算需要调整的金额
                target_value = total_value * target_decimal
                current_value = total_value * actual
                adjust_amount = target_value - current_value
                
                action = "buy" if adjust_amount > 0 else "sell"
                
                signal = Signal(
                    signal_type="rebalance_strong",
                    asset_class=asset_class,
                    action=action,
                    amount=abs(adjust_amount),
                    reason=f"相对偏离 {float(rel_deviation)*100:.2f}%（阈值 {float(strong_threshold)*100:.0f}%），建议强制再平衡",
                    urgency="high"
                )
                signals.append(signal)
                
                logger.info(f"触发强制再平衡信号: {signal}")
                continue
            
            # 轻度再平衡
            if abs_deviation >= light_threshold:
                if self.check_cooldown(asset_class, "rebalance_light"):
                    continue
                
                target_value = total_value * target_decimal
                current_value = total_value * actual
                adjust_amount = target_value - current_value
                
                action = "buy" if adjust_amount > 0 else "sell"
                
                signal = Signal(
                    signal_type="rebalance_light",
                    asset_class=asset_class,
                    action=action,
                    amount=abs(adjust_amount),
                    reason=f"绝对偏离 {float(abs_deviation)*100:.2f}%（阈值 {float(light_threshold)*100:.0f}%），建议调整至目标",
                    urgency="medium"
                )
                signals.append(signal)
                
                logger.info(f"触发轻度再平衡信号: {signal}")
        
        return signals
    
    def generate_tactical_signals(
        self,
        asset_class: str,
        nav_90d_series: List[Tuple[date, Decimal]],
        current_weight: Decimal,
        target_weight: Decimal,
        fund_type: str = "domestic"
    ) -> Optional[Signal]:
        """
        生成战术信号（加仓/减仓）
        
        Args:
            asset_class: 资产类别
            nav_90d_series: 近90日净值序列
            current_weight: 当前权重
            target_weight: 目标权重
            fund_type: 基金类型（用于风险提示）
        
        Returns:
            信号对象或 None
        """
        thresholds = self.config.get_thresholds()
        
        dd_threshold = Decimal(str(thresholds.get("tactical_drawdown", 0.10)))
        profit_threshold = Decimal(str(thresholds.get("tactical_profit", 0.15)))
        cooldown_days = thresholds.get("cooldown_days", {}).get("tactical", 30)
        
        # 计算90日回撤
        peak_90d, drawdown_90d = self.metrics.calculate_90d_drawdown(nav_90d_series)
        
        if peak_90d is None or drawdown_90d is None:
            logger.debug(f"{asset_class} 数据不足，跳过战术信号")
            return None
        
        # 加仓信号：回撤 >= 10% 且不超重
        if drawdown_90d <= -dd_threshold and current_weight <= target_weight:
            if self.check_cooldown(asset_class, "tactical_add"):
                return None
            
            # 建议加码金额（可配置）
            suggest_amount = Decimal("200")
            
            risk_note = ""
            if fund_type == "QDII":
                risk_note = "QDII 隔夜风险：今晚若反向波动，成交价将偏离触发点"
            
            signal = Signal(
                signal_type="tactical_add",
                asset_class=asset_class,
                action="buy",
                amount=suggest_amount,
                reason=f"近90日回撤 {float(drawdown_90d)*100:.2f}%（阈值 {float(dd_threshold)*100:.0f}%），且权重未超标，建议加码",
                urgency="medium",
                risk_note=risk_note
            )
            
            logger.info(f"触发战术加仓信号: {signal}")
            return signal
        
        # 减仓信号：超额收益 > 15% 且超重
        # TODO: 需要基准收益数据，暂用 90日高点作为简化判断
        if drawdown_90d >= profit_threshold and current_weight >= target_weight:
            if self.check_cooldown(asset_class, "tactical_reduce"):
                return None
            
            suggest_amount = Decimal("200")
            
            signal = Signal(
                signal_type="tactical_reduce",
                asset_class=asset_class,
                action="sell",
                amount=suggest_amount,
                reason=f"相对90日高点超额 {float(drawdown_90d)*100:.2f}%（阈值 {float(profit_threshold)*100:.0f}%），且权重超标，建议减码",
                urgency="low"
            )
            
            logger.info(f"触发战术减仓信号: {signal}")
            return signal
        
        return None
    
    def prioritize_signals(self, signals: List[Signal]) -> List[Signal]:
        """
        信号优先级排序与冲突处理
        
        优先级：
        1. rebalance_strong（高）
        2. rebalance_light（中）
        3. tactical_add/tactical_reduce（低）
        
        Args:
            signals: 信号列表
        
        Returns:
            排序后的信号列表
        """
        priority_map = {
            "rebalance_strong": 3,
            "rebalance_light": 2,
            "tactical_add": 1,
            "tactical_reduce": 1
        }
        
        # 按优先级排序
        sorted_signals = sorted(
            signals,
            key=lambda s: priority_map.get(s.signal_type, 0),
            reverse=True
        )
        
        # 同一资产的信号合并（保留优先级高的）
        seen_assets = set()
        filtered_signals = []
        
        for signal in sorted_signals:
            if signal.asset_class not in seen_assets:
                filtered_signals.append(signal)
                seen_assets.add(signal.asset_class)
            else:
                logger.info(f"信号冲突，保留高优先级: {signal.asset_class}")
        
        return filtered_signals
    
    def record_signal(self, signal: Signal, executed: bool = False):
        """
        记录信号到历史
        
        Args:
            signal: 信号对象
            executed: 是否已执行
        """
        history = self.state.setdefault("signal_history", [])
        
        record = signal.to_dict()
        record["executed"] = executed
        record["recorded_at"] = datetime.now().isoformat()
        
        history.append(record)
        
        # 只保留最近 100 条
        if len(history) > 100:
            self.state["signal_history"] = history[-100:]
        
        # 如果已执行，设置冷却期
        if executed:
            cooldown_days_config = self.config.get_thresholds().get("cooldown_days", {})
            
            if signal.signal_type == "rebalance_strong":
                days = cooldown_days_config.get("strong", 90)
            elif signal.signal_type == "rebalance_light":
                days = cooldown_days_config.get("light", 60)
            else:  # tactical
                days = cooldown_days_config.get("tactical", 30)
            
            self.set_cooldown(signal.asset_class, signal.signal_type, days)
        
        self._save_state()
        logger.info(f"记录信号: {signal}, 已执行={executed}")


# 全局实例
_signal_engine_instance: Optional[SignalEngine] = None


def get_signal_engine(
    config: Optional[ConfigLoader] = None,
    state_file: Optional[str] = None
) -> SignalEngine:
    """获取信号引擎实例（单例模式）"""
    global _signal_engine_instance
    if _signal_engine_instance is None:
        _signal_engine_instance = SignalEngine(config, state_file)
    return _signal_engine_instance

