"""PowerPoint 2003 Photo Album Creation Wizard Dialog for Lectern."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication, QSize, Qt
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely for PhotoAlbumDialog."""
    return QCoreApplication.translate("PhotoAlbumDialog", text)


LAYOUT_OPTIONS = [
    ("fit", safe_tr("适应幻灯片尺寸")),
    ("1", safe_tr("1 张图片")),
    ("2", safe_tr("2 张图片")),
    ("4", safe_tr("4 张图片")),
    ("1t", safe_tr("1 张图片，带标题")),
    ("2t", safe_tr("2 张图片，带标题")),
    ("4t", safe_tr("4 张图片，带标题")),
]

FRAME_OPTIONS = [
    ("rect", safe_tr("矩形")),
    ("round_rect", safe_tr("圆角矩形")),
    ("simple_white", safe_tr("简单框架，白色")),
    ("simple_black", safe_tr("简单框架，黑色")),
    ("soft_shadow", safe_tr("柔化边缘")),
]


class PhotoAlbumDialog(QDialog):
    """Photo Album creation dialog configuring batch picture slides and layout."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.picture_paths: list[str] = []
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle(safe_tr("相册"))
        self.resize(580, 420)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 1. Album Content Group
        self.grp_content = QGroupBox(safe_tr("相册内容"), self)
        content_layout = QHBoxLayout(self.grp_content)
        content_layout.setSpacing(10)

        # Left: File add button
        btn_col = QVBoxLayout()
        self.lbl_insert_from = QLabel(safe_tr("插入图片来自:"), self)
        self.btn_add_files = QPushButton(safe_tr("文件/磁盘...(&F)"), self)
        self.btn_add_files.clicked.connect(self._on_add_files)
        btn_col.addWidget(self.lbl_insert_from)
        btn_col.addWidget(self.btn_add_files)
        btn_col.addStretch()
        content_layout.addLayout(btn_col)

        # Middle: Pictures in album list & reorder buttons
        list_col = QVBoxLayout()
        self.lbl_pics_in_album = QLabel(safe_tr("相册中的图片:"), self)
        self.pic_list = QListWidget(self)
        self.pic_list.currentRowChanged.connect(self._on_row_changed)

        order_btns = QHBoxLayout()
        self.btn_up = QPushButton("↑", self)
        self.btn_up.setFixedWidth(32)
        self.btn_up.clicked.connect(self._on_move_up)

        self.btn_down = QPushButton("↓", self)
        self.btn_down.setFixedWidth(32)
        self.btn_down.clicked.connect(self._on_move_down)

        self.btn_remove = QPushButton(safe_tr("删除(&R)"), self)
        self.btn_remove.clicked.connect(self._on_remove)

        order_btns.addWidget(self.btn_up)
        order_btns.addWidget(self.btn_down)
        order_btns.addWidget(self.btn_remove)
        order_btns.addStretch()

        list_col.addWidget(self.lbl_pics_in_album)
        list_col.addWidget(self.pic_list, 1)
        list_col.addLayout(order_btns)
        content_layout.addLayout(list_col, 1)

        # Right: Preview frame
        prev_col = QVBoxLayout()
        self.lbl_preview = QLabel(safe_tr("预览:"), self)
        self.preview_box = QLabel(self)
        self.preview_box.setFixedSize(160, 120)
        self.preview_box.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        self.preview_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_box.setText(safe_tr("无预览"))

        prev_col.addWidget(self.lbl_preview)
        prev_col.addWidget(self.preview_box)
        prev_col.addStretch()
        content_layout.addLayout(prev_col)

        main_layout.addWidget(self.grp_content, 1)

        # 2. Album Layout Group
        self.grp_layout = QGroupBox(safe_tr("相册版式"), self)
        layout_form = QVBoxLayout(self.grp_layout)
        layout_form.setSpacing(8)

        # Picture layout combo
        row_layout = QHBoxLayout()
        self.lbl_pic_layout = QLabel(safe_tr("图片版式(&P):"), self)
        self.combo_layout = QComboBox(self)
        for key, text in LAYOUT_OPTIONS:
            self.combo_layout.addItem(text, key)
        row_layout.addWidget(self.lbl_pic_layout)
        row_layout.addWidget(self.combo_layout, 1)
        layout_form.addLayout(row_layout)

        # Frame shape combo
        row_frame = QHBoxLayout()
        self.lbl_frame_shape = QLabel(safe_tr("相框形状(&F):"), self)
        self.combo_frame = QComboBox(self)
        for key, text in FRAME_OPTIONS:
            self.combo_frame.addItem(text, key)
        row_frame.addWidget(self.lbl_frame_shape)
        row_frame.addWidget(self.combo_frame, 1)
        layout_form.addLayout(row_frame)

        # Captions below all pictures
        self.chk_captions = QCheckBox(safe_tr("所有图片下方均附带说明(&C)"), self)
        layout_form.addWidget(self.chk_captions)

        main_layout.addWidget(self.grp_layout)

        # 3. Create / Cancel buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        self.btn_create = QPushButton(safe_tr("创建(&C)"), self)
        self.btn_create.setDefault(True)
        self.btn_create.clicked.connect(self._on_create_clicked)

        self.btn_cancel = QPushButton(safe_tr("取消"), self)
        self.btn_cancel.clicked.connect(self.reject)

        btn_box.addWidget(self.btn_create)
        btn_box.addWidget(self.btn_cancel)
        main_layout.addLayout(btn_box)

    def _on_add_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            safe_tr("插入图片"),
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)",
        )
        for f in files:
            self.add_picture(f)

    def add_picture(self, path: str) -> None:
        self.picture_paths.append(path)
        name = Path(path).name
        item = QListWidgetItem(f"{len(self.picture_paths)}. {name}")
        self.pic_list.addItem(item)
        if self.pic_list.count() == 1:
            self.pic_list.setCurrentRow(0)

    def _on_row_changed(self, row: int) -> None:
        if 0 <= row < len(self.picture_paths):
            p = self.picture_paths[row]
            pix = QPixmap(p)
            if not pix.isNull():
                scaled = pix.scaled(
                    self.preview_box.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.preview_box.setPixmap(scaled)
            else:
                self.preview_box.setText(safe_tr("无法载入图片"))
        else:
            self.preview_box.clear()
            self.preview_box.setText(safe_tr("无预览"))

    def _on_move_up(self) -> None:
        row = self.pic_list.currentRow()
        if row > 0:
            self.picture_paths[row - 1], self.picture_paths[row] = (
                self.picture_paths[row],
                self.picture_paths[row - 1],
            )
            self._refresh_list(row - 1)

    def _on_move_down(self) -> None:
        row = self.pic_list.currentRow()
        if 0 <= row < len(self.picture_paths) - 1:
            self.picture_paths[row], self.picture_paths[row + 1] = (
                self.picture_paths[row + 1],
                self.picture_paths[row],
            )
            self._refresh_list(row + 1)

    def _on_remove(self) -> None:
        row = self.pic_list.currentRow()
        if 0 <= row < len(self.picture_paths):
            self.picture_paths.pop(row)
            self._refresh_list(max(0, row - 1) if self.picture_paths else -1)

    def _refresh_list(self, select_row: int) -> None:
        self.pic_list.clear()
        for i, p in enumerate(self.picture_paths):
            self.pic_list.addItem(f"{i + 1}. {Path(p).name}")
        if 0 <= select_row < self.pic_list.count():
            self.pic_list.setCurrentRow(select_row)

    def _on_create_clicked(self) -> None:
        if not self.picture_paths:
            QMessageBox.warning(
                self,
                safe_tr("相册"),
                safe_tr("请至少添加一张图片。"),
            )
            return
        self.accept()

    def get_album_spec(self) -> dict[str, Any]:
        """Return album layout configuration parameters."""
        return {
            "pictures": list(self.picture_paths),
            "layout": self.combo_layout.currentData(),
            "frame": self.combo_frame.currentData(),
            "captions": self.chk_captions.isChecked(),
        }

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("相册"))
        self.grp_content.setTitle(safe_tr("相册内容"))
        self.lbl_insert_from.setText(safe_tr("插入图片来自:"))
        self.btn_add_files.setText(safe_tr("文件/磁盘...(&F)"))
        self.lbl_pics_in_album.setText(safe_tr("相册中的图片:"))
        self.btn_remove.setText(safe_tr("删除(&R)"))
        self.lbl_preview.setText(safe_tr("预览:"))
        self.grp_layout.setTitle(safe_tr("相册版式"))
        self.lbl_pic_layout.setText(safe_tr("图片版式(&P):"))
        self.lbl_frame_shape.setText(safe_tr("相框形状(&F):"))
        self.chk_captions.setText(safe_tr("所有图片下方均附带说明(&C)"))
        self.btn_create.setText(safe_tr("创建(&C)"))
        self.btn_cancel.setText(safe_tr("取消"))
