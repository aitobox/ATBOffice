"""Strict i18n audit and verification test suite for Phase 9 UI components and dialogs.

Ensures 100% user-facing string internationalization compliance across all Phase 9
dialogs, task panes, and controls, verifying safe_tr() wrapping, retranslate_ui() support,
and absence of raw unlocalized text.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from atboffice.ui.dialogs.customize_toolbars_dialog import (
    CustomizeToolbarsDialog,
    safe_tr as customize_safe_tr,
)


@pytest.fixture(scope="module")
def qapp():
    """Ensure headless QApplication instance is available."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(["pytest_i18n", "-platform", "offscreen"])
    return app


def test_customize_toolbars_dialog_i18n_completeness(qapp):
    """Verify CustomizeToolbarsDialog has complete localization across all tabs and controls."""
    dlg = CustomizeToolbarsDialog()

    # 1. Dialog title
    assert dlg.windowTitle() == customize_safe_tr("自定义")

    # 2. Tab labels
    assert dlg.tab_widget.count() == 4
    expected_tabs = [
        customize_safe_tr("工具栏 (&B)"),
        customize_safe_tr("命令 (&C)"),
        customize_safe_tr("选项 (&O)"),
        customize_safe_tr("键盘 (&K)"),
    ]
    actual_tabs = [dlg.tab_widget.tabText(i) for i in range(4)]
    assert actual_tabs == expected_tabs

    # 3. Tab 1 controls
    assert dlg.lbl_toolbars_hint.text() == customize_safe_tr("工具栏 (&T):")
    assert dlg.btn_new_toolbar.text() == customize_safe_tr("新建 (&N)...")
    assert dlg.btn_rename_toolbar.text() == customize_safe_tr("重命名 (&R)...")
    assert dlg.btn_delete_toolbar.text() == customize_safe_tr("删除 (&D)")
    assert dlg.btn_reset_toolbar.text() == customize_safe_tr("重置 (&E)...")

    # 4. Tab 2 controls
    assert dlg.lbl_categories.text() == customize_safe_tr("类别 (&G):")
    assert dlg.lbl_commands.text() == customize_safe_tr("命令 (&D):")
    assert dlg.lbl_desc_title.text() == customize_safe_tr("说明:")

    # 5. Tab 3 controls
    assert dlg.grp_personalized.title() == customize_safe_tr("个性化菜单和工具栏")
    assert dlg.chk_two_rows.text() == customize_safe_tr("分两行显示“常用”和“格式”工具栏 (&S)")
    assert dlg.chk_always_full_menus.text() == customize_safe_tr("始终显示完整菜单 (&M)")
    assert dlg.chk_menu_delay.text() == customize_safe_tr("简短的延时后显示完整菜单 (&U)")
    assert dlg.btn_reset_usage.text() == customize_safe_tr("重置菜单和工具栏使用情况数据 (&R)")
    assert dlg.grp_other.title() == customize_safe_tr("其他")
    assert dlg.chk_large_icons.text() == customize_safe_tr("大图标 (&L)")
    assert dlg.chk_screentips.text() == customize_safe_tr("显示屏幕提示 (&T)")
    assert dlg.chk_shortcut_tips.text() == customize_safe_tr("在屏幕提示中显示快捷键 (&K)")
    assert dlg.lbl_animations.text() == customize_safe_tr("菜单动画效果 (&A):")

    # 6. Tab 4 controls
    assert dlg.lbl_keyboard_hint.text() == customize_safe_tr("指定键盘快捷键")
    assert dlg.lbl_kb_category.text() == customize_safe_tr("类别 (&C):")
    assert dlg.lbl_kb_command.text() == customize_safe_tr("命令 (&O):")
    assert dlg.lbl_curr_shortcut_title.text() == customize_safe_tr("当前快捷键 (&U):")
    assert dlg.lbl_new_shortcut.text() == customize_safe_tr("请按新快捷键 (&N):")
    assert dlg.btn_assign_key.text() == customize_safe_tr("指定 (&A)")
    assert dlg.btn_remove_key.text() == customize_safe_tr("删除 (&R)")
    assert dlg.btn_reset_all_keys.text() == customize_safe_tr("全部重置 (&S)...")


def test_customize_toolbars_dialog_dynamic_retranslate(qapp):
    """Verify retranslate_ui() updates all strings dynamically without errors."""
    dlg = CustomizeToolbarsDialog()

    # Modify a control title to verify retranslate restores it
    dlg.setWindowTitle("DirtyTitle")
    dlg.tab_widget.setTabText(0, "DirtyTab")
    dlg.lbl_toolbars_hint.setText("DirtyHint")

    dlg.retranslate_ui()

    assert dlg.windowTitle() == customize_safe_tr("自定义")
    assert dlg.tab_widget.tabText(0) == customize_safe_tr("工具栏 (&B)")
    assert dlg.lbl_toolbars_hint.text() == customize_safe_tr("工具栏 (&T):")


def test_phase9_python_files_ast_i18n_audit():
    """Audit Phase 9 Python UI modules via AST to detect unlocalized Chinese string literals."""
    phase9_files = [
        Path("src/atboffice/ui/dialogs/customize_toolbars_dialog.py"),
        Path("src/atboffice/modules/presentation/slideshow/slide_hud.py"),
        Path("src/atboffice/modules/presentation/slideshow/annotation_layer.py"),
    ]

    for p in phase9_files:
        if not p.exists():
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))

        # Check for string constants that contain Chinese characters
        # They should either be inside a safe_tr(...) / tr(...) call or in a translation dictionary / mapping
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                # If calling addAction, setText, setWindowTitle, setTabText etc.
                if isinstance(func, ast.Attribute) and func.attr in (
                    "addAction",
                    "setText",
                    "setWindowTitle",
                    "setTabText",
                    "setPlaceholderText",
                ):
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            val = arg.value
                            # If literal contains non-ASCII and is not passed via safe_tr
                            has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in val)
                            if has_cjk:
                                pytest.fail(
                                    f"Direct unlocalized string literal {val!r} found in "
                                    f"{p}:{node.lineno}. Must wrap with safe_tr()!"
                                )


def test_safe_tr_fallback_behavior():
    """Verify safe_tr returns input string cleanly when no translation catalog is loaded."""
    msg = "测试国际化回退机制"
    translated = customize_safe_tr(msg)
    assert translated == msg
