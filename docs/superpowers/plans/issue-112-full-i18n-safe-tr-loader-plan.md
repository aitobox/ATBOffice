# Implementation Plan: [Phase 2] 全量 7 国语言多语言翻译系统与 safe_tr 资源动态加载 (Issue #112)

## Phase 1: Resource Setup
- [ ] **Task 1.1**: Create `src/atboffice/resources/locale/` and copy 7 language JSON dictionaries (`zh-CN.json`, `zh-Hant.json`, `en.json`, `ja.json`, `ko.json`, `fr.json`, `de.json`) from `.vibeoffice/public/common/i18n/`.
- [ ] **Task 1.2**: Add `__init__.py` in `src/atboffice/resources/` and `src/atboffice/resources/locale/`.

## Phase 2: Test-Driven Development (TDD)
- [ ] **Task 2.1**: Create comprehensive unit tests in `tests/core/test_i18n.py` testing:
  - Resource files availability and integrity.
  - `load_locale` and language switching among all 7 supported locales.
  - Exact translation key matching (e.g., `&Save` -> `保存(&S)`).
  - Context stripping matching (`Line|chart` -> `折线图` vs `Line`).
  - Mnemonic handling (e.g. querying `Save` strips mnemonic from `&Save` -> `保存`).
  - CJK and untranslated string passthrough (e.g. `"自定义文本"` -> `"自定义文本"`).
  - Placeholder substitution (`safe_tr("Item {0} of {1}", 1, 10)` -> `"第 1 项，共 10 项"` or formatted output).
  - `I18nManager` signal emission (`locale_changed`).

## Phase 3: Core Implementation
- [ ] **Task 3.1**: Implement `src/atboffice/core/i18n.py`:
  - `TranslationCatalog`: Fast in-memory dictionary lookup, fallback cache, context stripping, mnemonic resolution.
  - `I18nManager`: QObject-based manager holding active catalog and emitting `locale_changed`.
  - Public API: `get_i18n_manager()`, `load_locale()`, `safe_tr()`, `tr()`, `get_available_locales()`.
- [ ] **Task 3.2**: Execute `pytest tests/core/test_i18n.py` to confirm all test cases pass.

## Phase 4: UI Shell Integration
- [ ] **Task 4.1**: Connect `BaseOfficeWindow` to `get_i18n_manager().locale_changed` and invoke `self.retranslate_ui()`.
- [ ] **Task 4.2**: Verify and implement `retranslate_ui()` in `MainWindow`, `StartCenterWindow`, `QuireWindow`, `LedgerWindow`, `LecternWindow`.
- [ ] **Task 4.3**: Update central imports of `safe_tr` across UI modules where appropriate.

## Phase 5: Verification & Quality Gate
- [ ] **Task 5.1**: Run `PYTHONPATH=src pytest tests/` to confirm 100% pass across all test suites.
- [ ] **Task 5.2**: Update state machine to `reviewing` and trigger `atb-github-code-reviewer`.
