# Implementation Plan: Issue #52 [Lectern] 幻灯片批注 (Comments) 气泡与作者图谱管理

## 1. 任务概述与分阶段目标

按照测试驱动开发（TDD）及严谨的代码设计原则，将 Issue #52 分解为 6 个明确任务，逐步实现数据模型、PresentationML 往返序列化、画布气泡与卡片交互、审阅导航与自动化测试覆盖。

---

## 2. 详细任务分解

### 任务 1：创建批注与作者数据模型 (`models/comment.py`)
- **文件**：`src/atboffice/modules/presentation/models/comment.py`
- **内容**：
  - 定义 `CommentAuthor`：包含 `id`, `name`, `initials`, `last_idx`, `color_idx`, `user_id`, `provider_id`，支持 `to_dict()`, `from_dict()`。
  - 定义 `CommentReply`：包含 `id`, `author_id`, `created`, `text`，支持 `to_dict()`, `from_dict()`。
  - 定义 `Comment`：包含 `id`, `author_id`, `text`, `x`, `y`, `idx`, `created`, `shape_id`, `status`, `replies`, `is_modern`，支持 `to_dict()`, `from_dict()`。
  - 辅助方法：生成全局唯一 ID、规范化时间戳。
- **验证**：编写单测测试模型的序列化与反序列化一致性。

### 任务 2：扩展 Slide 与 Presentation 容器模型
- **文件**：
  - `src/atboffice/modules/presentation/models/slide.py`
  - `src/atboffice/modules/presentation/models/presentation.py`
  - `src/atboffice/modules/presentation/models/__init__.py`
- **内容**：
  - 在 `Slide` 中增加 `comments: list[Comment] = field(default_factory=list)`，并在 `to_dict()`, `from_dict()`, `dup_slide()` 中完整处理批注拷贝与反序列化。
  - 在 `Presentation` 中增加 `comment_authors: list[CommentAuthor] = field(default_factory=list)`，提供辅助方法：
    - `get_or_create_author(name: str, initials: str = "") -> CommentAuthor`
    - `find_author(author_id: str) -> CommentAuthor | None`
    - `all_comments() -> list[tuple[int, Comment]]`
- **验证**：在 `tests/unit/presentation/test_comments.py` 中测试 slide 拷贝时批注深复制与 ID 重映射。

### 任务 3：PresentationML I/O 读取层支持 (`pptx_reader.py` & `xml_utils.py`)
- **文件**：
  - `src/atboffice/modules/presentation/io/xml_utils.py`
  - `src/atboffice/modules/presentation/io/pptx_reader.py`
- **内容**：
  - 增加关系类型与命名空间常量：
    - `REL_COMMENT_AUTHORS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/commentAuthors"`
    - `REL_COMMENTS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"`
    - `REL_AUTHORS_MODERN = "http://schemas.microsoft.com/office/2018/10/relationships/authors"`
    - `REL_COMMENTS_MODERN = "http://schemas.microsoft.com/office/2018/10/relationships/comments"`
    - `NS_P188 = "http://schemas.microsoft.com/office/powerpoint/2018/8/main"`
  - 在 `pptx_reader.py` 中：
    - 解析 `ppt/presentation.xml.rels` 中的作者表（`ppt/commentAuthors.xml` 与 `ppt/authors.xml`），填充至 `pres.comment_authors`。
    - 在解析每张幻灯片时，查找其关联的 comments 部件，兼容解析 legacy `<p:cmLst>` 和 modern `<p188:cmLst>`，填充至 `slide.comments`。

### 任务 4：PresentationML I/O 写入层支持 (`pptx_writer.py`)
- **文件**：`src/atboffice/modules/presentation/io/pptx_writer.py`
- **内容**：
  - 若演示文稿中任一幻灯片包含批注：
    - 序列化 `ppt/commentAuthors.xml`，维护各作者的 `lastIdx`。
    - 将关系写入 `ppt/_rels/presentation.xml.rels`。
    - 为包含批注的幻灯片生成 `ppt/comments/comment{N}.xml`，输出 `<p:cmLst><p:cm ...><p:pos x="..." y="..."/><p:text>...</p:text></p:cm></p:cmLst>`。
    - 将关系写入对应幻灯片 `.rels`。
    - 在 `[Content_Types].xml` 中声明 `Override`：
      - `application/vnd.openxmlformats-officedocument.presentationml.commentAuthors+xml`
      - `application/vnd.openxmlformats-officedocument.presentationml.comments+xml`
- **验证**：执行 PPTX 保存后重新读入，断言批注与作者数据 100% 保持无损。

### 任务 5：画布批注徽标与卡片交互 (`comment_overlay.py` & `slide_canvas.py`)
- **文件**：
  - `src/atboffice/modules/presentation/views/comment_overlay.py`
  - `src/atboffice/modules/presentation/views/slide_canvas.py`
  - `src/atboffice/modules/presentation/views/workspace.py`
- **内容**：
  - 实现 `CommentMarkerItem`：QGraphicsItem，绘制经典明黄气泡、作者缩写、支持拖动调整坐标与悬停高亮提示。
  - 实现 `CommentCardWidget`：浮层弹出面板，包含作者信息、时间、正文编辑、解决/重开切换、删除、回复链与回复输入框。
  - 在 `SlideScene` 加载幻灯片时同步渲染 `CommentMarkerItem`。
  - 在 `SlideCanvasView` 右键菜单中增加“插入批注”操作。
  - 提供 `navigate_comment(step: int)` 支持上一条/下一条批注无缝切换与焦点定位。
  - 全面包裹 `safe_tr()` 国际化多语言支持。

### 任务 6：自动化测试套件与全量回归
- **文件**：`tests/unit/presentation/test_comments.py`
- **内容**：
  - 单测 1：`CommentAuthor`, `CommentReply`, `Comment` 模型创建与序列化；
  - 单测 2：Presentation 与 Slide 容器中作者自动生成与批注深拷贝；
  - 单测 3：Legacy XML 格式解析（`<p:cmAuthorLst>` 与 `<p:cmLst>`）；
  - 单测 4：Modern XML 格式解析（`<p188:authorLst>` 与 `<p188:cmLst>` 及其回复）；
  - 单测 5：完整的 PPTX 二进制写入与重读无损还原往返测试；
  - 单测 6：`CommentMarkerItem` 画布绘制与坐标更新测试；
  - 单测 7：跨幻灯片批注导航测试；
  - 运行 `ruff check .` 与全量 700+ pytest 单测，确保无报错、无代码坏味道。
