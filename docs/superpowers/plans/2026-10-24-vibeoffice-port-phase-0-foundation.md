# VibeOffice Port Phase 0: Infrastructure Foundation & macOS Native Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the cross-platform (macOS prioritized) desktop foundation and lossless Open Packaging Conventions (OPC) infrastructure for ATBOffice in PySide6, enabling native windowing, Start Center, and byte-for-byte document preservation.

**Architecture:** Pure Python core algorithms (`vfs/`, `core/`, `drawing/`) with zero Qt dependencies for headless testing, paired with a PySide6 presentation layer (`ui/shell/`) implementing macOS unified menu bar, Retina scaling, and `QFileOpenEvent` file associations. An immutable source package model ensures unedited OOXML parts remain byte-identical upon resaving.

**Tech Stack:** Python 3.12+, PySide6 6.11+, `cryptography`, `defusedxml`, pytest 9.1+, pytest-qt.

**Spec:** [`docs/superpowers/specs/2026-10-24-vibeoffice-pyside6-port-design.md`](file:///Users/brainzhang/work/aitobox/ATBOffice/docs/superpowers/specs/2026-10-24-vibeoffice-pyside6-port-design.md)

## Global Constraints
- Target platform: macOS first (primary), Windows, Linux cross-platform compatible.
- All UI strings must be wrapped in `tr()` / `safe_tr()` with idiomatic Chinese/English translations (`core/i18n.py`).
- No GUI dependencies inside `src/atboffice/vfs/`, `src/atboffice/drawing/`, or `src/atboffice/core/config.py`.
- Atomic file write pattern (`tempfile` + `flush` + `os.replace`) required for all persistent storage.
- Strict OOXML schema node ordering enforced via `vfs/order.py`.

## Review Focus
1. Corrupted or truncated ZIP packages — must raise `CorruptedPackageError` with descriptive message, never raw unhandled `KeyError` or `IndexError`.
2. Encrypted documents without password — must detect Agile/Standard encryption headers and gracefully prompt via `PasswordRequiredError`.
3. Finder file association launch while app is already running — `QFileOpenEvent` must route to the existing process window manager without crashing or spawning duplicate menu bars.
4. Saving to read-only or permission-denied location — must abort before modifying disk and return `PermissionDeniedError` without destroying source file.
5. Strict vs Transitional OOXML namespace mismatch — must normalize `purl.oclc.org` namespaces to standard transitional URLs without dropping custom child attributes.

---

### Task 1: Core Foundation & i18n Services

**Files:**
- Create: `src/atboffice/core/config.py`
- Create: `src/atboffice/core/events.py`
- Create: `src/atboffice/core/i18n.py`
- Create: `src/atboffice/core/commands.py`
- Test: `tests/unit/core/test_config.py`
- Test: `tests/unit/core/test_i18n.py`
- Test: `tests/unit/core/test_commands.py`

**Interfaces:**
- Consumes: Standard library (`json`, `pathlib`, `typing`)
- Produces:
  - `ConfigManager.get(key: str, default: Any = None) -> Any`
  - `ConfigManager.set(key: str, value: Any) -> None`
  - `EventBus.emit(event: str, **kwargs: Any) -> None`
  - `EventBus.subscribe(event: str, callback: Callable[..., None]) -> None`
  - `tr(text: str, context: str = "") -> str`
  - `CommandRegistry.register(cmd_id: str, handler: Callable[..., Any], enabled_fn: Callable[[], bool] | None = None, key_sequence: str | None = None) -> None`
  - `CommandRegistry.execute(cmd_id: str, *args: Any, **kwargs: Any) -> Any`

- [ ] **Step 1: Write the failing tests for ConfigManager, EventBus, i18n, and CommandRegistry**

```python
# tests/unit/core/test_config.py
from pathlib import Path
from atboffice.core.config import ConfigManager

def test_config_get_set_atomic(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    cfg = ConfigManager(config_path=cfg_file)
    assert cfg.get("theme", "luna") == "luna"
    cfg.set("theme", "paper")
    assert cfg.get("theme") == "paper"
    assert cfg_file.exists()

# tests/unit/core/test_i18n.py
from atboffice.core.i18n import tr, set_locale, get_locale

def test_i18n_translation():
    set_locale("zh_CN")
    assert tr("&File") == "文件(&F)"
    assert tr("&New") == "新建(&N)"
    set_locale("en_US")
    assert tr("&File") == "File(&F)"

# tests/unit/core/test_commands.py
from atboffice.core.commands import CommandRegistry

def test_command_registration_and_execution():
    reg = CommandRegistry()
    executed = []
    reg.register("file.new", lambda: executed.append(True), key_sequence="Ctrl+N")
    reg.execute("file.new")
    assert executed == [True]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/unit/core/test_config.py tests/unit/core/test_i18n.py tests/unit/core/test_commands.py -v`
Expected: FAIL (modules not found)

- [ ] **Step 3: Implement ConfigManager, EventBus, i18n, and CommandRegistry**

Implement `src/atboffice/core/config.py` using atomic writes (`tempfile.NamedTemporaryFile` + `os.replace`).
Implement `src/atboffice/core/events.py` with subscriber dict.
Implement `src/atboffice/core/i18n.py` with embedded zh_CN/en_US translation tables and mnemonic ampersand stripper (`plain_amp`).
Implement `src/atboffice/core/commands.py` with before-exec hooks and enabled-checking.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/core/test_config.py tests/unit/core/test_i18n.py tests/unit/core/test_commands.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/core/ tests/unit/core/
git commit -m "feat(core): add config, event bus, i18n and command registry"
```

---

### Task 2: Lossless OPC Packaging Engine & XML Tree

**Files:**
- Create: `src/atboffice/vfs/xml_tree.py`
- Create: `src/atboffice/vfs/order.py`
- Create: `src/atboffice/vfs/opc.py`
- Test: `tests/unit/vfs/test_xml_tree.py`
- Test: `tests/unit/vfs/test_opc.py`

**Interfaces:**
- Consumes: Standard library (`zipfile`, `xml.etree.ElementTree`, `io`)
- Produces:
  - `XmlTree.parse(xml_bytes: bytes) -> XmlTree`
  - `XmlTree.serialize(order_rules: OrderRule | None = None) -> bytes`
  - `SourcePackage.open(file_or_bytes: Path | bytes) -> SourcePackage`
  - `SourcePackage.read_part(part_name: str) -> bytes`
  - `SourcePackage.has_part(part_name: str) -> bool`
  - `PackageWriter.replace_part(part_name: str, content: bytes, content_type: str | None = None) -> None`
  - `PackageWriter.save(target_path: Path) -> None`

- [ ] **Step 1: Write the failing tests for XML Tree and Lossless OPC Packaging**

```python
# tests/unit/vfs/test_opc.py
import zipfile
import io
from pathlib import Path
from atboffice.vfs.opc import SourcePackage, PackageWriter

def test_opc_lossless_carry(tmp_path: Path):
    # Create a synthetic OPC package with 2 parts: document.xml and vbaProject.bin
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", b"<Types><Default Extension='xml' ContentType='text/xml'/></Types>")
        zf.writestr("word/document.xml", b"<w:document><w:body><w:p><w:r><w:t>Hello</w:t></w:r></w:p></w:body></w:document>")
        zf.writestr("word/vbaProject.bin", b"\xDE\xAD\xBE\xEF\x01\x02\x03\x04")  # opaque binary macro
    pkg_bytes = buf.getvalue()

    pkg = SourcePackage.from_bytes(pkg_bytes)
    assert pkg.has_part("word/vbaProject.bin")
    
    writer = PackageWriter(source_package=pkg)
    # Edit ONLY document.xml
    new_doc_xml = b"<w:document><w:body><w:p><w:r><w:t>Hello World</w:t></w:r></w:p></w:body></w:document>"
    writer.replace_part("word/document.xml", new_doc_xml)
    
    out_file = tmp_path / "saved.docx"
    writer.save(out_file)
    
    # Verify: vbaProject.bin was carried byte-for-byte identical
    with zipfile.ZipFile(out_file, "r") as zf:
        assert zf.read("word/vbaProject.bin") == b"\xDE\xAD\xBE\xEF\x01\x02\x03\x04"
        assert zf.read("word/document.xml") == new_doc_xml
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/unit/vfs/test_opc.py -v`
Expected: FAIL (opc not found)

- [ ] **Step 3: Implement `xml_tree.py`, `order.py`, and `opc.py`**

Implement `src/atboffice/vfs/xml_tree.py` with preservation of prefixes, attributes and whitespace.
Implement `src/atboffice/vfs/order.py` with ECMA-376 schema ordering sequence dicts.
Implement `src/atboffice/vfs/opc.py` with `SourcePackage` (reads part table and bytes without unzipping all) and `PackageWriter` (copies untouched ZIP members directly, applies atomic save).

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/vfs/test_opc.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/vfs/ tests/unit/vfs/
git commit -m "feat(vfs): implement lossless OPC package reader and writer"
```

---

### Task 3: ECMA-376 Standard & Agile Cryptography Engine

**Files:**
- Create: `src/atboffice/vfs/crypto.py`
- Test: `tests/unit/vfs/test_crypto.py`

**Interfaces:**
- Consumes: `cryptography.hazmat.primitives.ciphers` (AES), `hashlib`
- Produces:
  - `is_encrypted_package(raw_bytes: bytes) -> bool`
  - `decrypt_package(raw_bytes: bytes, password: str) -> bytes`
  - `encrypt_package(raw_bytes: bytes, password: str, agile: bool = True) -> bytes`

- [ ] **Step 1: Write the failing tests for Agile and Standard Encryption**

```python
# tests/unit/vfs/test_crypto.py
import pytest
from atboffice.vfs.crypto import is_encrypted_package, decrypt_package, encrypt_package

def test_roundtrip_agile_encryption():
    plaintext_data = b"PK\x03\x04test_zip_package_content"
    password = "SecretPassword123!"
    
    encrypted = encrypt_package(plaintext_data, password=password, agile=True)
    assert is_encrypted_package(encrypted)
    
    decrypted = decrypt_package(encrypted, password=password)
    assert decrypted == plaintext_data

def test_wrong_password_raises():
    plaintext_data = b"PK\x03\x04test_zip_package_content"
    encrypted = encrypt_package(plaintext_data, password="CorrectPassword", agile=True)
    with pytest.raises(ValueError, match="Invalid password"):
        decrypt_package(encrypted, password="WrongPassword")
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/unit/vfs/test_crypto.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `crypto.py`**

Implement OLE compound file detection (`D0 CF 11 E0 A1 B1 1A E1`), `EncryptionInfo` stream parsing for Agile (AES-256 + SHA-512) and Standard (AES-128 + SHA-1), key derivation with spin counts, and payload decryption.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/vfs/test_crypto.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/vfs/crypto.py tests/unit/vfs/test_crypto.py
git commit -m "feat(vfs): add ECMA-376 Agile and Standard AES encryption engine"
```

---

### Task 4: Excel Number Formatter Engine

**Files:**
- Create: `src/atboffice/drawing/numfmt.py`
- Test: `tests/unit/drawing/test_numfmt.py`

**Interfaces:**
- Consumes: Standard library (`datetime`, `re`)
- Produces:
  - `format_number(value: float | int | str | datetime, format_str: str, locale: str = "en") -> str`

- [ ] **Step 1: Write the failing tests for Excel number format string evaluations**

```python
# tests/unit/drawing/test_numfmt.py
from datetime import datetime
from atboffice.drawing.numfmt import format_number

def test_number_formatting():
    assert format_number(1234.567, "#,##0.00") == "1,234.57"
    assert format_number(0.854, "0.0%") == "85.4%"
    assert format_number(-50, "$#,##0;($#,##0);\"-\"") == "($50)"
    assert format_number(0, "$#,##0;($#,##0);\"-\"") == "-"

def test_date_weekday_formatting():
    dt = datetime(2026, 10, 24)  # Saturday
    assert format_number(dt, "yyyy-mm-dd dddd") == "2026-10-24 Saturday"
    assert format_number(dt, "[$-804]aaaa") == "星期六"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/unit/drawing/test_numfmt.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `numfmt.py`**

Port `.vibeoffice/public/common/numfmt.js` into Python: section splitting by `;`, color and condition extractors (`[Green][>100]`), date code substitutions (`yyyy`, `m`, `d`, `aaa`, `aaaa`), fraction conversions, and exponential notation.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/drawing/test_numfmt.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/drawing/numfmt.py tests/unit/drawing/test_numfmt.py
git commit -m "feat(drawing): implement Excel compatible number formatter"
```

---

### Task 5: DrawingML 92 AutoShapes & 54 Pattern Fills

**Files:**
- Create: `src/atboffice/drawing/geometry.py`
- Create: `src/atboffice/drawing/patterns.py`
- Test: `tests/unit/drawing/test_geometry.py`

**Interfaces:**
- Consumes: Standard library (`math`, `typing`)
- Produces:
  - `get_shape_preset(preset_id: str) -> ShapePreset`
  - `ShapePreset.generate_path(w: float, h: float, adjustments: dict[str, float] | None = None) -> list[PathCommand]`
  - `get_pattern_bitmap(pattern_name: str, fg_hex: str, bg_hex: str) -> bytes`

- [ ] **Step 1: Write the failing tests for 92 shape presets and pattern generation**

```python
# tests/unit/drawing/test_geometry.py
from atboffice.drawing.geometry import get_shape_preset, SHAPE_PRESETS

def test_shape_presets_registered():
    assert len(SHAPE_PRESETS) >= 92
    rect = get_shape_preset("rect")
    assert rect is not None
    commands = rect.generate_path(100.0, 50.0)
    assert len(commands) > 0

def test_rounded_rect_adjustments():
    round_rect = get_shape_preset("roundRect")
    cmds1 = round_rect.generate_path(100.0, 100.0, {"adj": 16667})
    cmds2 = round_rect.generate_path(100.0, 100.0, {"adj": 50000})
    assert cmds1 != cmds2
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/unit/drawing/test_geometry.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `geometry.py` and `patterns.py`**

Port `.vibeoffice/public/common/geometry.js` 92 preset definitions (rect, roundRect, ellipse, triangle, chevron, star5, callouts, arrows) and adjustment formulas into pure Python. Port 54 preset 8x8 pattern matrices into `patterns.py`.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/drawing/test_geometry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/drawing/ tests/unit/drawing/
git commit -m "feat(drawing): implement 92 AutoShape presets and 54 pattern fills"
```

---

### Task 6: macOS Desktop Shell, Native Menu Bar & File Associations

**Files:**
- Create: `src/atboffice/core/app.py`
- Create: `src/atboffice/ui/shell/mac_menu.py`
- Create: `src/atboffice/ui/shell/main_window.py`
- Modify: `src/atboffice/__main__.py`
- Test: `tests/gui/test_mac_shell.py`

**Interfaces:**
- Consumes: `PySide6.QtWidgets`, `PySide6.QtGui`, `atboffice.core.commands`
- Produces:
  - `ATBApplication(QApplication)` with `event(e)` handling `QEvent.Type.FileOpen`
  - `build_mac_menu_bar(window: QMainWindow) -> QMenuBar`
  - `MainWindow` hosting unified tab/dock navigation

- [ ] **Step 1: Write the failing tests for macOS Shell and Window Management**

```python
# tests/gui/test_mac_shell.py
import pytest
from PySide6.QtGui import QKeySequence
from atboffice.ui.shell.main_window import MainWindow

def test_main_window_has_menu_and_title(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    assert "ATBOffice" in win.windowTitle()
    mb = win.menuBar()
    assert mb is not None
    actions = [a.text() for a in mb.actions()]
    assert any("文件" in a or "File" in a for a in actions)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/gui/test_mac_shell.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `app.py`, `mac_menu.py`, and `main_window.py`**

Configure `ATBApplication` with Retina pass-through scaling policy.
Implement `mac_menu.py` enabling `setNativeMenuBar(True)` on macOS, creating standard File, Edit, View, Insert, Format, Tools, Window, Help menus hooked into `CommandRegistry`.
Connect `QFileOpenEvent` in `app.py` to forward opened document paths to `MainWindow.open_document(path)`.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/gui/test_mac_shell.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/core/app.py src/atboffice/ui/shell/ src/atboffice/__main__.py tests/gui/test_mac_shell.py
git commit -m "feat(ui): add macOS native desktop shell, menu bar, and window dispatcher"
```

---

### Task 7: Start Center & Template Hub

**Files:**
- Create: `src/atboffice/core/recent.py`
- Create: `src/atboffice/ui/shell/start_center.py`
- Test: `tests/gui/test_start_center.py`

**Interfaces:**
- Consumes: `atboffice.core.config`, `atboffice.core.recent`
- Produces:
  - `RecentManager.add_recent(path: Path, app_kind: str) -> None`
  - `RecentManager.list_recent() -> list[RecentItem]`
  - `StartCenterWidget(QWidget)` showing recent cards, New Blank, and Template grid

- [ ] **Step 1: Write the failing tests for RecentManager and StartCenterWidget**

```python
# tests/gui/test_start_center.py
from pathlib import Path
from atboffice.core.recent import RecentManager
from atboffice.ui.shell.start_center import StartCenterWidget

def test_recent_manager_crud(tmp_path: Path):
    mgr = RecentManager(storage_path=tmp_path / "recent.json")
    doc_path = tmp_path / "test.docx"
    doc_path.touch()
    mgr.add_recent(doc_path, "quire")
    items = mgr.list_recent()
    assert len(items) == 1
    assert items[0].path == str(doc_path)

def test_start_center_widget(qtbot, tmp_path: Path):
    mgr = RecentManager(storage_path=tmp_path / "recent.json")
    widget = StartCenterWidget(recent_mgr=mgr)
    qtbot.addWidget(widget)
    widget.show()
    assert widget.findChild(object, "create_blank_button") is not None
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/gui/test_start_center.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `recent.py` and `start_center.py`**

Implement `RecentManager` with atomic persistence.
Implement `StartCenterWidget` providing:
- Left sidebar: Open file, Recent documents, Create file, Settings, About.
- Main area: Recent cards with thumbnails, and template gallery for Quire, Ledger, and Lectern.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/gui/test_start_center.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/core/recent.py src/atboffice/ui/shell/start_center.py tests/gui/test_start_center.py
git commit -m "feat(ui): add Start Center dashboard and recent documents manager"
```

---

### Task 8: End-to-End Integration & macOS Smoke Verification

**Files:**
- Create: `tests/test_phase0_integration.py`

**Interfaces:**
- Consumes: All Phase 0 components (`SourcePackage`, `PackageWriter`, `MainWindow`, `StartCenterWidget`)

- [ ] **Step 1: Write the Phase 0 end-to-end integration test**

```python
# tests/test_phase0_integration.py
import pytest
from pathlib import Path
from atboffice.ui.shell.main_window import MainWindow
from atboffice.vfs.opc import SourcePackage

def test_phase0_app_startup_and_sample_inspection(qtbot, tmp_path: Path):
    # Verify main window launches cleanly with start center
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    assert win.isVisible()
    
    # Verify sample package inspection
    sample_file = Path(".vibeoffice/tools/ooxml/sample.docx")
    if sample_file.exists():
        pkg = SourcePackage.open(sample_file)
        assert pkg.has_part("word/document.xml")
```

- [ ] **Step 2: Run end-to-end test**

Run: `pytest tests/test_phase0_integration.py -v`
Expected: PASS

- [ ] **Step 3: Run full pytest suite across all Phase 0 tasks**

Run: `pytest tests/ -v`
Expected: 100% PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_phase0_integration.py
git commit -m "test: add Phase 0 end-to-end integration and smoke verification"
```
