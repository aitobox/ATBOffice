# Plan: Issue #369 — placeholder prompt text

Spec: `docs/superpowers/specs/issue-369-lectern-placeholder-prompt-text-spec.md`

## Chunk 1 — Tests first
- Create `tests/test_lectern_placeholders.py`:
  - tdf103876: slide 1 ctrTitle is empty; prompt body text == "Click to add title" and
    its run color resolves to red.
  - tdf143129: subTitle prompt == "Click to add subtitle" and paragraph keeps `bu` char.
  - master-slides: idx 14 prompt == layout custom text "00 MONTH 2022".
  - Scene with `show_placeholder_prompts=False` renders no prompt (spy on builder / pixel).
  - Synthesized placeholders carry no prompt text in the model.
  - Every prompt string has a non-English value in each non-en locale.
- Run → expect failures.

## Chunk 2 — Model + reader
- `models/text.py`: `prompt_run: TextRun | None = field(default=None, repr=False, compare=False)`.
- `io/pptx_reader.py`: `PlaceholderTemplate.custom_prompt`; parse `hasCustomPrompt`;
  in `_apply_placeholder_text_inheritance`, when the body is empty, cascade into a
  synthetic run and assign `text_body.prompt_run` (text = layout text if custom prompt).

## Chunk 3 — View + scene + resolver
- `views/shape_item.py`: `build_prompt_body(text_body, ph_type)` and paint step
  "3b. Empty placeholder prompt + dashed outline" gated by scene flag and editing state.
- `views/slide_canvas.py`: `show_placeholder_prompts` attribute.
- `ui/shell/lectern_window.py`: print scenes set it False.
- `models/placeholder_resolver.py`: empty styled run instead of baked prompt text.

## Chunk 4 — i18n + verification
- Translate es/ru entries.
- `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_lectern_placeholders.py -v`
- Full suite; compare failures with baseline on main.
