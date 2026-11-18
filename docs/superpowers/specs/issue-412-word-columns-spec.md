# Issue #412: Word section column geometry and balancing

## Intent and evidence

Match the reference layout for `libreoffice__fdo52208.docx` and
`libreoffice__tdf121670_columnsInSectionsOnly.docx`. The former declares a
single explicit 2,000-twip column, but the reader discards it. The latter's
opening section is incorrectly balanced before a next-page break.

Reference: `.vibeoffice/public/quire/js/docx-read.js` preserves `equalWidth`,
individual widths and gaps, and infers column count from children. `layout.js`
uses those widths directly and balances only when entering a compatible
continuous section. It does not balance the final document section.

## Approach

Extend the existing `ColumnsProperties` with per-column gaps; preserve its
existing widths and equal-width switch through import, layout, and export.
Use uniform spacing for programmatically created columns without explicit
gaps. Keep zero gaps and single explicit widths. Missing or invalid dimensions
fall back to usable geometry. Remove unconditional end-of-section balancing.

Alternatives considered: an import-only fix cannot affect layout; a new
column model duplicates the existing dialog contract; fixture-specific width
overrides would hide the defect. The existing model is the smallest coherent
fix. This is an autonomous implementation decision under the requested
end-to-end workflow, not a separately user-approved design.

## Requirements and constraints

- Keep fdo52208's second paragraph on page one, wrapped into two lines.
- Keep tdf121670's opening text in column one; preserve page two's continuous
  three-column to single-column section transition.
- Preserve unequal widths, explicit zero gaps, inferred counts, and export.
- Respect destination column width when content continues across columns.
- Do not redistribute already measured lines into columns of different widths.
- Python 3.12+, PySide6; no new dependencies or UI strings.
- Preserve the primary worktree's unrelated documentation edit.
- Scope excludes other Epic #406 issues and a general layout-engine redesign.

## Checklist

- [ ] Add failing fixture, geometry, and roundtrip regressions.
- [ ] Implement column preservation and correct balancing boundaries.
- [ ] Verify narrow-column continuation and malformed/missing geometry.
- [ ] Run regression suites and recapture the two fixture canvases.
- [ ] Audit, review, push the PR, verify checks, and merge into main.
