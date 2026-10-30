"""Quire AutoCorrect and AutoFormat as-you-type engine."""

from __future__ import annotations

import re
from typing import Any

from atboffice.core.settings import AppSettings

# Default symbol substitutions
DEFAULT_SYMBOLS: dict[str, str] = {
    "(c)": "©",
    "(C)": "©",
    "(r)": "®",
    "(R)": "®",
    "(tm)": "™",
    "(TM)": "™",
    "...": "…",
    ":)": "☺",
    ":-)": "☺",
    ":(": "☹",
    ":-(": "☹",
    "-->": "→",
    "<--": "←",
    "==>": "⇒",
    "<==": "⇐",
    "<=>": "⇔",
}

# Default fraction substitutions
DEFAULT_FRACTIONS: dict[str, str] = {
    "1/2": "½",
    "1/4": "¼",
    "3/4": "¾",
}

# Common English abbreviations that should not trigger sentence-capitalization
DEFAULT_EXCEPTIONS: set[str] = {
    "a.", "abbr.", "abs.", "acad.", "acct.", "adj.", "adv.", "al.", "apr.",
    "approx.", "assn.", "aug.", "ave.", "b.a.", "c.", "ca.", "cf.", "co.",
    "corp.", "dec.", "dept.", "dr.", "e.g.", "ed.", "esp.", "est.", "etc.",
    "ex.", "feb.", "fig.", "figs.", "fri.", "gen.", "i.e.", "inc.", "jan.",
    "jr.", "jul.", "jun.", "ltd.", "mar.", "max.", "min.", "misc.", "mon.",
    "mr.", "mrs.", "ms.", "mt.", "no.", "nov.", "oct.", "p.", "pp.", "prof.",
    "ref.", "rev.", "sat.", "sep.", "sept.", "sr.", "st.", "sun.", "tel.",
    "thu.", "tue.", "u.s.", "vol.", "vs.", "wed.",
}

# Common typos derived from Apache OpenOffice / SCOWL / vibeoffice autocorrect
DEFAULT_TYPOS: dict[str, str] = {
    "teh": "the",
    "recieve": "receive",
    "recieved": "received",
    "recieving": "receiving",
    "accomodate": "accommodate",
    "acommodate": "accommodate",
    "definately": "definitely",
    "alot": "a lot",
    "could of been": "could have been",
    "could of had": "could have had",
    "should of been": "should have been",
    "would of been": "would have been",
    "cutsomers": "customers",
    "cutsomer": "customer",
    "i": "I",
    "dont": "don't",
    "doesnt": "doesn't",
    "wouldnt": "wouldn't",
    "couldnt": "couldn't",
    "shouldnt": "shouldn't",
    "isnt": "isn't",
    "arent": "aren't",
    "wasnt": "wasn't",
    "werent": "weren't",
    "hasnt": "hasn't",
    "havent": "haven't",
    "hadnt": "hadn't",
    "youre": "you're",
    "theyre": "they're",
    "theyve": "they've",
    "thats": "that's",
    "theres": "there's",
    "heres": "here's",
    "whens": "when's",
    "hows": "how's",
    "i'm": "I'm",
    "i'd": "I'd",
    "i'll": "I'll",
    "i've": "I've",
    "cafe": "café",
    "naive": "naïve",
    "facade": "façade",
    "deja vu": "déjà vu",
    "adn": "and",
    "agian": "again",
    "ahve": "have",
    "allready": "already",
    "alwasy": "always",
    "becasue": "because",
    "beacuse": "because",
    "becuase": "because",
    "begining": "beginning",
    "beleive": "believe",
    "cna": "can",
    "comittee": "committee",
    "commitee": "committee",
    "documetn": "document",
    "freind": "friend",
    "foward": "forward",
    "goverment": "government",
    "happend": "happened",
    "jsut": "just",
    "knowlege": "knowledge",
    "neccessary": "necessary",
    "ocasion": "occasion",
    "occured": "occurred",
    "peice": "piece",
    "peolpe": "people",
    "reccomend": "recommend",
    "seperate": "separate",
    "shoudl": "should",
    "taht": "that",
    "tahn": "than",
    "thier": "their",
    "untill": "until",
    "waht": "what",
    "wiht": "with",
    "wierd": "weird",
    "woudl": "would",
    "wnat": "want",
}


def restore_case(target: str, original: str) -> str:
    """Restore casing pattern of original word onto replacement target."""
    if not original:
        return target
    if original.isupper() and len(original) > 1:
        return target.upper()
    if original[0].isupper() and not target[0].isupper():
        return target[0].upper() + target[1:]
    return target


class AutoCorrectEngine:
    """AutoCorrect engine managing character transforms, symbol replacements, and list conversions."""

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings.get_instance()
        self.typos: dict[str, str] = dict(DEFAULT_TYPOS)
        self.symbols: dict[str, str] = dict(DEFAULT_SYMBOLS)
        self.fractions: dict[str, str] = dict(DEFAULT_FRACTIONS)
        self.exceptions: set[str] = set(DEFAULT_EXCEPTIONS)

    def is_enabled(self, option_key: str, default: bool = True) -> bool:
        """Check if a specific autocorrect feature is active in settings."""
        try:
            return bool(self.settings.get_value(option_key, default))
        except Exception:
            return default

    def smart_char(self, ch: str, prev_char: str) -> str:
        """Convert straight quotes to curly opening/closing quotes based on context."""
        if not self.is_enabled("autocorrect/smart_quotes", True):
            return ch

        if ch == '"':
            # Opening quote if preceded by whitespace, start of text, or open bracket/dash
            if not prev_char or prev_char in " \t\r\n([{—–/-«„‚\"'":
                return "“"
            return "”"

        if ch == "'":
            # Opening single quote if preceded by whitespace or open punctuation, unless preceded by a letter/number (apostrophe)
            if not prev_char or prev_char in " \t\r\n([{—–/-«„‚":
                return "‘"
            return "’"

        return ch

    def process_typing(
        self, text_before: str, typed_char: str
    ) -> tuple[int, int, str] | None:
        """Evaluate text immediately before caret when a character is typed.

        Returns (replace_start_offset, replace_end_offset, replacement_string) or None.
        """
        if not self.is_enabled("autocorrect/replace_text_as_you_type", True):
            return None

        # 1. Immediate symbol triggers on specific closing characters
        if typed_char in (")", ".", ">", "-"):
            for sym, rep in self.symbols.items():
                if text_before.endswith(sym):
                    start = len(text_before) - len(sym)
                    end = len(text_before)
                    return start, end, rep

        # 2. Em-dash conversion on double hyphen: e.g. "word--" -> "word—"
        if self.is_enabled("autocorrect/dashes", True):
            m_dash = re.search(r"(\w)--$", text_before)
            if m_dash:
                start = len(text_before) - 2
                end = len(text_before)
                return start, end, "—"

            # En-dash conversion on "word - " when typing the next word
            if text_before.endswith(" - "):
                start = len(text_before) - 3
                end = len(text_before)
                return start, end, " – "

        # 3. Delimiter triggers (space or standard punctuation)
        delimiters = ' \t\n.,;:!?)]}"\'”’'
        if typed_char not in delimiters:
            return None

        # Determine the word token just before the typed terminator
        # Note: if typed_char was already inserted into text_before, strip it for token extraction
        content = text_before
        if content.endswith(typed_char):
            content = content[:-len(typed_char)]

        m = re.search(r"(\S+)$", content)
        if not m:
            return None

        raw_token = m.group(1)
        raw_start = len(content) - len(raw_token)
        raw_end = len(content)

        # Strip leading punctuation e.g. "(" or '"'
        m_lead = re.match(r"^[(\"“‘'\[]+", raw_token)
        lead_len = len(m_lead.group(0)) if m_lead else 0
        token = raw_token[lead_len:]
        word_start = raw_start + lead_len
        word_end = raw_end

        if not token:
            return None

        # Check symbol substitution on standalone tokens (e.g. "(c)" before space)
        if raw_token in self.symbols:
            return raw_start, raw_end, self.symbols[raw_token]

        # Check fractions e.g. "1/2" -> "½"
        if self.is_enabled("autocorrect/fractions", True) and token in self.fractions:
            return word_start, word_end, self.fractions[token]

        # Check multi-word typos (e.g. "could of been")
        content_lower = content.lower()
        for pattern, rep in self.typos.items():
            if " " in pattern and content_lower.endswith(pattern):
                p_start = len(content) - len(pattern)
                p_end = len(content)
                return p_start, p_end, rep

        # Check single-word typos with case restoration
        token_lower = token.lower()
        if token in self.typos:
            return word_start, word_end, self.typos[token]
        if token_lower in self.typos:
            rep = self.typos[token_lower]
            return word_start, word_end, restore_case(rep, token)

        return None

    def process_enter(self, para_text: str) -> tuple[str, str] | None:
        """Inspect paragraph when Enter is pressed to auto-convert lists.

        Returns (kind, stripped_text) where kind is 'number' or 'bullet', or None.
        """
        if not self.is_enabled("autocorrect/auto_lists", True):
            return None

        t = para_text.rstrip("\r\n")

        # Numbered list: e.g. "1. Hello" or "1) Hello"
        m_num = re.match(r"^(\d{1,3})([.)])\s+(.*)$", t)
        if m_num:
            return "number", m_num.group(3)

        # Bullet list: e.g. "* Hello" or "- Hello" or "• Hello"
        m_bullet = re.match(r"^([*\-•>])\s+(.*)$", t)
        if m_bullet:
            return "bullet", m_bullet.group(2)

        return None
