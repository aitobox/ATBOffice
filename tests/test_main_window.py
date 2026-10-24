from atboffice.ui.main_window import MainWindow


def test_main_window_has_three_office_modules(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    tabs = window.centralWidget()
    assert tabs.count() == 3
    assert [tabs.tabText(index) for index in range(tabs.count())] == [
        "文字处理",
        "电子表格",
        "演示文稿",
    ]
