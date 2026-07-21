"""Equivalence-aware pronunciation metrics.

Plain WER against raw text punishes a TTS system for saying "May fifth twenty
twenty six" when the input was "May 5, 2026" — which is exactly what it should
say. ``compare_text`` maps both the expected text and the ASR transcript into
one canonical spoken form first, so WER/CER measure real pronunciation errors,
not formatting differences.

Ported from the QA harness evaluated in DOI 10.5281/zenodo.20757553.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from .normalize import normalize_text, number_to_words, ONES


def _fold_diacritics(text: str) -> str:
    """Reykjavík == Reykjavik, Göteborg == Goteborg — applied to BOTH sides,
    so languages that keep their marks (å in Norwegian) still compare equal."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def levenshtein(seq_a: list[str] | str, seq_b: list[str] | str) -> int:
    if len(seq_a) < len(seq_b):
        seq_a, seq_b = seq_b, seq_a
    previous = list(range(len(seq_b) + 1))
    for i, item_a in enumerate(seq_a, 1):
        current = [i]
        for j, item_b in enumerate(seq_b, 1):
            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            replace_cost = previous[j - 1] + (0 if item_a == item_b else 1)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def wer(expected: str, actual: str) -> float:
    """Word error rate between two already-canonicalized strings."""
    expected_words = expected.split()
    actual_words = actual.split()
    if not expected_words:
        return 0.0 if not actual_words else 1.0
    return levenshtein(expected_words, actual_words) / float(len(expected_words))


def cer(expected: str, actual: str) -> float:
    """Character error rate between two already-canonicalized strings."""
    expected_chars = expected.replace(" ", "")
    actual_chars = actual.replace(" ", "")
    if not expected_chars:
        return 0.0 if not actual_chars else 1.0
    return levenshtein(expected_chars, actual_chars) / float(len(expected_chars))


def _ampm_words(suffix: str) -> str:
    suffix = suffix.lower().replace(".", "").replace(" ", "")
    if suffix in {"a", "am", "m"}:
        return "ay em"
    if suffix in {"p", "pm"}:
        return "pee em"
    return ""


def _time_words(hour: int, minute: int, suffix: str = "") -> str:
    hour_text = number_to_words(hour)
    if minute == 0:
        minute_text = "o clock"
    elif minute < 10:
        minute_text = "oh " + number_to_words(minute)
    else:
        minute_text = number_to_words(minute)
    return f"{hour_text} {minute_text} {_ampm_words(suffix)}".strip()


def _preprocess_numeric_times(text: str) -> str:
    out = str(text or "")
    out = re.sub(r"\b([AaPp])\s*\.?\s*[Mm]\.?\b", lambda m: m.group(1).lower() + "m", out)

    def replace_compact(match: re.Match[str]) -> str:
        return _time_words(int(match.group(1)), int(match.group(2)), match.group(3) or "")

    suffix = r"([AaPp](?:[Mm])?|[Mm])"
    out = re.sub(rf"\b(\d{{1,2}})([0-5]\d)\s*{suffix}\b", replace_compact, out)
    out = re.sub(rf"\b(\d{{1,2}})\s+([0-5]\d)\s*{suffix}\b", replace_compact, out)
    out = re.sub(rf"\b(\d{{1,2}}):([0-5]\d)\s*{suffix}?\b", replace_compact, out)
    out = re.sub(rf"\b(\d{{1,2}})\.([0-5]\d)\s*{suffix}\b", replace_compact, out)
    return out


def _canonical_acronym_phrases(text: str) -> str:
    """Map different valid spellings/hearings of an acronym to one canonical token."""
    out = str(text or "").lower()
    out = re.sub(r"[-_/]+", " ", out)
    out = re.sub(r"\be\s*\.?\s*u\s*\.?\b", " eu ", out)
    out = re.sub(r"\bee\s+you\b", " eu ", out)
    out = re.sub(r"\be\s+you\b", " eu ", out)
    out = re.sub(r"\bay\s+you\b", " eu ", out)
    out = re.sub(r"\bu\.\s*s\.?(?!\w)", " usa ", out)
    out = re.sub(r"\bu\s*\.?\s*s\s*\.?\s*a\s*\.?\b", " usa ", out)
    out = re.sub(r"\byou\s+ess\s+ay\b", " usa ", out)
    out = re.sub(r"\ba\s+p\s+i\b", " api ", out)
    out = re.sub(r"\bay\s+pee\s+eye\b", " api ", out)
    out = re.sub(r"\bsee\s+pee\s+you\b", " cpu ", out)
    out = re.sub(r"\bgee\s+pee\s+you\b", " gpu ", out)
    out = re.sub(r"\baitch\s+tee\s+tee\s+pee\b", " http ", out)
    out = re.sub(r"\btee\s+tee\s+ess\b", " tts ", out)
    return out


# --- Numeral-literal + context-gated roman canonicalization -----------------
# These run BEFORE compare_text lowercases/strips, so casing is available.
# They are applied by call site (equivalence_compare = strict, keyword_coverage
# = keywords) so each fix only touches the policy it is meant for.

# words that put a following (>=2-char) roman token into a roman/regnal reading
ROMAN_CONTEXT = {
    "chapter", "section", "part", "book", "act", "scene", "volume", "vol",
    "canto", "appendix", "figure", "table", "number", "no", "war", "bowl",
    "olympiad", "dynasty", "pope", "saint", "st", "king", "queen", "emperor",
    "empress", "tsar", "sultan", "louis", "henry", "george", "edward",
    "william", "richard", "charles", "elizabeth", "james", "philip",
    "ferdinand", "frederick", "christian", "gustav", "carl", "olav", "harald",
    "benedict", "pius", "paul", "john", "gregory", "leo", "clement", "urban",
    "innocent", "year", "class", "mark", "type", "phase", "level", "grade",
    "world",
}
# capitalized words that must NOT count as a proper-noun context trigger
_FUNCTION_WORDS = {
    "my", "the", "a", "an", "of", "size", "this", "that", "your", "our", "his",
    "her", "its", "their", "in", "on", "at", "to", "is", "was", "it", "and",
    "or", "for", "with",
}
_ROMAN_RE = re.compile(r"^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$")
_ROMAN_VALUE = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
_ORDINAL_TO_CARDINAL = {
    "first": "one", "second": "two", "third": "three", "fourth": "four",
    "fifth": "five", "sixth": "six", "seventh": "seven", "eighth": "eight",
    "ninth": "nine", "tenth": "ten", "eleventh": "eleven", "twelfth": "twelve",
    "thirteenth": "thirteen", "fourteenth": "fourteen", "fifteenth": "fifteen",
    "sixteenth": "sixteen", "seventeenth": "seventeen", "eighteenth": "eighteen",
    "nineteenth": "nineteen", "twentieth": "twenty", "thirtieth": "thirty",
}


def _roman_to_int(numeral: str) -> int:
    total = prev = 0
    for ch in reversed(numeral):
        value = _ROMAN_VALUE[ch]
        total += -value if value < prev else value
        prev = max(prev, value)
    return total


def _is_proper_noun(token: str) -> bool:
    return bool(re.match(r"^[A-Z][a-z]+$", token)) and token.lower() not in _FUNCTION_WORDS


def _roman_context_ok(core: str, prev_core: str) -> bool:
    """A well-formed roman expands only in context, AND only when it is >=2
    chars. A single roman letter (C/D/I/L/M/V/X) is too ambiguous to expand
    ('Vitamin C', 'Model X', 'Figure X', 'Section C', the pronoun 'I') — and it
    never needs to, because keyword_coverage already drops <2-char tokens
    ('Act V' passes on {act, scene, two} without expanding the 'V')."""
    if not prev_core or len(core) < 2:
        return False
    return prev_core.lower() in ROMAN_CONTEXT or _is_proper_noun(prev_core)


def expand_numerals_in_context(text: str) -> str:
    """In a roman/regnal context, (a) expand a well-formed roman numeral to its
    cardinal words and (b) reconcile a spelled ordinal ('the Eighth') to the
    same cardinal, so 'Henry VIII' == 'Henry the Eighth'. Context-gated so
    unrelated capitals ('Vitamin C', 'She came first') are untouched."""
    tokens = str(text or "").split()
    out: list[str] = []
    for i, token in enumerate(tokens):
        core = re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$", "", token)
        j = i - 1
        if j >= 0 and re.sub(r"[^A-Za-z]", "", tokens[j]).lower() == "the":
            j -= 1  # look past an intervening "the" (Henry the Eighth)
        prev_core = re.sub(r"[^A-Za-z]", "", tokens[j]) if j >= 0 else ""
        if (core.isupper() and _ROMAN_RE.match(core) and _roman_to_int(core) > 0
                and _roman_context_ok(core, prev_core)):
            out.append(token.replace(core, number_to_words(_roman_to_int(core))))
            continue
        if (core.lower() in _ORDINAL_TO_CARDINAL
                and (prev_core.lower() in ROMAN_CONTEXT or _is_proper_noun(prev_core))):
            out.append(token.replace(core, _ORDINAL_TO_CARDINAL[core.lower()]))
            continue
        out.append(token)
    return " ".join(out)


def compare_text(text: str) -> str:
    """Canonical spoken form used on both sides of the comparison."""
    normalized = _preprocess_numeric_times(str(text or ""))
    normalized = normalize_text(normalized)
    normalized = normalized.lower().replace("&", " and ")
    normalized = _canonical_acronym_phrases(normalized)
    normalized = _fold_diacritics(normalized)
    normalized = re.sub(r"[^a-z0-9α-ωæøß\s]", " ", normalized, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", normalized).strip()


_STOPWORDS = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "at",
              "is", "was", "for", "it", "with", "that", "this"}


def keyword_coverage(expected: str, transcript: str) -> float:
    """Fraction of salient expected tokens that appear in the transcript.

    Used for categories with multiple valid readings (URLs, currencies, ...):
    instead of exact spoken-form matching, the key content words/digits must
    survive the TTS -> ASR round trip.
    """
    exp_tokens = [t for t in compare_text(expand_numerals_in_context(expected)).split()
                  if len(t) >= 2 and t not in _STOPWORDS]
    if not exp_tokens:
        return 1.0
    got = set(compare_text(expand_numerals_in_context(transcript)).split())
    hit = sum(1 for t in exp_tokens if t in got)
    return hit / len(exp_tokens)


def equivalence_compare(expected: str, actual: str) -> dict[str, Any]:
    """Compare expected text and an ASR transcript in canonical spoken form.

    Returns ``expected_cmp``/``actual_cmp`` (the canonical strings — feed these
    to :func:`wer` / :func:`cer`), ``equivalent`` (canonical match), and
    ``equivalence_pass`` (canonical match where the raw strings differed —
    i.e. the equivalence layer did real work).
    """
    expected_cmp = compare_text(expected)
    actual_cmp = compare_text(actual)
    expected_plain = re.sub(r"\s+", " ", str(expected or "").strip().lower())
    actual_plain = re.sub(r"\s+", " ", str(actual or "").strip().lower())
    equivalent = expected_cmp == actual_cmp
    return {
        "expected_cmp": expected_cmp,
        "actual_cmp": actual_cmp,
        "equivalent": equivalent,
        "equivalence_pass": bool(equivalent and expected_plain != actual_plain),
    }
