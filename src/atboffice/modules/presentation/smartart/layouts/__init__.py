"""Registry for all 26 SmartArt layouts across 7 categories."""

from __future__ import annotations

from typing import Any

from atboffice.modules.presentation.smartart.layouts.cycle_layouts import (
    make_continuous_cycle,
    make_cycle,
    make_radial,
)
from atboffice.modules.presentation.smartart.layouts.hierarchy_layouts import (
    make_h_hierarchy,
    make_hierarchy,
    make_org_chart,
)
from atboffice.modules.presentation.smartart.layouts.list_layouts import (
    make_block_list,
    make_h_bullet,
    make_lined_list,
    make_stacked_list,
    make_v_box,
    make_vertical_bullet,
)
from atboffice.modules.presentation.smartart.layouts.matrix_layouts import (
    make_matrix,
)
from atboffice.modules.presentation.smartart.layouts.process_layouts import (
    make_chevron,
    make_continuous_arrow,
    make_process,
    make_step_up,
    make_timeline,
    make_v_process,
)
from atboffice.modules.presentation.smartart.layouts.pyramid_layouts import (
    make_inverted_pyramid,
    make_pyramid,
    make_pyramid_list,
)
from atboffice.modules.presentation.smartart.layouts.relationship_layouts import (
    make_funnel,
    make_linear_venn,
    make_target,
    make_venn,
)

CATEGORIES: list[tuple[str, str]] = [
    ("list", "List"),
    ("process", "Process"),
    ("cycle", "Cycle"),
    ("hierarchy", "Hierarchy"),
    ("relationship", "Relationship"),
    ("matrix", "Matrix"),
    ("pyramid", "Pyramid"),
]

LAYOUTS: list[dict[str, Any]] = [
    # List (6)
    {
        "id": "blockList",
        "name": "Basic Block List",
        "cat": "list",
        "desc": "Blocks of equal size, in rows; sub-items become bullets inside each block.",
        "make": make_block_list,
    },
    {
        "id": "verticalBullet",
        "name": "Vertical Bullet List",
        "cat": "list",
        "desc": "Items stacked in bars, each with its sub-items as a bulleted list below.",
        "make": make_vertical_bullet,
        "levels": 2,
    },
    {
        "id": "stackedList",
        "name": "Stacked List",
        "cat": "list",
        "desc": "Each item in a circle, its sub-items on a card beside it.",
        "make": make_stacked_list,
        "levels": 2,
    },
    {
        "id": "hBullet",
        "name": "Horizontal Bullet List",
        "cat": "list",
        "desc": "Columns, each with a heading and its sub-items as bullets.",
        "make": make_h_bullet,
        "levels": 2,
    },
    {
        "id": "linedList",
        "name": "Lined List",
        "cat": "list",
        "desc": "Items under rules, with their sub-items to the right.",
        "make": make_lined_list,
        "levels": 2,
    },
    {
        "id": "vBox",
        "name": "Vertical Box List",
        "cat": "list",
        "desc": "A labelled box for each item, holding its sub-items.",
        "make": make_v_box,
        "levels": 2,
    },
    # Process (6)
    {
        "id": "process",
        "name": "Basic Process",
        "cat": "process",
        "desc": "Steps in a row, joined by arrows.",
        "make": make_process,
    },
    {
        "id": "chevron",
        "name": "Basic Chevron Process",
        "cat": "process",
        "desc": "Steps as chevrons pointing onward.",
        "make": make_chevron,
    },
    {
        "id": "stepUp",
        "name": "Step Up Process",
        "cat": "process",
        "desc": "Steps that climb, each a little higher than the last.",
        "make": make_step_up,
    },
    {
        "id": "continuousArrow",
        "name": "Continuous Arrow Process",
        "cat": "process",
        "desc": "Steps along one arrow, for a flow that keeps going.",
        "make": make_continuous_arrow,
    },
    {
        "id": "vProcess",
        "name": "Vertical Process",
        "cat": "process",
        "desc": "Steps from top to bottom, joined by arrows.",
        "make": make_v_process,
    },
    {
        "id": "timeline",
        "name": "Basic Timeline",
        "cat": "process",
        "desc": "Events along a line, in order.",
        "make": make_timeline,
    },
    # Cycle (3)
    {
        "id": "cycle",
        "name": "Basic Cycle",
        "cat": "cycle",
        "desc": "Stages that repeat, in a circle with arrows between them.",
        "make": make_cycle,
    },
    {
        "id": "radial",
        "name": "Basic Radial",
        "cat": "cycle",
        "desc": "A central idea with the items that relate to it around it.",
        "make": make_radial,
        "levels": 2,
    },
    {
        "id": "continuousCycle",
        "name": "Continuous Cycle",
        "cat": "cycle",
        "desc": "Stages around a ring, for something that never stops.",
        "make": make_continuous_cycle,
    },
    # Hierarchy (3)
    {
        "id": "orgChart",
        "name": "Organization Chart",
        "cat": "hierarchy",
        "desc": "People or units and who reports to whom, top down.",
        "make": make_org_chart,
        "levels": 9,
        "tree": True,
    },
    {
        "id": "hierarchy",
        "name": "Hierarchy",
        "cat": "hierarchy",
        "desc": "Levels from the top down, each joined straight to the one above.",
        "make": make_hierarchy,
        "levels": 9,
        "tree": True,
    },
    {
        "id": "hHierarchy",
        "name": "Horizontal Hierarchy",
        "cat": "hierarchy",
        "desc": "A tree that grows from left to right.",
        "make": make_h_hierarchy,
        "levels": 9,
        "tree": True,
    },
    # Relationship (4)
    {
        "id": "venn",
        "name": "Basic Venn",
        "cat": "relationship",
        "desc": "Overlapping circles for ideas that share something.",
        "make": make_venn,
    },
    {
        "id": "target",
        "name": "Basic Target",
        "cat": "relationship",
        "desc": "Rings inside rings, from the whole to the core.",
        "make": make_target,
    },
    {
        "id": "linearVenn",
        "name": "Linear Venn",
        "cat": "relationship",
        "desc": "Overlapping circles in a row, for ideas that follow on.",
        "make": make_linear_venn,
    },
    {
        "id": "funnel",
        "name": "Funnel",
        "cat": "relationship",
        "desc": "Ideas that narrow down through layers to one result at the bottom.",
        "make": make_funnel,
    },
    # Matrix (1)
    {
        "id": "matrix",
        "name": "Basic Matrix",
        "cat": "matrix",
        "desc": "Items in a grid of equal quarters, for comparing them side by side.",
        "make": make_matrix,
    },
    # Pyramid (3)
    {
        "id": "pyramid",
        "name": "Basic Pyramid",
        "cat": "pyramid",
        "desc": "Levels that build on one another, broadest at the bottom.",
        "make": make_pyramid,
    },
    {
        "id": "invertedPyramid",
        "name": "Inverted Pyramid",
        "cat": "pyramid",
        "desc": "Levels from the broadest at the top to the narrowest at the bottom.",
        "make": make_inverted_pyramid,
    },
    {
        "id": "pyramidList",
        "name": "Pyramid List",
        "cat": "pyramid",
        "desc": "Items on cards laid over a pyramid, from the top down.",
        "make": make_pyramid_list,
    },
]


def get_layout(layout_id: str) -> dict[str, Any] | None:
    """Find layout definition dictionary by id."""
    for l in LAYOUTS:
        if l["id"] == layout_id:
            return l
    return None
