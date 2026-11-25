"""Regression tests for DOCX save fidelity (data that used to be lost on save)."""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from atboffice.modules.writer.io import read_docx, write_docx

CORPUS = Path(__file__).resolve().parents[2] / "docs" / "word" / "docx"


def _corpus(name: str) -> bytes:
    path = CORPUS / name
    if not path.exists():
        pytest.skip(f"corpus file missing: {name}")
    return path.read_bytes()


def _part(data: bytes, name: str) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return z.read(name).decode("utf-8")


def _count(xml: str, local: str) -> int:
    return len(re.findall(rf"<w:{local}\b", xml))


def test_comment_references_survive_save() -> None:
    src = _corpus("openxml-sdk__Comment066.docx")
    before = _count(_part(src, "word/document.xml"), "commentReference")
    out = write_docx(read_docx(src))
    assert before > 0
    assert _count(_part(out, "word/document.xml"), "commentReference") == before


def test_footnote_references_survive_save() -> None:
    src = _corpus("libreoffice__tdf153255.docx")
    before = _count(_part(src, "word/document.xml"), "footnoteReference")
    out = write_docx(read_docx(src))
    assert before > 0
    assert _count(_part(out, "word/document.xml"), "footnoteReference") == before


def test_unchanged_styles_part_is_carried() -> None:
    src = _corpus("openxml-sdk__Comment066.docx")
    out = write_docx(read_docx(src))
    assert _part(out, "word/styles.xml") == _part(src, "word/styles.xml")


def test_edited_style_is_patched_in_place() -> None:
    src = _corpus("openxml-sdk__Comment066.docx")
    before = _part(src, "word/styles.xml")
    latent = _count(before, "lsdException")
    doc = read_docx(src)
    style = next(s for s in doc.styles.values() if not s.builtin and s.style_type == "paragraph")
    style.r_pr.b = True
    styles = _part(write_docx(doc), "word/styles.xml")
    assert _count(styles, "lsdException") == latent
    element = re.search(
        rf'<w:style\b[^>]*w:styleId="{re.escape(style.id)}".*?</w:style>', styles, re.S
    )
    assert element is not None and "<w:b/>" in element.group(0)


def test_markup_compatibility_prefixes_stay_declared() -> None:
    src = _corpus("poi__60316.docx")
    xml = _part(write_docx(read_docx(src)), "word/document.xml")
    declared = set(re.findall(r'xmlns:([A-Za-z0-9]+)="', xml))
    referenced: set[str] = set()
    for attr in re.findall(r'(?:Requires|Ignorable)="([^"]*)"', xml):
        referenced.update(attr.split())
    assert referenced, "fixture should use mc:Requires / mc:Ignorable"
    assert referenced <= declared
    assert not re.search(r"<ns\d+:", xml)


def _rename_header(data: bytes, old: str, new: str) -> bytes:
    src = zipfile.ZipFile(io.BytesIO(data))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for info in src.infolist():
            name = info.filename.replace(old, new)
            payload = src.read(info.filename)
            if name.endswith(".rels") or name == "[Content_Types].xml":
                payload = payload.replace(old.encode(), new.encode())
            out.writestr(name, payload)
    return buf.getvalue()


def test_header_part_names_are_not_mangled() -> None:
    src = _corpus("poi__headerPic.docx")
    names = zipfile.ZipFile(io.BytesIO(src)).namelist()
    header = next(n for n in names if re.fullmatch(r"word/header\d*\.xml", n))
    old = header.rsplit("/", 1)[1]
    data = _rename_header(src, old, "reportHeader.xml")
    out = write_docx(read_docx(data))
    out_names = zipfile.ZipFile(io.BytesIO(out)).namelist()
    assert "word/reportHeader.xml" in out_names
    assert "word/eportHeader.xml" not in out_names
