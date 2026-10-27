# Technical Specification: Lectern Fullscreen Slide Show Engine & 58 Transitions

## 1. Overview & Objectives
This specification designs and implements the full-featured, high-performance slide show presentation engine for Lectern (`atboffice.modules.presentation.slideshow`), porting and enhancing the complete capabilities from `.vibeoffice/public/lectern/js/slideshow.js`.

Key deliverables:
1. **Transition Engine (`transitions.py`)**:
   - Complete catalogue of **58 distinct slide transitions** (plus 'none' and 'random').
   - High-performance QPainter 2D transition rendering algorithms supporting clipping paths, linear/radial/conic masks, directional sweeps, interleaving combs, split blinds, and alpha blends.
   - 60 FPS smooth double-buffered frame progression with easing curves.
2. **Slide Show Viewport (`slideshow_view.py`)**:
   - Fullscreen / windowed presentation viewport (`SlideShowView`).
   - Dynamic letterbox / pillarbox scaling preserving slide aspect ratio with pure black background.
   - Comprehensive input handling:
     - Keyboard: Space, Enter, PageDown, Right, Down, 'N' (Next); PageUp, Left, Up, Backspace, 'P' (Prev); Home, End; 'B'/'.' (Black screen); 'W'/',' (White screen); Esc (End show); Digits + Enter (Direct slide jump).
     - Mouse: Left click advance, mouse wheel paging, idle cursor auto-hiding.
     - Context Menu: Classic PowerPoint right-click popup menu (Next, Previous, Go to Slide, Screen [Black/White/Pause], End Show).
     - Popbar: Hover floating on-screen navigation buttons at bottom-left (Previous, Menu, Next).
   - Auto-advance timing (`slide.transition.after`) and continuous loop playback (`presentation.show.loop`).
   - End-of-show screen ("放映结束，单击鼠标退出。").
3. **Workspace Integration (`workspace.py` & `view.py`)**:
   - F5 shortcut: Start presentation from first slide.
   - Shift+F5 shortcut: Start presentation from active slide.
   - Clean signals (`slideChanged`, `showEnded`).
   - 100% complete i18n support with `safe_tr()` and `retranslate_ui()`.

---

## 2. Transition Catalogue (58 Transition Effects)

All 58 transition variations from PowerPoint 2003 / `.vibeoffice/slideshow.js`:

| # | Type | Name | Parameters | Visual Effect |
|---|---|---|---|---|
| 0 | `none` | 无切换 (No Transition) | - | 瞬间切换 |
| 1-2 | `blinds` | 百叶窗 (Blinds) | `dir='horz'` / `dir='vert'` | 6 条水平或垂直百叶窗同步旋转展开 |
| 3-4 | `zoom` / `box` | 盒状 (Box) | `dir='in'` / `dir='out'` | 矩形向中心收缩或向外扩大展开 |
| 5-6 | `checker` | 棋盘 (Checkerboard) | `dir='horz'` / `dir='vert'` | 黑白交错网格交替滑入展开 |
| 7-8 | `comb` | 梳理 (Comb) | `dir='horz'` / `dir='vert'` | 奇偶条纹从两侧相对穿插交错滑入 |
| 9-16 | `cover` | 覆盖 (Cover) | 8 方向: `d`, `l`, `r`, `u`, `ld`, `lu`, `rd`, `ru` | 新幻灯片从 8 个不同方向滑入覆盖在旧页上 |
| 17-18 | `cut` | 快速切入 (Cut) | 普通切入 / `thruBlk=True` (黑屏切入) | 极速切换，支持经由瞬间黑屏 |
| 19 | `dissolve` | 溶解 (Dissolve) | - | 伪随机微小像素颗粒溶解过渡 |
| 20-21 | `fade` | 淡入淡出 (Fade) | 平滑淡入 / `thruBlk=True` (黑屏淡出) | 透明度平滑过渡或先黑屏后淡入 |
| 22 | `newsflash` | 旋转飞入 (Newsflash) | - | 围绕中心点旋转 720 度并伴随比例放大 |
| 23-26 | `push` | 推移 (Push) | 4 方向: `d`, `l`, `r`, `u` | 新幻灯片将旧幻灯片向指定方向推出视野 |
| 27-28 | `randomBar`| 随机线条 (Random Bars) | `dir='horz'` / `dir='vert'` | 随机顺序出现的细条纹逐渐拼合新画面 |
| 29-31 | `circle`, `diamond`, `plus` | 形状 (Shape) | 形状扩展 | 圆形、菱形、十字形从中心向外扩展 |
| 32-35 | `split` | 分割 (Split) | 4 变体: `horzIn`, `horzOut`, `vertIn`, `vertOut` | 水平/垂直方向由中心向两边展开或由外向内合拢 |
| 36-39 | `strips` | 阶梯状 (Strips) | 4 对角: `ld`, `lu`, `rd`, `ru` | 对角线阶梯锯齿状切入 |
| 40-47 | `pull` (uncover)| 揭开 (Uncover) | 8 方向: `d`, `l`, `r`, `u`, `ld`, `lu`, `rd`, `ru` | 旧幻灯片向指定方向移开，露出下方的新幻灯片 |
| 48 | `wedge` | 扇形展开 (Wedge) | - | 顶部中心开始双向顺时针与逆时针扇形展开 |
| 49-53 | `wheel` | 轮子 (Wheel Clockwise) | 5 变体: 1, 2, 3, 4, 8 辐条 | 1/2/3/4/8 辐条顺时针旋转扇区扫描展开 |
| 54-57 | `wipe` | 擦除 (Wipe) | 4 方向: `d`, `l`, `r`, `u` | 匀速单向边缘平直擦除 |
| 58 | `random` | 随机切换 (Random Transition) | 运行时随机挑选 | 随机挑选 58 种动效之一 |

---

## 3. Architecture & Class Diagram

```
+--------------------------------------------------------------------------------+
|                             PresentationView                                   |
|                                     │                                          |
|                                     ▼                                          |
|                              LecternWorkspace                                  |
|         (Shortcuts: F5 -> from start, Shift+F5 -> from current)                |
|                                     │                                          |
|                                     ▼                                          |
|                              SlideShowView                                     |
|  - QWidget (Frameless, Black background, Double-buffered QPainter)              |
|  - Aspect-ratio letterboxed stage (W x H)                                      |
|  - Navigation state: order, pos, in_transition, blank, ended, goto_buf         |
|  - Popbar (Floating bottom-left Prev/Menu/Next)                                |
|  - QMenu right-click context menu (Next/Prev/GoTo/Screen/End)                   |
|  - 60 FPS QTimer driving transition frames                                     |
|                                     │                                          |
|                                     ▼                                          |
|                         transitions.py (Engine)                                |
|  - TRANSITIONS catalogue (58 effects + none + random)                          |
|  - render_transition_frame(painter, img_from, img_to, trans, progress, W, H)   |
|  - render_slide_to_image(slide, presentation, width, height) -> QImage         |
+--------------------------------------------------------------------------------+
```

---

## 4. Edge Cases & Robustness
1. **Empty Presentation**:
   - If presentation has 0 slides, display an informational warning dialog and abort gracefully without raising exceptions.
2. **Hidden Slides**:
   - Normal linear playback (`next()`/`prev()`) automatically skips hidden slides (`slide.hidden == True`).
   - Direct jump via "Go to Slide" or preview mode allows viewing hidden slides.
3. **Mid-Transition Interruption**:
   - If the user clicks or presses a key while a transition animation is still playing, the animation is immediately completed to progress=1.0 and finalized, ensuring zero lag or visual corruption.
4. **Blank Screen Handling**:
   - Pressing 'B' or '.' blanks the screen to pitch black; pressing 'W' or ',' blanks the screen to white.
   - Any keypress or mouse click while blank immediately restores the active slide without advancing slide index.
5. **Direct Number Navigation (`goto_buf`)**:
   - User types digit keys (e.g. '2') -> floating on-screen overlay shows "定位到幻灯片 2".
   - Pressing Enter jumps directly to slide 2; pressing non-digit cancels buffer.
6. **Auto-Advance & Loop Timing**:
   - `slide.transition.after`: If set to `N` seconds, a single-shot timer automatically calls `next()` when reached.
   - If `presentation.show.loop` is True, reaching past the last slide loops back to slide 0.
   - Otherwise, displays standard end screen ("放映结束，单击鼠标退出。").
7. **High-DPI & Multi-Monitor**:
   - Support arbitrary display resolutions (Retina/4K/ultrawide) via scaled double-buffered QImage blit.
   - Pure black letterbox bars fill remaining screen area.
8. **Internationalization (i18n)**:
   - 100% of labels, tooltips, popup items, and overlays use `safe_tr()` with idiomatic Chinese translations and English fallbacks.

---

## 5. Verification Plan
- Unit tests for transitions catalogue, metadata queries, and transition frame rendering algorithms (`tests/unit/presentation/test_transitions.py`).
- GUI tests for `SlideShowView` lifecycle, keyboard navigation, context menu, blanking, and direct goto (`tests/gui/test_slideshow.py`).
- Zero regressions across existing presentation test suite.
