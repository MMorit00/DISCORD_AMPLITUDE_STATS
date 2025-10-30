"""
再平衡与战术信号引擎
支持：净口径信号、冷却机制、优先级处理
"""
import json
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple, Literal
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from domain.models import Signal
from infrastructure.config.config_loader import ConfigLoader
from config.constants import (
    SignalType as SignalTypeConst,
    ActionType as ActionTypeConst,
    UrgencyType as UrgencyTypeConst,
    ThresholdKeys,
    CooldownKeys,
    FundType,
)

logger = logging.getLogger(__name__)


# ==================
# Types & Constants
# ==================

SignalType = Literal["rebalance_light", "rebalance_strong", "tactical_add", "tactical_reduce"]
ActionType = Literal["buy", "sell", "rebalance"]
UrgencyType = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class Thresholds:
    """阈值配置模型（从配置读取后可映射为该结构）
    仅结构化，不改变取值逻辑。
    """
    rebalance_light_absolute: float
    rebalance_strong_relative: float
    tactical_drawdown: float
    tactical_profit: float
    cooldown_days: Dict[str, int]


# ==================
# Repositories（状态持久化）
# ==================

class SignalStateRepository:
    """信号状态仓储（负责 state.json 的读写）
    
    职责：
    - 加载状态文件 -> Dict
    - 保存状态 Dict -> 文件
    - 初始化空状态结构
    """
    
    def __init__(self, state_file: Path):
        self.state_file = state_file
    
    def load(self) -> Dict[str, Any]:
        """加载状态文件，不存在或失败则返回默认空结构"""
        if not self.state_file.exists():
            return self._default_state()
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载状态文件失败: {e}")
            return self._default_state()
    
    def save(self, state: Dict[str, Any]) -> None:
        """保存状态到文件"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            logger.info(f"保存信号状态: {self.state_file}")
        except Exception as e:
            logger.error(f"保存状态文件失败: {e}")
    
    def _default_state(self) -> Dict[str, Any]:
        """默认空状态结构"""
        return {
            "last_signals": {},
            "signal_history": [],
            "last_rebalance": None,
            "cooldown_tracker": {}
        }


# ==================
# Services（服务层）
# ==================

class ThresholdsProvider:
    """阈值提供服务（集中从配置读取阈值）
    
    职责：
    - 统一读取阈值配置
    - 可选返回结构化 Thresholds 对象
    """
    
    def __init__(self, config: ConfigLoader):
        self.config = config
    
    def get_raw(self) -> Dict[str, Any]:
        """获取原始阈值字典（保持兼容现有逻辑）"""
        return self.config.get_thresholds()
    
    def get_structured(self) -> Thresholds:
        """获取结构化阈值对象（可选，便于策略层使用）"""
        raw = self.get_raw()
        return Thresholds(
            rebalance_light_absolute=raw.get(ThresholdKeys.rebalance_light_absolute, 0.05),
            rebalance_strong_relative=raw.get(ThresholdKeys.rebalance_strong_relative, 0.20),
            tactical_drawdown=raw.get(ThresholdKeys.tactical_drawdown, 0.10),
            tactical_profit=raw.get(ThresholdKeys.tactical_profit, 0.15),
            cooldown_days=raw.get(ThresholdKeys.cooldown_days, {})
        )


# ==================
# Policies（策略层）
# ==================

class CooldownPolicy:
    """冷却策略（负责冷却期检查与设置）
    
    职责：
    - 检查资产+信号类型是否在冷却期
    - 设置冷却期（天数）
    - 状态由 state 字典管理，仓储负责持久化
    """
    
    def __init__(self, state: Dict[str, Any]):
        """
        Args:
            state: Engine 的状态字典（包含 cooldown_tracker）
        """
        self.state = state
    
    def check(self, asset_class: str, signal_type: str) -> bool:
        """
        检查是否在冷却期
        
        Returns:
            True=冷却中，False=可触发
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
    
    def set(self, asset_class: str, signal_type: str, days: int):
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


class RebalancePolicy:
    """再平衡策略（生成再平衡信号）
    
    职责：
    - 根据权重偏离生成轻度/强制再平衡信号
    - 输入：实际权重、目标权重、总市值、阈值
    - 输出：信号列表
    """
    
    def __init__(self, thresholds_provider: ThresholdsProvider, cooldown_policy: CooldownPolicy):
        self.thresholds_provider = thresholds_provider
        self.cooldown_policy = cooldown_policy
    
    def generate(
        self,
        weights_net: Dict[str, Decimal],
        target_weights: Dict[str, float],
        total_value: Decimal
    ) -> List['Signal']:
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
        thresholds = self.thresholds_provider.get_raw()
        
        light_threshold = Decimal(str(thresholds.get(ThresholdKeys.rebalance_light_absolute, 0.05)))
        strong_threshold = Decimal(str(thresholds.get(ThresholdKeys.rebalance_strong_relative, 0.20)))
        
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
                if self.cooldown_policy.check(asset_class, SignalTypeConst.rebalance_strong):
                    continue
                
                # 计算需要调整的金额
                target_value = total_value * target_decimal
                current_value = total_value * actual
                adjust_amount = target_value - current_value
                
                action = ActionTypeConst.buy if adjust_amount > 0 else ActionTypeConst.sell
                
                signal = Signal(
                    signal_type=SignalTypeConst.rebalance_strong,
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
                if self.cooldown_policy.check(asset_class, SignalTypeConst.rebalance_light):
                    continue
                
                target_value = total_value * target_decimal
                current_value = total_value * actual
                adjust_amount = target_value - current_value
                
                action = ActionTypeConst.buy if adjust_amount > 0 else ActionTypeConst.sell
                
                signal = Signal(
                    signal_type=SignalTypeConst.rebalance_light,
                    asset_class=asset_class,
                    action=action,
                    amount=abs(adjust_amount),
                    reason=f"绝对偏离 {float(abs_deviation)*100:.2f}%（阈值 {float(light_threshold)*100:.0f}%），建议调整至目标",
                    urgency="medium"
                )
                signals.append(signal)
                
                logger.info(f"触发轻度再平衡信号: {signal}")
        
        return signals


class TacticalPolicy:
    """战术策略（生成加仓/减仓信号）
    
    职责：
    - 根据 90 日回撤/收益生成战术信号
    - 输入：资产类别、净值序列、权重、阈值、基金类型
    - 输出：可选信号
    """
    
    def __init__(
        self,
        thresholds_provider: ThresholdsProvider,
        cooldown_policy: CooldownPolicy,
        metrics
    ):
        self.thresholds_provider = thresholds_provider
        self.cooldown_policy = cooldown_policy
        self.metrics = metrics
    
    def generate(
        self,
        asset_class: str,
        nav_90d_series: List[Tuple[date, Decimal]],
        current_weight: Decimal,
        target_weight: Decimal,
        fund_type: str = "domestic"
    ) -> Optional['Signal']:
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
        thresholds = self.thresholds_provider.get_raw()
        
        dd_threshold = Decimal(str(thresholds.get(ThresholdKeys.tactical_drawdown, 0.10)))
        profit_threshold = Decimal(str(thresholds.get(ThresholdKeys.tactical_profit, 0.15)))
        
        # 计算90日回撤
        peak_90d, drawdown_90d = self.metrics.calculate_90d_drawdown(nav_90d_series)
        
        if peak_90d is None or drawdown_90d is None:
            logger.debug(f"{asset_class} 数据不足，跳过战术信号")
            return None
        
        # 加仓信号：回撤 >= 10% 且不超重
        if drawdown_90d <= -dd_threshold and current_weight <= target_weight:
            if self.cooldown_policy.check(asset_class, SignalTypeConst.tactical_add):
                return None
            
            # 建议加码金额（可配置）
            suggest_amount = Decimal("200")
            
            risk_note = ""
            if fund_type == FundType.qdii:
                risk_note = "QDII 隔夜风险：今晚若反向波动，成交价将偏离触发点"
            
            signal = Signal(
                signal_type=SignalTypeConst.tactical_add,
                asset_class=asset_class,
                action=ActionTypeConst.buy,
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
            if self.cooldown_policy.check(asset_class, SignalTypeConst.tactical_reduce):
                return None
            
            suggest_amount = Decimal("200")
            
            signal = Signal(
                signal_type=SignalTypeConst.tactical_reduce,
                asset_class=asset_class,
                action=ActionTypeConst.sell,
                amount=suggest_amount,
                reason=f"相对90日高点超额 {float(drawdown_90d)*100:.2f}%（阈值 {float(profit_threshold)*100:.0f}%），且权重超标，建议减码",
                urgency="low"
            )
            
            logger.info(f"触发战术减仓信号: {signal}")
            return signal
        
        return None


class PriorityPolicy:
    """优先级策略（信号排序与去冲突）
    
    职责：
    - 按优先级排序信号
    - 同资产保留高优先级信号
    
    TODO: 当前设计会丢弃低优先级信号，导致信息丢失。
    改进方向：
    1. 保留所有信号（sort_and_annotate），标记 is_primary/conflict_with
    2. 分离"信息展示"与"执行决策"（recommended vs conflicts）
    3. 用户应看到完整市场图景（例如"既要减仓又有抄底信号"说明拐点）
    参考讨论：2025-10-29 用户反馈
    """
    
    def sort_and_dedup(self, signals: List['Signal']) -> List['Signal']:
        """
        信号优先级排序与冲突处理
        
        优先级：
        1. rebalance_strong（高）
        2. rebalance_light（中）
        3. tactical_add/tactical_reduce（低）
        
        Args:
            signals: 信号列表
        
        Returns:
            排序后的信号列表（注意：当前会丢弃低优先级冲突信号）
        
        TODO: 改为 sort_and_annotate，保留所有信号并标注优先级
        """
        priority_map = {
            SignalTypeConst.rebalance_strong: 3,
            SignalTypeConst.rebalance_light: 2,
            SignalTypeConst.tactical_add: 1,
            SignalTypeConst.tactical_reduce: 1
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


# ==================
# Entities（领域实体）
# ==================
# 注意：Signal 类已移至 domain/models.py，此处直接导入使用


# ==================
# Engine（编排层）
# ==================

class SignalEngine:
    """信号引擎（编排层）
    
    职责：
    - 组装仓储/策略/服务依赖
    - 对外提供信号生成/优先级排序/记录等 API
    """
    
    def __init__(
        self,
        metrics,
        config: Optional[ConfigLoader] = None,
        state_file: Optional[str] = None
    ):
        self.config = config or ConfigLoader()
        
        if state_file is None:
            base_dir = Path(__file__).parent.parent
            state_file = base_dir / "data" / "state.json"
        
        # 组装仓储
        self.state_repo = SignalStateRepository(Path(state_file))
        self.state = self.state_repo.load()
        
        # 组装服务（依赖注入）
        self.thresholds_provider = ThresholdsProvider(self.config)
        self.metrics = metrics
        
        # 组装策略
        self.cooldown_policy = CooldownPolicy(self.state)
        self.rebalance_policy = RebalancePolicy(self.thresholds_provider, self.cooldown_policy)
        self.tactical_policy = TacticalPolicy(self.thresholds_provider, self.cooldown_policy, self.metrics)
        self.priority_policy = PriorityPolicy()
    
    def _save_state(self):
        """保存信号状态（委托仓储）"""
        self.state_repo.save(self.state)
    
    # ---- 对外 API ----
    
    def check_cooldown(self, asset_class: str, signal_type: str) -> bool:
        """检查是否在冷却期（委托 CooldownPolicy）"""
        return self.cooldown_policy.check(asset_class, signal_type)
    
    def set_cooldown(self, asset_class: str, signal_type: str, days: int):
        """设置冷却期（委托 CooldownPolicy）"""
        self.cooldown_policy.set(asset_class, signal_type, days)
    
    def generate_rebalance_signals(
        self,
        weights_net: Dict[str, Decimal],
        target_weights: Dict[str, float],
        total_value: Decimal
    ) -> List[Signal]:
        """生成再平衡信号（委托 RebalancePolicy）"""
        return self.rebalance_policy.generate(weights_net, target_weights, total_value)
    
    def generate_tactical_signals(
        self,
        asset_class: str,
        nav_90d_series: List[Tuple[date, Decimal]],
        current_weight: Decimal,
        target_weight: Decimal,
        fund_type: str = "domestic"
    ) -> Optional[Signal]:
        """生成战术信号（委托 TacticalPolicy）"""
        return self.tactical_policy.generate(
            asset_class, nav_90d_series, current_weight, target_weight, fund_type
        )
    
    def prioritize_signals(self, signals: List[Signal]) -> List[Signal]:
        """信号优先级排序与冲突处理（委托 PriorityPolicy）"""
        return self.priority_policy.sort_and_dedup(signals)
    
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
            cooldown_days_config = self.config.get_thresholds().get(ThresholdKeys.cooldown_days, {})
            
            if signal.signal_type == SignalTypeConst.rebalance_strong:
                days = cooldown_days_config.get(CooldownKeys.strong, 90)
            elif signal.signal_type == SignalTypeConst.rebalance_light:
                days = cooldown_days_config.get(CooldownKeys.light, 60)
            else:  # tactical
                days = cooldown_days_config.get(CooldownKeys.tactical, 30)
            
            self.set_cooldown(signal.asset_class, signal.signal_type, days)
        
        self._save_state()
        logger.info(f"记录信号: {signal}, 已执行={executed}")

