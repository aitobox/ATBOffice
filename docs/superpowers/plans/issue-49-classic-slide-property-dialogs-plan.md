# Implementation Plan: Issue #49 - Classic Slide Property Dialogs

## Tasks
1. **Task 1: Test Suite Creation (TDD Red Phase)**
   - Target: `tests/gui/test_lectern_dialogs.py`
   - Test `FormatShapeDialog` initialization, tab switching, property mutation (fill, line, size, rotation, margins, alt text).
   - Test `SetupShowDialog` initialization, show types (speaker, window, kiosk), loop option, slide range calculation.
   - Test `HeaderFooterDialog` and `SlideLayoutDialog`.
   - Test `retranslate_ui` on all dialogs.

2. **Task 2: Implement FormatShapeDialog**
   - Target: `src/atboffice/modules/presentation/dialogs/format_shape.py`
   - 6 tabs: Colors & Lines, Size, Position, Picture, Text Box, Web.
   - Live synchronization with `Shape`, `Fill`, `Line`, `TextBody`.

3. **Task 3: Implement SetupShowDialog**
   - Target: `src/atboffice/modules/presentation/dialogs/setup_show.py`
   - Show type radio group, show options checkboxes & pen color button, slide range spinner controls, advance slide radio group.
   - Live synchronization with `SlideShowSettings`.

4. **Task 4: Implement HeaderFooterDialog & SlideLayoutDialog**
   - Target: `src/atboffice/modules/presentation/dialogs/header_footer.py`
   - Target: `src/atboffice/modules/presentation/dialogs/slide_layout.py`
   - Header/Footer settings synchronization.
   - Slide Layout selection grid and apply callback.

5. **Task 5: Update Package Exports**
   - Target: `src/atboffice/modules/presentation/dialogs/__init__.py`
   - Re-export all dialogs.

6. **Task 6: Verification & Test Suite Pass (Green Phase)**
   - Run `conda run -n ATBOffice pytest tests/gui/test_lectern_dialogs.py -v`.
   - Run all existing presentation tests to ensure no regressions.
