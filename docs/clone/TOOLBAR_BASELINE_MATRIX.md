# ATBOffice Phase 5: 三模块工具栏逐控件对照与基线矩阵

本矩阵由 `scripts/audit_toolbars_parity.py` 自动化脚本静态提取与动态反射生成，
完整比对 `.vibeoffice` 原版 Office 2003 Luna JS 工具栏与 `src/atboffice/ui/shell/*_toolbars.py` 目标实现。

## 1. 概览汇总

| 模块 | 工具栏总数 | 控件项总数 | 正常接线 (WIRED) | 存根占位 (STUB) | 仅UI待接 (UI_ONLY) | 缺失 (MISSING) | 对照完成率 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Quire** | 10 | 150 | 150 | 0 | 0 | 0 | **100.0%** |
| **Ledger** | 8 | 65 | 65 | 0 | 0 | 0 | **100.0%** |
| **Lectern** | 10 | 117 | 117 | 0 | 0 | 0 | **100.0%** |

## 2. Quire 逐工具栏详细对照表

### Quire — Toolbar: `drawing` (22 项，19/19 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `drawMenu (drop)` | `绘图` | DropDownButton | 绘图 | 绘图 | — | — | `WIRED` |
| 2 | `selectObjects` | `selectObjects` | Action | 选择对象(S) | 选择画布上的图形对象 | ✓ | — | `WIRED` |
| 3 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 4 | `autoShapes (drop)` | `自选图形` | DropDownButton | 自选图形 | 自选图形 | — | — | `WIRED` |
| 5 | `drawLine` | `drawLine` | Action | 线条(L) | 绘制直线 | — | — | `WIRED` |
| 6 | `drawArrow` | `drawArrow` | Action | 箭头(A) | 绘制箭头 | — | — | `WIRED` |
| 7 | `drawRect` | `drawRect` | Action | 矩形(R) | 绘制矩形 | — | — | `WIRED` |
| 8 | `drawOval` | `drawOval` | Action | 椭圆(O) | 绘制椭圆 | — | — | `WIRED` |
| 9 | `textBox` | `textBox` | Action | 文本框(T) | 绘制文本框 | — | — | `WIRED` |
| 10 | `insertWordArt` | `insertWordArt` | Action | 插入艺术字(W)... | 插入艺术字 | ✓ | — | `WIRED` |
| 11 | `insertDiagram` | `insertDiagram` | Action | 插入图示(D)... | 插入组织结构图或循环图 | ✓ | — | `WIRED` |
| 12 | `insertClipArt` | `insertClipArt` | Action | 剪贴画(C)... | 插入剪贴画 | ✓ | — | `WIRED` |
| 13 | `insertPicture` | `insertPicture` | Action | 插入图片(P)... | 插入来自文件的图片 | ✓ | — | `WIRED` |
| 14 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 15 | `fillColor (split)` | `填充颜色` | ColorPicker | 填充颜色 | 填充颜色 | ✓ | — | `WIRED` |
| 16 | `lineColor (split)` | `线条颜色` | ColorPicker | 线条颜色 | 线条颜色 | ✓ | — | `WIRED` |
| 17 | `fontColorBtn (split)` | `字体颜色` | ColorPicker | 字体颜色 | 字体颜色 | ✓ | — | `WIRED` |
| 18 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 19 | `lineStyle (drop)` | `线型` | DropDownButton | 线型 | 线型 | ✓ | — | `WIRED` |
| 20 | `dashStyle (drop)` | `虚线线型` | DropDownButton | 虚线线型 | 虚线线型 | ✓ | — | `WIRED` |
| 21 | `arrowStyle (drop)` | `箭头样式` | DropDownButton | 箭头样式 | 箭头样式 | ✓ | — | `WIRED` |
| 22 | `shadowStyle (drop)` | `阴影样式` | DropDownButton | 阴影样式 | 阴影样式 | ✓ | — | `WIRED` |

### Quire — Toolbar: `formatting` (23 项，19/19 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `stylesPane` | `format_styles` | Action | 样式和格式… | 打开样式面板应用正文或标题层级样式 | ✓ | — | `WIRED` |
| 2 | `style (combo)` | `Quire_StyleCombo` | ComboBox | 样式 | 样式 | — | — | `WIRED` |
| 3 | `font (combo)` | `Quire_FontCombo` | ComboBox | 字体 | 字体 | — | — | `WIRED` |
| 4 | `size (combo)` | `Quire_SizeCombo` | ComboBox | 字号 | 字号 | — | — | `WIRED` |
| 5 | `bold` | `bold` | Action | 加粗(B) | 加粗 (Ctrl+B) | ✓ | Ctrl+B | `WIRED` |
| 6 | `italic` | `italic` | Action | 倾斜(I) | 倾斜 (Ctrl+I) | ✓ | Ctrl+I | `WIRED` |
| 7 | `underline` | `underline` | Action | 下划线(U) | 下划线 (Ctrl+U) | ✓ | Ctrl+U | `WIRED` |
| 8 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 9 | `alignLeft` | `alignLeft` | Action | 左对齐(L) | 左对齐 (Ctrl+L) | ✓ | Ctrl+L | `WIRED` |
| 10 | `alignCenter` | `alignCenter` | Action | 居中(E) | 居中 (Ctrl+E) | ✓ | Ctrl+E | `WIRED` |
| 11 | `alignRight` | `alignRight` | Action | 右对齐(R) | 右对齐 (Ctrl+R) | ✓ | Ctrl+R | `WIRED` |
| 12 | `justify` | `justify` | Action | 两端对齐(J) | 两端对齐 (Ctrl+J) | ✓ | Ctrl+J | `WIRED` |
| 13 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 14 | `lineSpacing (drop)` | `行距` | DropDownButton | 行距 | 行距 | ✓ | — | `WIRED` |
| 15 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 16 | `numbering` | `format_numbering` | Action | 项目编号 | 开启或关闭段落顺序编号列表 | ✓ | — | `WIRED` |
| 17 | `bullets` | `format_bullets` | Action | 项目符号 | 开启或关闭段落项目符号列表 | ✓ | — | `WIRED` |
| 18 | `decIndent` | `decIndent` | Action | 减少缩进量(D) | 减少缩进量 | ✓ | — | `WIRED` |
| 19 | `incIndent` | `incIndent` | Action | 增加缩进量(I) | 增加缩进量 | ✓ | — | `WIRED` |
| 20 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 21 | `borderBtn (split)` | `borderBtn` | SplitButton | 边框(B) | 外部边框与网格 | ✓ | — | `WIRED` |
| 22 | `highlightBtn (split)` | `突出显示` | ColorPicker | 突出显示 | 突出显示 | ✓ | — | `WIRED` |
| 23 | `fontColorBtn (split)` | `字体颜色` | ColorPicker | 字体颜色 | 字体颜色 | ✓ | — | `WIRED` |

### Quire — Toolbar: `headerFooter` (17 项，13/13 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `hfAutoText (drop)` | `插入自动图文集` | DropDownButton | 插入自动图文集 | 插入自动图文集 | — | — | `WIRED` |
| 2 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 3 | `hfPageNum` | `hfPageNum` | Action | 插入页码(P) | 插入页码字段 | ✓ | — | `WIRED` |
| 4 | `hfNumPages` | `hfNumPages` | Action | 插入页数(N) | 插入总页数字段 | ✓ | — | `WIRED` |
| 5 | `hfFormatPageNum` | `hfFormatPageNum` | Action | 设置页码格式(F)... | 设置页码格式 | ✓ | — | `WIRED` |
| 6 | `hfDate` | `hfDate` | Action | 插入日期(D) | 插入当前日期字段 | ✓ | — | `WIRED` |
| 7 | `hfTime` | `hfTime` | Action | 插入时间(T) | 插入当前时间字段 | ✓ | — | `WIRED` |
| 8 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 9 | `pageSetup` | `pageSetup` | Action | 页面设置(U)... | 页面设置 | ✓ | — | `WIRED` |
| 10 | `hfShowText` | `hfShowText` | Action | 显示/隐藏文档文字(W) | 显示或隐藏正文文字 | ✓ | — | `WIRED` |
| 11 | `hfLinkPrev` | `hfLinkPrev` | Action | 链接到前一个(L) | 链接到前一节页眉页脚 | ✓ | — | `WIRED` |
| 12 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 13 | `hfSwitch` | `hfSwitch` | Action | 在页眉和页脚间切换(S) | 在页眉与页脚区域之间切换 | ✓ | — | `WIRED` |
| 14 | `hfPrev` | `hfPrev` | Action | 显示前一项(B) | 跳转到上一节页眉页脚 | ✓ | — | `WIRED` |
| 15 | `hfNext` | `hfNext` | Action | 显示下一项(X) | 跳转到下一节页眉页脚 | ✓ | — | `WIRED` |
| 16 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 17 | `hfClose` | `hfClose` | Action | 关闭(C) | 关闭页眉和页脚 | ✓ | — | `WIRED` |

### Quire — Toolbar: `mailMerge` (17 项，14/14 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `mmMainDoc` | `mmMainDoc` | Action | 主文档设置(M)... | 设置邮件合并主文档类型 | ✓ | — | `WIRED` |
| 2 | `mmOpenSource` | `mmOpenSource` | Action | 打开数据源(D)... | 连接外部数据源 | ✓ | — | `WIRED` |
| 3 | `mmRecipients` | `mmRecipients` | Action | 收件人列表(R)... | 编辑收件人列表 | ✓ | — | `WIRED` |
| 4 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 5 | `mmAddress` | `mmAddress` | Action | 地址块(A)... | 插入规范地址块域 | ✓ | — | `WIRED` |
| 6 | `mmGreeting` | `mmGreeting` | Action | 问候语(G)... | 插入问候语域 | ✓ | — | `WIRED` |
| 7 | `mmInsertField` | `mmInsertField` | Action | 插入合并域(F)... | 插入特定字段 | ✓ | — | `WIRED` |
| 8 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 9 | `mmViewData` | `mmViewData` | Action | 查看合并数据(V) | 切换查看合并数据与域代码 | ✓ | — | `WIRED` |
| 10 | `mmFirst` | `mmFirst` | Action | 首记录(1) | 跳转到第一条记录 | ✓ | — | `WIRED` |
| 11 | `mmPrev` | `mmPrev` | Action | 上一记录(P) | 跳转到上一条记录 | ✓ | — | `WIRED` |
| 12 | `mmRecord (combo)` | `Quire_MMRecordCombo` | ComboBox | 记录编号 | 记录编号 | — | — | `WIRED` |
| 13 | `mmNext` | `mmNext` | Action | 下一记录(N) | 跳转到下一条记录 | ✓ | — | `WIRED` |
| 14 | `mmLast` | `mmLast` | Action | 尾记录(L) | 跳转到最后一条记录 | ✓ | — | `WIRED` |
| 15 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 16 | `mmMergeNew` | `mmMergeNew` | Action | 合并到新文档(N)... | 生成合并结果新文档 | ✓ | — | `WIRED` |
| 17 | `mmMergePrint` | `mmMergePrint` | Action | 合并到打印机(P)... | 批量输出到打印机 | ✓ | — | `WIRED` |

### Quire — Toolbar: `outlining` (16 项，14/14 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `promoteH1` | `promoteH1` | Action | 提升到 1 级(1) | 直接提升为标题 1 | ✓ | — | `WIRED` |
| 2 | `promote` | `promote` | Action | 提升(P) | 提升大纲级别 (Alt+Shift+Left) | ✓ | — | `WIRED` |
| 3 | `outlineLevel (combo)` | `Quire_OutlineLevelCombo` | ComboBox | 大纲级别 | 大纲级别 | — | — | `WIRED` |
| 4 | `demote` | `demote` | Action | 降低(D) | 降低大纲级别 (Alt+Shift+Right) | ✓ | — | `WIRED` |
| 5 | `demoteBody` | `demoteBody` | Action | 降为正文(B) | 将标题降为正文文本 (Ctrl+Shift+N) | ✓ | — | `WIRED` |
| 6 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 7 | `moveUp` | `moveUp` | Action | 上移(U) | 上移选定段落 (Alt+Shift+Up) | ✓ | — | `WIRED` |
| 8 | `moveDown` | `moveDown` | Action | 下移(O) | 下移选定段落 (Alt+Shift+Down) | ✓ | — | `WIRED` |
| 9 | `expand` | `expand` | Action | 展开(E) | 展开下级内容 | ✓ | — | `WIRED` |
| 10 | `collapse` | `collapse` | Action | 折叠(C) | 折叠下级内容 | ✓ | — | `WIRED` |
| 11 | `showLevel (combo)` | `Quire_ShowLevelCombo` | ComboBox | 显示级别 | 显示级别 | — | — | `WIRED` |
| 12 | `olFirstLine` | `olFirstLine` | Action | 仅显示首行(F) | 仅显示段落首行 | ✓ | — | `WIRED` |
| 13 | `olFormatting` | `olFormatting` | Action | 显示格式(S) | 显示文本实际格式 | ✓ | — | `WIRED` |
| 14 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 15 | `updateTOC` | `updateTOC` | Action | 更新目录(T) | 更新文档目录 | ✓ | — | `WIRED` |
| 16 | `gotoTOC` | `gotoTOC` | Action | 转到目录(G) | 跳转到目录位置 | ✓ | — | `WIRED` |

### Quire — Toolbar: `picture` (14 项，12/12 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `insertPicture` | `pic_insert` | Action | 插入图片(I)... | 从文件插入图片 | ✓ | — | `WIRED` |
| 2 | `colorPic (drop)` | `颜色` | DropDownButton | 颜色 | 颜色 | ✓ | — | `WIRED` |
| 3 | `picMoreContrast` | `picMoreContrast` | Action | 增加对比度(M) | 增加图片对比度 | ✓ | — | `WIRED` |
| 4 | `picLessContrast` | `picLessContrast` | Action | 降低对比度(L) | 降低图片对比度 | ✓ | — | `WIRED` |
| 5 | `picMoreBright` | `picMoreBright` | Action | 增加亮度(B) | 增加图片亮度 | ✓ | — | `WIRED` |
| 6 | `picLessBright` | `picLessBright` | Action | 降低亮度(D) | 降低图片亮度 | ✓ | — | `WIRED` |
| 7 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 8 | `picCrop` | `picCrop` | Action | 裁剪(R) | 激活裁剪控制柄 | ✓ | — | `WIRED` |
| 9 | `picRotate` | `picRotate` | Action | 向左旋转 90°(T) | 向左旋转 90 度 | ✓ | — | `WIRED` |
| 10 | `lineStyle (drop)` | `线条样式` | DropDownButton | 线条样式 | 线条样式 | ✓ | — | `WIRED` |
| 11 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 12 | `textWrap (drop)` | `文字环绕` | DropDownButton | 文字环绕 | 文字环绕 | ✓ | — | `WIRED` |
| 13 | `formatObject` | `formatObject` | Action | 设置对象格式(O)... | 设置对象格式对话框 | ✓ | — | `WIRED` |
| 14 | `picReset` | `picReset` | Action | 重设图片(P) | 恢复原始尺寸与颜色设置 | ✓ | — | `WIRED` |

### Quire — Toolbar: `reviewing` (12 项，9/9 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `markupDisplay (drop)` | `显示以供审阅` | DropDownButton | 显示以供审阅 | 显示以供审阅 | — | — | `WIRED` |
| 2 | `show (drop)` | `显示` | DropDownButton | 显示 | 显示 | — | — | `WIRED` |
| 3 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 4 | `prevChange` | `prevChange` | Action | 前一处修订或批注(P) | 定位到前一处修订或批注 | ✓ | — | `WIRED` |
| 5 | `nextChange` | `nextChange` | Action | 后一处修订或批注(N) | 定位到后一处修订或批注 | ✓ | — | `WIRED` |
| 6 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 7 | `acceptChange (split)` | `acceptChange` | SplitButton | 接受所选修订(A) | 接受所选修订 | ✓ | — | `WIRED` |
| 8 | `rejectChange (split)` | `rejectChange` | SplitButton | 拒绝所选修订(R) | 拒绝所选修订或删除批注 | ✓ | — | `WIRED` |
| 9 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 10 | `insertComment` | `insertComment` | Action | 插入批注(C) | 插入新批注 | — | — | `WIRED` |
| 11 | `trackChanges` | `trackChanges` | Action | 修订(T) | 开启或关闭修订记录 (Ctrl+Shift+E) | ✓ | Ctrl+Shift+E | `WIRED` |
| 12 | `reviewingPane` | `reviewingPane` | Action | 审阅窗格(V) | 显示或隐藏审阅窗格 | ✓ | — | `WIRED` |

### Quire — Toolbar: `standard` (29 项，26/26 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `new` | `file_new` | Action | 新建文档 | 创建空白文档 | ✓ | Ctrl+N | `WIRED` |
| 2 | `open` | `file_open` | Action | 打开… | 打开现有文档或文件 | ✓ | Ctrl+O | `WIRED` |
| 3 | `save` | `file_save` | Action | 保存当前文档 | 保存当前文本文档 | ✓ | Ctrl+S | `WIRED` |
| 4 | `permission` | `permission` | Action | 权限(M) | 权限设置 (只读/编辑) | ✓ | — | `WIRED` |
| 5 | `sendMail` | `sendMail` | Action | 发送(E) | 通过电子邮件发送 | ✓ | — | `WIRED` |
| 6 | `print` | `file_print` | Action | 打印… | 调用打印机配置打印文档 | ✓ | Ctrl+P | `WIRED` |
| 7 | `printPreview` | `file_print_preview` | Action | 打印预览 | 打开全功能交互式打印预览视口 | ✓ | — | `WIRED` |
| 8 | `spelling` | `tools_spelling` | Action | 拼写和语法检查… | 运行词典校对并审查拼写错误 (F7) | ✓ | F7 | `WIRED` |
| 9 | `research` | `research` | Action | 信息检索(R)... | 信息检索与翻译 (Alt+Click) | ✓ | — | `WIRED` |
| 10 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 11 | `cut` | `edit_cut` | Action | 剪切 | 剪切选中内容 | ✓ | Ctrl+X | `WIRED` |
| 12 | `copy` | `edit_copy` | Action | 复制 | 复制选中内容 | ✓ | Ctrl+C | `WIRED` |
| 13 | `paste` | `edit_paste` | Action | 粘贴 | 粘贴剪贴板内容 | ✓ | Ctrl+V | `WIRED` |
| 14 | `painter` | `painter` | Action | 格式刷(P) | 格式刷 (双击可连续应用) | ✓ | — | `WIRED` |
| 15 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 16 | `undo (split)` | `edit_undo` | SplitButton | 撤销 | 撤销上一步操作 | ✓ | Ctrl+Z | `WIRED` |
| 17 | `redo (split)` | `edit_redo` | SplitButton | 重做 | 恢复撤销的操作 | ✓ | Ctrl+Y | `WIRED` |
| 18 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 19 | `hyperlink` | `insert_hyperlink` | Action | 超链接… | 插入或编辑网页、书签跳转超链接 | ✓ | Ctrl+K | `WIRED` |
| 20 | `tb_tables` | `tb_tables` | Action | 表格和边框(B) | 显示或隐藏表格和边框工具栏 | ✓ | — | `WIRED` |
| 21 | `table (drop)` | `插入表格` | DropDownButton | 插入表格 | 插入表格 | ✓ | — | `WIRED` |
| 22 | `insertExcel` | `insertExcel` | Action | 插入 Excel 工作表(E) | 插入 Microsoft Excel 工作表 | ✓ | — | `WIRED` |
| 23 | `columns (drop)` | `分栏` | DropDownButton | 分栏 | 分栏 | ✓ | — | `WIRED` |
| 24 | `tb_drawing` | `tb_drawing` | Action | 绘图(D) | 显示或隐藏绘图工具栏 | ✓ | — | `WIRED` |
| 25 | `docMap` | `docMap` | Action | 文档结构图(D) | 显示或隐藏文档结构图 | ✓ | — | `WIRED` |
| 26 | `showMarks` | `showMarks` | Action | 显示/隐藏编辑标记(S) | 显示或隐藏段落标记与格式 | ✓ | — | `WIRED` |
| 27 | `zoom (combo)` | `Quire_ZoomCombo` | ComboBox | 显示比例 | 显示比例 | — | — | `WIRED` |
| 28 | `help` | `help_contents` | Action | ATBOffice 帮助 | 打开用户帮助文档 | ✓ | F1 | `WIRED` |
| 29 | `viewReading` | `viewReading` | Action | 阅读版式(R) | 进入阅读版式视图 | ✓ | — | `WIRED` |

### Quire — Toolbar: `tables` (23 项，18/18 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `drawTable` | `table_draw` | Action | 绘制表格 | 使用画笔自由绘制表格线网格 | ✓ | — | `WIRED` |
| 2 | `eraser` | `eraser` | Action | 擦除(E) | 擦除表格线 | ✓ | — | `WIRED` |
| 3 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 4 | `dashStyle (drop)` | `线型` | DropDownButton | 线型 | 线型 | ✓ | — | `WIRED` |
| 5 | `lineStyle (drop)` | `粗细` | DropDownButton | 粗细 | 粗细 | ✓ | — | `WIRED` |
| 6 | `lineColor (drop)` | `边框颜色` | DropDownButton | 边框颜色 | 边框颜色 | ✓ | — | `WIRED` |
| 7 | `borderBtn (split)` | `tableBorderBtn` | SplitButton | 边框(B) | 应用边框 | ✓ | — | `WIRED` |
| 8 | `fillColor (drop)` | `底纹颜色` | DropDownButton | 底纹颜色 | 底纹颜色 | ✓ | — | `WIRED` |
| 9 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 10 | `table (drop)` | `插入` | DropDownButton | 插入 | 插入 | ✓ | — | `WIRED` |
| 11 | `mergeCells` | `table_merge` | Action | 合并单元格 | 将选中的多个连续单元格合并为单个单元格 | ✓ | — | `WIRED` |
| 12 | `splitCells` | `table_split` | Action | 拆分单元格… | 将单元格按行列数重新拆分为多个小单元格 | ✓ | — | `WIRED` |
| 13 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 14 | `alignTop (drop)` | `对齐` | DropDownButton | 对齐 | 对齐 | ✓ | — | `WIRED` |
| 15 | `distRows` | `distRows` | Action | 平均分布各行(R) | 平均分布各行高度 | ✓ | — | `WIRED` |
| 16 | `distCols` | `distCols` | Action | 平均分布各列(C) | 平均分布各列宽度 | ✓ | — | `WIRED` |
| 17 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 18 | `tableAutoFormat` | `tableAutoFormat` | Action | 表格自动套用格式(F)... | 表格自动套用格式 | ✓ | — | `WIRED` |
| 19 | `textDirection` | `textDirection` | Action | 更改文字方向(D) | 更改单元格文字方向 | ✓ | — | `WIRED` |
| 20 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 21 | `sortAsc` | `data_sort_asc` | Action | 升序排序 | 按选中列的值进行递增从小到大排序 | ✓ | — | `WIRED` |
| 22 | `sortDesc` | `data_sort_desc` | Action | 降序排序 | 按选中列的值进行递减从大到小排序 | ✓ | — | `WIRED` |
| 23 | `autoSum` | `autoSum` | Action | 自动求和(S) | 计算单元格总和 | ✓ | — | `WIRED` |

### Quire — Toolbar: `wordart` (6 项，6/6 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `insertWordArt` | `wa_insert` | Action | 插入艺术字(W)... | 插入新艺术字对象 | ✓ | — | `WIRED` |
| 2 | `wordartEdit` | `wordartEdit` | Action | 编辑文字(E)... | 编辑艺术字文字与字体 | ✓ | — | `WIRED` |
| 3 | `wordartGallery` | `wordartGallery` | Action | 艺术字库(G)... | 选择艺术字预设样式库 | ✓ | — | `WIRED` |
| 4 | `formatObject` | `wa_format` | Action | 设置对象格式(O)... | 设置艺术字轮廓与填充 | ✓ | — | `WIRED` |
| 5 | `waShape (drop)` | `艺术字形状` | DropDownButton | 艺术字形状 | 艺术字形状 | ✓ | — | `WIRED` |
| 6 | `textWrap (drop)` | `文字环绕` | DropDownButton | 文字环绕 | 文字环绕 | ✓ | — | `WIRED` |

## 2. Ledger 逐工具栏详细对照表

### Ledger — Toolbar: `auditing` (13 项，10/10 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `traceError` | `traceError` | Action | 错误检查(E) | 定位并检查公式错误 | ✓ | — | `WIRED` |
| 2 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 3 | `tracePrecedents` | `tracePrecedents` | Action | 追踪引用单元格(P) | 追踪向当前单元格提供数值的引用单元格 | ✓ | — | `WIRED` |
| 4 | `traceDependents` | `traceDependents` | Action | 追踪从属单元格(D) | 追踪引用当前单元格数值的从属单元格 | ✓ | — | `WIRED` |
| 5 | `removeArrows` | `removeArrows` | Action | 移去所有箭头(A) | 移去工作表中的所有追踪箭头 | ✓ | — | `WIRED` |
| 6 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 7 | `insertComment` | `insertComment` | Action | 新建批注(C) | 新建或编辑单元格批注 | — | — | `WIRED` |
| 8 | `validation` | `validation` | SplitButton | 数据有效性(V)... | 设置单元格数据输入有效性规则 | ✓ | — | `WIRED` |
| 9 | `circleInvalid` | `circleInvalid` | Action | 圈释无效数据(I) | 圈释不满足有效性规则的无效数据 | ✓ | — | `WIRED` |
| 10 | `clearCircles` | `clearCircles` | Action | 清除无效数据圈(L) | 清除无效数据标识圈 | ✓ | — | `WIRED` |
| 11 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 12 | `watchWindow` | `watchWindow` | Action | 监视窗口(W) | 打开公式数值监视窗口 | ✓ | — | `WIRED` |
| 13 | `evaluateFormula` | `evaluateFormula` | Action | 公式求值(F) | 分步计算求解复杂嵌套公式 | ✓ | — | `WIRED` |

### Ledger — Toolbar: `borders` (3 项，3/3 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `bordersApply (split)` | `bordersPalette` | SplitButton | 边框(B) | 应用单元格边框预设 | — | — | `WIRED` |
| 2 | `borderNone` | `borderNone` | Action | 无框线(N) | 清除所有选定单元格边框 | ✓ | — | `WIRED` |
| 3 | `borderOutline` | `borderOutline` | Action | 外侧框线(O) | 绘制外侧边框 | ✓ | — | `WIRED` |

### Ledger — Toolbar: `chart` (2 项，2/2 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `chartType (drop)` | `图表类型(&T)` | DropDownButton | 图表类型(&T) | 图表类型(&T) | ✓ | — | `WIRED` |
| 2 | `formatObject` | `formatObject` | Action | 设置图表格式(O)... | 打开所选图表对象的格式设置对话框 | ✓ | — | `WIRED` |

### Ledger — Toolbar: `drawing` (7 项，5/5 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `drawMenu (drop)` | `绘图` | DropDownButton | 绘图 | 绘图 | — | — | `WIRED` |
| 2 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 3 | `insertShape` | `insertShape` | Action | 自选图形(S) | 插入矩形、椭圆等自选图形 | ✓ | — | `WIRED` |
| 4 | `insertTextBox` | `insertTextBox` | Action | 文本框(T) | 插入横排文本框 | ✓ | — | `WIRED` |
| 5 | `insertPicture` | `insertPicture` | Action | 来自文件的图片(P)... | 从磁盘文件插入图片 | ✓ | — | `WIRED` |
| 6 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 7 | `fillColorApply` | `填充颜色` | ColorPicker | 填充颜色 | 填充颜色 | ✓ | — | `WIRED` |

### Ledger — Toolbar: `formatting` (24 项，19/19 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `font (combo)` | `Ledger_FontCombo` | ComboBox | 字体 | 字体 | — | — | `WIRED` |
| 2 | `size (combo)` | `Ledger_SizeCombo` | ComboBox | 字号 | 字号 | — | — | `WIRED` |
| 3 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 4 | `bold` | `bold` | Action | 加粗(B) | 加粗 (Ctrl+B) | ✓ | Ctrl+B | `WIRED` |
| 5 | `italic` | `italic` | Action | 倾斜(I) | 倾斜 (Ctrl+I) | ✓ | Ctrl+I | `WIRED` |
| 6 | `underline` | `underline` | Action | 下划线(U) | 下划线 (Ctrl+U) | ✓ | Ctrl+U | `WIRED` |
| 7 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 8 | `alignLeft` | `alignLeft` | Action | 左对齐(L) | 左对齐 (Ctrl+L) | ✓ | Ctrl+L | `WIRED` |
| 9 | `alignCenter` | `alignCenter` | Action | 居中(E) | 居中 (Ctrl+E) | ✓ | Ctrl+E | `WIRED` |
| 10 | `alignRight` | `alignRight` | Action | 右对齐(R) | 右对齐 (Ctrl+R) | ✓ | Ctrl+R | `WIRED` |
| 11 | `mergeCenter` | `mergeCenter` | Action | 合并及居中(M) | 合并选定单元格并居中文本 | ✓ | — | `WIRED` |
| 12 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 13 | `currencyStyle` | `currencyStyle` | Action | 货币样式(C) | 应用货币样式 ($ 1,234.00) | ✓ | — | `WIRED` |
| 14 | `percentStyle` | `percentStyle` | Action | 百分比样式(P) | 应用百分比样式 (12%) | ✓ | — | `WIRED` |
| 15 | `commaStyle` | `commaStyle` | Action | 千位分隔样式(K) | 应用千位分隔样式 (1,234.00) | ✓ | — | `WIRED` |
| 16 | `incDecimal` | `incDecimal` | Action | 增加小数位数(I) | 增加一位小数显示精度 | ✓ | — | `WIRED` |
| 17 | `decDecimal` | `decDecimal` | Action | 减少小数位数(D) | 减少一位小数显示精度 | ✓ | — | `WIRED` |
| 18 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 19 | `decIndent` | `decIndent` | Action | 减少缩进量(D) | 减少单元格左侧文本缩进量 | ✓ | — | `WIRED` |
| 20 | `incIndent` | `incIndent` | Action | 增加缩进量(I) | 增加单元格左侧文本缩进量 | ✓ | — | `WIRED` |
| 21 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 22 | `bordersApply (split)` | `bordersApply` | SplitButton | 边框(B) | 应用单元格边框预设 | ✓ | — | `WIRED` |
| 23 | `fillColorApply (split)` | `填充颜色` | ColorPicker | 填充颜色 | 填充颜色 | ✓ | — | `WIRED` |
| 24 | `fontColorApply (split)` | `字体颜色` | ColorPicker | 字体颜色 | 字体颜色 | ✓ | — | `WIRED` |

### Ledger — Toolbar: `list` (2 项，2/2 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `listMenu (drop)` | `列表(&L)` | DropDownButton | 列表(&L) | 列表(&L) | ✓ | — | `WIRED` |
| 2 | `totalRow` | `totalRow` | Action | 汇总行(T) | 在列表底部显示或隐藏自动汇总计算行 | ✓ | — | `WIRED` |

### Ledger — Toolbar: `reviewing` (5 项，4/4 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `insertComment` | `rev_insertComment` | Action | 新建批注(C) | 新建或编辑单元格批注 | — | — | `WIRED` |
| 2 | `showHideComment` | `showHideComment` | Action | 显示/隐藏批注(H) | 切换显示或隐藏选定单元格批注 | ✓ | — | `WIRED` |
| 3 | `deleteComment` | `deleteComment` | Action | 删除批注(D) | 删除选定单元格批注 | ✓ | — | `WIRED` |
| 4 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 5 | `showComments` | `showComments` | Action | 显示所有批注(A) | 显示工作表中的全部批注 | — | — | `WIRED` |

### Ledger — Toolbar: `standard` (26 项，20/20 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `newBook` | `file_new` | Action | 新建工作簿 | 创建空白工作簿 | ✓ | Ctrl+N | `WIRED` |
| 2 | `open` | `file_open` | Action | 打开… | 打开现有文档或文件 | ✓ | Ctrl+O | `WIRED` |
| 3 | `save` | `file_save` | Action | 保存当前工作簿 | 保存当前电子表格 | ✓ | Ctrl+S | `WIRED` |
| 4 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 5 | `printQuick` | `file_print` | Action | 打印… | 调用打印机配置打印文档 | ✓ | Ctrl+P | `WIRED` |
| 6 | `printPreview` | `file_print_preview` | Action | 打印预览 | 打开全功能交互式打印预览视口 | ✓ | — | `WIRED` |
| 7 | `spelling` | `tools_spelling` | Action | 拼写和语法检查… | 运行词典校对并审查拼写错误 (F7) | ✓ | F7 | `WIRED` |
| 8 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 9 | `cut` | `edit_cut` | Action | 剪切 | 剪切选中内容 | ✓ | Ctrl+X | `WIRED` |
| 10 | `copy` | `edit_copy` | Action | 复制 | 复制选中内容 | ✓ | Ctrl+C | `WIRED` |
| 11 | `paste` | `edit_paste` | Action | 粘贴 | 粘贴剪贴板内容 | ✓ | Ctrl+V | `WIRED` |
| 12 | `formatPainter` | `formatPainter` | Action | 格式刷(P) | 格式刷 (双击可连续应用) | ✓ | — | `WIRED` |
| 13 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 14 | `undo` | `edit_undo` | SplitButton | 撤销 | 撤销上一步操作 | ✓ | Ctrl+Z | `WIRED` |
| 15 | `redo` | `edit_redo` | SplitButton | 重做 | 恢复撤销的操作 | ✓ | Ctrl+Y | `WIRED` |
| 16 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 17 | `hyperlink` | `insert_hyperlink` | Action | 超链接… | 插入或编辑网页、书签跳转超链接 | ✓ | Ctrl+K | `WIRED` |
| 18 | `autoSum (split)` | `autoSum` | SplitButton | 自动求和(U) | 计算所选区域的总和 | ✓ | — | `WIRED` |
| 19 | `sortAsc` | `data_sort_asc` | Action | 升序排序 | 按选中列的值进行递增从小到大排序 | ✓ | — | `WIRED` |
| 20 | `sortDesc` | `data_sort_desc` | Action | 降序排序 | 按选中列的值进行递减从大到小排序 | ✓ | — | `WIRED` |
| 21 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 22 | `chartWizard` | `chartWizard` | Action | 图表向导(W)... | 启动图表向导创建统计图表 | ✓ | — | `WIRED` |
| 23 | `tb_drawing` | `tb_drawing` | Action | 绘图(D) | 显示或隐藏绘图工具栏 | ✓ | — | `WIRED` |
| 24 | `zoom (combo)` | `Ledger_ZoomCombo` | ComboBox | 显示比例 | 显示比例 | — | — | `WIRED` |
| 25 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 26 | `help` | `help_contents` | Action | ATBOffice 帮助 | 打开用户帮助文档 | ✓ | F1 | `WIRED` |

## 2. Lectern 逐工具栏详细对照表

### Lectern — Toolbar: `diagram` (13 项，11/11 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `diagramAddShape (split)` | `diagramAddShape` | SplitButton | 添加形状(A) | 在所选关系图元素周围添加新形状 | ✓ | — | `WIRED` |
| 2 | `diagramPromote` | `diagramPromote` | Action | 升级(P) | 提升所选图示元素层级 | ✓ | — | `WIRED` |
| 3 | `diagramDemote` | `diagramDemote` | Action | 降级(D) | 降低所选图示元素层级 | ✓ | — | `WIRED` |
| 4 | `diagramMoveUp` | `diagramMoveUp` | Action | 上移(U) | 在同层级中向前移动 | ✓ | — | `WIRED` |
| 5 | `diagramMoveDown` | `diagramMoveDown` | Action | 下移(W) | 在同层级中向后移动 | ✓ | — | `WIRED` |
| 6 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 7 | `layoutMenu (drop)` | `版式` | DropDownButton | 版式 | 版式 | — | — | `WIRED` |
| 8 | `colorsMenu (drop)` | `更改颜色` | DropDownButton | 更改颜色 | 更改颜色 | — | — | `WIRED` |
| 9 | `styleMenu (drop)` | `样式` | DropDownButton | 样式 | 样式 | — | — | `WIRED` |
| 10 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 11 | `diagramTextPane` | `diagramTextPane` | Action | 文本窗格(T) | 显示或隐藏 IntelliArt 文本大纲窗格 | ✓ | — | `WIRED` |
| 12 | `diagramReset` | `diagramReset` | Action | 重设图形(R) | 撤销格式修改并重置默认样式 | ✓ | — | `WIRED` |
| 13 | `diagramToShapes` | `diagramToShapes` | Action | 转换为形状(S) | 将 IntelliArt 关系图解散为标准独立自选图形 | ✓ | — | `WIRED` |

### Lectern — Toolbar: `drawing` (22 项，19/19 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `drawMenu (drop)` | `绘图` | DropDownButton | 绘图 | 绘图 | — | — | `WIRED` |
| 2 | `select` | `selectObjects` | Action | 选择对象(S) | 框选画布中的图形对象 | ✓ | — | `WIRED` |
| 3 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 4 | `autoShapes (drop)` | `自选图形` | DropDownButton | 自选图形 | 自选图形 | — | — | `WIRED` |
| 5 | `drawLine` | `drawLine` | Action | 线条(L) | 自由绘制直线段 | — | — | `WIRED` |
| 6 | `drawArrow` | `drawArrow` | Action | 箭头(A) | 绘制单向箭头线 | — | — | `WIRED` |
| 7 | `drawRect` | `drawRect` | Action | 矩形(R) | 绘制矩形几何图形 | — | — | `WIRED` |
| 8 | `drawOval` | `drawOval` | Action | 椭圆(O) | 绘制椭圆或正圆形 | — | — | `WIRED` |
| 9 | `textBox` | `textBox` | Action | 文本框(T) | 在幻灯片中绘制横向文本框 | — | — | `WIRED` |
| 10 | `insertWordArt` | `draw_insertWordArt` | Action | 插入艺术字(W)... | 插入艺术字 | — | — | `WIRED` |
| 11 | `insertDiagram` | `draw_insertDiagram` | Action | 插入图示(D)... | 插入组织结构图或循环图 | — | — | `WIRED` |
| 12 | `insertClipArt` | `insertClipArt` | Action | 剪贴画(C)... | 从剪贴画库中插入素材 | ✓ | — | `WIRED` |
| 13 | `insertPicture` | `draw_insertPicture` | Action | 来自文件的图片(P)... | 从磁盘文件插入图片 | — | — | `WIRED` |
| 14 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 15 | `fillColor (split)` | `填充颜色` | ColorPicker | 填充颜色 | 填充颜色 | ✓ | — | `WIRED` |
| 16 | `lineColor (split)` | `线条颜色` | ColorPicker | 线条颜色 | 线条颜色 | ✓ | — | `WIRED` |
| 17 | `fontColor (split)` | `字体颜色` | ColorPicker | 字体颜色 | 字体颜色 | ✓ | — | `WIRED` |
| 18 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 19 | `lineStyle (drop)` | `线型` | DropDownButton | 线型 | 线型 | ✓ | — | `WIRED` |
| 20 | `dashStyle (drop)` | `虚线线型` | DropDownButton | 虚线线型 | 虚线线型 | ✓ | — | `WIRED` |
| 21 | `arrowStyle (drop)` | `箭头样式` | DropDownButton | 箭头样式 | 箭头样式 | ✓ | — | `WIRED` |
| 22 | `shadowStyle (drop)` | `阴影样式` | DropDownButton | 阴影样式 | 阴影样式 | ✓ | — | `WIRED` |

### Lectern — Toolbar: `formatting` (24 项，17/17 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `font (combo)` | `Lectern_FontCombo` | ComboBox | 字体 | 字体 | — | — | `WIRED` |
| 2 | `size (combo)` | `Lectern_SizeCombo` | ComboBox | 字号 | 字号 | — | — | `WIRED` |
| 3 | `bold` | `separator` | Separator | — | — | — | — | `WIRED` |
| 4 | `italic` | `bold` | Action | 加粗(B) | 加粗 (Ctrl+B) | ✓ | Ctrl+B | `WIRED` |
| 5 | `underline` | `italic` | Action | 倾斜(I) | 倾斜 (Ctrl+I) | ✓ | Ctrl+I | `WIRED` |
| 6 | `shadowText` | `underline` | Action | 下划线(U) | 下划线 (Ctrl+U) | ✓ | Ctrl+U | `WIRED` |
| 7 | `|` | `shadowText` | Action | 阴影(S) | 文字阴影效果 | ✓ | — | `WIRED` |
| 8 | `alignLeft` | `separator` | Separator | — | — | — | — | `WIRED` |
| 9 | `alignCenter` | `alignLeft` | Action | 左对齐(L) | 将选定对象靠左对齐 | ✓ | Ctrl+L | `WIRED` |
| 10 | `alignRight` | `alignCenter` | Action | 水平居中(C) | 将选定对象水平居中 | ✓ | Ctrl+E | `WIRED` |
| 11 | `|` | `alignRight` | Action | 右对齐(R) | 将选定对象靠右对齐 | ✓ | Ctrl+R | `WIRED` |
| 12 | `numbering` | `separator` | Separator | — | — | — | — | `WIRED` |
| 13 | `bullets` | `format_numbering` | Action | 项目编号 | 开启或关闭段落顺序编号列表 | ✓ | — | `WIRED` |
| 14 | `|` | `format_bullets` | Action | 项目符号 | 开启或关闭段落项目符号列表 | ✓ | — | `WIRED` |
| 15 | `growFont` | `separator` | Separator | — | — | — | — | `WIRED` |
| 16 | `shrinkFont` | `growFont` | Action | 增大字号(G) | 增大文本字号 | ✓ | — | `WIRED` |
| 17 | `|` | `shrinkFont` | Action | 减小字号(K) | 减小文本字号 | ✓ | — | `WIRED` |
| 18 | `promote` | `separator` | Separator | — | — | — | — | `WIRED` |
| 19 | `demote` | `promote` | Action | 提升级别(P) | 降低缩进量 / 提升级别 (Alt+Shift+Left) | ✓ | Alt+Shift+Left | `WIRED` |
| 20 | `|` | `demote` | Action | 降低级别(D) | 增加缩进量 / 降低级别 (Alt+Shift+Right) | ✓ | Alt+Shift+Right | `WIRED` |
| 21 | `fontColor (split)` | `separator` | Separator | — | — | — | — | `WIRED` |
| 22 | `|` | `字体颜色` | ColorPicker | 字体颜色 | 字体颜色 | ✓ | — | `WIRED` |
| 23 | `slideDesign` | `separator` | Separator | — | — | — | — | `WIRED` |
| 24 | `newSlide` | `slideDesign` | Action | 幻灯片设计(D) | 打开幻灯片设计任务窗格 | — | — | `WIRED` |

### Lectern — Toolbar: `master` (4 项，4/4 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `insertTitleMaster` | `insertSlideMaster` | Action | 插入幻灯片母版(M) | 在演示文稿中插入新的幻灯片母版 | — | — | `WIRED` |
| 2 | `deleteTitleMaster` | `insertTitleMaster` | Action | 插入标题母版(T) | 插入新的标题母版 | ✓ | — | `WIRED` |
| 3 | `|` | `preserveMaster` | Action | 保留母版(P) | 保留所选母版以防止其未被使用时被自动删除 | — | — | `WIRED` |
| 4 | `closeMaster` | `renameMaster` | Action | 重命名母版(R)... | 重命名所选母版 | — | — | `WIRED` |

### Lectern — Toolbar: `outlining` (7 项，6/6 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `promote` | `outline_promote` | Action | 提升(P) | 提升大纲级别 (Alt+Shift+Left) | — | Alt+Shift+Left | `WIRED` |
| 2 | `demote` | `outline_demote` | Action | 降低(D) | 降低大纲级别 (Alt+Shift+Right) | — | Alt+Shift+Right | `WIRED` |
| 3 | `moveParaUp` | `moveParaUp` | Action | 上移(U) | 上移选定段落 (Alt+Shift+Up) | ✓ | Alt+Shift+Up | `WIRED` |
| 4 | `moveParaDown` | `moveParaDown` | Action | 下移(O) | 下移选定段落 (Alt+Shift+Down) | ✓ | Alt+Shift+Down | `WIRED` |
| 5 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 6 | `summarySlide` | `outline_summarySlide` | Action | 摘要幻灯片(S) | 生成摘要幻灯片 | — | — | `WIRED` |
| 7 | `showFormatting` | `outline_showFormatting` | Action | 显示格式(F) | 在大纲视图中显示或隐藏文本格式 | — | — | `WIRED` |

### Lectern — Toolbar: `picture` (14 项，12/12 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `insertPicture` | `pic_insert` | Action | 插入图片(I)... | 从磁盘文件插入图片 | ✓ | — | `WIRED` |
| 2 | `colorPic (drop)` | `颜色` | DropDownButton | 颜色 | 颜色 | — | — | `WIRED` |
| 3 | `picMoreContrast` | `picMoreContrast` | Action | 增加对比度(M) | 增加图片对比度 | ✓ | — | `WIRED` |
| 4 | `picLessContrast` | `picLessContrast` | Action | 降低对比度(L) | 降低图片对比度 | ✓ | — | `WIRED` |
| 5 | `picMoreBright` | `picMoreBright` | Action | 增加亮度(B) | 增加图片亮度 | ✓ | — | `WIRED` |
| 6 | `picLessBright` | `picLessBright` | Action | 降低亮度(D) | 降低图片亮度 | ✓ | — | `WIRED` |
| 7 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 8 | `picCrop` | `picCrop` | Action | 裁剪(C) | 裁剪图片尺寸与显示区域 | ✓ | — | `WIRED` |
| 9 | `rotateLeft` | `rotateLeft` | Action | 向左旋转 90°(R) | 将图片逆时针旋转 90 度 | ✓ | — | `WIRED` |
| 10 | `lineStyle (drop)` | `线型` | DropDownButton | 线型 | 线型 | ✓ | — | `WIRED` |
| 11 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 12 | `formatObject` | `formatObject` | Action | 设置图片格式(O)... | 打开图片格式与尺寸属性对话框 | ✓ | — | `WIRED` |
| 13 | `picTransparent` | `picTransparent` | Action | 设置透明色(T) | 拾取图片特定像素并将其设为透明 | ✓ | — | `WIRED` |
| 14 | `picReset` | `picReset` | Action | 重设图片(P) | 恢复图片的原始尺寸和色彩效果 | ✓ | — | `WIRED` |

### Lectern — Toolbar: `sorter` (9 项，7/7 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `hideSlide` | `hideSlide` | Action | 隐藏幻灯片(H) | 在放映中隐藏选定幻灯片 | ✓ | — | `WIRED` |
| 2 | `rehearse` | `rehearse` | Action | 排练计时(R) | 启动排练计时幻灯片放映 | ✓ | — | `WIRED` |
| 3 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 4 | `summarySlide` | `summarySlide` | Action | 摘要幻灯片(S) | 根据选定幻灯片标题生成摘要幻灯片 | ✓ | — | `WIRED` |
| 5 | `speakerNotes` | `speakerNotes` | Action | 演讲者备注(N) | 编辑演讲者备注 | ✓ | — | `WIRED` |
| 6 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 7 | `transitionPane` | `transitionPane` | Action | 幻灯片切换(T)... | 打开幻灯片切换任务窗格 | ✓ | — | `WIRED` |
| 8 | `slideDesign` | `sorter_slideDesign` | Action | 设计(D) | 打开幻灯片设计任务窗格 | — | — | `WIRED` |
| 9 | `newSlide` | `sorter_newSlide` | Action | 新幻灯片(M) | 插入新幻灯片 | — | — | `WIRED` |

### Lectern — Toolbar: `standard` (27 项，21/21 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `new` | `file_new` | Action | 新建演示文稿 | 创建空白演示文稿 | ✓ | Ctrl+N | `WIRED` |
| 2 | `open` | `file_open` | Action | 打开… | 打开现有文档或文件 | ✓ | Ctrl+O | `WIRED` |
| 3 | `save` | `file_save` | Action | 保存当前演示文稿 | 保存当前幻灯片演示 | ✓ | Ctrl+S | `WIRED` |
| 4 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 5 | `print` | `file_print` | Action | 打印… | 调用打印机配置打印文档 | ✓ | Ctrl+P | `WIRED` |
| 6 | `printPreview` | `file_print_preview` | Action | 打印预览 | 打开全功能交互式打印预览视口 | ✓ | — | `WIRED` |
| 7 | `spelling` | `tools_spelling` | Action | 拼写和语法检查… | 运行词典校对并审查拼写错误 (F7) | ✓ | F7 | `WIRED` |
| 8 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 9 | `cut` | `edit_cut` | Action | 剪切 | 剪切选中内容 | ✓ | Ctrl+X | `WIRED` |
| 10 | `copy` | `edit_copy` | Action | 复制 | 复制选中内容 | ✓ | Ctrl+C | `WIRED` |
| 11 | `paste` | `edit_paste` | Action | 粘贴 | 粘贴剪贴板内容 | ✓ | Ctrl+V | `WIRED` |
| 12 | `painter` | `formatPainter` | Action | 格式刷(P) | 格式刷 (双击可连续应用) | ✓ | — | `WIRED` |
| 13 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 14 | `undo` | `edit_undo` | SplitButton | 撤销 | 撤销上一步操作 | ✓ | Ctrl+Z | `WIRED` |
| 15 | `redo` | `edit_redo` | SplitButton | 重做 | 恢复撤销的操作 | ✓ | Ctrl+Y | `WIRED` |
| 16 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 17 | `insertChart` | `insertChart` | Action | 插入图表(H)... | 插入统计图表 | ✓ | — | `WIRED` |
| 18 | `insertTable` | `insertTable` | Action | 插入表格(B)... | 插入表格 | ✓ | — | `WIRED` |
| 19 | `tb_tables` | `tb_tables` | Action | 表格和边框(T) | 显示或隐藏表格和边框工具栏 | ✓ | — | `WIRED` |
| 20 | `hyperlink` | `insert_hyperlink` | Action | 超链接… | 插入或编辑网页、书签跳转超链接 | ✓ | Ctrl+K | `WIRED` |
| 21 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 22 | `expandAll` | `expandAll` | Action | 全部展开(E) | 在左侧大纲窗格中全部展开 | ✓ | — | `WIRED` |
| 23 | `showFormatting` | `showFormatting` | Action | 显示格式(F) | 显示纯文本或格式化文本 | ✓ | — | `WIRED` |
| 24 | `showGrid` | `showGrid` | Action | 网格和参考线(G) | 显示或隐藏对齐网格与参考线 | — | — | `WIRED` |
| 25 | `viewGray (split)` | `viewGray` | SplitButton | 颜色/灰度(C) | 切换彩色、灰度或纯黑白显示模式 | ✓ | — | `WIRED` |
| 26 | `zoom (combo)` | `Lectern_ZoomCombo` | ComboBox | 显示比例 | 显示比例 | — | — | `WIRED` |
| 27 | `help` | `separator` | Separator | — | — | — | — | `WIRED` |

### Lectern — Toolbar: `tables` (16 项，13/13 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `dashStyle (drop)` | `线型` | DropDownButton | 线型 | 线型 | ✓ | — | `WIRED` |
| 2 | `lineStyle (drop)` | `粗细` | DropDownButton | 粗细 | 粗细 | — | — | `WIRED` |
| 3 | `lineColor (drop)` | `线条颜色` | DropDownButton | 线条颜色 | 线条颜色 | — | — | `WIRED` |
| 4 | `bordersAll (drop)` | `tableBordersAll` | SplitButton | 边框(B) | 应用表格边框样式 | — | — | `WIRED` |
| 5 | `fillColor (drop)` | `底纹颜色` | DropDownButton | 底纹颜色 | 底纹颜色 | — | — | `WIRED` |
| 6 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 7 | `tableMenu (drop)` | `表格` | DropDownButton | 表格 | 表格 | — | — | `WIRED` |
| 8 | `mergeCells` | `tableMergeCells` | Action | 合并单元格(M) | 合并所选单元格 | — | — | `WIRED` |
| 9 | `splitCell` | `tableSplitCell` | Action | 拆分单元格(P)... | 拆分单元格 | — | — | `WIRED` |
| 10 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 11 | `cellTop` | `cellTop` | Action | 顶端对齐(T) | 单元格文本靠上对齐 | ✓ | — | `WIRED` |
| 12 | `cellMiddle` | `cellMiddle` | Action | 居中对齐(C) | 单元格文本垂直居中 | ✓ | — | `WIRED` |
| 13 | `cellBottom` | `cellBottom` | Action | 底端对齐(B) | 单元格文本靠下对齐 | ✓ | — | `WIRED` |
| 14 | `|` | `separator` | Separator | — | — | — | — | `WIRED` |
| 15 | `distRows` | `distRows` | Action | 平均分布各行(R) | 使所选行具有相同的高度 | ✓ | — | `WIRED` |
| 16 | `distCols` | `distCols` | Action | 平均分布各列(O) | 使所选列具有相同的宽度 | ✓ | — | `WIRED` |

### Lectern — Toolbar: `wordart` (9 项，7/7 已接线)

| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |
| 1 | `insertWordArt` | `wa_insert` | Action | 插入艺术字(W)... | 创建新的艺术字对象 | ✓ | — | `WIRED` |
| 2 | `wordartEdit` | `wordartEdit` | Action | 编辑文字(E)... | 修改艺术字文本内容及字体 | ✓ | — | `WIRED` |
| 3 | `wordartGallery` | `wordartGallery` | Action | 艺术字库(G)... | 打开艺术字预设样式库 | ✓ | — | `WIRED` |
| 4 | `formatObject` | `wa_format` | Action | 设置艺术字格式(O)... | 设置艺术字填充、线条与三维效果 | ✓ | — | `WIRED` |
| 5 | `waShape (drop)` | `separator` | Separator | — | — | — | — | `WIRED` |
| 6 | `waSameHeight` | `艺术字形状` | DropDownButton | 艺术字形状 | 艺术字形状 | — | — | `WIRED` |
| 7 | `waVertical` | `waSameHeight` | Action | 艺术字同样高度(H) | 使所选艺术字大小写字母具有相同高度 | ✓ | — | `WIRED` |
| 8 | `alignCenter (drop)` | `waVertical` | Action | 艺术字垂直文字(V) | 将艺术字排列方向切换为纵向排版 | ✓ | — | `WIRED` |
| 9 | `charSpacing (drop)` | `separator` | Separator | — | — | — | — | `WIRED` |
