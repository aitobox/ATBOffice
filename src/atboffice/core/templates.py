"""Central document template registry and metadata models."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QCoreApplication

logger = logging.getLogger(__name__)


def safe_tr(text: str) -> str:
    """Translate UI text safely for template system."""
    return QCoreApplication.translate("TemplateRegistry", text)


@dataclass
class TemplateInfo:
    """Metadata describing a document template for Quire, Ledger, or Lectern."""

    id: str
    name: str
    app: str  # "quire", "ledger", or "lectern"
    category: str
    icon: str = "📄"
    builder: Callable[[Any], Any] | None = None
    description: str = ""
    sample_path: str | None = None


class TemplateRegistry:
    """Central singleton managing template definitions across all applications."""

    _instance: TemplateRegistry | None = None

    def __init__(self) -> None:
        """Initialize empty template registry and load built-in templates."""
        self._templates: dict[tuple[str, str], TemplateInfo] = {}
        self.register_builtin_templates()

    @classmethod
    def get_instance(cls) -> TemplateRegistry:
        """Return the global TemplateRegistry singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (useful for clean unit testing)."""
        cls._instance = None

    def clear(self) -> None:
        """Remove all registered templates."""
        self._templates.clear()

    def register(self, template: TemplateInfo) -> None:
        """Register a new template or overwrite an existing one with same (app, id)."""
        key = (template.app.lower(), template.id)
        self._templates[key] = template
        logger.debug("Registered template: %s for %s", template.id, template.app)

    def unregister(self, template_id: str, app: str | None = None) -> bool:
        """Unregister a template by id and optional app.

        Returns:
            True if one or more templates were removed, False otherwise.
        """
        removed = False
        if app is not None:
            key = (app.lower(), template_id)
            if key in self._templates:
                del self._templates[key]
                removed = True
        else:
            keys_to_remove = [k for k in self._templates if k[1] == template_id]
            for k in keys_to_remove:
                del self._templates[k]
                removed = True
        return removed

    def get(self, template_id: str, app: str | None = None) -> TemplateInfo | None:
        """Retrieve a template by id and optional app."""
        if app is not None:
            return self._templates.get((app.lower(), template_id))

        # If app is omitted, search across apps
        for (_, tid), tpl in self._templates.items():
            if tid == template_id:
                return tpl
        return None

    def list_templates(
        self, app: str | None = None, category: str | None = None
    ) -> list[TemplateInfo]:
        """List templates matching optional app and category filters."""
        result: list[TemplateInfo] = []
        for (a, _), tpl in self._templates.items():
            if app is not None and a != app.lower():
                continue
            if category is not None and tpl.category != category:
                continue
            result.append(tpl)
        return result

    def list_categories(self, app: str | None = None) -> list[str]:
        """Return distinct category names for the given app (or all apps)."""
        cats: set[str] = set()
        for (a, _), tpl in self._templates.items():
            if app is not None and a != app.lower():
                continue
            if tpl.category:
                cats.add(tpl.category)
        return sorted(cats)

    def register_builtin_templates(self) -> None:
        """Register the 22 canonical built-in templates from .vibeoffice."""
        # 1. Quire templates (10)
        quire_items = [
            (
                "letter",
                safe_tr("当代信函"),
                safe_tr("信函与传真"),
                "✉️",
                safe_tr("包含公司抬头与日期格式的正式商业信函"),
            ),
            (
                "memo",
                safe_tr("专业备忘录"),
                safe_tr("备忘录"),
                "📝",
                safe_tr("标准企业内部备忘录格式"),
            ),
            (
                "fax",
                safe_tr("优雅传真"),
                safe_tr("信函与传真"),
                "📠",
                safe_tr("经典传真封面与内容排版"),
            ),
            (
                "resume",
                safe_tr("个人简历"),
                safe_tr("其它文档"),
                "👤",
                safe_tr("清晰专业的求职履历布局"),
            ),
            (
                "report",
                safe_tr("专业业务报告"),
                safe_tr("报告"),
                "📊",
                safe_tr("带有标题、目录与段落样式的正式报告"),
            ),
            (
                "agenda",
                safe_tr("会议议程"),
                safe_tr("其它文档"),
                "📋",
                safe_tr("会议时间节点与议题安排表"),
            ),
            (
                "minutes",
                safe_tr("会议纪要"),
                safe_tr("其它文档"),
                "🗒️",
                safe_tr("参会人员、决议与待办事项追踪"),
            ),
            (
                "todo",
                safe_tr("待办清单"),
                safe_tr("其它文档"),
                "☑️",
                safe_tr("清单核对与跟进模板"),
            ),
            (
                "flyer",
                safe_tr("活动传单"),
                safe_tr("其它文档"),
                "📢",
                safe_tr("高视觉冲击力的活动宣传单页"),
            ),
            (
                "recipe",
                safe_tr("食谱卡片"),
                safe_tr("其它文档"),
                "🍳",
                safe_tr("配料表与制作步骤卡片"),
            ),
        ]
        for tid, name, cat, icon, desc in quire_items:
            self.register(
                TemplateInfo(
                    id=tid,
                    name=name,
                    app="quire",
                    category=cat,
                    icon=icon,
                    description=desc,
                )
            )

        # 2. Ledger templates (8)
        ledger_items = [
            (
                "loan",
                safe_tr("贷款分期偿还表"),
                safe_tr("电子表格"),
                "🏦",
                safe_tr("包含 PMT 计算与 60 期还款明细"),
            ),
            (
                "expense",
                safe_tr("差旅报销单"),
                safe_tr("电子表格"),
                "🧾",
                safe_tr("差旅支出明细与自动统计汇总"),
            ),
            (
                "invoice",
                safe_tr("销售发票"),
                safe_tr("电子表格"),
                "💰",
                safe_tr("含税率计算与客户账单凭证"),
            ),
            (
                "timecard",
                safe_tr("考勤工时卡"),
                safe_tr("电子表格"),
                "⏱️",
                safe_tr("员工上下班打卡与加班核算"),
            ),
            (
                "budget",
                safe_tr("个人月度预算"),
                safe_tr("电子表格"),
                "📊",
                safe_tr("月度收支预算与实际差异对比"),
            ),
            (
                "tasks",
                safe_tr("项目任务追踪表"),
                safe_tr("电子表格"),
                "📌",
                safe_tr("任务责任人、截止日与状态跟踪"),
            ),
            (
                "shopping",
                safe_tr("采购购物清单"),
                safe_tr("电子表格"),
                "🛒",
                safe_tr("品类预算与采购结算清单"),
            ),
            (
                "schedule",
                safe_tr("周程安排表"),
                safe_tr("电子表格"),
                "📅",
                safe_tr("每周时间日程安排与备忘"),
            ),
        ]
        for tid, name, cat, icon, desc in ledger_items:
            self.register(
                TemplateInfo(
                    id=tid,
                    name=name,
                    app="ledger",
                    category=cat,
                    icon=icon,
                    description=desc,
                )
            )

        # 3. Lectern templates (4)
        lectern_items = [
            (
                "status",
                safe_tr("项目状态汇报"),
                safe_tr("演示文稿"),
                "📈",
                safe_tr("蓝图设计风格的进度汇报幻灯片"),
            ),
            (
                "meeting",
                safe_tr("团队例会"),
                safe_tr("演示文稿"),
                "👥",
                safe_tr("草地设计风格的周会演示幻灯片"),
            ),
            (
                "lesson",
                safe_tr("课程教案"),
                safe_tr("演示文稿"),
                "🎓",
                safe_tr("羊皮纸风格的课程讲义"),
            ),
            (
                "event",
                safe_tr("活动通告"),
                safe_tr("演示文稿"),
                "🎉",
                safe_tr("暗夜风格的活动宣讲与通告"),
            ),
        ]
        for tid, name, cat, icon, desc in lectern_items:
            self.register(
                TemplateInfo(
                    id=tid,
                    name=name,
                    app="lectern",
                    category=cat,
                    icon=icon,
                    description=desc,
                )
            )
