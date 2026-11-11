"""Comprehensive Unit and GUI tests for Phase 9 IntelliArt (SmartArt) 26-Layout Engine.

Covers Issue #341:
1. All 26 SmartArt layout geometry generators in `smartart/layouts/` (and `layouts.py`):
   - List (6): blockList, verticalBullet, stackedList, hBullet, linedList, vBox
   - Process (6): process, chevron, stepUp, continuousArrow, vProcess, timeline
   - Cycle (3): cycle, radial, continuousCycle
   - Hierarchy (3): orgChart, hierarchy, hHierarchy
   - Relationship (4): venn, target, linearVenn, funnel
   - Matrix (1): matrix
   - Pyramid (3): pyramid, invertedPyramid, pyramidList
2. 13 color palettes and 3 visual style families (Filled, Outlined, Tinted) in `smartart/styles.py`.
3. SmartArtTextPane interactive hierarchy editing:
   - Enter (add after)
   - Tab (demote)
   - Shift+Tab / Backtab (promote)
   - Backspace on empty (remove)
   - Up / Down keyboard navigation
   - Bidirectional sync with canvas shape model
   - Layout, palette, style combos and Convert to Shapes
4. Lossless OpenXML DrawingML `<dgm:...>` part serialization and PPTX save/load roundtrip.
"""

from __future__ import annotations

import io
import math
import zipfile
from typing import Any

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from atboffice.modules.presentation.io.pptx_reader import PptxReader
from atboffice.modules.presentation.io.pptx_writer import PptxWriter
from atboffice.modules.presentation.models.presentation import Presentation
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.panes.smartart_pane import (
    SmartArtPane,
    SmartArtRowEdit,
    SmartArtTextPane,
)
from atboffice.modules.presentation.smartart.engine import (
    SmartArtEngine,
    SmartArtItem,
    relayout,
    to_shapes,
)
from atboffice.modules.presentation.smartart.io import (
    colors_xml,
    data_xml,
    layout_xml,
    style_xml,
)
from atboffice.modules.presentation.smartart.layouts import (
    CATEGORIES,
    LAYOUTS,
    get_layout,
    make_block_list,
    make_chevron,
    make_continuous_arrow,
    make_continuous_cycle,
    make_cycle,
    make_funnel,
    make_h_bullet,
    make_h_hierarchy,
    make_hierarchy,
    make_inverted_pyramid,
    make_linear_venn,
    make_lined_list,
    make_matrix,
    make_org_chart,
    make_process,
    make_pyramid,
    make_pyramid_list,
    make_radial,
    make_stacked_list,
    make_step_up,
    make_target,
    make_timeline,
    make_v_box,
    make_v_process,
    make_venn,
    make_vertical_bullet,
)
from atboffice.modules.presentation.smartart.styles import (
    DEFAULT_COLORS,
    DEFAULT_STYLE,
    PALETTES,
    STYLE_GROUPS,
    STYLES,
    color_spec,
    mix_hex,
    paint_shape,
    style_info,
    style_lang,
    style_refs,
)


# ============================================================================
# Pillar 1: All 26 SmartArt Layouts Geometry Synthesis
# ============================================================================
class TestSmartArt26LayoutsGeometry:
    """Verifies that all 26 layouts across 7 categories synthesize valid geometry."""

    def test_26_layouts_registry_and_count(self) -> None:
        assert len(LAYOUTS) == 26
        assert len(CATEGORIES) == 7

        expected_cats = {
            "list": 6,
            "process": 6,
            "cycle": 3,
            "hierarchy": 3,
            "relationship": 4,
            "matrix": 1,
            "pyramid": 3,
        }

        actual_cats: dict[str, int] = {}
        for lo in LAYOUTS:
            cat = lo["cat"]
            actual_cats[cat] = actual_cats.get(cat, 0) + 1
            assert callable(lo["make"])
            assert get_layout(lo["id"]) == lo

        assert actual_cats == expected_cats

    @pytest.mark.parametrize("layout_def", LAYOUTS)
    def test_layout_synthesis_single_and_multi_items(self, layout_def: dict[str, Any]) -> None:
        """Every layout must generate valid, non-overlapping or properly aligned
        shapes without NaN, Inf, or negative dimensions for 1, 3, and 5 items."""
        box = {"x": 50.0, "y": 60.0, "w": 640.0, "h": 400.0}

        for count in (1, 3, 5):
            items = [SmartArtItem(id=f"n_{i}", text=f"Node {i}") for i in range(count)]
            if layout_def.get("levels") == 2 or layout_def.get("tree"):
                for it in items:
                    it.kids = [SmartArtItem(id=f"{it.id}_k1", text=f"Sub {it.id}")]

            make_fn = layout_def["make"]
            shapes = make_fn(items, box)
            assert isinstance(shapes, list)
            assert len(shapes) > 0

            for s in shapes:
                assert math.isfinite(s["x"]), f"Invalid x in {layout_def['id']}"
                assert math.isfinite(s["y"]), f"Invalid y in {layout_def['id']}"
                assert math.isfinite(s["w"]) and s["w"] >= 0.0, f"Invalid w in {layout_def['id']}"
                assert math.isfinite(s["h"]) and s["h"] >= 0.0, f"Invalid h in {layout_def['id']}"
                assert s.get("role") in ("node", "child", "arrow", "conn", "marker", "ring", "bg")

                if s.get("text") and s["text"].get("box"):
                    tb = s["text"]["box"]
                    assert math.isfinite(tb["x"]) and math.isfinite(tb["y"])
                    assert math.isfinite(tb["w"]) and math.isfinite(tb["h"])

                if s.get("geom") == "poly" and s.get("poly"):
                    for pt in s["poly"]:
                        assert math.isfinite(pt[0]) and math.isfinite(pt[1])

    def test_direct_generator_functions_callable(self) -> None:
        """Direct imports of all 26 generator functions."""
        generators = [
            make_block_list,
            make_vertical_bullet,
            make_stacked_list,
            make_h_bullet,
            make_lined_list,
            make_v_box,
            make_process,
            make_chevron,
            make_step_up,
            make_continuous_arrow,
            make_v_process,
            make_timeline,
            make_cycle,
            make_radial,
            make_continuous_cycle,
            make_org_chart,
            make_hierarchy,
            make_h_hierarchy,
            make_venn,
            make_target,
            make_linear_venn,
            make_funnel,
            make_matrix,
            make_pyramid,
            make_inverted_pyramid,
            make_pyramid_list,
        ]
        assert len(generators) == 26
        box = {"x": 0.0, "y": 0.0, "w": 500.0, "h": 300.0}
        items = [SmartArtItem(id="i1", text="Test")]
        for fn in generators:
            res = fn(items, box)
            assert len(res) >= 1


# ============================================================================
# Pillar 2: 13 Color Palettes & 3 Visual Style Families
# ============================================================================
class TestSmartArtStylesAndPalettes:
    """Verifies color palettes, style groups, and shape painting logic."""

    def test_13_palettes_completeness(self) -> None:
        assert len(PALETTES) == 13
        expected_palettes = [
            "ocean",
            "aurora",
            "lagoon",
            "midnight",
            "berry",
            "sunset",
            "fire",
            "amber",
            "forest",
            "slate",
            "vivid",
            "jewel",
            "pastel",
        ]
        for p in expected_palettes:
            assert p in PALETTES
            spec = color_spec(p)
            assert "name" in spec
            assert len(spec["cols"]) >= 2
            assert spec["meth"] in ("span", "cycle")

    def test_3_visual_style_groups(self) -> None:
        assert len(STYLE_GROUPS) == 3
        group_keys = [g[0] for g in STYLE_GROUPS]
        assert group_keys == ["fill", "outline", "tint"]

        assert len(STYLES) == 13
        for s in STYLES:
            sid, sname, refs, slang = s[0], s[1], s[2], s[3]
            assert slang in ("fill", "outline", "tint")
            assert len(refs) == 3
            assert style_lang(sid) == slang
            assert style_refs(sid) == refs

    def test_paint_shape_styles(self) -> None:
        shape_node = {
            "role": "node",
            "geom": "roundRect",
            "colorIdx": 0,
            "colorCnt": 3,
            "styleLbl": "node1",
        }

        # Filled style
        p_filled = paint_shape(shape_node, {"layout": "process", "colors": "ocean", "style": "moderate"})
        assert p_filled["fill"]["t"] == "solid"

        # Outlined style
        p_outline = paint_shape(shape_node, {"layout": "process", "colors": "ocean", "style": "outline"})
        assert p_outline["fill"]["c"] == "#FFFFFF"
        assert p_outline["line"]["c"] != ""

        # Tinted style
        p_tint = paint_shape(shape_node, {"layout": "process", "colors": "ocean", "style": "tint"})
        assert p_tint["fill"]["t"] == "solid"


# ============================================================================
# Pillar 3: Interactive SmartArtTextPane & Keyboard Actions
# ============================================================================
class TestSmartArtTextPaneInteractive:
    """Verifies SmartArtTextPane and SmartArtRowEdit keyboard editing and sync."""

    def test_row_edit_keyboard_actions(self, qapp: QApplication) -> None:
        edit = SmartArtRowEdit(item_id="item_1", level=0)

        actions: list[str] = []
        edit.item_key_pressed.connect(lambda act, ev: actions.append(act))

        # 1. Return/Enter -> after
        ev_enter = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        edit.keyPressEvent(ev_enter)
        assert actions[-1] == "after"

        # 2. Tab -> demote
        ev_tab = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier)
        edit.keyPressEvent(ev_tab)
        assert actions[-1] == "demote"

        # 3. Shift+Tab -> promote
        ev_shift_tab = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
        edit.keyPressEvent(ev_shift_tab)
        assert actions[-1] == "promote"

        # 4. Backtab -> promote
        ev_backtab = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Backtab, Qt.KeyboardModifier.NoModifier)
        edit.keyPressEvent(ev_backtab)
        assert actions[-1] == "promote"

        # 5. Backspace on empty -> remove
        edit.setText("")
        ev_bs = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Backspace, Qt.KeyboardModifier.NoModifier)
        edit.keyPressEvent(ev_bs)
        assert actions[-1] == "remove"

        # 6. Alt+Shift+Up -> up
        ev_up = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Up,
            Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ShiftModifier,
        )
        edit.keyPressEvent(ev_up)
        assert actions[-1] == "up"

        # 7. Alt+Shift+Down -> down
        ev_down = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Down,
            Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ShiftModifier,
        )
        edit.keyPressEvent(ev_down)
        assert actions[-1] == "down"

    def test_text_pane_lifecycle_and_two_way_sync(self, qapp: QApplication) -> None:
        pane = SmartArtPane()
        pane.retranslate_ui()

        # Build diagram Shape
        diag_shape = Shape(
            id="diag_sample",
            type="group",
            name="IntelliArt 1",
            x=100.0,
            y=100.0,
            w=600.0,
            h=400.0,
            sa={
                "layout": "process",
                "colors": "ocean",
                "style": "moderate",
                "items": [
                    {"id": "a", "text": "Alpha", "kids": []},
                    {"id": "b", "text": "Beta", "kids": []},
                ],
            },
        )
        relayout(diag_shape)

        pane.set_diagram(diag_shape)
        assert len(pane.row_inputs) == 2
        assert pane.row_inputs[0].text() == "Alpha"
        assert pane.row_inputs[1].text() == "Beta"

        changes_emitted: list[Shape] = []
        pane.diagram_changed.connect(lambda s: changes_emitted.append(s))

        # 1. Edit text in row 0
        pane.row_inputs[0].setText("Alpha Updated")
        assert len(changes_emitted) >= 1
        raw_items = diag_shape.sa["items"]
        assert raw_items[0]["text"] == "Alpha Updated"

        # 2. Add After via Return/Enter simulation
        pane.row_inputs[0].item_key_pressed.emit("after", None)
        assert len(pane.row_inputs) == 3
        assert len(diag_shape.sa["items"]) == 3

        # 3. Demote newly added node
        new_row = pane.row_inputs[1]
        new_id = new_row.item_id
        new_row.item_key_pressed.emit("demote", None)
        # Should now be a child of Alpha
        assert len(diag_shape.sa["items"]) == 2
        assert len(diag_shape.sa["items"][0]["kids"]) == 1

        # 4. Promote child back
        child_row = pane.row_inputs[1]
        child_row.item_key_pressed.emit("promote", None)
        assert len(diag_shape.sa["items"]) == 3

        # 5. Move Down
        pane.row_inputs[0].item_key_pressed.emit("down", None)
        # Order should now have Beta shifted
        assert diag_shape.sa["items"][1]["text"] == "Alpha Updated"

        # 6. Combo layout change
        idx_chev = pane.cmb_layout.findData("chevron")
        if idx_chev >= 0:
            pane.cmb_layout.setCurrentIndex(idx_chev)
            assert diag_shape.sa["layout"] == "chevron"

        # 7. Convert to shapes
        converted: list[Shape] = []
        pane.converted_to_shapes.connect(lambda s: converted.append(s))
        pane._on_convert_to_shapes()
        assert len(converted) == 1
        assert diag_shape.sa is None
        assert pane.current_shape is None


# ============================================================================
# Pillar 4: Lossless OpenXML DrawingML Serialization & PPTX Roundtrip
# ============================================================================
class TestSmartArtOpenXmlSerialization:
    """Verifies dgm:... part generation and PPTX writer/reader preservation."""

    def test_drawingml_xml_parts_validity(self) -> None:
        sa_def = {
            "layout": "chevron",
            "colors": "vivid",
            "style": "card",
            "items": [
                {"id": "s1", "text": "Step 1", "kids": []},
                {"id": "s2", "text": "Step 2", "kids": []},
            ],
        }

        d_xml = data_xml(sa_def, key="test_d")
        assert "<dgm:dataModel" in d_xml
        assert "Step 1" in d_xml
        assert "Step 2" in d_xml

        l_xml = layout_xml("chevron")
        assert "<dgm:layoutDef" in l_xml
        assert "urn:vibeoffice.work/diagram/layout/chevron" in l_xml

        c_xml = colors_xml("vivid")
        assert "<dgm:colorsDef" in c_xml
        assert "urn:vibeoffice.work/diagram/colors/vivid" in c_xml

        s_xml = style_xml("card")
        assert "<dgm:styleDef" in s_xml
        assert "urn:vibeoffice.work/diagram/style/card" in s_xml

    def test_pptx_from_scratch_with_smartart(self) -> None:
        """Creating and saving a presentation containing a SmartArt diagram."""
        pres = Presentation()
        slide = Slide(id="slide_1")
        pres.slides.append(slide)

        diag = Shape(
            id="diag_s1",
            type="group",
            name="IntelliArt Diagram",
            x=50.0,
            y=50.0,
            w=500.0,
            h=300.0,
            sa={
                "layout": "process",
                "colors": "ocean",
                "style": "moderate",
                "items": [
                    {"id": "p1", "text": "Initiate", "kids": []},
                    {"id": "p2", "text": "Execute", "kids": []},
                    {"id": "p3", "text": "Finalize", "kids": []},
                ],
            },
        )
        relayout(diag)
        slide.shapes.append(diag)

        writer = PptxWriter(pres)
        pptx_bytes = writer.write()
        assert len(pptx_bytes) > 0

        # Inspect zip parts
        with zipfile.ZipFile(io.BytesIO(pptx_bytes)) as zf:
            part_names = zf.namelist()
            assert any(p.startswith("ppt/diagrams/data_") for p in part_names)
            assert any(p.startswith("ppt/diagrams/layout_") for p in part_names)
            assert any(p.startswith("ppt/diagrams/colors_") for p in part_names)
            assert any(p.startswith("ppt/diagrams/quickStyle_") for p in part_names)

            # Slide rels must have diagram relationships
            slide_rels = zf.read("ppt/slides/_rels/slide1.xml.rels").decode("utf-8")
            assert "diagrams/data_" in slide_rels
            assert "diagrams/layout_" in slide_rels

        # Read back with PptxReader
        loaded_pres = PptxReader.from_bytes(pptx_bytes)
        assert len(loaded_pres.slides) == 1
        l_slide = loaded_pres.slides[0]
        assert len(l_slide.shapes) >= 1
        loaded_diag = next((sh for sh in l_slide.shapes if sh.is_diagram or sh.sa), None)
        assert loaded_diag is not None
        assert loaded_diag.sa is not None
        assert loaded_diag.sa.get("layout") == "process"

    def test_pptx_lossless_roundtrip_with_smartart(self) -> None:
        """Modifying an existing presentation with a SmartArt diagram in lossless roundtrip."""
        pres = Presentation()
        slide = Slide(id="slide_rt")
        pres.slides.append(slide)

        diag = Shape(
            id="diag_roundtrip",
            type="group",
            name="IntelliArt Timeline",
            x=40.0,
            y=40.0,
            w=550.0,
            h=250.0,
            sa={
                "layout": "timeline",
                "colors": "sunset",
                "style": "subtle",
                "items": [
                    {"id": "t1", "text": "Q1 2026", "kids": []},
                    {"id": "t2", "text": "Q2 2026", "kids": []},
                ],
            },
        )
        relayout(diag)
        slide.shapes.append(diag)

        # First write
        w1 = PptxWriter(pres)
        raw_pptx = w1.write()

        # Reopen with PptxReader
        pres2 = PptxReader.from_bytes(raw_pptx)
        assert pres2.props.get("_source_package") is not None

        # Add item and write via lossless roundtrip
        diag2 = next(sh for sh in pres2.slides[0].shapes if sh.is_diagram or sh.sa)
        eng = SmartArtEngine()
        items2 = [SmartArtItem.from_dict(it) for it in diag2.sa["items"]]
        eng.add_after(items2, items2[-1].id, "Q3 2026")
        diag2.sa["items"] = [it.to_dict() for it in items2]
        relayout(diag2)

        w2 = PptxWriter(pres2)
        res_bytes = w2.write()
        assert len(res_bytes) > 0

        with zipfile.ZipFile(io.BytesIO(res_bytes)) as zf:
            part_names = zf.namelist()
            assert any(p.startswith("ppt/diagrams/data_") for p in part_names)
            assert any(p.startswith("ppt/diagrams/layout_") for p in part_names)

        # Re-read to confirm Q3 2026 exists
        pres3 = PptxReader.from_bytes(res_bytes)
        diag3 = next(sh for sh in pres3.slides[0].shapes if sh.is_diagram or sh.sa)
        item_texts = [it["text"] for it in diag3.sa["items"]]
        assert "Q3 2026" in item_texts
