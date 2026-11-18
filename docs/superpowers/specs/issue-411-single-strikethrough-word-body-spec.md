# Issue #411: Draw imported single strikethrough in Word body text

## Problem

`libreoffice__tdf154751_dualStrikethrough.docx` imports its run correctly (`strike` on, `dstrike` off), but the editing canvas shows plain text. `WriterCanvasView._paint_line_portions` never draws strike decorations, while the print and header/footer paths do.

## Design

Add `_draw_strike_decoration` and call it from every text path in `_paint_line_portions`: normal, justified, and RTL.

- Single strike draws one line and double strike draws two. Double wins when both flags are set, matching `.vibeoffice` `render.js`.
- Interior blanks are struck so a phrase has one continuous line. Trailing blanks are not.
- Line thickness follows the font metrics, with the existing 0.75 pt minimum.

## Out of scope

- Body underline painting on the canvas.
- A run-level `w:strike w:val="0"` overriding a strike inherited from a style. `RunProperties.strike` cannot represent that state today.

## Task list

- [x] Add failing paint regression tests
- [x] Draw strike decorations in all body text paths
- [x] Verify the fixture render and Writer test suites
