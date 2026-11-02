"""Open Source Licenses credits dialog for ATBOffice matching VibeOffice oss-licenses.html."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from atboffice.core.i18n import safe_tr


@dataclass(frozen=True)
class OSSComponent:
    """Descriptor for an open-source library or component bundled with ATBOffice."""

    name: str
    license_type: str
    summary: str
    url: str
    license_text: str


OSS_COMPONENTS: Final[list[OSSComponent]] = [
    OSSComponent(
        name="PySide6 / Qt 6",
        license_type="LGPL v3",
        summary="Official Python bindings for the Qt application framework by The Qt Company.",
        url="https://wiki.qt.io/Qt_for_Python",
        license_text="""GNU LESSER GENERAL PUBLIC LICENSE
Version 3, 29 June 2007

Copyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>
Everyone is permitted to copy and distribute verbatim copies
of this license document, but changing it is not allowed.

This version of the GNU Lesser General Public License incorporates
the terms and conditions of version 3 of the GNU General Public
License, supplemented by the additional permissions listed below.

The Qt Toolkit is Copyright (C) The Qt Company Ltd. and other contributors.
Contact: https://www.qt.io/licensing/""",
    ),
    OSSComponent(
        name="Python 3.12+",
        license_type="PSF License",
        summary="Core Python programming language runtime environment.",
        url="https://www.python.org/",
        license_text="""PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2

1. This LICENSE AGREEMENT is between the Python Software Foundation ("PSF"), and
the Individual or Organization ("Licensee") accessing and otherwise using this
software ("Python") in source or binary form and its associated documentation.

2. Subject to the terms and conditions of this License Agreement, PSF hereby
grants Licensee a nonexclusive, royalty-free, world-wide license to reproduce,
analyze, test, perform and/or display publicly, prepare derivative works, distribute,
and otherwise use Python alone or in any derivative version.""",
    ),
    OSSComponent(
        name="openpyxl",
        license_type="MIT License",
        summary="Python library to read/write Excel 2010 xlsx/xlsm/xltx/xltm files.",
        url="https://openpyxl.readthedocs.io/",
        license_text="""MIT License

Copyright (c) 2010 openpyxl

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.""",
    ),
    OSSComponent(
        name="python-docx",
        license_type="MIT License",
        summary="Python library for creating and updating Microsoft Word (.docx) files.",
        url="https://python-docx.readthedocs.io/",
        license_text="""The MIT License (MIT)

Copyright (c) 2013 Steve Canny, https://github.com/scanny

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.""",
    ),
    OSSComponent(
        name="Pillow",
        license_type="HPND License",
        summary="The friendly Python Imaging Library fork by Jeffrey A. Clark and contributors.",
        url="https://python-pillow.org/",
        license_text="""The Python Imaging Library (PIL) is

    Copyright © 1997-2011 by Secret Labs AB
    Copyright © 1995-2011 by Fredrik Lundh

Pillow is the friendly PIL fork. It is

    Copyright © 2010-2024 by Jeffrey A. Clark and contributors.

Permission to use, copy, modify, and distribute this software and its
documentation for any purpose and without fee is hereby granted, provided that
the above copyright notice appear in all copies and that both that copyright
notice and this permission notice appear in supporting documentation.""",
    ),
    OSSComponent(
        name="Puff (Deflate Engine)",
        license_type="zlib License",
        summary="Lightweight, fast deflate decompression engine by Mark Adler.",
        url="https://github.com/madler/zlib/tree/master/contrib/puff",
        license_text="""Copyright (C) 2002-2013 Mark Adler

This software is provided 'as-is', without any express or implied
warranty. In no event will the authors be held liable for any damages
arising from the use of this software.

Permission is granted to anyone to use this software for any purpose,
including commercial applications, and to alter it and redistribute it
freely.""",
    ),
    OSSComponent(
        name="CommonMark",
        license_type="BSD-2-Clause",
        summary=(
            "Standard, unambiguous syntax specification and reference implementation for Markdown."
        ),
        url="https://commonmark.org/",
        license_text="""Copyright (c) 2014, John MacFarlane
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice,
  this list of conditions and the following disclaimer.""",
    ),
    OSSComponent(
        name="OpenXML SDK",
        license_type="MIT License",
        summary="Open XML schemas and document packaging specifications by Microsoft.",
        url="https://github.com/dotnet/Open-XML-SDK",
        license_text="""The MIT License (MIT)

Copyright (c) Microsoft Corporation

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so.""",
    ),
    OSSComponent(
        name="DejaVu Fonts",
        license_type="Bitstream Vera License",
        summary="DejaVu font family based on Bitstream Vera with wide Unicode coverage.",
        url="https://dejavu-fonts.github.io/",
        license_text="""Fonts are Copyright (c) 2003 by Bitstream, Inc. All Rights Reserved.
Bitstream Vera is a trademark of Bitstream, Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of the fonts accompanying this license to reproduce and distribute the
Font Software, including without limitation the rights to use, copy, merge,
publish, distribute, and/or sell copies.""",
    ),
]


class LicenseDialog(QDialog):
    """Credits and Open Source Licenses acknowledgment viewer dialog matching 010_page_licenses."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.components = list(OSS_COMPONENTS)

        self.setMinimumSize(680, 460)
        self.resize(750, 520)

        self._build_ui()
        self.retranslate_ui()
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 18, 20, 18)
        root_layout.setSpacing(12)

        # Header Title and Intro
        self.lbl_title = QLabel(self)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self.lbl_title.setFont(title_font)
        root_layout.addWidget(self.lbl_title)

        self.lbl_intro = QLabel(self)
        self.lbl_intro.setWordWrap(True)
        self.lbl_intro.setStyleSheet("color: #475569; font-size: 12px;")
        root_layout.addWidget(self.lbl_intro)

        # Filter Search Box
        search_row = QHBoxLayout()
        self.txt_search = QLineEdit(self)
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self.txt_search)
        root_layout.addLayout(search_row)

        # Splitter Layout (Left list, Right details + text)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Left list widget
        self.list_widget = QListWidget(splitter)
        self.list_widget.setFixedWidth(240)
        self.list_widget.currentRowChanged.connect(self._on_item_selected)
        splitter.addWidget(self.list_widget)

        # Right container
        right_container = QWidget(splitter)
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.setSpacing(8)

        self.lbl_comp_name = QLabel(right_container)
        comp_font = QFont()
        comp_font.setPointSize(14)
        comp_font.setBold(True)
        self.lbl_comp_name.setFont(comp_font)
        right_layout.addWidget(self.lbl_comp_name)

        self.lbl_comp_meta = QLabel(right_container)
        self.lbl_comp_meta.setStyleSheet("color: #0284C7; font-weight: bold; font-size: 11px;")
        right_layout.addWidget(self.lbl_comp_meta)

        self.lbl_comp_desc = QLabel(right_container)
        self.lbl_comp_desc.setWordWrap(True)
        self.lbl_comp_desc.setStyleSheet("color: #334155; font-size: 12px;")
        right_layout.addWidget(self.lbl_comp_desc)

        self.text_license = QPlainTextEdit(right_container)
        self.text_license.setReadOnly(True)
        font = QFont("Courier New", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.text_license.setFont(font)
        self.text_license.setStyleSheet(
            "background-color: #F8FAFC; border: 1px solid #CBD5E1; "
            "border-radius: 4px; padding: 6px;"
        )
        right_layout.addWidget(self.text_license, stretch=1)

        splitter.addWidget(right_container)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root_layout.addWidget(splitter, stretch=1)

        # Bottom Button Bar
        btn_layout = QHBoxLayout()
        self.btn_copy = QPushButton(self)
        self.btn_copy.clicked.connect(self._on_copy_license)
        btn_layout.addWidget(self.btn_copy)

        btn_layout.addStretch(1)

        self.btn_close = QPushButton(self)
        self.btn_close.setDefault(True)
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)

        root_layout.addLayout(btn_layout)

        self._populate_list()

    def _populate_list(self, filter_text: str = "") -> None:
        """Fill list widget with filtered open-source components."""
        self.list_widget.clear()
        query = filter_text.strip().lower()

        for comp in self.components:
            if query and (
                query not in comp.name.lower()
                and query not in comp.license_type.lower()
                and query not in comp.summary.lower()
            ):
                continue
            item = QListWidgetItem(f"{comp.name} ({comp.license_type})")
            item.setData(Qt.ItemDataRole.UserRole, comp)
            self.list_widget.addItem(item)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        else:
            self.lbl_comp_name.setText(safe_tr("未找到匹配的组件"))
            self.lbl_comp_meta.setText("")
            self.lbl_comp_desc.setText("")
            self.text_license.setPlainText("")

    def _on_search_changed(self, text: str) -> None:
        self._populate_list(text)

    def _on_item_selected(self, row: int) -> None:
        if row < 0 or row >= self.list_widget.count():
            return
        item = self.list_widget.item(row)
        comp: OSSComponent = item.data(Qt.ItemDataRole.UserRole)
        self.lbl_comp_name.setText(comp.name)
        self.lbl_comp_meta.setText(f"{comp.license_type}  •  {comp.url}")
        self.lbl_comp_desc.setText(comp.summary)
        self.text_license.setPlainText(comp.license_text)

    def _on_copy_license(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None and self.text_license.toPlainText():
            clipboard.setText(self.text_license.toPlainText())

    def retranslate_ui(self) -> None:
        """Update localized UI text dynamically."""
        self.setWindowTitle(safe_tr("开源许可证与鸣谢 — ATBOffice"))
        self.lbl_title.setText(safe_tr("开源软件与字体许可证声明"))
        self.lbl_intro.setText(
            safe_tr("ATBOffice 由多款杰出的开源项目驱动，向所有开源贡献者致敬。")
        )
        self.txt_search.setPlaceholderText(safe_tr("搜索开源组件名称或许可证类型…"))
        self.btn_copy.setText(safe_tr("复制许可证文本(&C)"))
        self.btn_close.setText(safe_tr("关闭(&O)"))
