"""Office 2003 styled Templates selection and preview dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QCoreApplication, QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from atboffice.core.templates import TemplateInfo


def safe_tr(text: str) -> str:
    """Translate UI text safely for TemplatesDialog."""
    return QCoreApplication.translate("TemplatesDialog", text)


class TemplatesDialog(QDialog):
    """Office 2003 'Templates on this computer...' dialog with live preview and category filters."""

    def __init__(
        self,
        app: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.target_app = app.lower() if app else None
        self._selected_template_id: str | None = None

        self.setWindowTitle(safe_tr("本机上的模板"))
        self.resize(680, 480)
        self.setMinimumSize(560, 380)

        self._init_ui()
        self._load_templates()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Top Bar: App Tabs or Category Filter
        self.tab_widget = QTabWidget(self)
        self.tab_widget.setDocumentMode(True)

        # Tabs: All, Quire, Ledger, Lectern
        self.tab_all = QWidget()
        self.tab_quire = QWidget()
        self.tab_ledger = QWidget()
        self.tab_lectern = QWidget()

        self.tab_widget.addTab(self.tab_all, safe_tr("常用模板"))
        self.tab_widget.addTab(self.tab_quire, safe_tr("文本文档 (Quire)"))
        self.tab_widget.addTab(self.tab_ledger, safe_tr("电子表格 (Ledger)"))
        self.tab_widget.addTab(self.tab_lectern, safe_tr("演示文稿 (Lectern)"))

        if self.target_app == "quire":
            self.tab_widget.setCurrentIndex(1)
        elif self.target_app == "ledger":
            self.tab_widget.setCurrentIndex(2)
        elif self.target_app == "lectern":
            self.tab_widget.setCurrentIndex(3)
        else:
            self.tab_widget.setCurrentIndex(0)

        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        main_layout.addWidget(self.tab_widget)

        # Center split: List on Left, Preview Card on Right
        center_layout = QHBoxLayout()
        center_layout.setSpacing(12)

        # Left: Templates List
        left_box = QVBoxLayout()
        left_box.setSpacing(6)

        # Category filter combo
        h_cat = QHBoxLayout()
        self.lbl_category = QLabel(safe_tr("分类:"), self)
        self.combo_category = QComboBox(self)
        self.combo_category.addItem(safe_tr("所有分类"), "")
        self.combo_category.currentIndexChanged.connect(self._on_category_changed)
        h_cat.addWidget(self.lbl_category)
        h_cat.addWidget(self.combo_category, stretch=1)
        left_box.addLayout(h_cat)

        self.list_widget = QListWidget(self)
        self.list_widget.setIconSize(QSize(28, 28))
        self.list_widget.setStyleSheet(
            """
            QListWidget {
                border: 1px solid #7B9EBD;
                background: #FFFFFF;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #F1F5F9;
            }
            QListWidget::item:selected {
                background: #3B82F6;
                color: #FFFFFF;
            }
            QListWidget::item:hover:!selected {
                background: #F8FAFC;
            }
            """
        )
        self.list_widget.currentItemChanged.connect(self._on_item_selected)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        left_box.addWidget(self.list_widget, stretch=1)
        center_layout.addLayout(left_box, stretch=3)

        # Right: Details & Preview Panel
        self.preview_frame = QFrame(self)
        self.preview_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.preview_frame.setStyleSheet(
            """
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
            }
            """
        )
        preview_layout = QVBoxLayout(self.preview_frame)
        preview_layout.setContentsMargins(14, 16, 14, 14)
        preview_layout.setSpacing(10)
        preview_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Preview Header: Big Icon
        self.lbl_preview_icon = QLabel("📄", self.preview_frame)
        icon_font = QFont()
        icon_font.setPointSize(44)
        self.lbl_preview_icon.setFont(icon_font)
        self.lbl_preview_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.lbl_preview_icon)

        # Preview Title
        self.lbl_preview_title = QLabel(safe_tr("选择模板以预览"), self.preview_frame)
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        self.lbl_preview_title.setFont(title_font)
        self.lbl_preview_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview_title.setWordWrap(True)
        preview_layout.addWidget(self.lbl_preview_title)

        # App & Category Badges
        self.lbl_preview_meta = QLabel("", self.preview_frame)
        self.lbl_preview_meta.setStyleSheet("color: #2563EB; font-weight: bold; font-size: 11px;")
        self.lbl_preview_meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.lbl_preview_meta)

        # Divider line
        div = QFrame(self.preview_frame)
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color: #E2E8F0;")
        preview_layout.addWidget(div)

        # Description
        self.lbl_preview_desc = QLabel("", self.preview_frame)
        self.lbl_preview_desc.setStyleSheet("color: #475569; font-size: 11px; line-height: 1.4;")
        self.lbl_preview_desc.setWordWrap(True)
        preview_layout.addWidget(self.lbl_preview_desc)

        preview_layout.addStretch(1)
        center_layout.addWidget(self.preview_frame, stretch=2)

        main_layout.addLayout(center_layout, stretch=1)

        # Bottom Button Row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        btn_layout.addStretch(1)

        self.btn_create = QPushButton(safe_tr("新建(&N)"), self)
        self.btn_create.setDefault(True)
        self.btn_create.setStyleSheet(
            "QPushButton { min-width: 80px; padding: 5px 14px; font-weight: bold; }"
        )
        self.btn_create.clicked.connect(self._on_create_clicked)
        btn_layout.addWidget(self.btn_create)

        self.btn_cancel = QPushButton(safe_tr("取消"), self)
        self.btn_cancel.setStyleSheet("QPushButton { min-width: 80px; padding: 5px 14px; }")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        main_layout.addLayout(btn_layout)

    def _get_active_app_filter(self) -> str | None:
        idx = self.tab_widget.currentIndex()
        if idx == 1:
            return "quire"
        if idx == 2:
            return "ledger"
        if idx == 3:
            return "lectern"
        return self.target_app if self.target_app else None

    def _on_tab_changed(self, index: int) -> None:
        self._update_categories_combo()
        self._load_templates()

    def _update_categories_combo(self) -> None:
        from atboffice.core.templates import TemplateRegistry

        reg = TemplateRegistry.get_instance()
        app_filter = self._get_active_app_filter()
        cats = reg.list_categories(app=app_filter)

        self.combo_category.blockSignals(True)
        self.combo_category.clear()
        self.combo_category.addItem(safe_tr("所有分类"), "")
        for cat in cats:
            self.combo_category.addItem(cat, cat)
        self.combo_category.blockSignals(False)

    def _on_category_changed(self) -> None:
        self._load_templates()

    def _load_templates(self) -> None:
        from atboffice.core.templates import TemplateRegistry

        reg = TemplateRegistry.get_instance()
        app_filter = self._get_active_app_filter()
        cat_data = self.combo_category.currentData()
        cat_filter = cat_data if cat_data else None

        templates = reg.list_templates(app=app_filter, category=cat_filter)

        self.list_widget.clear()
        for tpl in templates:
            item_text = f"{tpl.icon}  {tpl.name}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, tpl.id)
            self.list_widget.addItem(item)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
            self.btn_create.setEnabled(True)
        else:
            self.btn_create.setEnabled(False)
            self._clear_preview()

    def _on_item_selected(
        self, current: QListWidgetItem | None, previous: QListWidgetItem | None
    ) -> None:
        if not current:
            self._clear_preview()
            return

        template_id = current.data(Qt.ItemDataRole.UserRole)
        self._selected_template_id = template_id

        from atboffice.core.templates import TemplateRegistry

        reg = TemplateRegistry.get_instance()
        app_filter = self._get_active_app_filter()
        tpl = reg.get(template_id, app=app_filter)
        if not tpl:
            tpl = reg.get(template_id)

        if tpl:
            self.lbl_preview_icon.setText(tpl.icon)
            self.lbl_preview_title.setText(tpl.name)
            app_names = {
                "quire": "Quire " + safe_tr("文本文档"),
                "ledger": "Ledger " + safe_tr("电子表格"),
                "lectern": "Lectern " + safe_tr("演示文稿"),
            }
            app_str = app_names.get(tpl.app.lower(), tpl.app.capitalize())
            meta_str = f"{app_str} · {tpl.category}" if tpl.category else app_str
            self.lbl_preview_meta.setText(meta_str)
            self.lbl_preview_desc.setText(tpl.description or safe_tr("标准内置文档模板"))
            self.btn_create.setEnabled(True)

    def _clear_preview(self) -> None:
        self._selected_template_id = None
        self.lbl_preview_icon.setText("📄")
        self.lbl_preview_title.setText(safe_tr("暂无可用模板"))
        self.lbl_preview_meta.setText("")
        self.lbl_preview_desc.setText("")

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        self._selected_template_id = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def _on_create_clicked(self) -> None:
        if self._selected_template_id:
            self.accept()

    def get_selected_template_id(self) -> str | None:
        """Return the unique template ID chosen by the user."""
        return self._selected_template_id

    def get_selected_template(self) -> TemplateInfo | None:
        """Return the TemplateInfo model chosen by the user."""
        if not self._selected_template_id:
            return None
        from atboffice.core.templates import TemplateRegistry

        return TemplateRegistry.get_instance().get(self._selected_template_id)

    def retranslate_ui(self) -> None:
        """Translate all UI texts to the current locale."""
        self.setWindowTitle(safe_tr("本机上的模板"))
        self.tab_widget.setTabText(0, safe_tr("常用模板"))
        self.tab_widget.setTabText(1, safe_tr("文本文档 (Quire)"))
        self.tab_widget.setTabText(2, safe_tr("电子表格 (Ledger)"))
        self.tab_widget.setTabText(3, safe_tr("演示文稿 (Lectern)"))
        self.lbl_category.setText(safe_tr("分类:"))
        self.btn_create.setText(safe_tr("新建(&N)"))
        self.btn_cancel.setText(safe_tr("取消"))
        self._update_categories_combo()
        self._load_templates()
