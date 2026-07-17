"""Edge-case text normalization and input classification for TTS QA.

Numbers, decimals, dates, clock times, acronyms, isolated letters and
vocalizations are expanded to the words a listener should hear, so that the
text sent to a TTS engine and the text expected back from ASR agree.

Ported from the QA harness evaluated in DOI 10.5281/zenodo.20757553.
"""

from __future__ import annotations

import re

LETTER_WORDS = {
    "A": "ay", "B": "bee", "C": "see", "D": "dee", "E": "ee", "F": "eff",
    "G": "gee", "H": "aitch", "I": "eye", "J": "jay", "K": "kay", "L": "ell",
    "M": "em", "N": "en", "O": "oh", "P": "pee", "Q": "cue", "R": "are",
    "S": "ess", "T": "tee", "U": "you", "V": "vee", "W": "double you",
    "X": "ex", "Y": "why", "Z": "zee",
}

ACRONYM_WORDS = {
    "API": "ay pee eye",
    "EU": "ee you",
    "USA": "you ess ay",
    "NASA": "nasa",
    "CPU": "see pee you",
    "GPU": "gee pee you",
    "HTTP": "aitch tee tee pee",
    "TTS": "tee tee ess",
    "AM": "ay em",
    "PM": "pee em",
}

GREEK_LETTERS = {
    "Α": "άλφα", "Η": "ήτα", "Θ": "θήτα", "Χ": "χι", "Β": "βήτα",
    "Γ": "γάμμα", "Δ": "δέλτα", "Ρ": "ρο", "Ω": "ωμέγα",
}

ONES = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen",
]

TENS = {20: "twenty", 30: "thirty", 40: "forty", 50: "fifty", 60: "sixty",
        70: "seventy", 80: "eighty", 90: "ninety"}

MONTHS = {
    "january": "January", "jan": "January", "february": "February", "feb": "February",
    "march": "March", "mar": "March", "april": "April", "apr": "April", "may": "May",
    "june": "June", "jun": "June", "july": "July", "jul": "July", "august": "August",
    "aug": "August", "september": "September", "sep": "September", "sept": "September",
    "october": "October", "oct": "October", "november": "November", "nov": "November",
    "december": "December", "dec": "December",
}

MONTH_BY_NUMBER = {i + 1: m for i, m in enumerate([
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December"])}

ORDINALS = {
    1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth",
    7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth", 11: "eleventh",
    12: "twelfth", 13: "thirteenth", 14: "fourteenth", 15: "fifteenth",
    16: "sixteenth", 17: "seventeenth", 18: "eighteenth", 19: "nineteenth",
    20: "twentieth", 21: "twenty first", 22: "twenty second", 23: "twenty third",
    24: "twenty fourth", 25: "twenty fifth", 26: "twenty sixth",
    27: "twenty seventh", 28: "twenty eighth", 29: "twenty ninth",
    30: "thirtieth", 31: "thirty first",
}

# Thousands separator inside a number: "1,000" -> "1000". Stripped before
# classification so grouped numbers reach the `number` path instead of the
# generic `\b\d+\b` fallback, which would split on the comma and read "1,000"
# as "one" + "zero". The lookahead requires exactly three following digits, so
# comma-as-punctuation ("In 1995, we shipped", "options 1,2,3") is untouched.
THOUSANDS_SEPARATOR = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")


def plain_token(text: str) -> str:
    return re.sub(r"^[\s\"']+|[\s.!?,;:\"']+$", "", str(text or "")).strip()


def is_vocalization(text: str) -> bool:
    """True for non-lexical vocalizations such as 'ahh', 'hmm', 'ugh'."""
    token = plain_token(text).lower()
    patterns = (
        r"a+h+", r"aa+h+", r"ha+h?", r"o+h+", r"o+oh+", r"u+gh+",
        r"m+", r"hm+", r"h+m+", r"mhm+",
    )
    return bool(re.fullmatch(r"(?:" + "|".join(patterns) + r")", token))


def has_greek(text: str) -> bool:
    return bool(re.search(r"[Α-Ωα-ωΆ-Ώά-ώ]", str(text or "")))


def classify_input(text: str, category: str = "") -> str:
    """Classify input text into a QA type.

    Returns one of: vocalization, letter, greek_letter, acronym, decimal,
    number, time, greek_word, normal. An explicit ``category`` (from a case
    fixture) wins over heuristics.
    """
    cat = str(category or "").strip().lower()
    raw = str(text or "").strip()
    token = plain_token(raw)

    if cat in {"vocalization", "emotional_sound"} or is_vocalization(raw):
        return "vocalization"
    if cat in {"letter", "isolated_letter"}:
        return "greek_letter" if token in GREEK_LETTERS else "letter"
    if cat == "acronym":
        return "acronym"
    if cat == "number":
        return "decimal" if re.fullmatch(r"\d+\.\d+", token) else "number"
    if cat in {"time", "date_time"}:
        return "time"
    if cat in {"greek_letter", "greek_word"}:
        return cat

    if token in GREEK_LETTERS:
        return "greek_letter"
    if len(token) == 1 and token.upper() in LETTER_WORDS:
        return "letter"
    if re.fullmatch(r"[A-Z]{2,6}", token):
        return "acronym"
    if re.fullmatch(r"\d+\.\d+", token):
        return "decimal"
    if re.search(r"\b\d{1,2}:\d{2}\b", raw) or re.search(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", raw):
        return "time"
    if re.fullmatch(r"\d+", token):
        return "number"
    if has_greek(raw):
        return "greek_word"
    return "normal"


SHORT_TYPES = {"letter", "vocalization", "greek_letter"}


def number_to_words(value: int) -> str:
    if value < 0:
        return "minus " + number_to_words(abs(value))
    if value < 20:
        return ONES[value]
    if value < 100:
        tens = (value // 10) * 10
        rest = value % 10
        return TENS[tens] if rest == 0 else f"{TENS[tens]} {ONES[rest]}"
    if value < 1000:
        rest = value % 100
        head = f"{ONES[value // 100]} hundred"
        return head if rest == 0 else f"{head} {number_to_words(rest)}"
    if value < 1_000_000:
        rest = value % 1000
        head = f"{number_to_words(value // 1000)} thousand"
        return head if rest == 0 else f"{head} {number_to_words(rest)}"
    rest = value % 1_000_000
    head = f"{number_to_words(value // 1_000_000)} million"
    return head if rest == 0 else f"{head} {number_to_words(rest)}"


def ordinal_to_words(value: int) -> str:
    return ORDINALS.get(value, number_to_words(value))


def decimal_to_words(text: str) -> str:
    left, right = text.split(".", 1)
    if len(right) == 4 and right[:2] == right[2:]:
        right = right[:2]
    left_words = number_to_words(int(left))
    if len(right) == 2 and not right.startswith("0"):
        right_words = number_to_words(int(right))
    elif len(right) == 1:
        right_words = ONES[int(right)]
    else:
        right_words = " ".join("oh" if ch == "0" else ONES[int(ch)] for ch in right)
    return f"{left_words} point {right_words}"


def expand_acronym(token: str) -> str:
    known = ACRONYM_WORDS.get(token.upper())
    if known:
        return known
    return " ".join(LETTER_WORDS[ch] for ch in token.upper() if ch in LETTER_WORDS)


def _replace_time(match: re.Match[str]) -> str:
    hour = int(match.group(1))
    minute = int(match.group(2))
    suffix = (match.group(3) or "").upper().replace(".", "")
    hour_text = number_to_words(hour)
    if minute == 0:
        minute_text = "o clock"
    elif minute < 10:
        minute_text = "oh " + number_to_words(minute)
    else:
        minute_text = number_to_words(minute)
    suffix_text = ""
    if suffix == "AM":
        suffix_text = " ay em"
    elif suffix == "PM":
        suffix_text = " pee em"
    return f"{hour_text} {minute_text}{suffix_text}".strip()


def _replace_numeric_date(match: re.Match[str]) -> str:
    month_num = int(match.group(1))
    day_num = int(match.group(2))
    year_num = int(match.group(3))
    if year_num < 100:
        year_num += 2000
    month = MONTH_BY_NUMBER.get(month_num, number_to_words(month_num))
    return f"{month} {ordinal_to_words(day_num)} {number_to_words(year_num)}"


def _replace_month_date(match: re.Match[str]) -> str:
    month = MONTHS[match.group(1).lower()]
    day = ordinal_to_words(int(match.group(2)))
    year = number_to_words(int(match.group(3)))
    return f"{month} {day} {year}"


def normalize_text(text: str, category: str = "") -> str:
    """Expand a raw input string to the words a listener should hear."""
    raw = str(text or "").strip()
    out = (
        raw.replace("“", '"').replace("”", '"')
        .replace("‘", "'").replace("’", "'")
        .replace("…", "...")
    )
    out = THOUSANDS_SEPARATOR.sub("", out)
    text_type = classify_input(out, category)
    token = plain_token(out)

    if text_type == "vocalization":
        return out
    if text_type == "greek_letter" and token in GREEK_LETTERS:
        return GREEK_LETTERS[token]
    if text_type == "letter" and token.upper() in LETTER_WORDS:
        return LETTER_WORDS[token.upper()]
    if text_type == "acronym":
        return expand_acronym(token)
    if text_type == "decimal":
        return decimal_to_words(token)
    if text_type == "number":
        return number_to_words(int(token))

    month_names = "|".join(sorted(MONTHS, key=len, reverse=True))
    out = re.sub(
        rf"\b({month_names})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?[,]?\s+(\d{{4}})\b",
        _replace_month_date, out, flags=re.IGNORECASE,
    )
    out = re.sub(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b", _replace_numeric_date, out)
    out = re.sub(r"\b(\d{1,2}):(\d{2})\s*([AaPp]\.?[Mm]\.?)?\b", _replace_time, out)
    out = re.sub(r"\b\d+\.\d+\b", lambda m: decimal_to_words(m.group(0)), out)
    out = re.sub(r"\b\d+\b", lambda m: number_to_words(int(m.group(0))), out)
    out = re.sub(r"\b[A-Z]{2,6}\b", lambda m: expand_acronym(m.group(0)), out)
    out = out.replace("...", ", ")
    return re.sub(r"\s+", " ", out).strip()


def retry_text(normalized_text: str, text_type: str) -> str:
    """A slightly rephrased variant used for one retry after a hard failure."""
    text = str(normalized_text or "").strip()
    if not text:
        return text
    if text_type == "number" and text.lower() == "ten":
        return "the number ten"
    return text if text.endswith((".", "!", "?")) else text + "."
