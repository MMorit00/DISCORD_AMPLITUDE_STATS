"""
报告生成器（文本直出）
支持：日报、周报、月报、半年报、年报
说明：直接返回渲染后的纯文本，移除 DTO 中间层。
"""
import logging
from datetime import datetime, date
from typing import List, Optional
from decimal import Decimal

from portfolio_report.config.loader import ConfigLoader
from portfolio_report.application.signals_engine import SignalEngine
from portfolio_report.domain.services.portfolio import Portfolio
from portfolio_report.domain.models import Signal
from portfolio_report.domain.constants import AssetClass


logger = logging.getLogger(__name__)


class ReportBuilder:
    """报告生成器"""
    
    def __init__(
        self,
        portfolio: Portfolio,
        signal_engine: Optional[SignalEngine] = None,
        config: Optional[ConfigLoader] = None
    ):
        self.portfolio = portfolio
        self.signal_engine = signal_engine or SignalEngine()
        self.config = config or ConfigLoader()
    
    def build_daily_report(self) -> str:
        """生成日报（文本直出）"""
        lines: List[str] = []
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("📊 投资组合日报")
        lines.append(f"  🗓️ {date.today().strftime('%Y年%m月%d日')}")
        lines.append("")

        # 总市值
        lines.append("💰 总市值")
        lines.append(f"  净值口径: ¥{self.portfolio.total_value_net:,.2f}")
        if self.portfolio.total_value_est > 0:
            lines.append(f"  估值口径: ¥{self.portfolio.total_value_est:,.2f}")
        lines.append("")

        # 权重分布
        target_weights = self.config.get_target_weights()
        lines.append("📈 权重分布（净值口径）")
        for asset_class in AssetClass.all():
            actual = self.portfolio.weights_net.get(asset_class, Decimal("0"))
            target = Decimal(str(target_weights.get(asset_class, 0)))
            deviation = actual - target
            deviation_pct = float(deviation) * 100
            emoji = "🔴" if abs(deviation) > Decimal("0.05") else "🟢"
            sign = "+" if deviation > 0 else ""
            lines.append(
                f"  {emoji} {asset_class}: {float(actual)*100:.2f}% (目标 {float(target)*100:.0f}%, {sign}{deviation_pct:.2f}%)"
            )

        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)
    
    # 已移除 _build_daily_dto（用文本直出替代）
    
    def build_weekly_report(self) -> str:
        """生成周报（文本直出）"""
        lines: List[str] = []
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("📊 投资组合周报")
        lines.append(f"  🗓️ {date.today().strftime('%Y年%m月%d日')}")
        lines.append("")
        lines.append("💰 组合市值")
        lines.append(f"  ¥{self.portfolio.total_value_net:,.2f}")
        lines.append("")
        lines.append("📊 权重偏离分析")
        deviations = self.portfolio.get_weight_deviation()
        thresholds = self.config.get_thresholds()
        abs_threshold = Decimal(str(thresholds.get("rebalance_light_absolute", 0.05)))
        rel_threshold = Decimal(str(thresholds.get("rebalance_strong_relative", 0.20)))
        for asset_class, (abs_dev, rel_dev) in deviations.items():
            status = "⚠️ 接近阈值" if abs_dev >= abs_threshold * Decimal("0.8") else "✅ 正常"
            lines.append(f"  {status} {asset_class}")
            lines.append(f"    绝对偏离: {float(abs_dev)*100:.2f}% (阈值 {float(abs_threshold)*100:.0f}%)")
            lines.append(f"    相对偏离: {float(rel_dev)*100:.2f}% (阈值 {float(rel_threshold)*100:.0f}%)")
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)
    
    # 已移除 _build_weekly_dto（用文本直出替代）
    
    def build_monthly_report(self, signals: Optional[List[Signal]] = None) -> str:
        """生成月报（文本直出）"""
        lines: List[str] = []
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("📊 投资组合月报")
        lines.append(f"  🗓️ {date.today().strftime('%Y年%m月')}")
        lines.append("")
        lines.append("💰 组合市值")
        lines.append(f"  ¥{self.portfolio.total_value_net:,.2f}")
        lines.append("")
        lines.append("📊 权重分布")
        target_weights = self.config.get_target_weights()
        for asset_class, actual in self.portfolio.weights_net.items():
            target = Decimal(str(target_weights.get(asset_class, 0)))
            lines.append(f"  • {asset_class}: {float(actual)*100:.2f}% (目标 {float(target)*100:.0f}%)")
        lines.append("")
        if signals and len(signals) > 0:
            lines.append(f"🔔 操作建议 ({len(signals)})")
            for signal in signals:
                urgency_emoji = "🔴" if signal.urgency == "high" else "🟡" if signal.urgency == "medium" else "🟢"
                action_text = "买入" if signal.action == "buy" else "卖出" if signal.action == "sell" else "调仓"
                lines.append(f"  {urgency_emoji} {signal.asset_class} - {action_text} ¥{signal.amount:.0f}")
                lines.append(f"    理由: {signal.reason}")
                if getattr(signal, "risk_note", None):
                    lines.append(f"    ⚠️ {signal.risk_note}")
        else:
            lines.append("✅ 权重在合理范围内")
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)
    
    
    def build_signal_alert(self, signals: List[Signal], alert_time: str = "14:40") -> str:
        """生成信号提醒（文本直出）"""
        if not signals:
            return ""
        lines: List[str] = []
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        if alert_time == "07:30":
            lines.append("🌅 QDII 昨夜信号推送")
        else:
            lines.append("⏰ 最终确认提醒")
        lines.append(f"  🕐 {alert_time} - ⏳ 15:00 前确认")
        lines.append("")
        for signal in signals:
            urgency_emoji = "🔴" if signal.urgency == "high" else "🟡"
            action_text = "买入" if signal.action == "buy" else "卖出"
            lines.append(f"  {urgency_emoji} {signal.asset_class} - {action_text} ¥{signal.amount:.0f}")
            lines.append(f"    {signal.reason}")
            if getattr(signal, "risk_note", None):
                lines.append(f"    ⚠️ {signal.risk_note}")
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)
    
    
    
    # 便捷函数
def create_daily_report(portfolio: Portfolio) -> str:
    """创建日报"""
    builder = ReportBuilder(portfolio)
    return builder.build_daily_report()


def create_weekly_report(portfolio: Portfolio) -> str:
    """创建周报"""
    builder = ReportBuilder(portfolio)
    return builder.build_weekly_report()


def create_monthly_report(portfolio: Portfolio, signals: List[Signal]) -> str:
    """创建月报"""
    builder = ReportBuilder(portfolio)
    return builder.build_monthly_report(signals)



