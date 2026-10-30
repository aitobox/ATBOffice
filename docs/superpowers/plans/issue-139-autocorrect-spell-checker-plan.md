# Implementation Plan: Quire 键入自动更正与拼写检查校对引擎 (Issue #139)

## Proposed Changes

### Task 1: Dictionaries and Settings Setup
- Copy `.vibeoffice/public/common/dict/en_US.words` and `en_GB.words` into `src/atboffice/resources/dict/`.
- Add dictionary discovery logic with built-in fallback wordlist.
- In `src/atboffice/core/settings.py`, register:
  - `"spelling/check_as_you_type": True`
  - `"spelling/check_grammar_as_you_type": True`
  - `"spelling/ignore_uppercase": True`
  - `"spelling/ignore_numbers": True`
  - `"autocorrect/smart_quotes": True`
  - `"autocorrect/replace_text_as_you_type": True`
  - `"autocorrect/dashes": True`
  - `"autocorrect/fractions": True`
  - `"autocorrect/auto_lists": True`

### Task 2: AutoCorrect Engine (`src/atboffice/modules/writer/autocorrect.py`)
- Define `AutoCorrectEngine` class:
  - Default typos map (from Apache OpenOffice / vibeoffice): `teh` -> `the`, `recieve` -> `receive`, `definately` -> `definitely`, etc.
  - Symbol map: `(c)` -> `©`, `(r)` -> `®`, `(tm)` -> `™`, `...` -> `…`, `-->` -> `→`, `<--` -> `←`, `==>` -> `⇒`, `<==` -> `⇐`, `<=>` -> `⇔`, `:)` -> `☺`, `:(` -> `☹`.
  - Fractions: `1/2` -> `½`, `1/4` -> `¼`, `3/4` -> `¾`.
  - Smart quotes: `smart_char(ch, prev_char)` converting `"` to `“`/`”` and `'` to `‘`/`’`.
  - `process_character(text, cursor_pos, ch)` returning replacement range and new text if matched.
  - `process_enter(paragraph_text)` detecting `1. `, `* `, `- ` for automatic bullet / numbered list conversion.

### Task 3: Spell Engine (`src/atboffice/modules/writer/spell.py`)
- Define `SpellEngine` singleton/class:
  - Front-coded dictionary decoder: parses `.words` files into `dict[str, int]` word-frequency map and lowercase lookup index.
  - Word tokenizer: extracts words, handles internal apostrophes and hyphens.
  - `is_valid_word(word)`: checks against dictionary, custom dictionary (`custom_dict`), and session `ignore_all` set.
  - `suggest(word, max_suggestions=8)`: Damerau-Levenshtein distance calculation with keyboard proximity weights and frequency ordering.
  - `add_to_custom_dict(word)`, `ignore_all(word)`.
  - Cache lookup results for sub-millisecond repeated checks.

### Task 4: Canvas & Caret Controller Integration
- In `src/atboffice/modules/writer/views/caret_controller.py`:
  - Wire `AutoCorrectEngine.smart_char` inside `insert_text`.
  - On typing space or punctuation `[.,;:!?)\]}"'”’]`, trigger `after_type` to apply token replacement and reposition caret.
  - In `insert_paragraph_break`: check `after_enter` for auto bullet/numbering list conversion.
- In `src/atboffice/modules/writer/views/canvas_view.py`:
  - In `_paint_page_content`: if `spelling/check_as_you_type` is True, check words in text portions and draw red wavy underline under misspelled words.
  - In `contextMenuEvent`: if right-click hit is on a misspelled word, show suggestions, "全部忽略", and "添加到词典".

### Task 5: F7 Spelling and Grammar Dialog (`src/atboffice/modules/writer/dialogs/spelling_dialog.py`)
- Create `SpellingGrammarDialog(QDialog)`:
  - Scans document paragraphs for misspelled words.
  - Displays context sentence with the misspelled word highlighted.
  - Displays suggestion candidates in a QListWidget.
  - Buttons:
    - 忽略一次 (`btn_ignore_once`)
    - 全部忽略 (`btn_ignore_all`)
    - 添加到词典 (`btn_add_dict`)
    - 更改 (`btn_change`)
    - 全部更改 (`btn_change_all`)
    - 自动更正 (`btn_autocorrect`)
    - 取消 / 关闭 (`btn_close`)
  - Full i18n support and `retranslate_ui`.
- Wire `spelling` action and F7 shortcut in `QuireWindow`.

### Task 6: Unit Tests (`tests/modules/writer/test_autocorrect_spell.py`)
- Tests verifying:
  1. AutoCorrect replacements: `(c)` -> `©`, `--` -> `—`, `1/2` -> `½`, `teh` -> `the`, `Teh` -> `The`.
  2. Smart quotes: opening vs closing quotes.
  3. Spell engine: front-coded word loading, `is_valid_word`, `suggest("teh")` returning `"the"`.
  4. Red wavy line rendering & option toggle (`check_as_you_type`).
  5. Context menu items generation.
  6. Spelling dialog navigation and replacement.

### Task 7: Full Verification
- Run `PYTHONPATH=src pytest tests/modules/writer/test_autocorrect_spell.py -v`.
- Run `PYTHONPATH=src pytest tests/`.
