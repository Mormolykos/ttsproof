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
from typing import Any

from .normalize import normalize_text, number_to_words, ONES


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


def compare_text(text: str) -> str:
    """Canonical spoken form used on both sides of the comparison."""
    normalized = _preprocess_numeric_times(str(text or ""))
    normalized = normalize_text(normalized)
    normalized = normalized.lower().replace("&", " and ")
    normalized = _canonical_acronym_phrases(normalized)
    normalized = re.sub(r"[^a-z0-9α-ωά-ώæøåäöüéèêçñß\s]", " ", normalized, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", normalized).strip()


_STOPWORDS = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "at",
              "is", "was", "for", "it", "with", "that", "this"}


def keyword_coverage(expected: str, transcript: str) -> float:
    """Fraction of salient expected tokens that appear in the transcript.

    Used for categories with multiple valid readings (URLs, currencies, ...):
    instead of exact spoken-form matching, the key content words/digits must
    survive the TTS -> ASR round trip.
    """
    exp_tokens = [t for t in compare_text(expected).split()
                  if len(t) >= 2 and t not in _STOPWORDS]
    if not exp_tokens:
        return 1.0
    got = set(compare_text(transcript).split())
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
