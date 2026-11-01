# ATBOffice 打包与自动发布指南 (Build & Release Guide)

本文档详细介绍了 ATBOffice 基于 **Nuitka** 的跨平台打包体系，包括本地单模块测试、各平台打包工具链使用以及基于 GitHub Actions 的自动化发布与手动触发流程。

---

## 一、架构概览

ATBOffice 采用模块化、脚本驱动的打包架构，核心逻辑收敛于 `scripts/build/` 目录下，解耦了 CI 环境与本地编译流程。

```
scripts/build/
├── __init__.py
├── common.py           # 共享工具库：版本检测、标准产物命名、Nuitka 基础参数、PYTHONPATH 注入
├── build_macos.py      # macOS 打包：Nuitka GUI Bundle、Keychain 证书导入、代码签名、DMG 制作、公证与装订
├── build_linux.py      # Linux 打包：Nuitka 独立目录、AppDir 结构组装、AppImage 封装
├── build_windows.py    # Windows 打包：Nuitka 控制台抑制编译、POSIX 规范的便携式 ZIP 压缩
└── package.py          # 统一 CLI 调度器，支持指定平台或自动嗅探系统环境
```

### 产物规范与目标平台

| 平台 | 目标架构 | 打包格式 | 典型产物命名 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| **macOS** | ARM64 (Apple Silicon) | `.dmg` | `ATBOffice-0.1.0-macos-arm64.dmg` | 包含 `/Applications` 软链接，支持 Hardened Runtime 签名与苹果公证 |
| **Linux** | x86_64 (amd64) | `.AppImage` | `ATBOffice-0.1.0-linux-x86_64.AppImage` | 单一独立执行文件，内置 AppRun、图标与桌面元数据 |
| **Windows** | x64 | `.zip` (Portable) | `ATBOffice-0.1.0-windows-x64.zip` | 解压即用便携包，内置 `ATBOffice/atboffice.exe`，免安装运行 |

---

## 二、本地手工打包

开发者无需依赖 GitHub Actions，可以在本地开发机直接运行各平台的打包脚本进行测试与调试。

### 1. 环境准备

确保已激活 Python 3.12+ 开发环境并安装打包依赖：

```bash
conda activate ATBOffice
pip install nuitka zstandard pyside6 cryptography
```

### 2. 统一入口 (`package.py`)

可以通过 `scripts/build/package.py` 调度所有平台构建：

```bash
# 自动检测当前操作系统并构建对应安装包
python scripts/build/package.py auto

# 指定目标平台与版本号
python scripts/build/package.py windows --version test1.0.0
python scripts/build/package.py macos --skip-signing --skip-notarize
python scripts/build/package.py linux
```

### 3. 各平台独立打包脚本

每个平台脚本都可以独立执行，并支持平台专属配置：

#### macOS (`build_macos.py`)
```bash
# 本地免证书测试编译（跳过代码签名与公证）
python scripts/build/build_macos.py --skip-signing --skip-notarize

# 指定版本与输出目录
python scripts/build/build_macos.py --output-dir dist/ --version 1.0.0

# 严格模式（若环境变量中缺少 Developer ID 或公证凭证则报错退出）
python scripts/build/build_macos.py --strict-signing
```

#### Linux (`build_linux.py`)
```bash
# 标准构建（若系统未安装 appimagetool，脚本会自动下载到 build/tools/）
python scripts/build/build_linux.py

# 手动指定本地 appimagetool 路径
python scripts/build/build_linux.py --appimagetool /usr/local/bin/appimagetool
```

#### Windows (`build_windows.py`)
```bash
# 构建 Windows 便携式 ZIP 压缩包
python scripts/build/build_windows.py --version test1.0.0
```

---

## 三、GitHub Actions 自动发布工作流

仓库集成了 `.github/workflows/release.yml`，提供了**标签触发自动发布**与**手动触发定向打包**两种模式。

### 1. 模式 A：Git Tag 触发自动发布

向远程仓库推送符合规则的 Git Tag 时，将全自动触发三平台矩阵并行编译并发布 GitHub Release：

- **正式版本 Tag 模式**：
  - `0.1.0`、`1.0.0`
  - `v0.1.0`、`v1.0.0`
  - 自动创建标准的 GitHub 正式发布（Release）。
- **测试/预发布 Tag 模式**：
  - `test0.1.0`、`test1.0.0-rc1`、`test-20261101`
  - 任何以 `test` 开头的标签，工作流都会自动标记为 **Pre-release（预发布）**。

```bash
# 发布测试版并触发 CI 打包
git tag test1.0.0
git push origin test1.0.0

# 发布正式版并触发 CI 打包
git tag v1.0.0
git push origin v1.0.0
```

### 2. 模式 B：手动触发与定向平台打包 (`workflow_dispatch`)

如果不想新建 Git Tag，或者只想单独验证某一个平台的安装包（例如单独打包 Windows 便携包），可以使用 GitHub Actions 的手动触发机制。

#### Web 界面操作
1. 打开 GitHub 仓库，进入 **Actions** 标签页。
2. 在左侧列表中选择 **Release** 工作流。
3. 点击右侧的 **Run workflow** 下拉按钮：
   - **`Version string`**：输入目标版本号（例如 `test1.0.0` 或 `v0.2.0`）。若包含 `test` 前缀将自动设为 Pre-release。
   - **`Platform to build`**：下拉选择构建平台：
     - `all`：并行打包 macOS、Linux、Windows。
     - `windows`：仅启动 Windows runner，打包并发布 Windows ZIP。
     - `macos`：仅启动 macOS (ARM64) runner，打包、签名并公证 DMG。
     - `linux`：仅启动 Ubuntu runner，打包并发布 AppImage。
   - **`Publish as GitHub Release`**：
     - `true`（默认）：自动在 GitHub Releases 创建发布条目并上传产物。
     - `false`：仅在 Actions 执行详情中生成构件（Artifacts）供下载，不推送到 Releases 页面。

#### GitHub CLI (`gh`) 命令行触发
```bash
# 场景 1：仅为 Windows 平台构建并发布 test1.0.0 便携包
gh workflow run release.yml -f platform=windows -f version=test1.0.0

# 场景 2：构建全平台发布，但不生成正式 GitHub Release（仅在 Actions 产物中测试）
gh workflow run release.yml -f platform=all -f version=test1.0.0 -f publish_release=false

# 场景 3：仅为 macOS 重新构建并公证发布
gh workflow run release.yml -f platform=macos -f version=v1.0.1
```

---

## 四、macOS 证书与公证机制

CI 构建环境中通过 GitHub Secrets 实现了完整的苹果官方代码签名与公证链：

### 1. 所需环境变量 / GitHub Secrets
- `APPLE_ID`：Apple 开发者账号邮箱。
- `APPLE_PASSWORD`：Apple ID 的 App 专用密码（App-Specific Password）。
- `APPLE_TEAM_ID`：10 位的 Apple Team ID。
- `MAC_CERTS_P12_BASE64`：Base64 编码的 `Developer ID Application` 证书与私钥导出包（.p12）。
- `MAC_CERTS_PASSWORD`：P12 导出证书的解密密码。
- `MAC_PROVISION_PROFILE_BASE64`：（可选）配置描述文件。

### 2. 执行机制与安全性
- **隔离 Keychain**：在 runner 运行期间通过 `security create-keychain` 动态创建临时钥匙串，并在流程结束（`finally`）立即删除销毁，不污染 runner 环境。
- **强化运行时 (Hardened Runtime)**：`codesign` 携带 `--options runtime --timestamp` 参数，满足 macOS Gatekeeper 与公证要求。
- **Notarytool 等待机制**：调用 `xcrun notarytool submit --wait` 异步查询公证结果，审核通过后调用 `xcrun stapler staple` 将公证票据直接装订入 `.dmg` 文件。
- **严格校验**：CI 中使用 `--strict-signing` 参数；若证书解析失败或密钥失效，会直接中止构建，防止静默产生未签名受阻的损坏安装包。

---

## 五、打包常见排错与注意事项

1. **多语言与词典资源打包丢失**：
   - 项目使用 `src/` 源码布局，`scripts/build/common.py` 会在执行 Nuitka 前主动将 `<root>/src` 注入 `PYTHONPATH`，配合 `--include-package-data=atboffice`，确保 `src/atboffice/resources/locale/*.json` 与 `dict/` 完整打包进二进制。
2. **Linux AppImage FUSE 报错**：
   - 现代 Linux 系统或容器未安装 `libfuse.so.2` 时运行 `appimagetool` 可能失败，构建脚本内部已内置 `APPIMAGE_EXTRACT_AND_RUN=1` 环境变量自动降级解包运行。
3. **Windows 终端黑框隐匿**：
   - `build_windows.py` 配置了 `--windows-console-mode=disable`，双击运行 exe 时直接呈现 Qt 界面，不会弹出多余的命令行黑框。
4. **编译加速**：
   - Nuitka 支持 `ccache` 缓存。在本地开发机安装 `ccache`（如 `brew install ccache` 或 `apt install ccache`）可将重复打包时间从数分钟缩短至数十秒。
