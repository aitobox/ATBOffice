# Spec: Issue #369 — Show prompt text in empty placeholders (edit mode)

## Problem
Empty PowerPoint placeholders render nothing. The reader keeps the placeholder with an
empty paragraph that has no runs, so no style survives, and no view draws a prompt.

## Original behavior (`.vibeoffice/public/lectern/js/render.js:618-646`, `index.html:156-159`)
- In edit mode only, an empty placeholder (`sh.ph` with empty text) draws a prompt body:
  one paragraph built from the first paragraph's props and first run / end run props.
- Prompt text: `L.t(PROMPTS[ph.type] ?? 'Click to add text')`; `dt`/`ftr`/`sldNum` → none.
- The prompt is hidden while the shape is being edited.
- An empty placeholder gets a `1px dashed rgba(90,90,90,.75)` outline in edit mode.
- Thumbnails, slide show and print leave empty placeholders out.

## Decisions (autonomous, >= 90% confidence)
1. **Prompt text priority**: layout placeholder's own text when the layout marks it
   `hasCustomPrompt="1"` (PowerPoint shows layout text only then; plain layouts carry
   "Click to edit Master title style" which PowerPoint never shows on the slide) →
   otherwise `safe_tr(PROMPTS[type])`, unknown types → `safe_tr("Click to add text")`.
2. **Prompt style**: the reader already cascades layout → master → defaultTextStyle into
   runs. For a run-less paragraph it now cascades into a transient `TextBody.prompt_run`
   (not serialized, so round-trip output is unchanged). Render priority: first run of
   the first paragraph (user-typed-then-deleted text keeps its style) → `prompt_run` →
   plain defaults. Color is the inherited color (acceptance #1 expects red); no gray
   override — matches the original, which applies no opacity.
3. **Edit-mode gate**: `SlideScene.show_placeholder_prompts` (default `True`). The print
   path sets it `False`. Items without a scene never draw prompts. Thumbnails and the
   slide show use separate renderers that already skip empty text — unchanged.
4. **Synthesized layout placeholders** (`resolve_unoverridden_placeholders`, new slides):
   stop baking the English prompt in as real text (printed, untranslated). Emit an empty
   styled run instead; the new prompt path draws the translated text in edit mode only.
5. **i18n**: all prompt strings already exist in all 9 locale JSON files; es and ru hold
   English copies — translate them.

## Edge cases
- Placeholder that is a table/chart/image/group: not affected (separate paint paths).
- `dt`/`ftr`/`sldNum` empty: no prompt, still dashed outline (editing aid).
- Editing in progress: prompt hidden, editor shows the caret only.
- Autofit cache: the prompt is rendered with no cache host so it never perturbs the
  real text's autofit cache.
- Undo/redo via `from_dict` drops `prompt_run`; falls back to defaults, no crash.
- Out of scope: parsing `<a:endParaRPr>` into `end_props` (would change writer output).

## Task list
- [x] Task 1: Reader — `hasCustomPrompt` on layout placeholders; cascade style into `TextBody.prompt_run`
- [x] Task 2: Model — transient `TextBody.prompt_run` field (excluded from to_dict/compare)
- [x] Task 3: View — prompt body builder + edit-mode prompt and dashed outline in `ShapeGraphicsItem`
- [x] Task 4: Scene gate — `SlideScene.show_placeholder_prompts`; print path disables it
- [x] Task 5: Resolver — synthesized placeholders no longer bake prompt text
- [x] Task 6: i18n — translate es/ru prompt strings
- [x] Task 7: Tests `tests/test_lectern_placeholders.py` + full suite
