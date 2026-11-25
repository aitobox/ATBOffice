"""Regression tests for PPTX save fidelity."""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from atboffice.modules.presentation.io import read_pptx, write_pptx

CORPUS = Path(__file__).resolve().parents[2] / "docs" / "powerpoint" / "pptx"


def _corpus(name: str) -> bytes:
    path = CORPUS / name
    if not path.exists():
        pytest.skip(f"corpus file missing: {name}")
    return path.read_bytes()


def _part(data: bytes, name: str) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return z.read(name).decode("utf-8")


def _slide_ids(pres_xml: str) -> list[str]:
    return re.findall(r'<p:sldId\b[^>]*\bid="(\d+)"', pres_xml)


def test_slide_ids_are_kept_on_save() -> None:
    src = _corpus("libreoffice__master-slides.pptx")
    before = _slide_ids(_part(src, "ppt/presentation.xml"))
    pres = read_pptx(src)
    for s in pres.slides:
        s.is_dirty = True
    after = _slide_ids(_part(write_pptx(pres), "ppt/presentation.xml"))
    assert before and after == before


def test_section_list_points_at_existing_slide_ids() -> None:
    src = _corpus("libreoffice__master-slides.pptx")
    xml = _part(write_pptx(read_pptx(src)), "ppt/presentation.xml")
    ids = set(_slide_ids(xml))
    for sid in re.findall(r'<p14:sldId\b[^>]*\bid="(\d+)"', xml):
        assert sid in ids


def test_new_slide_gets_an_unused_id() -> None:
    src = _corpus("libreoffice__master-slides.pptx")
    pres = read_pptx(src)
    from atboffice.modules.presentation.models.slide import dup_slide

    pres.slides.append(dup_slide(pres.slides[0]))
    ids = _slide_ids(_part(write_pptx(pres), "ppt/presentation.xml"))
    assert len(ids) == len(set(ids)) == len(pres.slides)
    assert all(256 <= int(i) < 2**31 for i in ids)


def test_deleted_slide_relationship_is_removed() -> None:
    src = _corpus("libreoffice__master-slides.pptx")
    pres = read_pptx(src)
    if len(pres.slides) < 2:
        pytest.skip("needs two slides")
    pres.slides.pop()
    out = write_pptx(pres)
    names = set(zipfile.ZipFile(io.BytesIO(out)).namelist())
    rels = _part(out, "ppt/_rels/presentation.xml.rels")
    for target in re.findall(r'Target="(slides/[^"]+)"', rels):
        assert f"ppt/{target}" in names
