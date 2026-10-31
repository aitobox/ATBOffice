"""Clipart gallery dialog and built-in vector drawings (64x64) for Quire, Lectern, and Ledger."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    """Translate UI text with fallback to original string."""
    app = QApplication.instance()
    if app:
        translated = app.translate("Clipart", text)
        if translated and translated != text:
            return translated
    return text


class ClipartCategory(StrEnum):
    """Clipart classification categories."""

    BUSINESS = "business"
    TECHNOLOGY = "technology"
    NATURE = "nature"
    SYMBOLS = "symbols"


@dataclass
class ClipartItem:
    """Built-in vector clipart model."""

    id: str
    name_en: str
    name_zh: str
    category: ClipartCategory
    keywords: str
    svg_body: str

    def to_svg_xml(self) -> str:
        """Wrap inner SVG primitives into valid XML document."""
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" '
            f'viewBox="0 0 64 64">{self.svg_body}</svg>'
        )

    @property
    def display_name(self) -> str:
        """Localized display name."""
        return safe_tr(self.name_zh)


_O = 'stroke="#222" stroke-width="2" stroke-linejoin="round"'

CLIPART_DATABASE: list[ClipartItem] = [
    ClipartItem(
        id="clip0",
        name_en="Light bulb",
        name_zh="灯泡",
        category=ClipartCategory.TECHNOLOGY,
        keywords="idea light bulb think innovation creative 思考 创意 灵感 发明",
        svg_body=(
            f'<path d="M32 6c-11 0-19 8-19 18 0 7 4 11 7 15 2 3 3 5 3 8h18c0-3 1-5'
            f' 3-8 3-4 7-8 7-15 0-10-8-18-19-18z" fill="#ffe259" {_O}/>'
            '<path d="M24 22a9 9 0 0 1 8-8" fill="none" stroke="#fff"'
            ' stroke-width="3" stroke-linecap="round"/>'
            f'<rect x="23" y="47" width="18" height="5" fill="#b9c2cc" {_O}/>'
            f'<rect x="24" y="52" width="16" height="4" fill="#9aa3ad" {_O}/>'
            f'<path d="M28 56h8l-2 4h-4z" fill="#555" {_O}/>'
        ),
    ),
    ClipartItem(
        id="clip1",
        name_en="Globe",
        name_zh="地球仪",
        category=ClipartCategory.NATURE,
        keywords="globe world international earth global 全球 世界 国际 地球",
        svg_body=(
            f'<circle cx="32" cy="32" r="25" fill="#5aa9e6" {_O}/>'
            f'<path d="M18 18c6 2 6 8 12 8s4 8 10 6 6 6 4 10-8 2-10 8-8 4-10-2'
            f' 2-8-4-10-8-2-6-8 0-10 4-12z" fill="#6cc04a" {_O}/>'
            '<path d="M7 32h50M32 7c-9 8-9 42 0 50M32 7c9 8 9 42 0 50" fill="none"'
            ' stroke="#1e4f80" stroke-width="1.3" opacity=".6"/>'
        ),
    ),
    ClipartItem(
        id="clip2",
        name_en="Rocket",
        name_zh="火箭",
        category=ClipartCategory.TECHNOLOGY,
        keywords="rocket launch start growth space 启动 发射 飞船 太空 腾飞",
        svg_body=(
            f'<path d="M32 4c9 7 13 18 12 32l-6 8H26l-6-8C19 22 23 11 32 4z" fill="#eef2f7" {_O}/>'
            f'<circle cx="32" cy="24" r="6" fill="#4aa3df" {_O}/>'
            f'<path d="M20 36l-8 12 10-3zM44 36l8 12-10-3z" fill="#e74c3c" {_O}/>'
            f'<path d="M26 44h12l-2 6h-8z" fill="#888" {_O}/>'
            f'<path d="M28 50c0 6 4 10 4 10s4-4 4-10z" fill="#ff9f1a" {_O}/>'
        ),
    ),
    ClipartItem(
        id="clip3",
        name_en="Trophy",
        name_zh="奖杯",
        category=ClipartCategory.BUSINESS,
        keywords="trophy award win success prize achievement 优胜 荣誉 胜利 竞赛",
        svg_body=(
            f'<path d="M18 8h28v10c0 10-6 17-14 17S18 28 18 18z" fill="#f5c542" {_O}/>'
            f'<path d="M18 12H9c0 9 5 14 11 14M46 12h9c0 9-5 14-11 14" fill="none" {_O}/>'
            f'<rect x="28" y="35" width="8" height="10" fill="#d4a017" {_O}/>'
            f'<path d="M20 45h24v6H20z" fill="#8b5a2b" {_O}/>'
            f'<path d="M16 51h32v7H16z" fill="#6d4421" {_O}/>'
            '<path d="M25 13v10" stroke="#fff" stroke-width="3" stroke-linecap="round"/>'
        ),
    ),
    ClipartItem(
        id="clip4",
        name_en="Gears",
        name_zh="齿轮",
        category=ClipartCategory.TECHNOLOGY,
        keywords="gears process settings engineering machine work 配置 机制 运转 工程",
        svg_body=(
            f'<g {_O} fill="#9aa7b8"><path d="M26 10l4 0 1 5 4 2 4-3 3 3-3 4 2 4 5'
            f' 1v4l-5 1-2 4 3 4-3 3-4-3-4 2-1 5h-4l-1-5-4-2-4 3-3-3'
            f' 3-4-2-4-5-1v-4l5-1 2-4-3-4 3-3 4 3 4-2z"/></g>'
            f'<circle cx="28" cy="27" r="6" fill="#fff" {_O}/>'
            f'<g {_O} fill="#e8a33d"><path d="M46 36h3l1 3 3 1 2-2 2 2-2 2 1 3 3'
            f' 1v3l-3 1-1 3 2 2-2 2-2-2-3 1-1 3h-3l-1-3-3-1-2 2-2-2'
            f' 2-2-1-3-3-1v-3l3-1 1-3-2-2 2-2 2 2 3-1z"/></g>'
            f'<circle cx="47.5" cy="47.5" r="3.5" fill="#fff" {_O}/>'
        ),
    ),
    ClipartItem(
        id="clip5",
        name_en="Growth chart",
        name_zh="增长图表",
        category=ClipartCategory.BUSINESS,
        keywords="chart graph growth results increase sales profit 业绩 趋势 柱状图 上涨",
        svg_body=(
            f'<rect x="6" y="8" width="52" height="48" fill="#fff" {_O}/>'
            f'<rect x="12" y="38" width="8" height="14" fill="#5b9bd5" {_O}/>'
            f'<rect x="24" y="30" width="8" height="22" fill="#5b9bd5" {_O}/>'
            f'<rect x="36" y="22" width="8" height="30" fill="#5b9bd5" {_O}/>'
            f'<rect x="48" y="14" width="6" height="38" fill="#5b9bd5" {_O}/>'
            '<path d="M10 34l12-8 10 2 18-16" fill="none" stroke="#e74c3c"'
            ' stroke-width="3" stroke-linecap="round"/>'
            '<path d="M45 10l7 1-1 7" fill="none" stroke="#e74c3c"'
            ' stroke-width="3" stroke-linecap="round"/>'
        ),
    ),
    ClipartItem(
        id="clip6",
        name_en="Calendar",
        name_zh="日历",
        category=ClipartCategory.BUSINESS,
        keywords="calendar schedule date plan time deadline 日期 计划 日程 时间表",
        svg_body=(
            f'<rect x="8" y="12" width="48" height="44" rx="3" fill="#fff" {_O}/>'
            f'<path d="M8 15a3 3 0 0 1 3-3h42a3 3 0 0 1 3 3v9H8z" fill="#d64541" {_O}/>'
            '<path d="M20 6v10M44 6v10" stroke="#222" stroke-width="3" stroke-linecap="round"/>'
            '<g fill="#9aa7b8"><rect x="14" y="30" width="7" height="6"/><rect'
            ' x="25" y="30" width="7" height="6"/><rect x="36" y="30" width="7"'
            ' height="6"/><rect x="14" y="41" width="7" height="6"/><rect x="25"'
            ' y="41" width="7" height="6"/></g>'
            '<rect x="36" y="41" width="7" height="6" fill="#d64541"/>'
        ),
    ),
    ClipartItem(
        id="clip7",
        name_en="Magnifier",
        name_zh="放大镜",
        category=ClipartCategory.SYMBOLS,
        keywords="search magnifier research find investigate 查找 探索 搜索 观察",
        svg_body=(
            f'<circle cx="26" cy="26" r="17" fill="#cfe9ff" {_O}/>'
            '<path d="M18 20a10 10 0 0 1 8-6" fill="none" stroke="#fff"'
            ' stroke-width="3" stroke-linecap="round"/>'
            '<path d="M38 38l16 16" stroke="#6d4421" stroke-width="8" stroke-linecap="round"/>'
            '<path d="M38 38l16 16" stroke="#222" stroke-width="10"'
            ' stroke-linecap="round" opacity=".15"/>'
        ),
    ),
    ClipartItem(
        id="clip8",
        name_en="Team",
        name_zh="团队",
        category=ClipartCategory.BUSINESS,
        keywords="people team group staff meeting users 人员 用户 会议 协作 组织",
        svg_body=(
            f'<circle cx="20" cy="20" r="8" fill="#f2c39b" {_O}/>'
            f'<path d="M6 50c0-12 6-18 14-18s14 6 14 18z" fill="#4a7bc8" {_O}/>'
            f'<circle cx="44" cy="20" r="8" fill="#e0a87c" {_O}/>'
            f'<path d="M30 50c0-12 6-18 14-18s14 6 14 18z" fill="#6cb04a" {_O}/>'
            f'<circle cx="32" cy="28" r="9" fill="#f2c39b" {_O}/>'
            f'<path d="M16 60c0-14 7-21 16-21s16 7 16 21z" fill="#e8641c" {_O}/>'
        ),
    ),
    ClipartItem(
        id="clip9",
        name_en="House",
        name_zh="房屋",
        category=ClipartCategory.NATURE,
        keywords="house home real estate property building 住宅 建筑 房产 家园",
        svg_body=(
            '<path d="M8 30L32 8l24 22" fill="none" stroke="#222" stroke-width="3"'
            ' stroke-linejoin="round"/>'
            f'<path d="M14 26v30h36V26L32 10z" fill="#f4e3c1" {_O}/>'
            f'<path d="M6 31L32 7l26 24-4 3L32 14 10 34z" fill="#c0392b" {_O}/>'
            f'<rect x="27" y="38" width="10" height="18" fill="#8b5a2b" {_O}/>'
            f'<rect x="17" y="32" width="8" height="8" fill="#9fd3ff" {_O}/>'
            f'<rect x="40" y="32" width="8" height="8" fill="#9fd3ff" {_O}/>'
        ),
    ),
    ClipartItem(
        id="clip10",
        name_en="Computer",
        name_zh="计算机",
        category=ClipartCategory.TECHNOLOGY,
        keywords="computer monitor technology pc screen it 显示器 电脑 设备 硬件",
        svg_body=(
            f'<rect x="6" y="8" width="52" height="36" rx="2" fill="#d5dbe3" {_O}/>'
            f'<rect x="10" y="12" width="44" height="28" fill="#2f6fd0" {_O}/>'
            '<path d="M14 16h20M14 21h14" stroke="#cfe3ff" stroke-width="2"/>'
            f'<path d="M26 44h12l2 8H24z" fill="#b6bec9" {_O}/>'
            f'<rect x="16" y="52" width="32" height="5" rx="1" fill="#9aa3ad" {_O}/>'
        ),
    ),
    ClipartItem(
        id="clip11",
        name_en="Telephone",
        name_zh="电话",
        category=ClipartCategory.TECHNOLOGY,
        keywords="telephone phone call contact support 客服 热线 呼叫 通讯",
        svg_body=(
            f'<path d="M14 8c-4 2-7 6-6 11 3 15 17 31 33 35 5 1 9-2 11-6l-9-8-6'
            f' 4c-7-3-12-9-15-15l4-6z" fill="#e74c3c" {_O}/>'
            '<path d="M15 12c-2 1-3 3-3 5" fill="none" stroke="#fff"'
            ' stroke-width="2" stroke-linecap="round"/>'
        ),
    ),
    ClipartItem(
        id="clip12",
        name_en="Envelope",
        name_zh="信封",
        category=ClipartCategory.SYMBOLS,
        keywords="envelope mail email message letter 邮件 电子邮件 消息 沟通",
        svg_body=(
            f'<rect x="6" y="14" width="52" height="36" rx="2" fill="#fff8e1" {_O}/>'
            f'<path d="M6 16l26 20 26-20" fill="none" {_O}/>'
            '<path d="M6 50l20-17M58 50L38 33" fill="none" stroke="#222" stroke-width="1.5"/>'
        ),
    ),
    ClipartItem(
        id="clip13",
        name_en="Star",
        name_zh="五角星",
        category=ClipartCategory.SYMBOLS,
        keywords="star rating favorite quality excellent 收藏 评分 重点 优质",
        svg_body=(
            f'<path d="M32 5l8 17 18 2-13 13 4 19-17-9-17 9 4-19L6 24l18-2z" fill="#ffd34e" {_O}/>'
            '<path d="M32 13l4 10" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/>'
        ),
    ),
    ClipartItem(
        id="clip14",
        name_en="Check mark",
        name_zh="勾选标记",
        category=ClipartCategory.SYMBOLS,
        keywords="check done complete approved yes ok 确认 成功 完成 通过",
        svg_body=(
            f'<circle cx="32" cy="32" r="26" fill="#3fae49" {_O}/>'
            '<path d="M19 33l9 9 18-20" fill="none" stroke="#fff" stroke-width="7"'
            ' stroke-linecap="round" stroke-linejoin="round"/>'
        ),
    ),
    ClipartItem(
        id="clip15",
        name_en="Clock",
        name_zh="时钟",
        category=ClipartCategory.SYMBOLS,
        keywords="clock time hour deadline schedule 时间 钟表 刻度 准时",
        svg_body=(
            f'<circle cx="32" cy="32" r="26" fill="#fff" {_O}/>'
            '<circle cx="32" cy="32" r="22" fill="none" stroke="#4a7bc8" stroke-width="3"/>'
            '<path d="M32 16v16l10 7" fill="none" stroke="#222" stroke-width="3"'
            ' stroke-linecap="round"/>'
            '<g fill="#222"><circle cx="32" cy="12" r="1.5"/><circle cx="52"'
            ' cy="32" r="1.5"/><circle cx="32" cy="52" r="1.5"/><circle cx="12"'
            ' cy="32" r="1.5"/></g>'
        ),
    ),
    ClipartItem(
        id="clip16",
        name_en="Puzzle",
        name_zh="拼图",
        category=ClipartCategory.SYMBOLS,
        keywords="puzzle solution fit strategy problem piece 解决 契合 模块 策略 方案",
        svg_body=(
            f'<path d="M10 18h12c-2-8 12-8 10 0h12v12c8-2 8 12 0 10v12H32c2 8-12'
            f' 8-10 0H10V40c-8 2-8-12 0-10z" fill="#9b59b6" {_O}/>'
            '<path d="M14 22h6" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/>'
        ),
    ),
    ClipartItem(
        id="clip17",
        name_en="Target",
        name_zh="目标靶心",
        category=ClipartCategory.BUSINESS,
        keywords="target goal objective aim focus 聚焦 准星 射击 目标",
        svg_body=(
            f'<circle cx="30" cy="34" r="24" fill="#fff" {_O}/>'
            f'<circle cx="30" cy="34" r="17" fill="#e74c3c" {_O}/>'
            f'<circle cx="30" cy="34" r="10" fill="#fff" {_O}/>'
            f'<circle cx="30" cy="34" r="4" fill="#e74c3c" {_O}/>'
            '<path d="M30 34L56 8" stroke="#6d4421" stroke-width="3"/>'
            f'<path d="M50 6l8-2-2 8-5 1z" fill="#3fae49" {_O}/>'
        ),
    ),
    ClipartItem(
        id="clip18",
        name_en="Money",
        name_zh="金钱",
        category=ClipartCategory.BUSINESS,
        keywords="money finance budget dollar coins cost revenue 资产 资金 收益 成本 美元",
        svg_body=(
            f'<path d="M20 22c-6 8-10 16-10 22 0 10 10 14 22 14s22-4'
            f' 22-14c0-6-4-14-10-22z" fill="#6cb04a" {_O}/>'
            f'<path d="M22 14h20l-4 8H26z" fill="#5a9a3d" {_O}/>'
            f'<path d="M24 14c-2-6 4-8 8-4 4-4 10-2 8 4" fill="none" {_O}/>'
            '<text x="32" y="48" text-anchor="middle" font-family="Arial"'
            ' font-weight="bold" font-size="18" fill="#fff">$</text>'
        ),
    ),
    ClipartItem(
        id="clip19",
        name_en="Flag",
        name_zh="旗帜",
        category=ClipartCategory.SYMBOLS,
        keywords="flag milestone goal finish achievement 里程碑 标杆 目标 胜出",
        svg_body=(
            '<path d="M14 6v54" stroke="#6d4421" stroke-width="4" stroke-linecap="round"/>'
            f'<path d="M16 8c10-4 18 4 28 0s12 0 12 0v24s-4-4-12 0-18-4-28 0z"'
            f' fill="#2e86c1" {_O}/>'
            '<path d="M16 8h10v6H16zM36 14h10v6H36zM26 20h10v6H26z" fill="#fff" opacity=".85"/>'
        ),
    ),
    ClipartItem(
        id="clip20",
        name_en="Book",
        name_zh="书籍",
        category=ClipartCategory.BUSINESS,
        keywords="book education learning training study read 知识 学习 资料 培训 文档",
        svg_body=(
            f'<path d="M8 12c8-2 16-2 24 4v40c-8-6-16-6-24-4z" fill="#fff" {_O}/>'
            f'<path d="M56 12c-8-2-16-2-24 4v40c8-6 16-6 24-4z" fill="#fff" {_O}/>'
            '<path d="M12 22c5-1 10 0 15 2M12 29c5-1 10 0 15 2M37 24c5-2 10-3'
            ' 15-2M37 31c5-2 10-3 15-2" stroke="#9aa7b8" stroke-width="1.6"'
            ' fill="none"/>'
            '<path d="M6 14v42c9-2 18-2 26 3 8-5 17-5 26-3V14" fill="none"'
            ' stroke="#c0392b" stroke-width="3"/>'
        ),
    ),
    ClipartItem(
        id="clip21",
        name_en="Leaf",
        name_zh="树叶",
        category=ClipartCategory.NATURE,
        keywords="leaf environment green nature sustainability eco 环保 绿色 生态 植物 自然",
        svg_body=(
            f'<path d="M10 54C8 30 22 10 54 8c2 28-12 46-40 46z" fill="#6cc04a" {_O}/>'
            '<path d="M12 52C24 40 34 30 46 18" fill="none" stroke="#2f7a1f"'
            ' stroke-width="2.5" stroke-linecap="round"/>'
            '<path d="M24 40l-2-10M32 32l-1-9M38 26l6 1M30 36l8 2"'
            ' stroke="#2f7a1f" stroke-width="1.6"/>'
        ),
    ),
    ClipartItem(
        id="clip22",
        name_en="Cloud",
        name_zh="云朵",
        category=ClipartCategory.TECHNOLOGY,
        keywords="cloud weather computing storage online 云计算 存储 网络 服务",
        svg_body=(
            f'<path d="M18 48c-8 0-12-5-12-11s5-11 11-11c2-9 9-14 17-14 9 0 16 7 16'
            f' 15 6 0 10 5 10 10 0 7-5 11-11 11z" fill="#eaf4ff" {_O}/>'
            '<path d="M16 32c1-3 3-4 6-5" fill="none" stroke="#fff"'
            ' stroke-width="2.5" stroke-linecap="round"/>'
        ),
    ),
    ClipartItem(
        id="clip23",
        name_en="Warning",
        name_zh="警告",
        category=ClipartCategory.SYMBOLS,
        keywords="warning caution risk alert attention danger 警示 注意 风险 提示",
        svg_body=(
            f'<path d="M32 6l28 50H4z" fill="#ffd400" {_O}/>'
            '<path d="M32 22v18" stroke="#222" stroke-width="6" stroke-linecap="round"/>'
            '<circle cx="32" cy="48" r="3.5" fill="#222"/>'
        ),
    ),
]


def get_clipart_by_id(clip_id: str) -> ClipartItem | None:
    """Retrieve clipart item by its unique ID."""
    for item in CLIPART_DATABASE:
        if item.id == clip_id:
            return item
    return None


def search_clipart(
    query: str,
    category: ClipartCategory | None = None,
) -> list[ClipartItem]:
    """Search clipart by query text and optional category filter."""
    tokens = [t.lower().strip() for t in query.split() if t.strip()]

    results: list[ClipartItem] = []
    for item in CLIPART_DATABASE:
        if category is not None and item.category != category:
            continue

        if not tokens:
            results.append(item)
            continue

        haystack = f"{item.name_en} {item.name_zh} {item.keywords}".lower()
        if all(token in haystack for token in tokens):
            results.append(item)

    return results


def render_clipart_pixmap(item: ClipartItem, size: int = 128) -> QPixmap:
    """Render vector clipart to a crisp rasterized QPixmap with transparent background."""
    xml_data = item.to_svg_xml().encode("utf-8")
    renderer = QSvgRenderer(QByteArray(xml_data))

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return pixmap


class ClipartDialog(QDialog):
    """Clipart gallery dialog offering category filtering and search."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("剪贴画选择库 — ATBOffice"))
        self.resize(620, 480)
        self.setMinimumSize(480, 360)

        self._pixmap_cache: dict[str, QPixmap] = {}
        self._init_ui()
        self._populate_categories()
        self._refresh_list()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Filter bar: Category combo + Search input
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)

        lbl_cat = QLabel(safe_tr("分类(&C):"), self)
        filter_layout.addWidget(lbl_cat)

        self.combo_category = QComboBox(self)
        self.combo_category.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.combo_category)

        lbl_search = QLabel(safe_tr("搜索(&S):"), self)
        filter_layout.addWidget(lbl_search)

        self.edit_search = QLineEdit(self)
        self.edit_search.setPlaceholderText(safe_tr("输入关键词检索 (如 火箭、奖杯、图表)..."))
        self.edit_search.setClearButtonEnabled(True)
        self.edit_search.textChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.edit_search, stretch=1)

        layout.addLayout(filter_layout)

        # Clipart list grid
        self.list_widget = QListWidget(self)
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(64, 64))
        self.list_widget.setGridSize(QSize(96, 96))
        self.list_widget.setSpacing(8)
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setMovement(QListWidget.Movement.Static)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.list_widget, stretch=1)

        # Status & Action Buttons
        btn_layout = QHBoxLayout()
        self.label_status = QLabel(self)
        self.label_status.setStyleSheet("color: #666;")
        btn_layout.addWidget(self.label_status)

        btn_layout.addStretch()

        self.btn_insert = QPushButton(safe_tr("插入(&I)"), self)
        self.btn_insert.setDefault(True)
        self.btn_insert.setStyleSheet(
            "background-color: #2e6bc6; color: white; font-weight: bold; padding: 6px 16px;"
        )
        self.btn_insert.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_insert)

        self.btn_cancel = QPushButton(safe_tr("取消(&C)"), self)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

    def _populate_categories(self) -> None:
        self.combo_category.clear()
        self.combo_category.addItem(safe_tr("全部分类 (All)"), None)
        self.combo_category.addItem(safe_tr("商务与财务 (Business)"), ClipartCategory.BUSINESS)
        self.combo_category.addItem(safe_tr("科学与科技 (Technology)"), ClipartCategory.TECHNOLOGY)
        self.combo_category.addItem(safe_tr("自然与地理 (Nature)"), ClipartCategory.NATURE)
        self.combo_category.addItem(safe_tr("符号与标志 (Symbols)"), ClipartCategory.SYMBOLS)

    def _on_filter_changed(self) -> None:
        self._refresh_list()

    def _refresh_list(self) -> None:
        query = self.edit_search.text()
        cat_data = self.combo_category.currentData()
        items = search_clipart(query=query, category=cat_data)

        self.list_widget.clear()
        for it in items:
            if it.id not in self._pixmap_cache:
                self._pixmap_cache[it.id] = render_clipart_pixmap(it, size=64)
            pix = self._pixmap_cache[it.id]

            list_item = QListWidgetItem(QIcon(pix), it.display_name)
            list_item.setToolTip(f"{it.name_zh} ({it.name_en})\n{it.keywords}")
            list_item.setData(Qt.ItemDataRole.UserRole, it.id)
            list_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_widget.addItem(list_item)

        total_cnt = len(items)
        self.label_status.setText(
            safe_tr("共找到 {n} 个剪贴画").format(n=total_cnt)
        )
        self.btn_insert.setEnabled(total_cnt > 0)
        if total_cnt > 0:
            self.list_widget.setCurrentRow(0)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        self.accept()

    def get_selected_clipart(self) -> ClipartItem | None:
        """Return the currently selected ClipartItem, or None."""
        curr = self.list_widget.currentItem()
        if not curr:
            return None
        clip_id = curr.data(Qt.ItemDataRole.UserRole)
        return get_clipart_by_id(clip_id)


def prompt_insert_clipart(parent_window: QWidget | None = None) -> ClipartItem | None:
    """Show Clipart dialog and insert chosen vector drawing into active document/canvas."""
    dlg = ClipartDialog(parent=parent_window)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None

    clip = dlg.get_selected_clipart()
    if clip and parent_window:
        _try_insert_clipart_into_window(parent_window, clip)
    return clip


def _try_insert_clipart_into_window(window: QWidget, clip: ClipartItem) -> None:
    """Insert clipart vector item into Lectern, Quire, or Ledger."""
    # 1. Lectern (Presentation Slide)
    if hasattr(window, "add_shape") or hasattr(window, "current_slide"):
        from atboffice.modules.presentation.models.shape import Shape

        shape = Shape(
            id=f"clipart_{clip.id}_{id(clip)}",
            type="image",
            name=f"Clipart: {clip.name_zh}",
            x=120.0,
            y=120.0,
            w=160.0,
            h=160.0,
            svg_content=clip.to_svg_xml(),
        )
        if hasattr(window, "add_shape"):
            window.add_shape(shape)
        elif hasattr(window, "current_slide"):
            slide = window.current_slide
            if slide and hasattr(slide, "shapes"):
                slide.shapes.append(shape)
                if hasattr(window, "update_canvas"):
                    window.update_canvas()

    # 2. Quire (Word Processor)
    elif hasattr(window, "insert_image") or hasattr(window, "editor"):
        pix = render_clipart_pixmap(clip, size=256)
        if hasattr(window, "insert_image"):
            window.insert_image(pix)
        elif hasattr(window, "editor") and hasattr(window.editor, "textCursor"):
            cursor = window.editor.textCursor()
            cursor.insertImage(pix.toImage())
