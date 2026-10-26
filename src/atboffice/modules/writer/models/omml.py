"""Office Math ML (OMML) data models, parser, and serializer for Quire word processor.

Strictly follows OOXML ISO/IEC 29500-1 §22.1 and .vibeoffice/public/quire/js/omml.js.
Supports fractions, scripts, radicals, delimiters, n-ary operators, functions, accents,
matrices, equation arrays, phantoms, and styled alphabets.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

from atboffice.modules.writer.models.document import RunItem
from atboffice.modules.writer.models.properties import RunProperties

NS_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# Styled alphabet code point base offsets and exception maps
_HOLES = {
    "double-struck": {
        "C": 0x2102,
        "H": 0x210D,
        "N": 0x2115,
        "P": 0x2119,
        "Q": 0x211A,
        "R": 0x211D,
        "Z": 0x2124,
    },
    "script": {
        "B": 0x212C,
        "E": 0x2130,
        "F": 0x2131,
        "H": 0x210B,
        "I": 0x2110,
        "L": 0x2112,
        "M": 0x2133,
        "R": 0x211B,
        "e": 0x212F,
        "g": 0x210A,
        "o": 0x2134,
    },
    "fraktur": {
        "C": 0x212D,
        "H": 0x210C,
        "I": 0x2111,
        "R": 0x211C,
        "Z": 0x2128,
    },
}

_BASE = {
    "double-struck": 0x1D538,
    "script": 0x1D49C,
    "fraktur": 0x1D504,
    "sans-serif": 0x1D5A0,
    "monospace": 0x1D670,
}


def style_math_char(ch: str, scr: str | None) -> str:
    """Convert ASCII Latin char to styled mathematical unicode equivalent."""
    if not scr or scr not in _BASE:
        return ch
    if scr in _HOLES and ch in _HOLES[scr]:
        return chr(_HOLES[scr][ch])
    cp = ord(ch)
    base = _BASE[scr]
    if 65 <= cp <= 90:  # A-Z
        return chr(base + cp - 65)
    if 97 <= cp <= 122:  # a-z
        return chr(base + 26 + cp - 97)
    if 48 <= cp <= 57 and scr in ("double-struck", "sans-serif", "monospace"):
        num_base = {"double-struck": 0x1D7D8, "sans-serif": 0x1D7E2, "monospace": 0x1D7F6}[scr]
        return chr(num_base + cp - 48)
    return ch


def _local_tag(elem: ET.Element | str) -> str:
    tag = elem.tag if isinstance(elem, ET.Element) else elem
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag.split(":")[-1]


def _get_val(elem: ET.Element | None) -> str | None:
    if elem is None:
        return None
    for k, v in elem.attrib.items():
        if _local_tag(k) == "val":
            return v
    return None


def _is_on(v: str | None) -> bool:
    return v is not None and v not in ("0", "false", "off")


# ---------------------------------------------------------------------------
# AST Node Hierarchy
# ---------------------------------------------------------------------------


@dataclass
class MathNode:
    """Base class for all mathematical AST nodes."""

    pass


@dataclass
class MathRun(MathNode):
    """Run containing math text and font/style formatting."""

    text: str = ""
    style: str | None = None  # "b", "bi", "p", "i"
    script: str | None = None  # "double-struck", "script", "fraktur", etc.
    normal: bool = False


@dataclass
class MathFraction(MathNode):
    """Fraction element m:f."""

    num: list[MathNode] = field(default_factory=list)
    den: list[MathNode] = field(default_factory=list)
    type: str = "bar"  # "bar", "skw", "lin", "noBar"


@dataclass
class MathSup(MathNode):
    """Superscript element m:sSup."""

    base: list[MathNode] = field(default_factory=list)
    sup: list[MathNode] = field(default_factory=list)


@dataclass
class MathSub(MathNode):
    """Subscript element m:sSub."""

    base: list[MathNode] = field(default_factory=list)
    sub: list[MathNode] = field(default_factory=list)


@dataclass
class MathSubSup(MathNode):
    """Subscript-superscript element m:sSubSup."""

    base: list[MathNode] = field(default_factory=list)
    sub: list[MathNode] = field(default_factory=list)
    sup: list[MathNode] = field(default_factory=list)


@dataclass
class MathPre(MathNode):
    """Pre-superscript/subscript element m:sPre."""

    base: list[MathNode] = field(default_factory=list)
    sub: list[MathNode] = field(default_factory=list)
    sup: list[MathNode] = field(default_factory=list)


@dataclass
class MathRadical(MathNode):
    """Radical element m:rad."""

    base: list[MathNode] = field(default_factory=list)
    deg: list[MathNode] = field(default_factory=list)
    deg_hide: bool = False


@dataclass
class MathDelimiter(MathNode):
    """Delimiter / brackets element m:d."""

    items: list[list[MathNode]] = field(default_factory=list)
    beg_chr: str = "("
    end_chr: str = ")"
    sep_chr: str = "|"
    grow: bool = True


@dataclass
class MathNary(MathNode):
    """N-ary operator (integral, sum, product) element m:nary."""

    op: str = "∫"
    sub: list[MathNode] = field(default_factory=list)
    sup: list[MathNode] = field(default_factory=list)
    base: list[MathNode] = field(default_factory=list)
    sub_hide: bool = False
    sup_hide: bool = False
    lim_loc: str = "undOvr"  # "undOvr" or "subSup"


@dataclass
class MathFunction(MathNode):
    """Function call element m:func (e.g., sin, cos, lim)."""

    name: list[MathNode] = field(default_factory=list)
    base: list[MathNode] = field(default_factory=list)


@dataclass
class MathAccent(MathNode):
    """Accent element m:acc (e.g. hat, bar, arrow)."""

    base: list[MathNode] = field(default_factory=list)
    chr: str = "̂"


@dataclass
class MathBar(MathNode):
    """Bar element m:bar."""

    base: list[MathNode] = field(default_factory=list)
    pos: str = "top"  # "top" or "bot"


@dataclass
class MathGroupChar(MathNode):
    """Group character element m:groupChr (e.g. underbrace)."""

    base: list[MathNode] = field(default_factory=list)
    chr: str = "⏟"
    pos: str = "bot"  # "bot" or "top"


@dataclass
class MathLimitLower(MathNode):
    """Lower limit element m:limLow."""

    base: list[MathNode] = field(default_factory=list)
    lim: list[MathNode] = field(default_factory=list)


@dataclass
class MathLimitUpper(MathNode):
    """Upper limit element m:limUpp."""

    base: list[MathNode] = field(default_factory=list)
    lim: list[MathNode] = field(default_factory=list)


@dataclass
class MathMatrix(MathNode):
    """Matrix element m:m."""

    rows: list[list[list[MathNode]]] = field(default_factory=list)
    jc: str | None = None


@dataclass
class MathEqArray(MathNode):
    """Equation array element m:eqArr."""

    items: list[list[MathNode]] = field(default_factory=list)


@dataclass
class MathBoxNode(MathNode):
    """Box element m:box."""

    base: list[MathNode] = field(default_factory=list)


@dataclass
class MathBorderBoxNode(MathNode):
    """Border box element m:borderBox."""

    base: list[MathNode] = field(default_factory=list)


@dataclass
class MathPhantomNode(MathNode):
    """Phantom element m:phant."""

    base: list[MathNode] = field(default_factory=list)
    show: bool = False


# ---------------------------------------------------------------------------
# OfficeMathItem Document Run Item
# ---------------------------------------------------------------------------


@dataclass
class OfficeMathItem(RunItem):
    """Inline or display mathematical formula item inside Paragraph.runs."""

    nodes: list[MathNode] = field(default_factory=list)
    raw_xml: str | None = None
    display: bool = False  # True if m:oMathPara block paragraph
    jc: str | None = None  # "centerGroup", "left", "right", "center"
    font_size: float = 12.0
    width: float = 0.0
    height: float = 0.0
    ascent: float = 0.0
    descent: float = 0.0
    layout_box: Any = None

    def __init__(
        self,
        nodes: list[MathNode] | None = None,
        raw_xml: str | None = None,
        display: bool = False,
        jc: str | None = None,
        font_size: float = 12.0,
        r_pr: RunProperties | None = None,
    ) -> None:
        super().__init__(t="omath", r_pr=r_pr or RunProperties())
        self.nodes = nodes or []
        self.raw_xml = raw_xml
        self.display = display
        self.jc = jc
        self.font_size = font_size
        self.width = 0.0
        self.height = 0.0
        self.ascent = 0.0
        self.descent = 0.0
        self.layout_box = None


# ---------------------------------------------------------------------------
# Parser: XML -> Math AST
# ---------------------------------------------------------------------------


def _find_child(parent: ET.Element, tag_name: str) -> ET.Element | None:
    for c in parent:
        if _local_tag(c) == tag_name:
            return c
    return None


def _find_children(parent: ET.Element, tag_name: str) -> list[ET.Element]:
    return [c for c in parent if _local_tag(c) == tag_name]


def _parse_run(elem: ET.Element) -> list[MathNode]:
    r_pr = _find_child(elem, "rPr")
    sty: str | None = None
    scr: str | None = None
    nor: bool = False

    if r_pr is not None:
        sty_elem = _find_child(r_pr, "sty")
        sty = _get_val(sty_elem)
        scr_elem = _find_child(r_pr, "scr")
        scr = _get_val(scr_elem)
        nor_elem = _find_child(r_pr, "nor")
        nor = _is_on(_get_val(nor_elem)) if nor_elem is not None else False

    text_parts: list[str] = []
    for c in elem:
        lt = _local_tag(c)
        if lt == "t":
            text_parts.append(c.text or "")
        elif lt == "br":
            text_parts.append(" ")

    full_text = "".join(text_parts)
    if not full_text:
        return []

    if scr:
        full_text = "".join(style_math_char(ch, scr) for ch in full_text)

    return [MathRun(text=full_text, style=sty, script=scr, normal=nor)]


def _parse_arg(elem: ET.Element | None) -> list[MathNode]:
    if elem is None:
        return []
    nodes: list[MathNode] = []
    for c in elem:
        res = _parse_element(c)
        if res:
            nodes.extend(res)
    return nodes


def _parse_element(elem: ET.Element) -> list[MathNode]:
    tag = _local_tag(elem)

    if tag == "r":
        return _parse_run(elem)

    elif tag == "f":
        f_pr = _find_child(elem, "fPr")
        f_type = "bar"
        if f_pr is not None:
            type_elem = _find_child(f_pr, "type")
            f_type = _get_val(type_elem) or "bar"
        num = _parse_arg(_find_child(elem, "num"))
        den = _parse_arg(_find_child(elem, "den"))
        return [MathFraction(num=num, den=den, type=f_type)]

    elif tag == "sSup":
        base = _parse_arg(_find_child(elem, "e"))
        sup = _parse_arg(_find_child(elem, "sup"))
        return [MathSup(base=base, sup=sup)]

    elif tag == "sSub":
        base = _parse_arg(_find_child(elem, "e"))
        sub = _parse_arg(_find_child(elem, "sub"))
        return [MathSub(base=base, sub=sub)]

    elif tag == "sSubSup":
        base = _parse_arg(_find_child(elem, "e"))
        sub = _parse_arg(_find_child(elem, "sub"))
        sup = _parse_arg(_find_child(elem, "sup"))
        return [MathSubSup(base=base, sub=sub, sup=sup)]

    elif tag == "sPre":
        base = _parse_arg(_find_child(elem, "e"))
        sub = _parse_arg(_find_child(elem, "sub"))
        sup = _parse_arg(_find_child(elem, "sup"))
        return [MathPre(base=base, sub=sub, sup=sup)]

    elif tag == "rad":
        rad_pr = _find_child(elem, "radPr")
        deg_hide = False
        if rad_pr is not None:
            dh_elem = _find_child(rad_pr, "degHide")
            deg_hide = _is_on(_get_val(dh_elem))
        base = _parse_arg(_find_child(elem, "e"))
        deg = _parse_arg(_find_child(elem, "deg"))
        return [MathRadical(base=base, deg=deg, deg_hide=deg_hide)]

    elif tag == "d":
        d_pr = _find_child(elem, "dPr")
        beg_chr = "("
        end_chr = ")"
        sep_chr = "|"
        grow = True
        if d_pr is not None:
            bc = _get_val(_find_child(d_pr, "begChr"))
            if bc is not None:
                beg_chr = bc
            ec = _get_val(_find_child(d_pr, "endChr"))
            if ec is not None:
                end_chr = ec
            sc = _get_val(_find_child(d_pr, "sepChr"))
            if sc is not None:
                sep_chr = sc
            gr = _get_val(_find_child(d_pr, "grow"))
            if gr is not None:
                grow = _is_on(gr)

        items = [_parse_arg(e) for e in _find_children(elem, "e")]
        return [
            MathDelimiter(items=items, beg_chr=beg_chr, end_chr=end_chr, sep_chr=sep_chr, grow=grow)
        ]

    elif tag == "nary":
        n_pr = _find_child(elem, "naryPr")
        op = "∫"
        sub_hide = False
        sup_hide = False
        lim_loc = "undOvr"
        if n_pr is not None:
            op_val = _get_val(_find_child(n_pr, "chr"))
            if op_val:
                op = op_val
            sub_hide = _is_on(_get_val(_find_child(n_pr, "subHide")))
            sup_hide = _is_on(_get_val(_find_child(n_pr, "supHide")))
            loc = _get_val(_find_child(n_pr, "limLoc"))
            if loc:
                lim_loc = loc
            elif op in ("∫", "∬", "∭", "∮"):
                lim_loc = "subSup"

        sub = [] if sub_hide else _parse_arg(_find_child(elem, "sub"))
        sup = [] if sup_hide else _parse_arg(_find_child(elem, "sup"))
        base = _parse_arg(_find_child(elem, "e"))
        return [
            MathNary(
                op=op,
                sub=sub,
                sup=sup,
                base=base,
                sub_hide=sub_hide,
                sup_hide=sup_hide,
                lim_loc=lim_loc,
            )
        ]

    elif tag == "func":
        name = _parse_arg(_find_child(elem, "fName"))
        base = _parse_arg(_find_child(elem, "e"))
        return [MathFunction(name=name, base=base)]

    elif tag == "acc":
        acc_pr = _find_child(elem, "accPr")
        ch = "̂"
        if acc_pr is not None:
            ch_val = _get_val(_find_child(acc_pr, "chr"))
            if ch_val:
                ch = ch_val
        base = _parse_arg(_find_child(elem, "e"))
        return [MathAccent(base=base, chr=ch)]

    elif tag == "bar":
        bar_pr = _find_child(elem, "barPr")
        pos = "top"
        if bar_pr is not None:
            pos_val = _get_val(_find_child(bar_pr, "pos"))
            if pos_val:
                pos = pos_val
        base = _parse_arg(_find_child(elem, "e"))
        return [MathBar(base=base, pos=pos)]

    elif tag == "groupChr":
        gc_pr = _find_child(elem, "groupChrPr")
        ch = "⏟"
        pos = "bot"
        if gc_pr is not None:
            ch_val = _get_val(_find_child(gc_pr, "chr"))
            if ch_val:
                ch = ch_val
            pos_val = _get_val(_find_child(gc_pr, "pos"))
            if pos_val:
                pos = pos_val
        base = _parse_arg(_find_child(elem, "e"))
        return [MathGroupChar(base=base, chr=ch, pos=pos)]

    elif tag == "limLow":
        base = _parse_arg(_find_child(elem, "e"))
        lim = _parse_arg(_find_child(elem, "lim"))
        return [MathLimitLower(base=base, lim=lim)]

    elif tag == "limUpp":
        base = _parse_arg(_find_child(elem, "e"))
        lim = _parse_arg(_find_child(elem, "lim"))
        return [MathLimitUpper(base=base, lim=lim)]

    elif tag == "m":
        rows: list[list[list[MathNode]]] = []
        for mr in _find_children(elem, "mr"):
            row = [_parse_arg(e) for e in _find_children(mr, "e")]
            rows.append(row)
        return [MathMatrix(rows=rows)]

    elif tag == "eqArr":
        items = [_parse_arg(e) for e in _find_children(elem, "e")]
        return [MathEqArray(items=items)]

    elif tag == "box":
        return [MathBoxNode(base=_parse_arg(_find_child(elem, "e")))]

    elif tag == "borderBox":
        return [MathBorderBoxNode(base=_parse_arg(_find_child(elem, "e")))]

    elif tag == "phant":
        ph_pr = _find_child(elem, "phantPr")
        show = False
        if ph_pr is not None:
            show = _is_on(_get_val(_find_child(ph_pr, "show")))
        return [MathPhantomNode(base=_parse_arg(_find_child(elem, "e")), show=show)]

    elif tag in ("oMath", "ins", "sdt", "sdtContent", "customXml"):
        out: list[MathNode] = []
        for c in elem:
            out.extend(_parse_element(c))
        return out

    return []


def parse_omml(elem_or_xml: ET.Element | str) -> OfficeMathItem:
    """Parse an <m:oMath> or <m:oMathPara> XML element or string into OfficeMathItem."""
    raw_str: str | None = None
    if isinstance(elem_or_xml, str):
        raw_str = elem_or_xml
        # Ensure namespace definition exists
        xml = elem_or_xml
        if "xmlns:m=" not in xml:
            xml = xml.replace(
                "<m:oMath",
                f'<m:oMath xmlns:m="{NS_M}" xmlns:w="{NS_W}"',
                1,
            )
        root = ET.fromstring(xml)
    else:
        root = elem_or_xml
        try:
            raw_str = ET.tostring(root, encoding="unicode")
        except Exception:
            raw_str = None

    tag = _local_tag(root)
    is_para = tag == "oMathPara"
    jc: str | None = None

    nodes: list[MathNode] = []
    if is_para:
        para_pr = _find_child(root, "oMathParaPr")
        if para_pr is not None:
            jc = _get_val(_find_child(para_pr, "jc")) or "centerGroup"
        for om in _find_children(root, "oMath"):
            nodes.extend(_parse_element(om))
    else:
        nodes.extend(_parse_element(root))

    # Detect font size from embedded w:rPr/w:sz if present
    font_size = 12.0
    for sz_elem in root.iter(f"{{{NS_W}}}sz"):
        val_str = _get_val(sz_elem)
        if val_str and val_str.isdigit():
            font_size = float(val_str) / 2.0
            break

    return OfficeMathItem(
        nodes=nodes,
        raw_xml=raw_str,
        display=is_para,
        jc=jc,
        font_size=font_size,
    )


# ---------------------------------------------------------------------------
# Serializer: Math AST -> OOXML XML Element
# ---------------------------------------------------------------------------


def _m(tag: str) -> str:
    return f"{{{NS_M}}}{tag}"


def _serialize_nodes(nodes: list[MathNode], parent: ET.Element) -> None:
    for node in nodes:
        if isinstance(node, MathRun):
            r = ET.SubElement(parent, _m("r"))
            if node.style or node.script or node.normal:
                r_pr = ET.SubElement(r, _m("rPr"))
                if node.style:
                    sty = ET.SubElement(r_pr, _m("sty"))
                    sty.set(_m("val"), node.style)
                if node.script:
                    scr = ET.SubElement(r_pr, _m("scr"))
                    scr.set(_m("val"), node.script)
                if node.normal:
                    nor = ET.SubElement(r_pr, _m("nor"))
                    nor.set(_m("val"), "1")
            t = ET.SubElement(r, _m("t"))
            t.text = node.text

        elif isinstance(node, MathFraction):
            f = ET.SubElement(parent, _m("f"))
            if node.type and node.type != "bar":
                f_pr = ET.SubElement(f, _m("fPr"))
                tp = ET.SubElement(f_pr, _m("type"))
                tp.set(_m("val"), node.type)
            num = ET.SubElement(f, _m("num"))
            _serialize_nodes(node.num, num)
            den = ET.SubElement(f, _m("den"))
            _serialize_nodes(node.den, den)

        elif isinstance(node, MathSup):
            sup_elem = ET.SubElement(parent, _m("sSup"))
            e = ET.SubElement(sup_elem, _m("e"))
            _serialize_nodes(node.base, e)
            sup = ET.SubElement(sup_elem, _m("sup"))
            _serialize_nodes(node.sup, sup)

        elif isinstance(node, MathSub):
            sub_elem = ET.SubElement(parent, _m("sSub"))
            e = ET.SubElement(sub_elem, _m("e"))
            _serialize_nodes(node.base, e)
            sub = ET.SubElement(sub_elem, _m("sub"))
            _serialize_nodes(node.sub, sub)

        elif isinstance(node, MathSubSup):
            ss_elem = ET.SubElement(parent, _m("sSubSup"))
            e = ET.SubElement(ss_elem, _m("e"))
            _serialize_nodes(node.base, e)
            sub = ET.SubElement(ss_elem, _m("sub"))
            _serialize_nodes(node.sub, sub)
            sup = ET.SubElement(ss_elem, _m("sup"))
            _serialize_nodes(node.sup, sup)

        elif isinstance(node, MathRadical):
            rad = ET.SubElement(parent, _m("rad"))
            if node.deg_hide:
                rad_pr = ET.SubElement(rad, _m("radPr"))
                dh = ET.SubElement(rad_pr, _m("degHide"))
                dh.set(_m("val"), "1")
            deg = ET.SubElement(rad, _m("deg"))
            _serialize_nodes(node.deg, deg)
            e = ET.SubElement(rad, _m("e"))
            _serialize_nodes(node.base, e)

        elif isinstance(node, MathDelimiter):
            d = ET.SubElement(parent, _m("d"))
            d_pr = ET.SubElement(d, _m("dPr"))
            if node.beg_chr:
                bc = ET.SubElement(d_pr, _m("begChr"))
                bc.set(_m("val"), node.beg_chr)
            if node.end_chr:
                ec = ET.SubElement(d_pr, _m("endChr"))
                ec.set(_m("val"), node.end_chr)
            if node.sep_chr:
                sc = ET.SubElement(d_pr, _m("sepChr"))
                sc.set(_m("val"), node.sep_chr)
            if not node.grow:
                gr = ET.SubElement(d_pr, _m("grow"))
                gr.set(_m("val"), "0")
            for item in node.items:
                e = ET.SubElement(d, _m("e"))
                _serialize_nodes(item, e)

        elif isinstance(node, MathNary):
            nary = ET.SubElement(parent, _m("nary"))
            nary_pr = ET.SubElement(nary, _m("naryPr"))
            ch = ET.SubElement(nary_pr, _m("chr"))
            ch.set(_m("val"), node.op)
            if node.sub_hide:
                sh = ET.SubElement(nary_pr, _m("subHide"))
                sh.set(_m("val"), "1")
            if node.sup_hide:
                sph = ET.SubElement(nary_pr, _m("supHide"))
                sph.set(_m("val"), "1")
            if node.lim_loc:
                loc = ET.SubElement(nary_pr, _m("limLoc"))
                loc.set(_m("val"), node.lim_loc)
            sub = ET.SubElement(nary, _m("sub"))
            _serialize_nodes(node.sub, sub)
            sup = ET.SubElement(nary, _m("sup"))
            _serialize_nodes(node.sup, sup)
            e = ET.SubElement(nary, _m("e"))
            _serialize_nodes(node.base, e)

        elif isinstance(node, MathFunction):
            fn = ET.SubElement(parent, _m("func"))
            f_name = ET.SubElement(fn, _m("fName"))
            _serialize_nodes(node.name, f_name)
            e = ET.SubElement(fn, _m("e"))
            _serialize_nodes(node.base, e)

        elif isinstance(node, MathMatrix):
            m = ET.SubElement(parent, _m("m"))
            for r in node.rows:
                mr = ET.SubElement(m, _m("mr"))
                for c in r:
                    e = ET.SubElement(mr, _m("e"))
                    _serialize_nodes(c, e)


def serialize_omml(item: OfficeMathItem) -> ET.Element:
    """Serialize OfficeMathItem back to standard OOXML <m:oMath> or <m:oMathPara> Element."""
    if item.raw_xml:
        try:
            return ET.fromstring(item.raw_xml)
        except Exception:
            pass

    if item.display:
        root = ET.Element(_m("oMathPara"))
        if item.jc:
            pr = ET.SubElement(root, _m("oMathParaPr"))
            jc_el = ET.SubElement(pr, _m("jc"))
            jc_el.set(_m("val"), item.jc)
        om = ET.SubElement(root, _m("oMath"))
        _serialize_nodes(item.nodes, om)
        return root

    root = ET.Element(_m("oMath"))
    _serialize_nodes(item.nodes, root)
    return root
