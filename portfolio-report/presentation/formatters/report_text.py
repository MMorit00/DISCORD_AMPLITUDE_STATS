"""
报告文本渲染器
负责将 ReportDTO 渲染为文本格式（Discord、邮件、终端等）
从 builder._render_report 提取，实现表现层分离
"""
from typing import Optional
from domain.models import ReportDTO, ReportSection


class ReportTextRenderer:
    """报告文本渲染器（可扩展为多种渠道格式）"""
    
    def render(self, dto: ReportDTO) -> str:
        """
        渲染 ReportDTO 为纯文本格式
        
        Args:
            dto: 报告结构化数据
            
        Returns:
            格式化后的文本
        """
        lines = []
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        
        for section in dto.sections:
            # 标题行
            if section.title:
                if section.emoji:
                    lines.append(f"{section.emoji} {section.title}")
                else:
                    lines.append(f"**{section.title}**")
            
            # 内容
            if section.content:
                if section.title:  # 如果有标题，内容缩进
                    lines.append(f"  {section.content}")
                else:
                    lines.append(section.content)
            
            lines.append("")
        
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        
        return "\n".join(lines)


class MarkdownRenderer:
    """Markdown 渲染器（备选，支持更丰富的格式）"""
    
    def render(self, dto: ReportDTO) -> str:
        """渲染为 Markdown 格式"""
        lines = []
        lines.append("---")
        
        for section in dto.sections:
            if section.title:
                lines.append(f"## {section.emoji} {section.title}" if section.emoji else f"## {section.title}")
            
            if section.content:
                lines.append("")
                lines.append(section.content)
                lines.append("")
        
        lines.append("---")
        
        return "\n".join(lines)


# ==================== 默认渲染器 ====================

_default_renderer: Optional[ReportTextRenderer] = None


def get_renderer() -> ReportTextRenderer:
    """获取默认渲染器"""
    global _default_renderer
    if _default_renderer is None:
        _default_renderer = ReportTextRenderer()
    return _default_renderer


def render_report(dto: ReportDTO) -> str:
    """便捷函数：渲染报告为文本"""
    return get_renderer().render(dto)

