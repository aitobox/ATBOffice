"""Unit tests for Lectern magnetic shape connectors, routing, and SmartArt layouts."""

import xml.etree.ElementTree as ET

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication

from atboffice.modules.presentation.io.pptx_reader import PptxReader
from atboffice.modules.presentation.io.writer_shapes import shape_to_xml
from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.smartart.engine import (
    SmartArtItem,
    relayout,
    to_shapes,
)
from atboffice.modules.presentation.smartart.layouts.hierarchy_layouts import (
    make_org_chart,
)
from atboffice.modules.presentation.smartart.layouts.process_layouts import (
    make_chevron,
)
from atboffice.modules.presentation.views.geometry_helper import (
    calculate_connector_route,
    create_shape_path,
    get_shape_connection_sites,
)
from atboffice.modules.presentation.views.shape_item import (
    HandleType,
    ShapeGraphicsItem,
)
from atboffice.modules.presentation.views.slide_canvas import SlideScene


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestShapeConnectionSitesAndRouting:
    """Tests for connection site calculations and connector routing."""

    def test_standard_shape_connection_sites(self):
        # 100x60 rectangle
        sites = get_shape_connection_sites("rect", 100.0, 60.0)
        assert len(sites) == 4
        # 0: Top, 1: Right, 2: Bottom, 3: Left
        assert sites[0] == (50.0, 0.0)
        assert sites[1] == (100.0, 30.0)
        assert sites[2] == (50.0, 60.0)
        assert sites[3] == (0.0, 30.0)

    def test_triangle_connection_sites(self):
        # 100x80 triangle with default center apex
        sites = get_shape_connection_sites("triangle", 100.0, 80.0, {"adj": 50000})
        assert len(sites) == 4
        assert sites[0] == (50.0, 0.0)   # Apex
        assert sites[2] == (50.0, 80.0)  # Bottom center

    def test_straight_connector_route(self):
        route = calculate_connector_route((10.0, 20.0), (100.0, 150.0), geom="straightConnector1")
        assert route == [(10.0, 20.0), (100.0, 150.0)]

    def test_bent_connector_elbow_route_horizontal(self):
        # Exiting horizontal sites (site 1: right to site 3: left)
        route = calculate_connector_route(
            (0.0, 0.0), (100.0, 60.0), geom="bentConnector3", site1_idx=1, site2_idx=3
        )
        assert len(route) == 4
        assert route[0] == (0.0, 0.0)
        assert route[1] == (50.0, 0.0)   # Stepped halfway along x
        assert route[2] == (50.0, 60.0)  # Stepped along y
        assert route[3] == (100.0, 60.0)

    def test_bent_connector_elbow_route_vertical(self):
        # Exiting vertical sites (site 2: bottom to site 0: top)
        route = calculate_connector_route(
            (0.0, 0.0), (80.0, 100.0), geom="bentConnector3", site1_idx=2, site2_idx=0
        )
        assert len(route) == 4
        assert route[0] == (0.0, 0.0)
        assert route[1] == (0.0, 50.0)   # Stepped halfway along y
        assert route[2] == (80.0, 50.0)  # Stepped along x
        assert route[3] == (80.0, 100.0)

    def test_connector_path_generation(self):
        adj = {"route": [[0.0, 0.0], [50.0, 0.0], [50.0, 100.0], [100.0, 100.0]]}
        path = create_shape_path("bentConnector3", 100.0, 100.0, adj=adj)
        assert not path.isEmpty()
        assert path.elementCount() == 4


class TestConnectorModelAndIO:
    """Tests for cxn_start, cxn_end properties on Shape and PPTX serialization."""

    def test_connector_model_serialization(self):
        sh = Shape(
            id="c1",
            type="line",
            geom="straightConnector1",
            x=10.0,
            y=20.0,
            w=100.0,
            h=50.0,
            cxn_start={"id": "shape_A", "idx": 1},
            cxn_end={"id": "shape_B", "idx": 3},
        )
        assert sh.is_connector is True

        d = sh.to_dict()
        assert d["cxn_start"] == {"id": "shape_A", "idx": 1}
        assert d["cxn_end"] == {"id": "shape_B", "idx": 3}

        restored = Shape.from_dict(d)
        assert restored.cxn_start == {"id": "shape_A", "idx": 1}
        assert restored.cxn_end == {"id": "shape_B", "idx": 3}
        assert restored.is_connector is True

        cloned = sh.clone()
        assert cloned.cxn_start == sh.cxn_start
        assert cloned.cxn_end == sh.cxn_end

    def test_pptx_reader_parses_cxn_sp(self):
        xml_content = """<p:cxnSp xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                                   xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
            <p:nvCxnSpPr>
                <p:cNvPr id="55" name="Elbow Connector 5"/>
                <p:cNvCxnSpPr>
                    <a:stCxn id="10" idx="2"/>
                    <a:endCxn id="20" idx="0"/>
                </p:cNvCxnSpPr>
                <p:nvPr/>
            </p:nvCxnSpPr>
            <p:spPr>
                <a:xfrm>
                    <a:off x="914400" y="914400"/>
                    <a:ext cx="1828800" cy="914400"/>
                </a:xfrm>
                <a:prstGeom prst="bentConnector3"/>
                <a:ln w="12700"/>
            </p:spPr>
        </p:cxnSp>"""
        elem = ET.fromstring(xml_content)
        reader = PptxReader.__new__(PptxReader)
        parsed = reader._parse_shape(elem, "ppt/slides/slide1.xml", {})

        assert parsed is not None
        assert parsed.id == "55"
        assert parsed.is_connector is True
        assert parsed.geom == "bentConnector3"
        assert parsed.cxn_start == {"id": "10", "idx": 2}
        assert parsed.cxn_end == {"id": "20", "idx": 0}

    def test_pptx_writer_serializes_cxn_sp(self):
        sh = Shape(
            id="c1",
            type="line",
            geom="straightConnector1",
            x=10.0,
            y=20.0,
            w=100.0,
            h=50.0,
            cxn_start={"id": "shape_1", "idx": 1},
            cxn_end={"id": "shape_2", "idx": 3},
        )
        xml_out = shape_to_xml(sh, id_resolver=lambda sid: sid)
        assert xml_out.startswith("<p:cxnSp>")
        assert '<a:stCxn id="shape_1" idx="1"/>' in xml_out
        assert '<a:endCxn id="shape_2" idx="3"/>' in xml_out


class TestMagneticSnappingAndDynamicRecalculation:
    """Tests for interactive magnetic snap handles and automatic route updates."""

    def test_connector_has_start_and_end_handles(self, qapp):
        sh = Shape(id="c1", type="line", geom="bentConnector3", x=50.0, y=50.0, w=100.0, h=60.0)
        item = ShapeGraphicsItem(sh)
        handle_types = [h.handle_type for h in item._handles]
        assert HandleType.START in handle_types
        assert HandleType.END in handle_types
        assert HandleType.NW not in handle_types  # Connectors don't use 8-corner resize handles

    def test_magnetic_snap_endpoint_dragging(self, qapp):
        scene = SlideScene(slide_width=800.0, slide_height=600.0)
        # Target shape at (200, 200, 100, 60)
        # Site 3 (left center) is at (200, 230)
        target = Shape(
            id="target_1", type="shape", geom="rect", x=200.0, y=200.0, w=100.0, h=60.0
        )
        scene.slide.shapes.append(target)
        target_item = ShapeGraphicsItem(target)
        scene.addItem(target_item)
        scene._items_by_id[target.id] = target_item

        # Connector at (50, 50, 80, 80)
        conn = Shape(
            id="conn_1",
            type="line",
            geom="straightConnector1",
            x=50.0,
            y=50.0,
            w=80.0,
            h=80.0,
        )
        scene.slide.shapes.append(conn)
        conn_item = ShapeGraphicsItem(conn)
        scene.addItem(conn_item)
        scene._items_by_id[conn.id] = conn_item

        # Drag end handle to (195, 232) -> within 15px snap radius of site 3 (200, 230)
        conn_item._do_drag_connector_endpoint(
            HandleType.END, QPointF(195.0, 232.0), Qt.KeyboardModifier.NoModifier
        )

        # Snapped to exact connection site
        p2 = conn.adj.get("p2")
        assert p2 == [200.0, 230.0]
        assert conn_item._pending_cxn_end == {"id": "target_1", "idx": 3}

        # End drag commits connection
        end_handle = next(h for h in conn_item._handles if h.handle_type == HandleType.END)
        conn_item.end_handle_drag(end_handle)
        assert conn.cxn_end == {"id": "target_1", "idx": 3}

    def test_automatic_connector_recalculation_on_connected_shape_move(self, qapp):
        scene = SlideScene(slide_width=800.0, slide_height=600.0)

        # Shape A at (50, 50, 100, 60) -> site 1 (right) is (150, 80)
        shape_a = Shape(id="A", type="shape", geom="rect", x=50.0, y=50.0, w=100.0, h=60.0)
        item_a = ShapeGraphicsItem(shape_a)
        scene.addItem(item_a)
        scene._items_by_id["A"] = item_a

        # Shape B at (300, 150, 100, 60) -> site 3 (left) is (300, 180)
        shape_b = Shape(id="B", type="shape", geom="rect", x=300.0, y=150.0, w=100.0, h=60.0)
        item_b = ShapeGraphicsItem(shape_b)
        scene.addItem(item_b)
        scene._items_by_id["B"] = item_b

        # Connector linking Shape A site 1 to Shape B site 3
        conn = Shape(
            id="conn_AB",
            type="line",
            geom="bentConnector3",
            x=150.0,
            y=80.0,
            w=150.0,
            h=100.0,
            cxn_start={"id": "A", "idx": 1},
            cxn_end={"id": "B", "idx": 3},
        )
        item_conn = ShapeGraphicsItem(conn)
        scene.addItem(item_conn)
        scene._items_by_id["conn_AB"] = item_conn

        # Initial endpoints
        scene.update_connected_connectors("A")
        assert conn.adj["p1"] == [150.0, 80.0]
        assert conn.adj["p2"] == [300.0, 180.0]

        # Now move Shape B down to y=250.0 (site 3 becomes 300, 280)
        item_b.setPos(QPointF(300.0, 250.0))
        shape_b.x = 300.0
        shape_b.y = 250.0

        # Trigger automatic update
        scene.update_connected_connectors("B")

        # Connector start remains at Shape A (150, 80)
        # while end magnetically follows Shape B to (300, 280)
        assert conn.adj["p1"] == [150.0, 80.0]
        assert conn.adj["p2"] == [300.0, 280.0]
        assert conn.h == 200.0  # Height increased from 100 to 200 to accommodate move
        assert len(conn.adj["route"]) == 4  # Elbow route recomputed


class TestSmartArtBaseLayouts:
    """Tests for hierarchical org charts and linear chevron layouts."""

    def test_make_org_chart_layout(self):
        items = [
            SmartArtItem(
                id="ceo",
                text="CEO",
                kids=[
                    SmartArtItem(id="cto", text="CTO"),
                    SmartArtItem(id="cfo", text="CFO"),
                ],
            )
        ]
        box = {"x": 100.0, "y": 50.0, "w": 600.0, "h": 400.0}
        shapes = make_org_chart(items, box)

        nodes = [s for s in shapes if s.get("role") == "node"]
        connectors = [s for s in shapes if s.get("role") == "conn"]

        assert len(nodes) == 3
        assert len(connectors) == 2
        # CEO is top level, CTO and CFO are child level
        ceo_node = next(s for s in nodes if s.get("itemId") == "ceo")
        cto_node = next(s for s in nodes if s.get("itemId") == "cto")
        assert cto_node["y"] > ceo_node["y"]  # Hierarchical placement down

        # Connectors have parentId and itemId for magnetic connection
        assert connectors[0]["parentId"] == "ceo"
        assert connectors[0]["itemId"] in ("cto", "cfo")

    def test_make_chevron_process_layout(self):
        items = [
            SmartArtItem(id="p1", text="Step 1"),
            SmartArtItem(id="p2", text="Step 2"),
            SmartArtItem(id="p3", text="Step 3"),
        ]
        box = {"x": 50.0, "y": 100.0, "w": 700.0, "h": 200.0}
        shapes = make_chevron(items, box)

        chevrons = [s for s in shapes if s.get("role") == "node"]
        assert len(chevrons) == 3
        assert all(s.get("geom") == "chevron" for s in chevrons)
        # Sequential left-to-right progression
        assert chevrons[0]["x"] < chevrons[1]["x"] < chevrons[2]["x"]

    def test_smartart_relayout_and_to_shapes_with_connectors(self):
        sa_def = {
            "layout": "orgChart",
            "items": [{"id": "r", "t": "Boss", "kids": [{"id": "k1", "t": "Worker"}]}],
        }
        group_shape = Shape(
            id="g_sa",
            type="group",
            name="SmartArt",
            x=50.0,
            y=50.0,
            w=600.0,
            h=400.0,
            sa=sa_def,
        )
        relayout(group_shape)
        assert len(group_shape.kids) >= 3  # Boss node, Worker node, connector

        conn_shapes = [k for k in group_shape.kids if k.is_connector]
        assert len(conn_shapes) >= 1
        conn = conn_shapes[0]
        assert conn.cxn_start is not None
        assert conn.cxn_end is not None

        # Convert to plain shapes
        to_shapes(group_shape)
        assert group_shape.sa is None
        # Connectors retain connection links
        assert conn.cxn_start is not None
        assert conn.cxn_end is not None
