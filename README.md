# ATBOffice

ATBOffice 是一个基于 PySide6 的跨平台桌面办公套件项目，目标平台为 Windows、macOS 和 Linux，包含文字处理、电子表格和演示文稿三个应用模块。

## 环境要求

- Python 3.12 或更高版本
- Windows、macOS 或 Linux

## 安装与运行

```bash
python -m venv .venv
```

激活虚拟环境后安装项目及开发依赖：

```bash
python -m pip install -e ".[dev]"
```

启动应用：

```bash
python -m atboffice
# 或安装后使用命令
atboffice
```

## 开发

```bash
ruff check .
pytest
```

项目使用 `src` 布局；各办公模块位于 `src/atboffice/modules/`，共享 UI 和应用入口分别位于 `src/atboffice/ui/` 与 `src/atboffice/`。

## 项目结构

```text
.
├── .github/workflows/ci.yml
├── src/atboffice/
│   ├── modules/
│   │   ├── presentation/
│   │   ├── spreadsheet/
│   │   └── writer/
│   └── ui/
├── tests/
└── pyproject.toml
```

Qt 负责处理不同操作系统的窗口系统与原生控件适配；平台相关打包和发布配置可在后续阶段补充。
