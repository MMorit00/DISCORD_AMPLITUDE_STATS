"""
SignalEngine（Application 层）：组装 Domain 策略与 Infrastructure 状态仓储
"""
import logging
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

from portfolio_report.config.loader import ConfigLoader
from portfolio_report.shared.constants import ThresholdKeys, CooldownKeys
from portfolio_report.domain.models import Signal
from portfolio_report.domain.services.signals import (
    CooldownPolicy,
    RebalancePolicy,
    TacticalPolicy,
    PriorityPolicy,
)
from portfolio_report.infrastructure.state.signal_state import SignalStateRepository


logger = logging.getLogger(__name__)


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
        state_file: Optional[str] = None,
    ):
        self.config = config or ConfigLoader()

        if state_file is None:
            # 默认使用包根目录下 data/state.json
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
        total_value: Decimal,
    ) -> List[Signal]:
        """生成再平衡信号（委托 RebalancePolicy）"""
        return self.rebalance_policy.generate(weights_net, target_weights, total_value)

    def generate_tactical_signals(
        self,
        asset_class: str,
        nav_90d_series: List[Tuple[date, Decimal]],
        current_weight: Decimal,
        target_weight: Decimal,
        fund_type: str = "domestic",
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

            # 根据信号类型选择冷却天数
            if signal.signal_type == "rebalance_strong":
                days = cooldown_days_config.get(CooldownKeys.strong, 90)
            elif signal.signal_type == "rebalance_light":
                days = cooldown_days_config.get(CooldownKeys.light, 60)
            else:  # tactical
                days = cooldown_days_config.get(CooldownKeys.tactical, 30)

            self.set_cooldown(signal.asset_class, signal.signal_type, days)

        self._save_state()
        logger.info(f"记录信号: {signal}, 已执行={executed}")


class ThresholdsProvider:
    """阈值提供服务（集中从配置读取阈值）"""
    def __init__(self, config: ConfigLoader):
        self.config = config
    def get_raw(self):
        return self.config.get_thresholds()


