# Specification: Issue #52 [Lectern] 幻灯片批注 (Comments) 气泡与作者图谱管理

## 1. 概述与业务价值

在演示文稿审阅与团队协作场景中，批注（Comments）系统至关重要。幻灯片批注允许用户、审阅人和作者在画布的具体位置或特定图元上添加评审意见、指派任务、回复讨论以及标记问题解决状态。

本规范定义了 ATBOffice Lectern (PowerPoint 2003 风格) 演示文稿模块中的批注系统与作者图谱（Comment Authors）的完整技术架构，包括：
1. **数据模型层**：`CommentAuthor`, `CommentReply`, `Comment` 模型，与 `Slide`、`Presentation` 的关联和序列化；
2. **PresentationML I/O 层**：双向兼容 Office 经典批注（Legacy Comments, ECMA-376 `ppt/comments/` + `ppt/commentAuthors.xml`）与现代批注（Modern Comments, MS-PPTX 2.16 `ppt/authors.xml`）；
3. **画布 UI 与交互层**：画布上的醒目黄色便签/气泡徽标（`CommentMarkerItem`），包含作者缩写、高亮、悬停提示、点击唤起沉浸式批注卡片浮层（`CommentCardWidget`）；
4. **审阅流程与工具链**：支持在幻灯片任意坐标或指定图元上“插入批注”、回复批注、标记解决/重新打开、删除批注，以及“上一条/下一条批注”快速遍历审阅；
5. **地道国际化（i18n）**：100% 控件与提示文案通过 `safe_tr()` 呈现自然流畅的地道中文。

---

## 2. 关键参考：.vibeoffice 原始代码与标准规范

- **.vibeoffice 参考实现**：
  - `.vibeoffice/public/lectern/js/comments.js`：定义了 `L.comments.read`, `L.comments.slide`, `L.comments.begin`, `L.comments.finish`，负责 legacy comments (`p:cmLst`, `p:cmAuthorLst`) 及 modern comments (`p188:cmLst`, `p188:authorLst`) 的解析、作者 ID 映射重写、图元锚定丢失回退到幻灯片坐标。
  - `.vibeoffice/tests/lectern/comments.mjs` & `comment-fixtures.py`：提供了标准批注验证用例（作者列表映射、创建 ID 校验、未修改批注字节保留、恢复与撤销）。
- **OpenXML (ECMA-376) 规范**：
  - `http://schemas.openxmlformats.org/officeDocument/2006/relationships/commentAuthors` -> `ppt/commentAuthors.xml`
  - `http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments` -> `../comments/comment{N}.xml`
  - 命名空间：`xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"`

---

## 3. 数据模型设计 (`src/atboffice/modules/presentation/models/comment.py`)

### 3.1 `CommentAuthor`
记录批注作者的唯一身份信息：
```python
@dataclass
class CommentAuthor:
    id: str  # 经典批注为数值字符串（如 "0", "1"），现代批注为 GUID
    name: str  # 作者全名（如 "张三"、"John Doe"）
    initials: str = ""  # 缩写首字母（如 "ZS", "JD"），用于在黄色气泡中精简显示
    last_idx: int = 0  # 该作者已发布批注的最大索引序号
    color_idx: int = 0  # 颜色索引 (0-31)
    user_id: str = ""  # 现代批注电子邮箱或用户标识
    provider_id: str = ""  # 身份提供商（如 "AD"）
```

### 3.2 `CommentReply`
记录现代批注中的追加答复记录：
```python
@dataclass
class CommentReply:
    id: str  # 唯一标识 (GUID)
    author_id: str  # 答复人 ID
    created: str  # ISO 8601 格式时间戳
    text: str  # 答复内容
```

### 3.3 `Comment`
记录单条幻灯片批注的完整属性：
```python
@dataclass
class Comment:
    id: str  # 批注唯一标识
    author_id: str  # 关联作者 ID
    text: str  # 批注正文内容
    x: float = 20.0  # 幻灯片 X 坐标 (pt)
    y: float = 20.0  # 幻灯片 Y 坐标 (pt)
    idx: int = 1  # 作者批注递增序号 (用于 Legacy 格式)
    created: str = ""  # 创建时间戳 ISO 8601
    shape_id: str | None = None  # 锚定的目标图元 ID (可选)
    status: str = "active"  # "active" | "resolved"
    replies: list[CommentReply] = field(default_factory=list)
    is_modern: bool = False  # 是否为现代批注结构
```

### 3.4 模型扩展
- `Slide`:
  - 增加 `comments: list[Comment] = field(default_factory=list)`
  - `to_dict()` / `from_dict()` 增加 `comments` 字段序列化
  - `dup_slide()` 支持深拷贝批注并重新分配唯一 ID
- `Presentation`:
  - 增加 `comment_authors: list[CommentAuthor] = field(default_factory=list)`
  - 提供作者管理工具方法：
    - `get_or_create_author(name: str, initials: str = "") -> CommentAuthor`
    - `find_author(author_id: str) -> CommentAuthor | None`
    - `all_comments() -> list[tuple[int, Comment]]` (返回包含幻灯片索引的平铺批注列表)

---

## 4. PresentationML I/O 设计

### 4.1 读取 (`pptx_reader.py`)
1. **作者列表解析**：
   - 检查 `ppt/presentation.xml.rels` 中的 `REL_COMMENT_AUTHORS` (`http://schemas.openxmlformats.org/officeDocument/2006/relationships/commentAuthors`) 与 `REL_AUTHORS` (`http://schemas.microsoft.com/office/2018/10/relationships/authors`)。
   - 解析 `<p:cmAuthorLst>` 与 `<p188:authorLst>`，构建 `CommentAuthor` 列表存入 `pres.comment_authors`。
2. **幻灯片批注解析**：
   - 读取每张幻灯片的关系部件，筛选 `REL_COMMENTS`。
   - 兼容解析 Legacy `<p:cmLst>`：
     - `<p:cm authorId="..." dt="..." idx="...">`
     - `<p:pos x="..." y="..."/>` (转换坐标为浮点数)
     - `<p:text>...</p:text>`
   - 兼容解析 Modern `<p188:cmLst>`：
     - `<p188:cm id="..." authorId="..." created="..." status="...">`
     - `<p188:pos x="..." y="..."/>`
     - `<p188:txBody><a:p><a:r><a:t>...</a:t></a:r></a:p></p188:txBody>`
     - `<p188:replyLst>` 内部的 `<p188:reply>`
     - `<ac:spMk id="..."/>` 锚定图元提取
   - 将解析所得批注填充入 `slide.comments`。

### 4.2 写入 (`pptx_writer.py`)
1. **条件式部件生成**：
   - 仅当演示文稿包含有效批注时，方生成 `ppt/commentAuthors.xml` 与 `ppt/comments/comment{N}.xml`，避免无批注文档产生幽灵部件。
2. **序列化 `ppt/commentAuthors.xml`**：
   - 输出符合 ECMA-376 标准的 `<p:cmAuthorLst xmlns:p="...">`。
   - 正确维护每个作者的 `lastIdx`。
   - 在 `ppt/_rels/presentation.xml.rels` 添加关系并声明 `[Content_Types].xml` 覆盖类型。
3. **序列化 `ppt/comments/comment{N}.xml`**：
   - 遍历各幻灯片，若其包含批注，则输出 `<p:cmLst xmlns:p="...">`。
   - 为各 `<p:cm>` 输出坐标 `<p:pos x="..." y="..."/>` 与文本 `<p:text>...</p:text>`。
   - 在 `ppt/slides/_rels/slide{N}.xml.rels` 添加关系声明。

---

## 5. UI 与交互架构设计 (`comment_overlay.py` & `slide_canvas.py`)

### 5.1 画布图元徽标 (`CommentMarkerItem`)
- 继承 `QGraphicsItem`，层级设定为 `ZValue = 1000`（浮于普通图形之上）。
- **视觉风格**：
  - 经典便签明黄底色（`#FFE066` / `#F59F00` 边框，圆角矩形气泡 + 底部小三角指示箭头）。
  - 已解决状态（Resolved）显示为淡灰色徽标（`#CED4DA` / `#868E96`）。
  - 内部居中显示作者首字母大写缩写（如 "FA", "ZS"）。
- **交互动作**：
  - `HoverEnter` / `HoverLeave` 鼠标悬停高亮；
  - Tooltip 显示作者姓名、时间及文本前缀；
  - 单击选中并在附近弹出/唤起 `CommentCardWidget` 详情浮层；
  - 支持拖拽调整批注在幻灯片上的摆放坐标（同时更新 `Comment.x`, `Comment.y`）。

### 5.2 批注详情卡片 (`CommentCardWidget`)
- 使用优雅轻量的弹出浮层，包含：
  1. **头部**：作者头像圆形徽标、姓名、相对时间戳（如“刚刚”、“2小时前”或具体日期）、“已解决/未解决”状态切换标签、“关闭”与“删除”按钮；
  2. **正文区**：支持富文本/纯文本展示与原位快速修改；
  3. **回复列表**：展示历史答复，支持多轮讨论展开；
  4. **底部输入框**：支持审阅者输入新回复并点击“答复 (Reply)”；
  5. 国际化与响应式销毁/失焦保存。

### 5.3 审阅导航与菜单集成
1. **右键菜单集成**：
   - 在 `SlideCanvasView.contextMenuEvent` 中增加“插入批注 (Insert Comment)”菜单项；在右键点击选定图形或空白处时，自动在鼠标点击点创建新批注并立即聚焦输入。
2. **审阅工具条/快捷遍历**：
   - 提供 `navigate_comment(direction: int)`（`+1` 为下一条，`-1` 为上一条）。
   - 自动跨页跳转：若当前页无下一条批注，自动切换至下一张含有批注的幻灯片并聚焦首个批注气泡。

---

## 6. 测试与验证策略

在 `tests/unit/presentation/test_comments.py` 中建立完整单测与集成测试：
1. **模型验证**：`CommentAuthor`, `Comment`, `CommentReply` 创建、序列化与反序列化字典；
2. **I/O 往返验证**：
   - 包含多作者、多批注的演示文稿保存为 PPTX 二进制字节流；
   - 重新通过 `read_pptx` 加载，验证作者列表、批注坐标、正文、时间戳、图元锚定完全无损还原；
3. **Legacy 与 Modern 兼容解析**：
   - 构造包含 `<p:cmLst>` 的经典 XML 样本进行解析；
   - 构造包含 `<p188:cmLst>` 的现代 XML 样本进行解析，验证回复链完整性；
4. **画布 UI 交互验证**：
   - 实例化 `CommentMarkerItem`，验证其尺寸、绘制（paint）、坐标同步；
   - 验证跨幻灯片“上一条/下一条批注”遍历逻辑；
5. **全量回归保障**：
   - 运行全部 700+ 项测试，确保 0 regression。
