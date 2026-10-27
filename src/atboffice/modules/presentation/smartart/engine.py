"""IntelliArt (SmartArt) Layout Engine and Shape Generator."""

from __future__ import annotations

from typing import Any

from atboffice.modules.presentation.models.shape import Fill, Line, Shape
from atboffice.modules.presentation.models.text import BulletInfo, Paragraph, Run, TextBody
from atboffice.modules.presentation.smartart.item import (
    SmartArtItem,
    add_above,
    add_after,
    add_before,
    add_below,
    blank,
    demote,
    items_from_outline,
    locate,
    move_down,
    move_up,
    new_id,
    outline,
    promote,
    remove_item,
)
from atboffice.modules.presentation.smartart.layouts import (
    CATEGORIES,
    LAYOUTS,
    get_layout,
)
from atboffice.modules.presentation.smartart.palettes import (
    DEFAULT_COLORS,
    DEFAULT_STYLE,
    PALETTES,
    STYLES,
    color_spec,
    mix_hex,
    paint_shape,
    style_info,
    style_lang,
    style_refs,
)
from atboffice.modules.presentation.smartart.text_fitting import (
    LINE_HEIGHT,
    fit_text,
    fits,
    measure_with,
    wrap_text,
)


class SmartArtEngine:
    """SmartArt Layout and Tree Mutation Engine."""

    def new_id(self) -> str:
        """Generate unique item ID."""
        return new_id()

    def blank(self, layout_id: str, n: int | None = None) -> list[SmartArtItem]:
        """Generate blank items for given layout."""
        return blank(layout_id, n)

    def outline(self, items: list[SmartArtItem]) -> list[dict[str, Any]]:
        """Flatten tree to outline list."""
        return outline(items)

    def locate(self, items: list[SmartArtItem], item_id: str) -> dict[str, Any] | None:
        """Locate item in tree."""
        return locate(items, item_id)

    def add_after(self, items: list[SmartArtItem], target_id: str, text: str = "") -> str:
        """Add item after target_id."""
        return add_after(items, target_id, text)

    def add_before(self, items: list[SmartArtItem], target_id: str, text: str = "") -> str:
        """Add item before target_id."""
        return add_before(items, target_id, text)

    def add_above(self, items: list[SmartArtItem], target_id: str, text: str = "") -> str:
        """Add item above target_id."""
        return add_above(items, target_id, text)

    def add_below(self, items: list[SmartArtItem], target_id: str, text: str = "") -> str:
        """Add child item below target_id."""
        return add_below(items, target_id, text)

    def promote(self, items: list[SmartArtItem], target_id: str) -> bool:
        """Promote target item up one hierarchy level."""
        return promote(items, target_id)

    def demote(self, items: list[SmartArtItem], target_id: str) -> bool:
        """Demote target item down into previous sibling's children."""
        return demote(items, target_id)

    def move_up(self, items: list[SmartArtItem], target_id: str) -> bool:
        """Move target item up within its sibling list."""
        return move_up(items, target_id)

    def move_down(self, items: list[SmartArtItem], target_id: str) -> bool:
        """Move target item down within its sibling list."""
        return move_down(items, target_id)

    def remove_item(self, items: list[SmartArtItem], target_id: str) -> bool:
        """Remove target item from tree."""
        return remove_item(items, target_id)

    def items_from_outline(self, lines: list[str]) -> list[SmartArtItem]:
        """Convert outline lines with indentation to SmartArtItem tree."""
        return items_from_outline(lines)

    def layout(
        self,
        layout_id: str,
        items: list[SmartArtItem] | list[dict[str, Any]],
        box: dict[str, float],
        opts: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Compute layout shapes for given items within bounding box."""
        opts = opts or {}
        parsed_items: list[SmartArtItem] = [
            SmartArtItem.from_dict(it) if isinstance(it, dict) else it for it in items
        ]
        lay = get_layout(layout_id) or LAYOUTS[0]
        shapes = lay["make"](parsed_items, box)
        fit_text(shapes, opts)
        return {"layout": lay["id"], "shapes": shapes}


def relayout(group_shape: Shape, design: Any = None) -> None:
    """Recompute all child shapes of a SmartArt diagram group based on sa metadata."""
    if not group_shape.sa:
        return
    sa = group_shape.sa
    layout_id = sa.get("layout", "process")
    raw_items = sa.get("items", [])
    items = [SmartArtItem.from_dict(it) if isinstance(it, dict) else it for it in raw_items]

    box = {"x": group_shape.x, "y": group_shape.y, "w": group_shape.w, "h": group_shape.h}
    eng = SmartArtEngine()
    res = eng.layout(layout_id, items, box)
    shapes = res["shapes"]

    seen: dict[str, int] = {}
    id_map: dict[str, str] = {}
    for k in group_shape.kids:
        if k.sa and "item" in k.sa and "role" in k.sa:
            tag = f"{k.sa['item']}:{k.sa['role']}"
            seen[tag] = seen.get(tag, 0) + 1
            id_map[f"{tag}:{seen[tag]}"] = k.id

    new_kids: list[Shape] = []
    curr_seen: dict[str, int] = {}
    for s in shapes:
        item_id = s.get("itemId", "")
        role = s.get("role", "node")
        tag = f"{item_id}:{role}"
        curr_seen[tag] = curr_seen.get(tag, 0) + 1
        kid_id = id_map.get(f"{tag}:{curr_seen[tag]}") or f"s_{new_id()}"

        p = paint_shape(s, sa)
        fill_dict = p.get("fill", {})
        line_dict = p.get("line", {})

        fill_obj = (
            Fill.none()
            if fill_dict.get("t") == "none"
            else Fill.solid(fill_dict.get("c", "#FFFFFF"), alpha=float(fill_dict.get("a", 1.0)))
        )
        line_obj = (
            Line.none()
            if not line_dict or line_dict.get("t") == "none"
            else Line(
                color=line_dict.get("c", "#000000"),
                width=float(line_dict.get("w", 1.0)),
                dash=line_dict.get("dash", "solid"),
            )
        )

        geom = s.get("geom", "rect")
        poly = s.get("poly") if geom == "poly" else None
        custom_path = None
        if geom == "path" and s.get("path"):
            custom_path = {
                "paths": [
                    {"w": s["w"], "h": s["h"], "cmds": s["path"], "fill": "none", "stroke": True}
                ]
            }

        tb_obj: TextBody | None = None
        if s.get("text"):
            text_info = s["text"]
            lines = text_info.get("lines", [])
            font_sz = float(s.get("fontSize", 12.0))
            text_color = p.get("text") or "#1F2937"
            align_mode = text_info.get("align", "ctr")
            paras: list[Paragraph] = []
            for ln in lines:
                lvl = ln.get("lvl", 0)
                bullet_info = BulletInfo(type="char", char="•") if lvl else BulletInfo(type="none")
                run = Run(text=str(ln.get("t", "")), size=font_sz, color=text_color)
                paras.append(
                    Paragraph(
                        level=lvl,
                        runs=[run],
                        props={"algn": align_mode, "bu": bullet_info.to_dict()},
                    )
                )
            tb_obj = TextBody(
                anchor=text_info.get("anchor", "ctr"),
                paragraphs=paras,
                insets=(font_sz * 0.25, font_sz * 0.25, font_sz * 0.25, font_sz * 0.25),
            )

        kid_shape = Shape(
            id=kid_id,
            type="shape",
            name=f"{layout_id} {role}",
            geom=geom,
            x=s["x"],
            y=s["y"],
            w=max(0.01, s["w"]),
            h=max(0.01, s["h"]),
            rot=float(s.get("rot", 0.0)),
            fill=fill_obj,
            line=line_obj,
            text=tb_obj,
            poly=poly,
            custom_path=custom_path,
            sa={"item": item_id, "role": role},
        )
        new_kids.append(kid_shape)

    group_shape.kids = new_kids


def to_shapes(group_shape: Shape) -> None:
    """Convert SmartArt diagram group to plain shapes group."""
    group_shape.sa = None
    group_shape.name = f"Group {group_shape.id}"
    for k in group_shape.kids:
        k.sa = None


__all__ = [
    "SmartArtItem",
    "SmartArtEngine",
    "CATEGORIES",
    "LAYOUTS",
    "get_layout",
    "PALETTES",
    "STYLES",
    "DEFAULT_COLORS",
    "DEFAULT_STYLE",
    "mix_hex",
    "paint_shape",
    "color_spec",
    "style_info",
    "style_lang",
    "style_refs",
    "fit_text",
    "fits",
    "wrap_text",
    "measure_with",
    "LINE_HEIGHT",
    "relayout",
    "to_shapes",
    "new_id",
    "blank",
    "outline",
    "locate",
    "add_after",
    "add_before",
    "add_above",
    "add_below",
    "promote",
    "demote",
    "move_up",
    "move_down",
    "remove_item",
    "items_from_outline",
]
