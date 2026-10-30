# Specification: [Phase 2] 全量 7 国语言多语言翻译系统与 safe_tr 资源动态加载 (Issue #112)

## 1. Context & Objectives
- **Parent Epic**: #96 - [Epic] ATBOffice 二期工程：1:1 完整全量移植与核心架构补完 (Phase 2)
- **Sequence**: Step 16 of 16 (Phase 2 收官核心任务)
- **Issue**: #112
- **Goal**:
  1. 完整引入原版 7 国语言（zh-CN, zh-Hant, en, ja, ko, fr, de）全量字典（6,000+ 词条）至 `src/atboffice/resources/locale/`。
  2. 实现核心模块 `src/atboffice/core/i18n.py`：
     - `TranslationCatalog`：高性能 JSON 翻译字典加载器、索引与双向带助记符（`&`）智能查找、上下文剥离（`|context`）、参数格式化与 fallback 机制；
     - `I18nManager`：全局单例管理器，基于 PySide6 `QObject` 提供 `locale_changed` 信号支持；
     - `load_locale(locale_name: str) -> None` 与 `safe_tr(key: str, *args) -> str`；
     - 中文字符串安全直接透传；英文及助记符精确或模糊匹配翻译。
  3. 联动 Shell 顶层窗口（`BaseOfficeWindow`, `MainWindow`, `StartCenterWindow`, `QuireWindow`, `LedgerWindow`, `LecternWindow` 等）实现 `retranslate_ui()` 信号槽机制，支持在运行时无缝热切换语言并刷新所有 MenuBar, ToolBar, ToolTip 与 StatusBar 文本。
  4. 编写全覆盖独立测试 `tests/core/test_i18n.py`。

---

## 2. Architecture & Design

### 2.1 File & Resource Layout
```
src/atboffice/
├── resources/
│   ├── __init__.py
│   └── locale/
│       ├── __init__.py
│       ├── zh-CN.json     # 6,069 词条 (简体中文)
│       ├── zh-Hant.json   # 繁体中文
│       ├── en.json        # 英文目录索引
│       ├── ja.json        # 日语
│       ├── ko.json        # 韩语
│       ├── fr.json        # 法语
│       └── de.json        # 德语
├── core/
│   └── i18n.py            # TranslationCatalog, I18nManager, load_locale, safe_tr, tr
└── ui/
    └── shell/
        ├── base_window.py # BaseOfficeWindow 监听 locale_changed -> retranslate_ui()
        ├── main_window.py # MainWindow 实现 retranslate_ui()
        ├── start_center.py# StartCenterWindow 实现 retranslate_ui()
        └── ...
```

### 2.2 TranslationCatalog Design
- **Locale Normalization**:
  - `zh`, `zh-cn`, `zh_cn`, `zh-hans`, `zh_hans` -> `zh-CN`
  - `zh-tw`, `zh-hk`, `zh-mo`, `zh-hant`, `zh_tw` -> `zh-Hant`
  - `en`, `en-us`, `en_us`, `en-gb` -> `en`
  - `ja`, `ja-jp`, `ja_jp` -> `ja`
  - `ko`, `ko-kr`, `ko_kr` -> `ko`
  - `fr`, `fr-fr`, `fr_fr` -> `fr`
  - `de`, `de-de`, `de_de` -> `de`
- **Lookup Resolution Order**:
  1. **Exact Key Match**: `dict.get(key)`. If found (and non-empty string), return translated string.
  2. **Context Stripping**: If key contains context suffix `|context` (e.g. `'Line|chart'`), try `plain(key)` (e.g. `'Line'`). If `dict.get(plain_key)` exists, return it.
  3. **Mnemonic Match**:
     - If key contains `&` (e.g. `"&Save"`), but dict only has `"Save"`, lookup stripped key and optionally preserve mnemonic intent.
     - If key has no `&` (e.g. `"Save"`), but dict has `"&Save" -> "保存(&S)"`, strip `(&S)` / `&` to return `"保存"`.
  4. **Fallback & Identity**:
     - If key already contains CJK characters (e.g. `"文件"`, `"保存"`, `"取消"`), return unchanged.
     - If key is English and untranslated, return `plain(key)` or `key`.
  5. **Placeholder Substitution**:
     - If `*args` provided: replace `{0}`, `{1}`, etc. with argument strings safely.

### 2.3 I18nManager & Signal Integration
- `I18nManager(QObject)`:
  - `locale_changed = Signal(str)`: Emitted when active locale is switched.
  - `current_locale: str`: Defaults to `"zh-CN"` (or system / config setting).
  - `load_locale(locale_name: str) -> None`: Loads catalog into memory and emits `locale_changed`.
  - `safe_tr(text: str, *args) -> str`: Calls catalog translation.

---

## 3. Edge Case Analysis ("Think One Step Ahead")

1. **Non-string or Empty Inputs**:
   - `safe_tr("")` -> `""`
   - `safe_tr(None)` -> `""` (safely handled without TypeError)
2. **Missing or Corrupted Locale Files**:
   - Graceful fallback: If a locale file fails to read or does not exist, log warning and fallback to English / un-translated keys without application crash.
3. **Mnemonic Key Stripping in East Asian Locales**:
   - In Chinese/Japanese/Korean, access keys are appended at the end like `文件(&F)` or `保存(&S)`. When stripped, `re.sub(r'\(&[A-Za-z0-9]\)', '', text)` produces clean `文件` or `保存`.
4. **Placeholders Inconsistency**:
   - Missing arguments: `safe_tr("Item {0} of {1}", 5)` leaves `{1}` safely as-is rather than raising IndexError or KeyError.
5. **UI Thread Safety & Performance**:
   - In-memory dict lookups with precomputed stripped-key fallback cache.
   - Signal emissions remain lightweight so `retranslate_ui()` is fast and smooth.

---

## 4. Acceptance Criteria
- [x] All 7 locale JSON dictionaries (zh-CN, zh-Hant, en, ja, ko, fr, de) located in `src/atboffice/resources/locale/`.
- [x] `src/atboffice/core/i18n.py` fully implemented with `TranslationCatalog`, `I18nManager`, `load_locale`, `safe_tr`, `tr`.
- [x] `BaseOfficeWindow` and shell windows connected to `locale_changed` and implement `retranslate_ui()`.
- [x] 100% test coverage in `tests/core/test_i18n.py` with 0 regressions in existing tests.
