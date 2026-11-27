"""Tests for Phase 13A Task 1: WordNet offline thesaurus engine (`en.thes`)."""

from __future__ import annotations

from pathlib import Path

import pytest

from atboffice.modules.common.thesaurus import (
    ThesaurusEngine,
    ThesaurusEntry,
    get_thesaurus_engine,
)


def test_thesaurus_lazy_load_and_exact_lookup() -> None:
    """Bundled `en.thes` loads lazily on first query and returns structured senses & antonyms."""
    eng = ThesaurusEngine()
    assert eng.is_loaded is False

    entry = eng.lookup("happy")
    assert eng.is_loaded is True
    assert isinstance(entry, ThesaurusEntry)
    assert entry.head.lower() == "happy"
    assert entry.from_base is False
    assert len(entry.senses) >= 1
    assert any(s.pos == "adj" for s in entry.senses)
    all_syns = [syn.lower() for s in entry.senses for syn in s.synonyms]
    assert any(w in all_syns for w in ("felicitous", "glad", "well-chosen"))
    assert "unhappy" in [a.lower() for a in entry.antonyms]


def test_thesaurus_stem_reduction_and_apostrophe_normalization() -> None:
    """Inflected and curly-apostrophe forms fall back to base headwords with `from_base=True`."""
    eng = get_thesaurus_engine()

    e_ing = eng.lookup("jogging")
    assert e_ing is not None
    assert e_ing.from_base is True
    assert e_ing.head.lower() == "jog"

    e_ly = eng.lookup("dogs")
    assert e_ly is not None
    assert e_ly.head.lower() == "dog"
    assert e_ly.from_base is True

    e_ed = eng.lookup("walked")
    assert e_ed is not None
    assert e_ed.head.lower() == "walk"
    assert e_ed.from_base is True

    e_ies = eng.lookup("cities")
    assert e_ies is not None
    assert e_ies.head.lower() == "city"
    assert e_ies.from_base is True

    e_apos = eng.lookup("abandon’s")
    assert e_apos is not None
    assert e_apos.head.lower() == "abandon"


def test_thesaurus_near_headwords_and_missing_file(tmp_path: Path) -> None:
    """Missing headwords yield alphabetical neighbors; missing file raises FileNotFoundError."""
    eng = get_thesaurus_engine()
    assert eng.lookup("zzzznotawordzzz") is None
    near_words = eng.near("happ", limit=8)
    assert len(near_words) == 8
    assert any(w.startswith("happ") for w in near_words)

    broken = ThesaurusEngine(dict_path=tmp_path / "missing.thes")
    with pytest.raises(FileNotFoundError):
        broken.lookup("happy")
