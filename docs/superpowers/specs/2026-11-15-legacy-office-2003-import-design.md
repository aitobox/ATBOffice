# Office 97–2003（.doc / .xls / .ppt）高保真导入与强制转存设计文档

- **日期**：2026-11-15
- **状态**：待评审（Draft for Review）
- **选定方案**：方案 B1-a — 内嵌基于官方包文件级裁剪的无头 LibreOffice 转换引擎 + 复用现有 OOXML 解析管线

---

## 1. 背景与目标（Intent & Why）

ATBOffice 目前对现代 OOXML 格式（`.docx` / `.xlsx` / `.pptx`）拥有完整的解析、渲染与编辑能力，但对历史广泛存在的 Office 97–2003 二进制格式支持不均：
- **`.xls / .xlt`**：已通过 `xlrd` 在 `xls_reader.py` 实现只读导入，但缺乏图表、自选图形、图片锚点等复杂对象支持，且不支持加密 `.xls`。
- **`.doc / .dot`**：仅兼容伪装成 `.doc` 的 HTML / RTF 文件，真正的 OLE2 二进制 `.doc` 直接拒绝。
- **`.ppt / .pps / .pot`**：完全不支持，打开时直接拒绝。

用户希望能够**尽可能无损 / 高保真地导入 `.doc`、`.xls`、`.ppt` 等老格式**，在 ATBOffice 中浏览和编辑，并**强制转存为现代 OOXML 格式（`.docx` / `.xlsx` / `.pptx`）**，防止覆盖破坏原始二进制文件。

### 1.1 目标（Goals）
1. 在 Quire（`.doc/.dot`）、Ledger（`.xls/.xlt`）、Lectern（`.ppt/.pps/.pot`）三端实现高保真导入，最大化保留排版、样式、表格、图片、矢量图形、图表与公式。
2. 统一三端“只读导入 + 禁止直接覆盖保存 + 引导另存为现代格式”的交互约束（对齐当前 `LedgerWindow` 对 `.xls` 的行为）。
3. 打包内置裁剪后的转换引擎（方案 B1-a），实现三平台（macOS ARM64 `.dmg`、Linux x86_64 `.AppImage`、Windows x64 `.zip`）离线开箱即用。
4. 支持异步非阻塞转换与进度取消、加密旧文件解密前置处理，以及完全满足 MPL-2.0 / LGPLv3+ / TDF 商标政策与苹果公证要求。

### 1.2 非目标（Non-Goals）
1. **不支持导出 / 写回**二进制 `.doc` / `.xls` / `.ppt` 格式。
2. **不执行**旧文档中的 VBA 宏脚本。
3. **不替换** ATBOffice 自研的编辑与排版渲染器（转换引擎仅在打开瞬间将二进制转为临时 OOXML）。
4. **不从 C++ 源码重新编译 LibreOffice**（即不采用 B1-b）。

### 1.3 反目标（Anti-Goals — 绝对禁止）
1. **禁止触发 GPL 强传染**：禁止在进程内静态/动态链接 LibreOfficeKit，禁止在裁剪包内保留 Poppler（GPL）等强传染模块。
2. **禁止在 macOS 触发系统桌面注册**：内嵌运行目录不得包含可被 Launch Services 识别并抢占文件关联的 `.app` Bundle 结构或 `CFBundleDocumentTypes`。
3. **禁止在 UI 界面使用“LibreOffice”商标或官方徽标**。
4. **禁止阻塞 Qt 主线程**：冷启动与大文档转换必须异步执行并支持取消。

---

## 2. 备选方案对比（Approaches）

| 方案 | 核心思路 | 优点 | 缺点 | 结论 |
| :--- | :--- | :--- | :--- | :--- |
| **A. 本机外部 LibreOffice 桥接** | 仅探测用户系统已安装的 `soffice` | 包体积零增长、无随包合规负担 | 非开箱即用，未装 LibreOffice 用户无法打开 | 落选（可作为开发态回退） |
| **B1-a. 内嵌官方包文件级裁剪版** | 取 TDF 官方跨平台发行版，脚本删去 GUI/GPL/无关模块后随 Nuitka 打包 | **离线开箱即用 + 高保真**、无需维护 C++ 编译链、源码归属直指官方 | 安装包体积增加约 100–200MB（压缩后）、需处理签名与合规脚本 | **已选定** |
| **B1-b. 从源码 `--headless` 重编** | CI 拉取 LibreOffice 源码按最小参数编译 | 体积最小、GPL 剥离最彻底 | 三端 C++ 编译链极重、必须自建并长期托管对应源码 | 落选 |
| **C. 纯 Python/Rust 原生解析** | 依赖 `olefile`/`office-oxide`/`xlrd` 自研映射 | 零外部进程、包体轻量 | `[MS-DOC]`/`[MS-PPT]` 极复杂，无法达到高保真目标 | 落选 |

---

## 3. 总体架构设计

### 3.1 数据流与转换管线

```
用户打开文件 (Quire / Ledger / Lectern / StartCenter)
  │
  ▼
[1] 格式嗅探与校验 (vfs/crypto.py: inspect_file_format)
  ├── 伪装的 HTML / RTF / XMLSS ──► 走现有原生快开解析器 (read_html / RtfReader / read_xmlss_workbook)
  ├── 跨应用误打开 (如 Quire 打开 .ppt) ──► 拒绝并提示正确应用
  ├── 现代 OOXML / 加密 OOXML ──► 走现有 try_decrypt_if_encrypted + read_docx/xlsx/pptx
  └── 旧版 OLE2 二进制 (.doc/.dot/.xls/.xlt/.ppt/.pps/.pot，含伪装后缀)
        │
        ▼
[2] 加密检测与前置解密 (vfs/legacy_converter.py + msoffcrypto-tool)
  ├── 若为标准/RC4 加密的旧版 OLE2 ──► 弹窗提示输入密码 ──► 解密至内存/临时文件
  └── 未加密 ──► 直接进入下一步
        │
        ▼
[3] 异步格式转换 (QThread + 可取消进度条)
  ├── 定位内置裁剪转换引擎 (ATBOffice 随包 vendor 目录，开发模式可回退系统 soffice)
  ├── 隔离用户配置目录 (-env:UserInstallation=file://<temp_profile>)
  ├── 执行无头转换: soffice --headless --nologo --nodefault --nofirststartwizard --nolockcheck --norestore --convert-to <docx|xlsx|pptx> --outdir <temp_out> <input>
  └── 超时控制 (默认 60s) & 用户取消强杀子进程树 & 临时目录 finally 清理
        │
        ▼
[4] 复用现有高保真 OOXML 解析器
  ├── .doc/.dot  ──► 临时 .docx ──► read_docx()
  ├── .xls/.xlt  ──► 临时 .xlsx ──► read_xlsx() (若引擎不可用或转换异常，可降级 read_xls())
  └── .ppt/.pps/.pot ──► 临时 .pptx ──► read_pptx()
        │
        ▼
[5] 只读导入态与强制转存约束 (BaseWindow / 各模块窗口)
  ├── 标记 is_read_only_import = True，状态栏提示“已从旧版格式高保真导入，请另存为现代格式”
  ├── 直接点击“保存”时拦截并提示，引导拉起“另存为 (.docx / .xlsx / .pptx)”
  └── 另存为成功后解除 is_read_only_import，切换 current_file_path 为新路径
```

### 3.2 模块划分与职责

#### (1) `src/atboffice/vfs/legacy_converter.py`（新增核心转换服务）
- **引擎发现 (`find_converter_executable`)**：
  1. 环境变量覆盖：`ATBOFFICE_CONVERTER_PATH`（便于 CI 和本地覆盖测试）。
  2. 随包内置目录：按平台探测应用根目录/Resources 下的 `vendor/lo_headless/`（macOS：`Contents/Resources/vendor/lo_headless/MacOS/soffice`；Linux：`vendor/lo_headless/program/soffice`；Windows：`vendor/lo_headless/program/soffice.exe`）。
  3. 开发模式回退：若处于源码运行环境（非 frozen），回退探测系统 `PATH` 或标准安装路径中的 `soffice`。
- **格式与加密处理 (`prepare_legacy_input`)**：
  - 使用 `msoffcrypto-tool` 检测旧版 OLE2 是否受密码保护（支持 Word/Excel/PowerPoint 97–2003 标准/RC4 加密）。若加密则回调密码提供器获取密码，解密至临时文件后交由转换器。
- **进程隔离执行 (`convert_legacy_to_ooxml`)**：
  - 每次转换创建独立 `tempfile.TemporaryDirectory(prefix="atboffice_legacy_")`，内部包含 `profile/`、`in/`、`out/` 三个子目录。
  - 传入 `-env:UserInstallation=Path(profile_dir).as_uri()`，彻底隔离并发调用与系统已有进程锁。
  - Windows 下传入 `CREATE_NO_WINDOW` 标志避免弹出命令行黑框；POSIX 下使用 `start_new_session=True` 以便取消或超时时清理整个子进程组。
  - 支持 `cancel_event: threading.Event` 与 `timeout_seconds: float = 60.0`。
  - 转换完成后校验输出文件存在且非空，返回临时文件字节流或由调用方读取后立即销毁整个临时目录。

#### (2) `src/atboffice/vfs/crypto.py`（格式嗅探升级）
- `inspect_file_format()` 增加控制参数（如 `allow_legacy_conversion: bool = True`）或扩展现有 `allow_excel97` 为通用的旧版格式放行机制：
  - 当文件确实属于目标应用支持的旧版 OLE2（含扩展名被改写为 `.docx` 但实际是 `word97` 的伪装文件，只要目标应用匹配）且转换器可用时，`should_reject = False`，并返回明确的 `ole_format`（`word97` / `excel97` / `powerpoint97`）和 `is_disguised` 标记，由窗口层路由至转换管线。
  - 跨应用错配（例如用 Quire 打开 `.xls` 或 `.ppt`）依然直接拒绝并给出准确提示。

#### (3) UI 层统一（`BaseWindow`、`QuireWindow`、`LedgerWindow`、`LecternWindow`、`StartCenter`）
- **通用化只读导入机制**：将目前只写在 [ledger_window.py](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/ledger_window.py#L407-L566) 中的 `is_read_only_import` 保护逻辑（保存拦截提示）沉淀到 `BaseWindow`：
  - 新增统一异步导入辅助方法（例如 `run_with_progress` / `import_legacy_file`），在 `QThread` 中调用 `legacy_converter`，配合 `QProgressDialog`（支持用户点击“取消”中止子进程）；在 `PYTEST_CURRENT_TEST` 或无事件循环测试上下文中可同步运行或走显式回调。
  - 当用户对 `is_read_only_import=True` 的文档执行“保存（Ctrl/Cmd+S）”时，弹窗告知“旧版格式仅支持导入浏览，不支持原格式覆盖保存”，并提供按钮直接打开“另存为”对话框（默认扩展名自动切为 `.docx` / `.xlsx` / `.pptx`）。
- **各端窗口接入**：
  - `QuireWindow.do_open`：支持真实二进制 `.doc` / `.dot`（以及伪装成其他 Word 后缀的 `word97` OLE2），转换后走 `read_docx()`；`do_save` 继续拒绝写入 `.doc`/`.dot`。
  - `LedgerWindow.do_open`：`.xls` / `.xlt` 优先走 `legacy_converter` -> `read_xlsx()` 获取完整图表/图形/公式高保真度；若裁剪引擎不可用或转换失败时自动降级回现有的 `xlrd` (`read_xls()`) 保证可用性。
  - `LecternWindow.do_open`：支持 `.ppt` / `.pps` / `.pot`（以及 `powerpoint97` OLE2），转换后走 `read_pptx()`；`do_save` 继续拒绝写入 `.ppt`/`.pps`/`.pot`。
  - 更新 `StartCenter` 与三端 `get_file_filter()` 的“所有支持的格式”过滤器，确保所有 `.doc/.dot/.xls/.xlt/.ppt/.pps/.pot` 均可选中打开。

#### (4) `src/atboffice/deep/audit/core.py`（质量审计适配）
- 更新 `_probe_legacy_open_outcome` 与真实 GUI 打开审计路径，区分“通过内置转换引擎成功导入为只读现代文档 (`imported_via_converter`)”、“加密失败”和“损坏文件”。

---

## 4. B1-a 裁剪打包与开源合规设计

### 4.1 官方包文件级裁剪脚本（`scripts/vendor/prune_libreoffice.py`）
以 TDF 官方发布的对应平台固定版本号安装包（版本锁死在构建配置中，保证可复现）为输入，执行确定性裁剪：

1. **剔除高风险与冗余组件**：
   - **GPL 剔除**：删除 `xpdfimport`、Poppler 相关共享库（`libpoppler*` / `poppler*`）、`pdfimport` 扩展以及 MySQL/MariaDB SDBC 驱动，确保产物中**零 GPL 传染性依赖**。
   - **无关应用与 GUI 剔除**：删除 Help 帮助文档、Gallery 图库、Templates、SDK、拼写词典（ATBOffice 自带词典）、Java/Python-UNO 桥（若不使用 UNO，仅保留 CLI `soffice` 执行所需核心）、Base 数据库模块（`sbase`）及冗余 UI 图标主题/多语言资源（仅保留 `en-US` 核心回退）。
   - **桌面集成剥离（防系统劫持）**：
     - macOS：不以 `.app` 目录形式存在（重命名为普通目录 `lo_headless`），移除外层 `Info.plist` 中的 `CFBundleDocumentTypes`、`UTExportedTypeDeclarations`、QuickLook（`.qlgenerator`）与 Spotlight 插件（`.mdimporter`）。
     - Linux：移除 `.desktop`、`mime` 注册、图标目录。
     - Windows：移除右键菜单/Explorer 缩略图 shell extension DLL 及快捷方式注册表模板。
2. **合规文件保留与校验**：
   - 保留 `LICENSE`、`NOTICE`、`CREDITS.fodt` 或第三方声明文件于 `vendor/lo_headless/licenses/`。
   - 裁剪脚本末尾自动执行**合规门禁检查**（扫描残留文件列表中是否存在 `poppler`、`xpdfimport`、`Info.plist` 关联声明等黑名单项）与**三格式转换冒烟测试**（真机验证 `.doc -> .docx`、`.xls -> .xlsx`、`.ppt -> .pptx` 成功且无报错）。

### 4.2 预裁剪产物托管与 Nuitka 三平台打包集成（方式 A）

1. **离线裁剪与托管归档（`scripts/vendor/prune_libreoffice.py` + `lo_headless_manifest.json`）**：
   - 维护一份受版本控制的清单文件 `scripts/vendor/lo_headless_manifest.json`，记录锁定的上游 LibreOffice 版本、对应官方源码归档 URL，以及 macOS ARM64 / Linux x86_64 / Windows x64 三个预裁剪压缩包的下载 URL 与 SHA256 校验值。
   - 三端预裁剪包通过离线运行 `prune_libreoffice.py` 生成后，作为独立 Vendor Release 资产托管（例如 GitHub Releases 专用 `vendor-lo-*` tag 或团队对象存储），避免将上百 MB 二进制直接提交到 Git 仓库。
2. **构建拉取与严格校验（`scripts/vendor/fetch_lo_headless.py` + `scripts/build/`）**：
   - `build_macos.py`、`build_linux.py`、`build_windows.py` 与 `.github/workflows/release.yml` 在 Nuitka 打包后调用 `fetch_lo_headless.py` 下载并校验 SHA256，将产物解压至打包目录，**不让 Nuitka 扫描外部二进制**：
     - **macOS (`build_macos.py`)**：放置于 `ATBOffice.app/Contents/Resources/vendor/lo_headless/`；`sign_app_bundle()` 需先递归签名其中所有 Mach-O 可执行文件与 `.dylib`（`--options runtime --timestamp`），再签名主 `ATBOffice.app`，确保 Apple 公证（`notarytool`）通过。
     - **Linux (`build_linux.py`)**：放置于 AppDir 内的 `usr/bin/vendor/lo_headless/`，保留执行权限与相对库查找路径。
     - **Windows (`build_windows.py`)**：放置于便携目录 `ATBOffice/vendor/lo_headless/`。
   - **缺失策略**：构建脚本默认**强制要求** `vendor/lo_headless` 就绪（校验失败或缺失即报错退出，`release.yml` 绝不产出残缺包）；仅当本地开发调试显式传入 `--allow-missing-converter` 时允许跳过内置转换器打包。

### 4.3 测试策略与 CI / 审计集成（选项 B）

1. **PR 日常 CI（`.github/workflows/ci.yml`）保持轻量无引擎**：
   - `ci.yml` 的 `ubuntu-latest` PR 检查**不安装** LibreOffice 也不下载 `lo_headless`，保持快速运行。
   - `legacy_converter` 的核心逻辑（参数构造、隔离配置目录、超时强杀、取消中断、`msoffcrypto-tool` 解密预处理、Quire/Ledger/Lectern 只读导入态与保存拦截）通过 Mock `subprocess` 在 PR 阶段全量测试。
   - `tests/gui/test_issue294_legacy_and_abnormal_open.py` 按 `is_legacy_converter_available()` 区分双态：无引擎的 PR CI 中继续守护“无转换器时旧版 `.doc`/`.ppt` 安全拒绝且不污染 `recent_files`”以及 `.xls`（`xlrd`）与加密/损坏样本计数；当存在真实转换引擎时（本地开发或发布前验证），启用 `.doc`/`.ppt` 真实转换导入与渲染断言，并同步补充转换模式下的 `expectations.json` 预期状态字段。
2. **全量语料审计（`.github/workflows/corpus-audit.yml`）与发布验证**：
   - `corpus-audit.yml`（按需手动触发 / 每周定时）在执行全量审计前拉取 Linux 版 `lo_headless`（或配置 `ATBOFFICE_CONVERTER_PATH`），使全量 `.doc` / `.xls` / `.ppt` 语料的真实导入、渲染与转存链路得到持续回归验证。
   - `release.yml` 打出三端安装包后，在各平台 runner 上（或解包冒烟步骤）验证内置 `lo_headless` 存在且可转换最小 `.doc/.xls/.ppt` 样本。

### 4.4 开源声明与商标合规
- 更新 [license_dialog.py](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/dialogs/license_dialog.py) 中的 `OSS_COMPONENTS`：
  - 新增 **“Document Format Conversion Engine (based on LibreOffice)”**（采用中性命名，不使用官方 Logo 或暗示 TDF 背书），标明 `MPL-2.0 / LGPL-3.0+`，给出锁定版本号的 TDF 官方源码归档 URL（及可选的自建源码镜像 URL），并列出 `msoffcrypto-tool (MIT)`。
  - 更新 `AboutDialog` 或文档说明，不在主界面宣传中直接使用“LibreOffice”商标名称。

---

## 5. 我方默认做出的设计决策（请确认）

在以上设计中，以下几处细节由我方按工程最佳实践先行给出默认决定，后续编码将照此执行：
1. **`.xls / .xlt` 策略**：当内嵌转换引擎可用时，默认走 `soffice (.xls -> .xlsx) -> read_xlsx()` 以确保图表、形状、绘图和公式的高保真；同时保留现有 `xlrd` (`read_xls()`) 作为无转换器时的快速降级方案。
2. **加密旧版文档**：引入轻量级纯 Python 库 `msoffcrypto-tool`（MIT 许可）在调用 `soffice` 之前完成密码弹窗与解密，不把密码传递逻辑耦合进外部进程参数。
3. **Nuitka 打包策略与缺失门禁**：在 Nuitka 编译完成后由构建脚本拉取并复制 `vendor/lo_headless/`，避免 Nuitka 把几百个外部二进制纳入依赖扫描；构建脚本默认严格校验 `vendor/lo_headless` 存在且 SHA256 匹配（本地开发可传 `--allow-missing-converter` 跳过）；macOS 增加子二进制递归签名步骤以配合公证。
4. **“保存”按钮交互**：用户对只读导入的旧文件点击“保存”时，除提示不支持直接覆盖外，弹窗提供“立即另存为...”快捷操作（或直接跳转另存为对话框）。

---

## 6. 留给实施规划阶段处理的问题

以下工程实现细节交由后续制定执行计划（Implementation Plan）与开发阶段敲定：
- 具体裁剪文件白名单/黑名单在三平台（macOS / Linux / Windows）上的实测最小可运行集合与体积基线数据。
- `pyproject.toml` 新增依赖 `msoffcrypto-tool` 的精确版本约束。
- 转换引擎在多标签并发打开大文件时的并发限制/串行队列或独立进程池上限。
- 完整单元测试（Mock `soffice` 进程、超时/取消/损坏/加密/伪装边界用例）与集成测试（真实样本 `.doc/.xls/.ppt` 转换与渲染验收）。
