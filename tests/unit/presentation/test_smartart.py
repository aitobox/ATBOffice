"""Unit tests for Lectern IntelliArt (SmartArt) engine, layout, and UI components."""

import math

import pytest

from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.smartart.engine import (
    CATEGORIES,
    LAYOUTS,
    PALETTES,
    STYLES,
    SmartArtEngine,
    SmartArtItem,
    mix_hex,
    paint_shape,
    relayout,
    to_shapes,
)
from atboffice.modules.presentation.smartart.io import (
    colors_xml,
    data_xml,
    layout_xml,
    style_xml,
)


class TestSmartArtModelAndTreeOps:
    """Tests for outline items, tree operations, and helpers."""

    def test_new_id_and_blank(self):
        eng = SmartArtEngine()
        item_id = eng.new_id()
        assert isinstance(item_id, str) and len(item_id) > 2

        # Blank for standard process layout
        items = eng.blank("process", 4)
        assert len(items) == 4
        assert all(it.text == "" and it.kids == [] for it in items)

        # Blank for tree layout (e.g. orgChart) has kids
        tree_items = eng.blank("orgChart")
        assert len(tree_items) == 1
        assert len(tree_items[0].kids) == 3

    def test_outline_flattening(self):
        eng = SmartArtEngine()
        root = SmartArtItem(id="r", text="Root")
        c1 = SmartArtItem(id="c1", text="Child 1")
        c2 = SmartArtItem(id="c2", text="Child 2")
        gc1 = SmartArtItem(id="gc1", text="Grandchild 1")
        c1.kids.append(gc1)
        root.kids.extend([c1, c2])

        flat = eng.outline([root])
        assert len(flat) == 4
        assert [f["item"].id for f in flat] == ["r", "c1", "gc1", "c2"]
        assert [f["level"] for f in flat] == [0, 1, 2, 1]
        assert flat[0]["parent"] is None
        assert flat[1]["parent"] == root
        assert flat[2]["parent"] == c1

    def test_tree_mutations(self):
        eng = SmartArtEngine()
        items = [
            SmartArtItem(id="1", text="One"),
            SmartArtItem(id="2", text="Two"),
            SmartArtItem(id="3", text="Three"),
        ]

        # Add after
        new_id = eng.add_after(items, "2", "Two.5")
        assert len(items) == 4
        assert items[2].id == new_id
        assert items[2].text == "Two.5"

        # Demote (make Two.5 a child of Two)
        eng.demote(items, new_id)
        assert len(items) == 3
        assert len(items[1].kids) == 1
        assert items[1].kids[0].id == new_id

        # Promote (bring Two.5 back to root level)
        eng.promote(items, new_id)
        assert len(items) == 4
        assert items[2].id == new_id
        assert len(items[1].kids) == 0

        # Move Up & Move Down
        eng.move_up(items, "3")
        assert [it.id for it in items] == ["1", "2", "3", new_id]

        eng.move_down(items, "1")
        assert [it.id for it in items] == ["2", "1", "3", new_id]

        # Remove item
        eng.remove_item(items, "1")
        assert [it.id for it in items] == ["2", "3", new_id]

    def test_items_from_outline_lines(self):
        eng = SmartArtEngine()
        lines = [
            "Topic 1",
            "\tSubtopic 1.1",
            "\t\tDetail 1.1.1",
            "\tSubtopic 1.2",
            "Topic 2",
        ]
        items = eng.items_from_outline(lines)
        assert len(items) == 2
        assert items[0].text == "Topic 1"
        assert len(items[0].kids) == 2
        assert items[0].kids[0].text == "Subtopic 1.1"
        assert len(items[0].kids[0].kids) == 1
        assert items[0].kids[0].kids[0].text == "Detail 1.1.1"
        assert items[1].text == "Topic 2"


class TestAll26Layouts:
    """Tests covering all 26 layouts across 7 categories."""

    def test_layout_count_and_categories(self):
        assert len(LAYOUTS) == 26
        assert len(CATEGORIES) == 7
        cats = [c[0] for c in CATEGORIES]
        assert cats == [
            "list",
            "process",
            "cycle",
            "hierarchy",
            "relationship",
            "matrix",
            "pyramid",
        ]

        layout_ids = [lo["id"] for lo in LAYOUTS]
        assert len(set(layout_ids)) == 26

    @pytest.mark.parametrize("layout_def", LAYOUTS)
    def test_layouts_with_various_item_counts(self, layout_def):
        """Verify each of the 26 layouts for 1, 3, and 6 items."""
        eng = SmartArtEngine()
        box = {"x": 50.0, "y": 60.0, "w": 600.0, "h": 400.0}

        for n in (1, 3, 6):
            items = [SmartArtItem(id=f"item_{i}", text=f"Item {i}") for i in range(n)]
            if layout_def.get("levels") == 2 or layout_def.get("tree"):
                # Add sub-items to test hierarchical layouts
                for it in items:
                    it.kids = [SmartArtItem(id=f"{it.id}_k1", text=f"Detail {it.id}")]

            res = eng.layout(layout_def["id"], items, box)
            assert res["layout"] == layout_def["id"]
            shapes = res["shapes"]
            assert len(shapes) > 0

            # All shapes must have finite coordinates
            for s in shapes:
                assert math.isfinite(s["x"]), f"Non-finite x in {layout_def['id']}"
                assert math.isfinite(s["y"]), f"Non-finite y in {layout_def['id']}"
                assert math.isfinite(s["w"]) and s["w"] >= 0, f"Invalid w in {layout_def['id']}"
                assert math.isfinite(s["h"]) and s["h"] >= 0, f"Invalid h in {layout_def['id']}"

                # Text box must be inside or aligned with shape if text exists
                if s.get("text") and s.get("text").get("box"):
                    tb = s["text"]["box"]
                    assert math.isfinite(tb["x"]) and math.isfinite(tb["y"])
                    assert math.isfinite(tb["w"]) and math.isfinite(tb["h"])

                # Check polygon coordinates if poly geom
                if s.get("geom") == "poly" and s.get("poly"):
                    for pt in s["poly"]:
                        assert math.isfinite(pt[0]) and math.isfinite(pt[1])


class TestAdaptiveFontSizing:
    """Tests uniform maximum adaptive font sizing."""

    def test_uniform_font_sizing_rule(self):
        eng = SmartArtEngine()
        box = {"x": 0.0, "y": 0.0, "w": 500.0, "h": 300.0}

        # Short text should yield larger font size
        short_items = [
            SmartArtItem(id="1", text="A"),
            SmartArtItem(id="2", text="B"),
            SmartArtItem(id="3", text="C"),
        ]
        res_short = eng.layout("process", short_items, box)
        node_shapes_short = [s for s in res_short["shapes"] if s["role"] == "node"]
        font_short = node_shapes_short[0]["fontSize"]

        # Long text should yield smaller font size
        long_items = [
            SmartArtItem(
                id="1", text="This is a substantially longer description with many sentences."
            ),
            SmartArtItem(
                id="2", text="Comprehensive architectural transformation in Python and Qt."
            ),
            SmartArtItem(id="3", text="Ensuring robust adaptive font size without overflow."),
        ]
        res_long = eng.layout("process", long_items, box)
        node_shapes_long = [s for s in res_long["shapes"] if s["role"] == "node"]
        font_long = node_shapes_long[0]["fontSize"]

        assert font_short > font_long
        assert font_long >= 6.0
        # Uniformity: all node shapes in res_long must have identical font size
        assert all(s["fontSize"] == font_long for s in node_shapes_long)


class TestPalettesAndStyles:
    """Tests color palettes, texture styles, and shape painting."""

    def test_mix_hex(self):
        assert mix_hex("#000000", "#FFFFFF", 0.0) == "#000000"
        assert mix_hex("#000000", "#FFFFFF", 1.0) == "#FFFFFF"
        assert mix_hex("#000000", "#FFFFFF", 0.5) == "#808080"

    def test_palettes_presence(self):
        assert len(PALETTES) >= 13
        assert "ocean" in PALETTES
        assert "vivid" in PALETTES
        assert "pastel" in PALETTES

    def test_styles_presence(self):
        assert len(STYLES) >= 11
        style_ids = [s[0] for s in STYLES]
        assert "moderate" in style_ids
        assert "outline" in style_ids
        assert "tint" in style_ids

    def test_paint_shape_filled_and_outlined(self):
        sa = {"layout": "process", "colors": "ocean", "style": "moderate"}
        s_node = {
            "role": "node",
            "geom": "roundRect",
            "colorIdx": 0,
            "colorCnt": 3,
            "styleLbl": "node1",
        }
        p_filled = paint_shape(s_node, sa)
        assert p_filled["fill"]["t"] == "solid"
        assert p_filled["text"] is not None

        sa_outline = {"layout": "process", "colors": "ocean", "style": "outline"}
        p_outline = paint_shape(s_node, sa_outline)
        assert p_outline["fill"]["c"] == "#FFFFFF"
        assert p_outline["line"]["dash"] == "solid"


class TestRelayoutAndToShapes:
    """Tests relayout() and to_shapes() on Shape models."""

    def test_relayout_and_conversion(self):
        g = Shape(
            id="diagram1",
            type="group",
            name="IntelliArt 1",
            x=100.0,
            y=100.0,
            w=500.0,
            h=300.0,
            sa={
                "layout": "chevron",
                "colors": "ocean",
                "style": "moderate",
                "items": [
                    SmartArtItem(id="i1", text="Phase 1").to_dict(),
                    SmartArtItem(id="i2", text="Phase 2").to_dict(),
                    SmartArtItem(id="i3", text="Phase 3").to_dict(),
                ],
            },
        )

        relayout(g)
        assert len(g.kids) == 3
        assert all(k.sa is not None for k in g.kids)
        assert all(k.geom == "chevron" for k in g.kids)

        # Convert to shapes
        to_shapes(g)
        assert g.sa is None
        assert g.name.startswith("Group")
        assert len(g.kids) == 3
        assert all(k.sa is None for k in g.kids)


class TestSmartArtXmlIo:
    """Tests DrawingML SmartArt XML generation."""

    def test_xml_generation(self):
        sa = {
            "layout": "process",
            "colors": "ocean",
            "style": "moderate",
            "items": [
                {"id": "n1", "text": "Step 1", "kids": []},
                {"id": "n2", "text": "Step 2", "kids": []},
            ],
        }

        d_xml = data_xml(sa)
        assert "dgm:dataModel" in d_xml
        assert "Step 1" in d_xml
        assert "Step 2" in d_xml

        l_xml = layout_xml("process")
        assert "dgm:layoutDef" in l_xml
        assert "urn:vibeoffice.work/diagram/layout/process" in l_xml

        c_xml = colors_xml("ocean")
        assert "dgm:colorsDef" in c_xml

        s_xml = style_xml("moderate")
        assert "dgm:styleDef" in s_xml


class TestSmartArtTextPane:
    """Tests for SmartArtTextPane interactive widget."""

    def test_text_pane_operations_and_signals(self, qapp):
        from atboffice.modules.presentation.smartart.text_pane import SmartArtTextPane

        pane = SmartArtTextPane()
        pane.retranslate_ui()

        g = Shape(
            id="diagram_test",
            type="group",
            name="IntelliArt (process)",
            x=50.0,
            y=50.0,
            w=500.0,
            h=300.0,
            sa={
                "layout": "process",
                "colors": "ocean",
                "style": "moderate",
                "items": [
                    SmartArtItem(id="t1", text="Alpha").to_dict(),
                    SmartArtItem(id="t2", text="Beta").to_dict(),
                ],
            },
        )
        relayout(g)

        pane.set_diagram(g)
        assert len(pane.row_inputs) == 2
        assert pane.row_inputs[0].text() == "Alpha"
        assert pane.row_inputs[1].text() == "Beta"

        # Signal check
        signals_received = []
        pane.diagram_changed.connect(lambda s: signals_received.append(s))

        # Add after
        pane.active_item_id = "t2"
        pane._on_add_after()
        assert len(pane.row_inputs) == 3
        assert len(signals_received) == 1

        # Layout change
        idx_chev = pane.cmb_layout.findData("chevron")
        if idx_chev >= 0:
            pane.cmb_layout.setCurrentIndex(idx_chev)
            assert g.sa["layout"] == "chevron"

        # Convert to shapes
        converted = []
        pane.converted_to_shapes.connect(lambda s: converted.append(s))
        pane._on_convert_to_shapes()
        assert len(converted) == 1
        assert g.sa is None
