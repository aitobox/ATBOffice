"""Shared offline WordNet thesaurus engine (`.vibeoffice/common/dict/en.thes`)."""

from __future__ import annotations

import bisect
import logging
import re
import threading
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_THESAURUS_PATH: Path = (
    Path(__file__).resolve().parents[2] / "resources" / "dict" / "en.thes"
)

_DOUBLED_ED_RE = re.compile(r"([b-df-hj-np-tv-z])\1ed$")
_DOUBLED_ING_RE = re.compile(r"([b-df-hj-np-tv-z])\1ing$")

POS_ABBR: dict[str, str] = {
    "noun": "n.",
    "verb": "v.",
    "adj": "adj.",
    "adv": "adv.",
}


@dataclass(frozen=True)
class ThesaurusSense:
    """One grammatical part-of-speech sense group and its synonyms."""

    pos: str
    synonyms: tuple[str, ...]


@dataclass(frozen=True)
class ThesaurusEntry:
    """Structured thesaurus lookup result for a headword or stemmed base form."""

    head: str
    from_base: bool
    senses: tuple[ThesaurusSense, ...]
    antonyms: tuple[str, ...]


def _stem_candidates(word: str) -> list[str]:
    """Generate ordered lowercase candidate headwords matching `.vibeoffice` rules."""
    w = str(word).strip().lower().replace("\u2019", "'")
    if not w:
        return []
    tries: list[str] = [w]

    def _add(cand: str) -> None:
        if cand and len(cand) > 1 and cand not in tries:
            tries.append(cand)

    if w.endswith("'s"):
        _add(w[:-2])
    if w.endswith("ies"):
        _add(w[:-3] + "y")
    if w.endswith("es"):
        _add(w[:-2])
    if w.endswith("s"):
        _add(w[:-1])
    if w.endswith("ied"):
        _add(w[:-3] + "y")
    if w.endswith("ed"):
        _add(w[:-2])
    if w.endswith("d"):
        _add(w[:-1])
    if _DOUBLED_ED_RE.search(w):
        _add(_DOUBLED_ED_RE.sub(r"\1", w))
    if w.endswith("ing"):
        _add(w[:-3])
        _add(w[:-3] + "e")
    if _DOUBLED_ING_RE.search(w):
        _add(_DOUBLED_ING_RE.sub(r"\1", w))
    if w.endswith("ily"):
        _add(w[:-3] + "y")
    if w.endswith("ly"):
        _add(w[:-2])
    if w.endswith("ier"):
        _add(w[:-3] + "y")
    if w.endswith("er"):
        _add(w[:-2])
    if w.endswith("iest"):
        _add(w[:-4] + "y")
    if w.endswith("est"):
        _add(w[:-3])

    return tries


def _parse_entry_line(line: str, from_base: bool) -> ThesaurusEntry:
    """Parse ``head|pos:syn1,syn2;...|ant1,ant2`` into a ``ThesaurusEntry``."""
    parts = line.split("|")
    head = parts[0] if parts else ""
    senses_raw = parts[1] if len(parts) > 1 else ""
    ants_raw = parts[2] if len(parts) > 2 else ""

    senses: list[ThesaurusSense] = []
    for chunk in senses_raw.split(";"):
        if not chunk:
            continue
        sep = chunk.find(":")
        if sep < 0:
            continue
        pos = chunk[:sep].strip()
        syns = tuple(s.strip() for s in chunk[sep + 1 :].split(",") if s.strip())
        if syns:
            senses.append(ThesaurusSense(pos=pos, synonyms=syns))

    ants = tuple(a.strip() for a in ants_raw.split(",") if a.strip()) if ants_raw else ()
    return ThesaurusEntry(head=head, from_base=from_base, senses=tuple(senses), antonyms=ants)


class ThesaurusEngine:
    """Thread-safe lazy-loading WordNet English thesaurus engine."""

    _instance: ThesaurusEngine | None = None

    def __init__(self, dict_path: Path | None = None) -> None:
        self._dict_path = Path(dict_path) if dict_path is not None else DEFAULT_THESAURUS_PATH
        self._lock = threading.Lock()
        self._data: dict[str, str] | None = None
        self._keys: list[str] | None = None

    @classmethod
    def get_instance(cls) -> ThesaurusEngine:
        """Return shared process-wide thesaurus engine."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (useful for clean unit testing)."""
        cls._instance = None

    @property
    def is_loaded(self) -> bool:
        """Return whether the thesaurus dictionary has been parsed into memory."""
        return self._data is not None

    def ensure_loaded(self) -> None:
        """Load ``en.thes`` on demand once, raising ``OSError`` if missing/unreadable."""
        if self._data is not None:
            return
        with self._lock:
            if self._data is not None:
                return
            try:
                text = self._dict_path.read_text(encoding="utf-8")
            except OSError:
                logger.exception("Failed to load thesaurus dictionary from %s", self._dict_path)
                raise
            mapping: dict[str, str] = {}
            for line in text.splitlines():
                if not line:
                    continue
                sep = line.find("|")
                if sep <= 0:
                    continue
                mapping[line[:sep].lower()] = line
            self._data = mapping
            self._keys = sorted(mapping.keys())

    def lookup(self, word: str) -> ThesaurusEntry | None:
        """Look up ``word`` or its inflected base form; returns ``None`` if absent."""
        self.ensure_loaded()
        assert self._data is not None
        candidates = _stem_candidates(word)
        if not candidates:
            return None
        query = candidates[0]
        for cand in candidates:
            line = self._data.get(cand)
            if line is not None:
                return _parse_entry_line(line, from_base=(cand != query))
        return None

    def near(self, word: str, limit: int = 12) -> list[str]:
        """Return up to ``limit`` alphabetically adjacent headwords around ``word``."""
        self.ensure_loaded()
        assert self._keys is not None
        if not self._keys or limit <= 0:
            return []
        w = str(word).strip().lower()
        idx = bisect.bisect_left(self._keys, w)
        start = max(0, idx - limit // 2)
        if start + limit > len(self._keys):
            start = max(0, len(self._keys) - limit)
        return self._keys[start : start + limit]


def get_thesaurus_engine() -> ThesaurusEngine:
    """Convenience accessor for the shared ``ThesaurusEngine`` singleton."""
    return ThesaurusEngine.get_instance()
