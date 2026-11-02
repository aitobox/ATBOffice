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
python scripts/run_corpus_audit.py --corpus-dir tests/docs/full_corpus --workers 4 --output audit_report.jsonl
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

Qt 负责处理不同操作系统的窗口系统与原生控件适配。

## 打包与发布 (Packaging & Release)

### 1. 本地手工打包命令

项目在 `scripts/build/` 下提供了各平台的独立打包入口与统一调度命令，方便在本地测试 Nuitka 编译与安装包生成：

```bash
# 统一入口 (自动识别当前系统或指定平台)
python scripts/build/package.py auto
python scripts/build/package.py macos [--skip-signing] [--skip-notarize]
python scripts/build/package.py linux
python scripts/build/package.py windows

# 各平台独立脚本
python scripts/build/build_macos.py [--skip-signing] [--skip-notarize]
python scripts/build/build_linux.py
python scripts/build/build_windows.py
```

- **macOS**：生成 `ATBOffice-<version>-macos-arm64.dmg`。本地测试时若无证书可加 `--skip-signing --skip-notarize`。
- **Linux**：生成免安装的独立 `ATBOffice-<version>-linux-x86_64.AppImage`。
- **Windows**：生成解压即用的便携包 `ATBOffice-<version>-windows-x64.zip`（包含 `atboffice.exe` 及全量依赖）。

### 2. GitHub Actions 自动发布

向仓库推送指定格式的 Git Tag 时，将自动触发 `.github/workflows/release.yml` 发布流程：
- **触发规则**：支持 `x.x.x`、`vx.x.x`（正式发布）以及 `test*`（如 `test0.1.0` 测试版本）。
- **预发布标记**：以 `test` 开头的 Tag 自动发布为 GitHub **Pre-release**，其余为正式 Release。
- **构建矩阵**：macOS (ARM64 Apple Silicon)、Linux (x86_64)、Windows (x64) 三平台并行打包。
- **macOS 公证**：自动接入 GitHub Secrets（`APPLE_*`、`MAC_*`），完成代码签名、DMG 制作与 Apple Notary Service 自动公证装订。
