"""PowerPoint 2003 Action Settings Dialog for Lectern."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from atboffice.modules.presentation.models.presentation import Presentation, Slide


def safe_tr(text: str) -> str:
    """Translate UI text safely for ActionSettingsDialog."""
    return QCoreApplication.translate("ActionSettingsDialog", text)


class ActionTabWidget(QWidget):
    """Sub-widget representing either Mouse Click or Mouse Over tab."""

    def __init__(
        self,
        tab_type: str,  # 'click' or 'hover'
        slides: list[Slide] | None = None,
        initial_data: dict[str, Any] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.tab_type = tab_type
        self.slides = slides or []
        self.initial_data = initial_data or {}
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title_text = (
            safe_tr("单击时的动作") if self.tab_type == "click" else safe_tr("鼠标悬停时的动作")
        )
        self.group_action = QGroupBox(title_text, self)
        group_layout = QVBoxLayout(self.group_action)
        group_layout.setSpacing(8)

        # 1. Radio: None
        self.radio_none = QRadioButton(safe_tr("无(&N)"), self)

        # 2. Radio: Hyperlink to
        self.radio_hlink = QRadioButton(safe_tr("超链接到(&H):"), self)

        self.btn_group = QButtonGroup(self)
        self.btn_group.addButton(self.radio_none, 1)
        self.btn_group.addButton(self.radio_hlink, 2)

        # Action combo
        self.action_combo = QComboBox(self)
        self.action_items = [
            ("next", safe_tr("下一张幻灯片")),
            ("prev", safe_tr("上一张幻灯片")),
            ("first", safe_tr("第一张幻灯片")),
            ("last", safe_tr("最后一张幻灯片")),
            ("lastViewed", safe_tr("最近查看的幻灯片")),
            ("end", safe_tr("结束放映")),
            ("slide", safe_tr("指定幻灯片...")),
            ("url", safe_tr("URL...")),
        ]
        for key, label in self.action_items:
            self.action_combo.addItem(label, key)

        # Slide select combo
        self.slide_combo = QComboBox(self)
        if self.slides:
            for i, s in enumerate(self.slides):
                self.slide_combo.addItem(f"{i + 1}. {getattr(s, 'title', f'Slide {i + 1}')}", s.id)
        else:
            self.slide_combo.addItem(safe_tr("1. 幻灯片 1"), "1")

        # URL text edit
        self.url_edit = QLineEdit(self)
        self.url_edit.setPlaceholderText("https://")

        # Layout for hyperlink row
        hlink_sub = QVBoxLayout()
        hlink_sub.setContentsMargins(24, 0, 0, 0)
        hlink_sub.setSpacing(4)
        hlink_sub.addWidget(self.action_combo)
        hlink_sub.addWidget(self.slide_combo)
        hlink_sub.addWidget(self.url_edit)

        group_layout.addWidget(self.radio_none)
        group_layout.addWidget(self.radio_hlink)
        group_layout.addLayout(hlink_sub)

        layout.addWidget(self.group_action)

        # 3. Sound checkbox and combo
        sound_row = QHBoxLayout()
        self.chk_sound = QCheckBox(safe_tr("播放声音(&P):"), self)
        self.sound_combo = QComboBox(self)
        self.sound_items = [
            ("applause", safe_tr("[鼓掌]")),
            ("bomb", safe_tr("[爆炸]")),
            ("chime", safe_tr("[风铃]")),
            ("laser", safe_tr("[激光]")),
            ("typewriter", safe_tr("[打字机]")),
        ]
        for key, name in self.sound_items:
            self.sound_combo.addItem(name, key)

        sound_row.addWidget(self.chk_sound)
        sound_row.addWidget(self.sound_combo, 1)
        layout.addLayout(sound_row)

        # 4. Highlight click checkbox (only on click tab)
        self.chk_highlight = QCheckBox(safe_tr("按时高亮显示(&K)"), self)
        if self.tab_type == "click":
            layout.addWidget(self.chk_highlight)

        layout.addStretch()

        # Connect signals
        self.radio_none.toggled.connect(self._sync_state)
        self.radio_hlink.toggled.connect(self._sync_state)
        self.action_combo.currentIndexChanged.connect(self._sync_state)
        self.chk_sound.toggled.connect(self._sync_state)

        # Load initial data
        self._load_data()
        self._sync_state()

    def _load_data(self) -> None:
        action = self.initial_data.get("action")
        slide_id = self.initial_data.get("slide")
        url = self.initial_data.get("url")
        sound = self.initial_data.get("sound")
        highlight = self.initial_data.get("highlight", False)

        if action or slide_id or url:
            self.radio_hlink.setChecked(True)
            if slide_id:
                idx = self.action_combo.findData("slide")
                if idx >= 0:
                    self.action_combo.setCurrentIndex(idx)
                s_idx = self.slide_combo.findData(slide_id)
                if s_idx >= 0:
                    self.slide_combo.setCurrentIndex(s_idx)
            elif url:
                idx = self.action_combo.findData("url")
                if idx >= 0:
                    self.action_combo.setCurrentIndex(idx)
                self.url_edit.setText(url)
            elif action:
                idx = self.action_combo.findData(action)
                if idx >= 0:
                    self.action_combo.setCurrentIndex(idx)
        else:
            self.radio_none.setChecked(True)

        if sound:
            self.chk_sound.setChecked(True)
            snd_idx = self.sound_combo.findData(sound)
            if snd_idx >= 0:
                self.sound_combo.setCurrentIndex(snd_idx)
        else:
            self.chk_sound.setChecked(False)

        self.chk_highlight.setChecked(bool(highlight))

    def _sync_state(self) -> None:
        is_hlink = self.radio_hlink.isChecked()
        self.action_combo.setEnabled(is_hlink)

        cur_act = self.action_combo.currentData()
        self.slide_combo.setVisible(is_hlink and cur_act == "slide")
        self.url_edit.setVisible(is_hlink and cur_act == "url")

        self.sound_combo.setEnabled(self.chk_sound.isChecked())

    def get_data(self) -> dict[str, Any]:
        if self.radio_none.isChecked():
            return {
                "none": True,
                "sound": self.sound_combo.currentData() if self.chk_sound.isChecked() else None,
                "highlight": self.chk_highlight.isChecked(),
            }
        act = self.action_combo.currentData()
        result: dict[str, Any] = {
            "none": False,
            "action": act,
            "sound": self.sound_combo.currentData() if self.chk_sound.isChecked() else None,
            "highlight": self.chk_highlight.isChecked(),
        }
        if act == "slide":
            result["slide"] = self.slide_combo.currentData()
        elif act == "url":
            result["url"] = self.url_edit.text()
        return result

    def retranslate_ui(self) -> None:
        title_text = (
            safe_tr("单击时的动作") if self.tab_type == "click" else safe_tr("鼠标悬停时的动作")
        )
        self.group_action.setTitle(title_text)
        self.radio_none.setText(safe_tr("无(&N)"))
        self.radio_hlink.setText(safe_tr("超链接到(&H):"))
        self.chk_sound.setText(safe_tr("播放声音(&P):"))
        self.chk_highlight.setText(safe_tr("按时高亮显示(&K)"))


class ActionSettingsDialog(QDialog):
    """Action Settings Dialog with Mouse Click and Mouse Over tabs."""

    def __init__(
        self,
        presentation: Presentation | None = None,
        initial_settings: dict[str, Any] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.presentation = presentation
        self.slides = getattr(presentation, "slides", []) if presentation else []
        self.initial_settings = initial_settings or {}
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle(safe_tr("动作设置"))
        self.resize(380, 360)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Tab widget
        self.tabs = QTabWidget(self)
        self.tab_click = ActionTabWidget(
            "click",
            self.slides,
            self.initial_settings.get("click"),
            self,
        )
        self.tab_hover = ActionTabWidget(
            "hover",
            self.slides,
            self.initial_settings.get("hover"),
            self,
        )

        self.tabs.addTab(self.tab_click, safe_tr("单击鼠标"))
        self.tabs.addTab(self.tab_hover, safe_tr("鼠标悬停"))
        main_layout.addWidget(self.tabs, 1)

        # Button Box
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def get_action_settings(self) -> dict[str, Any]:
        """Return full action settings dictionary for click and hover tabs."""
        return {
            "click": self.tab_click.get_data(),
            "hover": self.tab_hover.get_data(),
        }

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("动作设置"))
        self.tabs.setTabText(0, safe_tr("单击鼠标"))
        self.tabs.setTabText(1, safe_tr("鼠标悬停"))
        self.tab_click.retranslate_ui()
        self.tab_hover.retranslate_ui()
