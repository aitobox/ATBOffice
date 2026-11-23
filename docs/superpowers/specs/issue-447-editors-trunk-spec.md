# Issue #447 — Editors trunk gaps (Quire, Ledger, Lectern)

Part of Epic #436 (step 11 of 12). Blocks #448.

## Design

### Quire
- **View modes** (`views/canvas_view.py`): `page_slots()` gives a (rect, clip) per page.
  Normal stacks body areas with margins collapsed and dotted page-break lines; Web
  repaginates to one page as wide as the viewport (`layout/pagination._web_layout`);
  Reading places pages in side-by-side pairs and fits the zoom (restored on leaving);
  Print is unchanged.
- **Track changes** (`layout/revisions.py`): `apply(doc, item, r_pr)` restyles tracked
  runs in the author's colour (insertions underlined, deletions struck through) and
  returns `HIDE` for text that the Display for Review mode filters out
  (`final` hides deletions, `original` hides insertions). Show > Insertions and
  Deletions / Formatting are honoured.
- **Header/footer entry**: double-clicking a page's top/bottom margin (Print view)
  emits `header_footer_requested`, which opens the Header and Footer toolbar; the body
  is dimmed while `hf_edit_kind` is set.
- **Floating objects** (`views/float_edit.py`): hit-test page float boxes, select with
  eight sizing handles, drag to move (edits `float_pr` offsets; aligned/percent
  positions become absolute page offsets), drag a handle to resize (Shift keeps the
  aspect ratio). Each drag is one undo step.
- **Ruler** (`views/rulers/markers.py`): table column boundaries for the caret's table
  and gutters between text columns.

### Ledger
- Dynamic-array spill with `#SPILL!` and blue spill border (`calc/grid_spill.py`),
  structured references and `@` (`calc/structured_refs.py`), Ctrl+Shift+Enter arrays,
  draggable page breaks, outline gutter (`views/outline_gutter.py`), Window ▸ Split,
  HTML import/export (`io/html_io.py`).

### Lectern
- Live transition/animation preview overlay (`views/live_preview.py`), reveal-mask
  clip paths (`slideshow/transitions.reveal_clip`), rehearsal HUD saving
  `slide.transition.after` (`slideshow/rehearsal.py`), real media playback
  (`views/media_playback.py`).

## Task list
- [x] Quire view modes (Normal / Web / Reading)
- [x] Quire inline track-changes styling and Display for Review filtering
- [x] Quire header/footer double-click entry
- [x] Quire floating object select / move / resize
- [x] Quire ruler table column and column gutter markers
- [x] Ledger spill, structured refs, CSE, page-break drag, outline, split, HTML
- [x] Lectern live preview, reveal clips, rehearsal timings, media playback
- [x] Regression tests `tests/gui/test_phase11_editors_trunk.py`

## Known limitations
- Picture/Drawing/WordArt toolbar commands are not yet wired to the on-canvas float
  selection; they stay disabled with an explanatory reason.
- Rotation handles, motion-path editing, PivotCharts, Solver, Handout/Notes masters and
  the `en.thes` thesaurus are not part of this change.
