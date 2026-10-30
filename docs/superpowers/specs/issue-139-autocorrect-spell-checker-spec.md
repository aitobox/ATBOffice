# Specification: Quire 键入自动更正 (AutoCorrect) 与拼写检查校对引擎 (Issue #139)

## 1. Overview & Objectives
Issue #139 要求在 Python/PySide6 移植版本中实现成熟的键入自动替换（AutoCorrect）与离线拼写检查引擎（Spell Check Engine）。
对齐原版 Quire (`.vibeoffice/public/quire/js/autocorrect.js`, `spell.js`, `.vibeoffice/public/common/spell.js`) 的设计规范，提供：
1. 键入自动替换引擎（AutoCorrect Engine）：
   - 直引号自动转换为智能弯引号；
   - 破折号自动替换（`--` 转为 `—`）；
   - 特殊符号替换：`(c)` -> `©`、`(r)` -> `®`、`(tm)` -> `™`、箭头与表情等；
   - 常见分数替换：`1/2` -> `½`、`1/4` -> `¼`、`3/4` -> `¾`；
   - 段首 `1. ` 或 `* ` 自动转换为编号/项目符号列表；
   - 常见笔误自动纠错（如 `teh` -> `the`, `recieve` -> `receive`）及大小写模式自适应；
   - 缩写及例外过滤机制。
2. 离线拼写检查引擎（Spell Engine）：
   - 内置 front-coded 英语标准词库词表解码与加载；
   - 错词判断规则（忽略全大写、带数字词、URL/邮件、自定义词典与全部忽略白名单、所有格 `'s`、复合连字符词）；
   - 候选词推荐算法（Damerau-Levenshtein 键盘临近距离权重与词频打分）；
   - 错词在画布上渲染经典的 Word 2003 红色波浪下划线；
   - 错词右键上下文菜单集成建议候选词、全部忽略、添加到词典；
   - 支持设置项 `spelling/check_as_you_type` 控制波浪线显示/隐藏。
3. F7 拼写和语法检查对话框（Spelling and Grammar Dialog）：
   - 模态对话框，支持逐词扫描与上下文句子高亮定位；
   - 操作按钮：忽略一次、全部忽略、添加到词典、更改、全部更改、自动更正、关闭；
   - 快捷键 F7 绑定与全量 i18n 国际化支持。

---

## 2. Architecture & Module Design

### 2.1 File Organization
```
src/atboffice/
├── core/
│   └── settings.py                               # 扩充拼写与自动替换默认配置项
├── resources/
│   └── dict/
│       ├── en_US.words                           # 离线前缀编码英语词库 (639KB)
│       └── en_GB.words                           # 离线前缀编码英式英语词库 (637KB)
└── modules/
    └── writer/
        ├── autocorrect.py                        # AutoCorrect 引擎核心
        ├── spell.py                              # SpellEngine 离线词库、判错与推荐
        ├── dialogs/
        │   └── spelling_dialog.py                # F7 拼写与语法检查对话框
        └── views/
            ├── canvas_view.py                    # 画布波浪红线渲染、右键菜单错词建议、F7 触发
            └── caret_controller.py               # 键入与回车事件分发至 AutoCorrect
```

### 2.2 AutoCorrect 规则契约
- **智能直引号/弯引号** (`smart_char`):
  - 遇到 `"` 或 `'`，若前一个字符为空白、标点或行首，转为左弯引号 `“` / `‘`；否则转为右弯引号 `”` / `’`。
- **符号与笔误替换** (`after_type`):
  - 触发时机：用户键入分隔符（空格、标点符号 `.,;:!?)\]}"'”’`）。
  - 对光标前未完成的 token 检查：
    1. 特殊符号：`(c)` -> `©`, `(r)` -> `®`, `(tm)` -> `™`, `...` -> `…`, `-->` -> `→`, `<--` -> `←`, `==>` -> `⇒`, `<==` -> `⇐`, `<=>` -> `⇔`, `:)` -> `☺`, `:(` -> `☹`。
    2. 分数：`1/2` -> `½`, `1/4` -> `¼`, `3/4` -> `¾`。
    3. 破折号：`word--` -> `word—` (em-dash)。
    4. 词典笔误：如 `teh` -> `the`, `recieve` -> `receive`。
       大小写自适应：首字母大写输入保留首字母大写（`Teh` -> `The`），全大写输入保留全大写（`TEH` -> `THE`）。
- **段落回车自动格式化** (`after_enter`):
  - 段首为 `1. ` 或 `1) ` 时回车，自动为当前段及后继段设置编号列表；
  - 段首为 `* ` 或 `- ` 时回车，自动为当前段及后继段设置项目符号列表；
  - 并自动剔除段首触发标记。

### 2.3 拼写检查引擎契约
- **词表结构**:
  - `load_words_file(path)`: 解析 front-coded 压缩文件，生成 `dict[str, int]` 映射（词 -> 词频等级 0..9）及小写快速反查索引。
  - 内置精简核心 fallback 词典（以防资源文件加载异常）。
- **错词判定**:
  - `is_valid_word(w)` -> bool
    - 长度 < 2 返回 True；
    - 包含数字且 `ignore_numbers=True` 返回 True；
    - 全大写且 `ignore_uppercase=True` 返回 True；
    - 在自定义词典或 session `ignored_all` 集合中返回 True；
    - 词表中存在或小写存在返回 True；
    - 处理所有格（如 `John's` -> 检验 `John`）；
    - 连字符词（如 `well-known` -> 每段分别检验）。
- **建议生成**:
  - `suggest(word, max_suggestions=8)` -> list[str]
    - 生成 Damerau-Levenshtein 1/2 编辑距离候选词；
    - 根据键盘按键临近距离、Norvig 错词模型及词频加权排序；
    - 保持输入单词的大小写格式。

### 2.4 画布与交互集成
- **波浪线渲染**:
  - 在 `WriterCanvasView._paint_page_content` 中，若 `check_as_you_type` 开启，对文本 Portion 中的单词进行校验，发现错词时使用红色 QPen (`QColor(255, 0, 0)`) 在 baseline 下方绘制正弦波/锯齿波折线。
- **右键上下文菜单**:
  - 在 `contextMenuEvent` 中，根据鼠标位置命中错词，在菜单最前加入粗体候选建议项（点击直接替换错词）、`全部忽略`、`添加到词典`。
- **F7 快捷键与菜单命令**:
  - 在 `QuireWindow` 中将 `spelling` 动作与 F7 关联，唤起 `SpellingGrammarDialog`。

---

## 3. Acceptance Criteria Verification
1. 键入 `(c)` 并按空格，文字立即自动变为 `©`。
2. 键入 `teh` 等错词时，文字下方渲染红色波浪线；右键菜单中出现 `the` 纠错建议。
3. 按 F7 能唤起拼写检查对话框并依次定位至错词。
4. 在设置中关闭「键入时检查拼写」能隐藏所有波浪线提示。
5. `pytest tests/modules/writer/test_autocorrect_spell.py` 100% 通过。
