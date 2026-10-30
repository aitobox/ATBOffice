"""Offline Spell Checking Engine for Quire and Ledger."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from atboffice.core.settings import AppSettings

logger = logging.getLogger(__name__)

# Front-coded prefix character map (0..9, a..z)
PREFIX_CHARS = "0123456789abcdefghijklmnopqrstuvwxyz"

# Qwerty keyboard layout coordinates for proximity distance weighting
KEY_ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
KEY_POS: dict[str, tuple[float, float]] = {}
for r_idx, row in enumerate(KEY_ROWS):
    for c_idx, ch in enumerate(row):
        KEY_POS[ch] = (float(r_idx), float(c_idx) + float(r_idx) * 0.5)

# Built-in fallback word list for graceful degradation if dictionary file is inaccessible
FALLBACK_WORDS: list[str] = [
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it",
    "for", "not", "on", "with", "he", "as", "you", "do", "at", "this",
    "but", "his", "by", "from", "they", "we", "say", "her", "she", "or",
    "an", "will", "my", "one", "all", "would", "there", "their", "what",
    "so", "up", "out", "if", "about", "who", "get", "which", "go", "me",
    "when", "make", "can", "like", "time", "no", "just", "him", "know",
    "take", "people", "into", "year", "your", "good", "some", "could",
    "them", "see", "other", "than", "then", "now", "look", "only", "come",
    "its", "over", "think", "also", "back", "after", "use", "two", "how",
    "our", "work", "first", "well", "way", "even", "new", "want", "because",
    "any", "these", "give", "day", "most", "us", "word", "office", "quire",
    "document", "paragraph", "text", "write", "editor", "view", "table",
]


def damerau_levenshtein_distance(s1: str, s2: str) -> float:
    """Calculate Damerau-Levenshtein distance with keyboard proximity discounts."""
    n, m = len(s1), len(s2)
    d = [[0.0] * (m + 1) for _ in range(n + 1)]

    for i in range(n + 1):
        d[i][0] = float(i)
    for j in range(m + 1):
        d[0][j] = float(j)

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            c1, c2 = s1[i - 1], s2[j - 1]
            if c1 == c2:
                cost = 0.0
            else:
                p1, p2 = KEY_POS.get(c1), KEY_POS.get(c2)
                if p1 and p2 and abs(p1[0] - p2[0]) <= 1.0 and abs(p1[1] - p2[1]) <= 1.5:
                    cost = 0.8
                else:
                    cost = 1.0

            sub = d[i - 1][j - 1] + cost
            ins = d[i][j - 1] + (0.6 if j > 1 and s2[j - 1] == s2[j - 2] else 1.0)
            dele = d[i - 1][j] + (0.6 if i > 1 and s1[i - 1] == s1[i - 2] else 1.0)

            val = min(sub, ins, dele)
            if i > 1 and j > 1 and s1[i - 1] == s2[j - 2] and s1[i - 2] == s2[j - 1]:
                val = min(val, d[i - 2][j - 2] + 0.7)

            d[i][j] = val

    return d[n][m]


class SpellEngine:
    """Offline Spell Checking Engine with fast front-coded lexicon and suggestions."""

    _instance: SpellEngine | None = None

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings.get_instance()
        self.word_map: dict[str, int] = {}
        self.lower_map: dict[str, tuple[str, int]] = {}
        self.custom_dict: set[str] = set()
        self.ignored_all: set[str] = set()
        self.cache: dict[str, bool] = {}
        self.loaded_lang: str | None = None

        self._load_custom_dictionary()
        self._load_lexicon("en_US")

    @classmethod
    def get_instance(cls) -> SpellEngine:
        """Return global singleton SpellEngine instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance."""
        cls._instance = None

    def _load_custom_dictionary(self) -> None:
        """Load user-added words from application settings."""
        try:
            words = self.settings.get_value("spelling/custom_dict", [])
            if isinstance(words, list):
                self.custom_dict = {str(w).lower() for w in words}
        except Exception as e:
            logger.warning("Failed to load custom dictionary: %s", e)

    def _load_lexicon(self, lang: str = "en_US") -> None:
        """Load front-coded dictionary file from resources directory."""
        self.word_map.clear()
        self.lower_map.clear()
        self.cache.clear()

        # Locate dictionary file in resources/dict
        dict_dir = Path(__file__).resolve().parent.parent.parent / "resources" / "dict"
        dict_path = dict_dir / f"{lang}.words"
        if not dict_path.exists():
            # Try alternate path relative to repo
            dict_path = Path("src/atboffice/resources/dict") / f"{lang}.words"

        if dict_path.exists():
            try:
                prev = ""
                with open(dict_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        p_char = line[0]
                        if p_char not in PREFIX_CHARS:
                            continue
                        k = PREFIX_CHARS.index(p_char)
                        w = prev[:k] + line[1:-1]
                        freq = int(line[-1]) if line[-1].isdigit() else 5
                        self.word_map[w] = freq
                        prev = w

                for w, lv in self.word_map.items():
                    lw = w.lower()
                    if lw not in self.lower_map or self.lower_map[lw][1] > lv:
                        self.lower_map[lw] = (w, lv)

                self.loaded_lang = lang
                logger.info("Loaded %d words from %s", len(self.word_map), dict_path)
                return
            except Exception as e:
                logger.error("Failed to parse dictionary file %s: %s", dict_path, e)

        # Fallback dictionary
        for w in FALLBACK_WORDS:
            self.word_map[w] = 1
            self.lower_map[w.lower()] = (w, 1)
        self.loaded_lang = "fallback"

    def is_enabled(self, option_key: str, default: bool = True) -> bool:
        """Check setting flag."""
        try:
            return bool(self.settings.get_value(option_key, default))
        except Exception:
            return default

    def is_valid_word(self, word: str) -> bool:
        """Check if a word is spelled correctly."""
        w = word.replace("’", "'").strip()
        if len(w) < 2:
            return True

        if self.is_enabled("spelling/ignore_numbers", True) and any(c.isdigit() for c in w):
            return True

        if self.is_enabled("spelling/ignore_uppercase", True) and w.isupper() and len(w) > 1:
            return True

        if w in self.cache:
            return self.cache[w]

        res = self._check_word_raw(w)
        self.cache[w] = res
        return res

    def _check_word_raw(self, w: str) -> bool:
        lw = w.lower()
        if lw in self.custom_dict or lw in self.ignored_all:
            return True

        if w in self.word_map:
            return True

        # Capitalized or uppercase words matching lowercase entry
        if (w.istitle() or w.isupper()) and lw in self.word_map:
            return True

        if w.isupper() and lw in self.lower_map:
            return True

        if w.istitle() and lw in self.lower_map:
            orig, _ = self.lower_map[lw]
            if orig.istitle() or orig.islower():
                return True

        # Possessive s ("company's", "John's")
        m_poss = re.match(r"^(.+?)'s?$", w, re.IGNORECASE)
        if m_poss:
            base = m_poss.group(1)
            if len(base) > 1 and (base in self.word_map or base.lower() in self.lower_map):
                return True

        # Hyphenated compounds ("well-known")
        if "-" in w:
            parts = w.split("-")
            if all(not p or len(p) < 2 or self._check_word_raw(p) for p in parts):
                return True

        return False

    def suggest(self, word: str, max_suggestions: int = 8) -> list[str]:
        """Compute candidate spelling suggestions ranked by edit distance and word frequency."""
        w = word.replace("’", "'").strip()
        lw = w.lower()
        candidates: dict[str, float] = {}

        alphabet = "abcdefghijklmnopqrstuvwxyz'"

        # 1. Edit distance 1 variations
        splits = [(lw[:i], lw[i:]) for i in range(len(lw) + 1)]
        deletes = [L + R[1:] for L, R in splits if R]
        transposes = [L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1]
        replaces = [L + c + R[1:] for L, R in splits if R for c in alphabet]
        inserts = [L + c + R for L, R in splits for c in alphabet]

        edits1 = set(deletes + transposes + replaces + inserts)
        for cand in edits1:
            if cand in self.lower_map:
                real_w, freq = self.lower_map[cand]
                dist = damerau_levenshtein_distance(lw, cand)
                score = dist * 10.0 + float(freq) * 1.5
                if real_w not in candidates or candidates[real_w] > score:
                    candidates[real_w] = score

        # 2. If candidates are sparse, evaluate edit distance 2 for high-frequency words
        if len(candidates) < max_suggestions:
            for e1 in list(edits1)[:120]:
                for i in range(len(e1) + 1):
                    sub_cand = e1[:i] + e1[i + 1:] if i < len(e1) else e1
                    if sub_cand in self.lower_map:
                        real_w, freq = self.lower_map[sub_cand]
                        dist = damerau_levenshtein_distance(lw, sub_cand)
                        score = dist * 10.0 + float(freq) * 1.5 + 4.0
                        if real_w not in candidates or candidates[real_w] > score:
                            candidates[real_w] = score

        # Sort by lowest score
        sorted_cands = sorted(candidates.keys(), key=lambda k: candidates[k])

        # Restore original casing
        results: list[str] = []
        for cand in sorted_cands[:max_suggestions]:
            if word.isupper() and len(word) > 1:
                results.append(cand.upper())
            elif word.istitle() and not cand.istitle():
                results.append(cand.capitalize())
            else:
                results.append(cand)

        return results

    def add_to_custom_dict(self, word: str) -> None:
        """Add word to user custom dictionary and persist to settings."""
        w = word.strip().lower()
        if not w:
            return
        self.custom_dict.add(w)
        self.cache.clear()
        try:
            curr = list(self.settings.get_value("spelling/custom_dict", []))
            if w not in curr:
                curr.append(w)
                self.settings.set_value("spelling/custom_dict", curr)
        except Exception as e:
            logger.warning("Could not persist word to custom dict: %s", e)

    def ignore_all(self, word: str) -> None:
        """Ignore word for the remainder of this session."""
        w = word.strip().lower()
        if w:
            self.ignored_all.add(w)
            self.cache.clear()

    def tokenize_words(self, text: str) -> list[tuple[str, int, int]]:
        """Tokenize text into (word, start_offset, end_offset) triples."""
        results: list[tuple[str, int, int]] = []
        # Pattern matching words with inner apostrophes or hyphens
        re_word = re.compile(r"[\w]+(?:['’\-][\w]+)*", re.UNICODE)
        for m in re_word.finditer(text):
            results.append((m.group(0), m.start(), m.end()))
        return results
