"""
报告生成器
支持：日报、周报、月报、半年报、年报
采用两阶段生成：先构建 ReportDTO（结构化），再渲染为文本
"""
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Literal
from decimal import Decimal

from portfolio_report.infrastructure.config.config_loader import ConfigLoader
from portfolio_report.domain.services.portfolio import Portfolio
from portfolio_report.domain.services.signals import SignalEngine
from portfolio_report.domain.models import Signal, ReportDTO, ReportSection
from portfolio_report.config.constants import AssetClass, ReportType

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
        """生成日报（两阶段：DTO -> 文本）"""
        dto = self._build_daily_dto()
        return self._render_report(dto)
    
    def _build_daily_dto(self) -> ReportDTO:
        """构建日报结构化数据"""
        sections = []
        
        # 标题
        sections.append(ReportSection(
            title="投资组合日报",
            content=f"🗓️ {date.today().strftime('%Y年%m月%d日')}",
            emoji="📊"
        ))
        
        # 总市值
        market_value_lines = [f"净值口径: ¥{self.portfolio.total_value_net:,.2f}"]
        if self.portfolio.total_value_est > 0:
            market_value_lines.append(f"估值口径: ¥{self.portfolio.total_value_est:,.2f}")
        
        sections.append(ReportSection(
            title="总市值",
            content="\n  ".join(market_value_lines),
            emoji="💰"
        ))
        
        # 权重分布
        target_weights = self.config.get_target_weights()
        weight_lines = []
        
        for asset_class in AssetClass.all():
            actual = self.portfolio.weights_net.get(asset_class, Decimal("0"))
            target = Decimal(str(target_weights.get(asset_class, 0)))
            deviation = actual - target
            deviation_pct = float(deviation) * 100
            
            emoji = "🔴" if abs(deviation) > Decimal("0.05") else "🟢"
            sign = "+" if deviation > 0 else ""
            
            weight_lines.append(
                f"{emoji} {asset_class}: {float(actual)*100:.2f}% "
                f"(目标 {float(target)*100:.0f}%, {sign}{deviation_pct:.2f}%)"
            )
        
        sections.append(ReportSection(
            title="权重分布（净值口径）",
            content="\n  ".join(weight_lines),
            emoji="📈"
        ))
        
        return ReportDTO(
            report_type=ReportType.daily,
            generated_at=datetime.now(),
            sections=sections,
            metadata={
                "total_value_net": float(self.portfolio.total_value_net),
                "total_value_est": float(self.portfolio.total_value_est),
            }
        )
    
    def build_weekly_report(self) -> str:
        """生成周报（两阶段：DTO -> 文本）"""
        dto = self._build_weekly_dto()
        return self._render_report(dto)
    
    def _build_weekly_dto(self) -> ReportDTO:
        """构建周报结构化数据"""
        sections = []
        
        # 标题
        sections.append(ReportSection(
            title="投资组合周报",
            content=f"🗓️ {date.today().strftime('%Y年%m月%d日')} 周报",
            emoji="📊"
        ))
        
        # 总市值
        sections.append(ReportSection(
            title="组合市值",
            content=f"¥{self.portfolio.total_value_net:,.2f}",
            emoji="💰"
        ))
        
        # 权重偏离分析
        deviations = self.portfolio.get_weight_deviation()
        thresholds = self.config.get_thresholds()
        deviation_lines = []
        
        for asset_class, (abs_dev, rel_dev) in deviations.items():
            abs_threshold = Decimal(str(thresholds.get("rebalance_light_absolute", 0.05)))
            rel_threshold = Decimal(str(thresholds.get("rebalance_strong_relative", 0.20)))
            status = "⚠️ 接近阈值" if abs_dev >= abs_threshold * Decimal("0.8") else "✅ 正常"
            
            deviation_lines.append(f"{status} {asset_class}")
            deviation_lines.append(f"  绝对偏离: {float(abs_dev)*100:.2f}% (阈值 {float(abs_threshold)*100:.0f}%)")
            deviation_lines.append(f"  相对偏离: {float(rel_dev)*100:.2f}% (阈值 {float(rel_threshold)*100:.0f}%)")
        
        sections.append(ReportSection(
            title="权重偏离分析",
            content="\n  ".join(deviation_lines),
            emoji="📊"
        ))
        
        return ReportDTO(
            report_type=ReportType.weekly,
            generated_at=datetime.now(),
            sections=sections
        )
    
    def build_monthly_report(self, signals: Optional[List[Signal]] = None) -> str:
        """生成月报（两阶段：DTO -> 文本）"""
        dto = self._build_monthly_dto(signals)
        return self._render_report(dto)
    
    def _build_monthly_dto(self, signals: Optional[List[Signal]] = None) -> ReportDTO:
        """构建月报结构化数据"""
        sections = []
        
        # 标题
        sections.append(ReportSection(
            title="投资组合月报",
            content=f"🗓️ {date.today().strftime('%Y年%m月')}",
            emoji="📊"
        ))
        
        # 总市值
        sections.append(ReportSection(
            title="组合市值",
            content=f"¥{self.portfolio.total_value_net:,.2f}",
            emoji="💰"
        ))
        
        # 权重分布
        target_weights = self.config.get_target_weights()
        weight_lines = []
        
        for asset_class, actual in self.portfolio.weights_net.items():
            target = Decimal(str(target_weights.get(asset_class, 0)))
            weight_lines.append(
                f"• {asset_class}: {float(actual)*100:.2f}% "
                f"(目标 {float(target)*100:.0f}%)"
            )
        
        sections.append(ReportSection(
            title="权重分布",
            content="\n  ".join(weight_lines),
            emoji="📊"
        ))
        
        # 信号提示
        if signals and len(signals) > 0:
            signal_lines = []
            for signal in signals:
                urgency_emoji = "🔴" if signal.urgency == "high" else "🟡" if signal.urgency == "medium" else "🟢"
                action_text = "买入" if signal.action == "buy" else "卖出" if signal.action == "sell" else "调仓"
                
                signal_lines.append(f"{urgency_emoji} **{signal.asset_class}** - {action_text} ¥{signal.amount:.0f}")
                signal_lines.append(f"  理由: {signal.reason}")
                
                if signal.risk_note:
                    signal_lines.append(f"  ⚠️ {signal.risk_note}")
                signal_lines.append("")
            
            sections.append(ReportSection(
                title=f"操作建议 ({len(signals)})",
                content="\n".join(signal_lines),
                emoji="🔔"
            ))
        else:
            sections.append(ReportSection(
                title="无操作建议",
                content="权重在合理范围内",
                emoji="✅"
            ))
        
        return ReportDTO(
            report_type=ReportType.monthly,
            generated_at=datetime.now(),
            sections=sections,
            metadata={"signal_count": len(signals) if signals else 0}
        )
    
    def build_signal_alert(self, signals: List[Signal], alert_time: str = "14:40") -> str:
        """生成信号提醒（两阶段：DTO -> 文本）"""
        if not signals:
            return ""
        dto = self._build_signal_alert_dto(signals, alert_time)
        return self._render_report(dto)
    
    def _build_signal_alert_dto(self, signals: List[Signal], alert_time: str = "14:40") -> ReportDTO:
        """构建信号提醒结构化数据"""
        sections = []
        
        # 标题
        if alert_time == "07:30":
            title_text = "QDII 昨夜信号推送"
            emoji = "🌅"
        else:
            title_text = "最终确认提醒"
            emoji = "⏰"
        
        sections.append(ReportSection(
            title=title_text,
            content=f"🕐 {alert_time} - ⏳ 15:00 前确认",
            emoji=emoji
        ))
        
        # 信号详情
        signal_lines = []
        for signal in signals:
            urgency_emoji = "🔴" if signal.urgency == "high" else "🟡"
            action_text = "买入" if signal.action == "buy" else "卖出"
            
            signal_lines.append(f"{urgency_emoji} **{signal.asset_class}** - {action_text} ¥{signal.amount:.0f}")
            signal_lines.append(f"  {signal.reason}")
            
            if signal.risk_note:
                signal_lines.append(f"  ⚠️ {signal.risk_note}")
            signal_lines.append("")
        
        sections.append(ReportSection(
            title="",
            content="\n".join(signal_lines),
            emoji=""
        ))
        
        return ReportDTO(
            report_type=ReportType.signal_alert,
            generated_at=datetime.now(),
            sections=sections,
            metadata={"alert_time": alert_time, "signal_count": len(signals)}
        )
    
    def _render_report(self, dto: ReportDTO) -> str:
        """渲染 ReportDTO 为文本（委托给渲染器）"""
        from portfolio_report.presentation.formatters.report_text import render_report
        return render_report(dto)


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

