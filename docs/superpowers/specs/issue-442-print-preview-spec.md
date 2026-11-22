# Issue #442 — Unified printer geometry and in-window Office 2003 Print Preview

## Findings
- `BaseOfficeWindow.print_preview` opens a modal stock `QPrintPreviewDialog`; no module ever
  calls `setFullPage`, `setPageSize` or `setPageOrientation`, so hardware margins stack on top
  of document margins and landscape content is squeezed into portrait paper.
- Quire prints through `render_page_to_painter`, a stripped-down copy of the screen painter
  (no bullets, highlights, justification, borders/shading, watermarks, charts, shapes).
- Ledger has **no** page setup model, dialog or File > Page Setup entry; its printer loop
  ignores merges, conditional formats, wrap/rotation and drawings.
- Lectern hardcodes 960×540, never passes the presentation (so no design/master background),
  and only supports a fixed 3-per-page handout.

## Design
### Shared (`src/atboffice/ui/printing/`)
- `printer_setup.py` — `configure_page(printer, w_pt, h_pt)` (full page, zero margins, exact
  page size, orientation from aspect); `begin_points_painter(printer)` painter scaled to
  points; `print_font_scale(painter)` = 72 / device logical DPI (verified: a 72 pt font then
  renders 72 pt under the scaled painter).
- `preview_panel.py` — `PrintPreviewPanel`, a non-modal in-window overlay over the central
  widget: Print, Magnifier (fit ⇄ 100 %), One Page, Multiple Pages, Zoom, Page Setup, Close,
  page indicator, Esc/PgUp/PgDn; module-specific widgets via `add_extra_widget`. Built on
  `QPrintPreviewWidget`, whose pages come from the same `render_to_printer` used for Print
  and PDF export.
- `BaseOfficeWindow`: `prepare_printer()` hook before Print / Preview / PDF;
  `print_preview()` opens the panel; `open_page_setup()` hook; `print_preview_extras(panel)`.

### Lectern (`modules/presentation/printing.py`)
`PresentationPrintOptions` (what: slides / handouts 1-2-3-4-6-9 / notes / outline; color:
color / grayscale / pure B&W; frame slides; print hidden slides). Slides use the
presentation's own size and orientation; other layouts use portrait A4. Slides are painted by
`SlideScene(slide, presentation=pres)` so design backgrounds and master decorations print.
Grayscale / B&W are rendered via a high-resolution raster converted per pixel.

### Ledger (`modules/spreadsheet/printing/`)
- `setup.py` — `SheetPrintSetup` stored in `sheet.extra["print_setup"]`: orientation, paper,
  scale % or fit W×H, margins, header/footer (`&L&C&R` with `&P &N &D &T &F &A`), print area,
  rows/cols to repeat, gridlines, headings, black & white, page order, centring.
- `layout.py` — pagination (print area or used range incl. drawings, scale/fit, repeat
  titles, down-then-over / over-then-down).
- `render.py` — page rendering through `GridViewport.paint_print_region` (the on-screen
  `_paint_pane` path with selection/caret overlays suppressed), drawings via the object
  painter, headings, header/footer codes, B&W.
- `dialogs/page_setup_dialog.py` — Page / Margins / Header-Footer / Sheet tabs.
- xlsx round-trip of `pageMargins`, `pageSetup`, `printOptions`, `headerFooter`.

### Quire
`render_to_printer` paints each page through the screen painter `_paint_page_content` in a
print mode (points coordinates, print font scale, no spell-check squiggles), with each
page's own size/orientation; `render_page_to_painter` delegates to the same path.

### Menu
File > Page Setup (`pageSetup`) is added for Quire and Ledger.

## Task list
- [ ] Shared printer setup + in-window preview panel + base hooks
- [ ] Lectern print options and layouts
- [ ] Ledger print setup model, dialog, pagination, renderer, xlsx round-trip
- [ ] Quire print through the screen painter
- [ ] Tests `tests/gui/test_phase11_print_preview.py`, related suites, ruff
