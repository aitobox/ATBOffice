# Design Specification: Quire Built-in Document Templates (Issue #271)

## Overview
This specification defines the implementation of the 10 canonical built-in document templates for the Quire word processing module in ATBOffice, faithfully aligning with `.vibeoffice/public/quire/js/templates.js`.

The 10 templates are:
1. `letter` — Contemporary Letter (当代信函)
2. `memo` — Professional Memo (专业备忘录)
3. `fax` — Elegant Fax (优雅传真)
4. `resume` — Contemporary Résumé (个人简历)
5. `report` — Professional Report (专业业务报告)
6. `agenda` — Meeting Agenda (会议议程)
7. `minutes` — Meeting Minutes (会议纪要)
8. `todo` — To-Do Checklist (待办清单)
9. `flyer` — Event Flyer (活动传单)
10. `recipe` — Recipe (食谱卡片)

---

## Architectural Design

### 1. Module Structure
- **`src/atboffice/modules/writer/templates.py`**:
  - Core builders for all 10 templates.
  - Public entry point: `build_quire_template(template_id: str) -> Document`.
  - Exported alias: `DocumentModel = Document`.
  - Registration helper: `register_quire_templates(registry: TemplateRegistry | None = None)`.
  - DOM helpers:
    - `placeholder(label: str, r_pr: RunProperties | None = None) -> list[RunItem]`
    - `date_field(fmt: str, r_pr: RunProperties | None = None) -> list[RunItem]`
    - `simple_table(rows: list[list[str]], widths: list[float], header_fill: str | None = None, p_style: str | None = None) -> Table`
    - `make_bullet_abs(...)` and `make_number_abs(...)` for list numbering.
- **`src/atboffice/core/templates.py`**:
  - Wire up `TemplateInfo.builder` for the 10 Quire templates to call `build_quire_template(tid)`.
- **`src/atboffice/ui/shell/quire_window.py`**:
  - Implement `_apply_template_result(self, result: Any) -> None` to load generated `Document` onto `self.writer_view.canvas_view`.
  - Override `new_file(self)` to properly reset canvas with a fresh blank `Document`.

### 2. Template Specifications & Mapping

| Template ID | Primary Styles / Elements | Tables / Lists | Headers & Footers |
|---|---|---|---|
| `letter` | `CompanyName`, `ReturnAddress`, `InsideAddress`, `BodyTextLetter` | None | None |
| `memo` | `MemoTitle`, `MessageHeader` (indented tab stop), `MemoBody` | None | None |
| `fax` | `FaxTitle`, `FaxLabel` | 4x4 Table (grid: [60, 156, 60, 156]) | None |
| `resume` | `Name`, `Address1`, `SectionTitle`, `Objective`, `CompanyNameRes`, `JobTitle`, `Achievement` | Bullet list for achievements | None |
| `report` | `Title`, `Subtitle`, `Heading1`, `Heading2`, `TOCHeading` | TOC Field, Intro, Findings, Conclusion | Footer with `PAGE` field |
| `agenda` | `AgendaTitle`, `AgendaItem` | 6x3 Table (grid: [72, 252, 108]) | None |
| `minutes` | `MinutesTitle`, `MinutesHeading`, `MinutesText` | 5x3 Action Items Table (grid: [276, 96, 72]), Bullet list | None |
| `todo` | `ListTitle`, `ListHeading`, `Checklist` (hanging indent with checkbox) | Checkbox list items | None |
| `flyer` | `FlyerKicker`, `FlyerTitle`, `FlyerTagline`, `FlyerWhen`, `FlyerText` | Top/Bottom border rules | None |
| `recipe` | `RecipeTitle`, `RecipeHeading`, `RecipeText` | 2x4 Table (grid: [108, 108, 108, 108]), Bullets + Numbered steps | None |

---

## Edge Case Analysis (AI Execution Protocol)

1. **Unknown or Invalid Template ID**:
   - `build_quire_template("unknown")` raises `KeyError` or returns a fallback clean `Document`, gracefully handled in `load_template()`.
2. **Field and Macrobutton Structure**:
   - `FieldBeginItem`, `FieldSeparateItem`, `TextItem`, and `FieldEndItem` must maintain matching run properties to ensure layout and serialization do not raise `AttributeError`.
3. **Table Column Grid and Width Normalization**:
   - Explicit column grid matching points ([60, 156, 60, 156], etc.) and cell properties matching header styling and shading.
4. **Numbering Integrity**:
   - List definitions in `doc.numbering["abs"]` and `doc.numbering["nums"]` must have integer keys/IDs conforming to Word format and `addNum` logic so formatting and bullet rendering work correctly.
5. **i18n & UI Texts**:
   - All user-facing template display names, category names, and descriptions are localized with `safe_tr()`.
