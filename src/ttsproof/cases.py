"""Built-in edge-case benchmark corpus.

~700 deterministic cases across ~30 categories that are known to break TTS
systems. Every case carries a scoring ``policy``:

  strict      — expected spoken form is unambiguous; equivalence-aware WER gates it
  keywords    — several valid readings exist (URLs, currencies); key tokens must
                appear in the transcript instead
  structural  — no meaningful transcript exists (emoji, punctuation abuse);
                only the structural audio checks apply

The corpus is generated with a fixed seed, so case ids are stable across runs
and machines — which is what makes regression comparison meaningful.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from .normalize import GREEK_LETTERS, LETTER_WORDS

STRICT, KEYWORDS, STRUCTURAL = "strict", "keywords", "structural"


def _mk(cat: str, i: int, text: str, policy: str, language: str = "en",
        category_hint: str = "") -> dict[str, Any]:
    return {
        "id": f"{cat}_{i:03d}",
        "category": cat,
        "text": text,
        "policy": policy,
        "language": language,
        **({"category_hint": category_hint} if category_hint else {}),
    }


def _numbers(rng) -> list[dict]:
    values = [0, 1, 7, 10, 11, 13, 15, 19, 20, 21, 40, 55, 99, 100, 101, 110,
              123, 500, 999, 1000, 1001, 1234, 9999, 10000, 54321, 100000,
              123456, 999999, 1000000, 2500000]
    values += sorted(rng.sample(range(2, 10**6), 30))
    return [_mk("numbers", i, str(v), STRICT, category_hint="number")
            for i, v in enumerate(values)]


def _decimals(rng) -> list[dict]:
    texts = ["0.5", "1.5", "2.25", "3.14", "9.99", "10.01", "99.9", "100.001",
             "0.001", "12.34", "45.67", "3.333", "7.07", "50.5"]
    texts += [f"{rng.randrange(0, 500)}.{rng.randrange(1, 99):02d}" for _ in range(16)]
    return [_mk("decimals", i, t, STRICT, category_hint="number")
            for i, t in enumerate(dict.fromkeys(texts))]


def _currencies(rng) -> list[dict]:
    templates = [
        "$5", "$5.99", "$100", "$1,299", "€10", "€99.50", "£75", "£0.99",
        "500 NOK", "1.250 kr", "$1 million", "€2,5 millioner",
        "The price is $49.99 today.", "It costs €120 per month.",
        "He paid £3,500 for it.", "Tickets from $19.",
        "A budget of $2.4 million.", "Around 900 kr per night.",
    ]
    templates += [f"${rng.randrange(2, 999)}.{rng.randrange(0, 99):02d}" for _ in range(12)]
    return [_mk("currencies", i, t, KEYWORDS) for i, t in enumerate(dict.fromkeys(templates))]


def _percentages(rng) -> list[dict]:
    texts = ["5%", "50%", "99%", "100%", "0.5%", "12.5%",
             "Sales grew 25% this year.", "A 7% interest rate.",
             "Accuracy reached 99.9%.", "Down 3.2% since May."]
    texts += [f"{rng.randrange(1, 100)}%" for _ in range(10)]
    return [_mk("percentages", i, t, KEYWORDS) for i, t in enumerate(dict.fromkeys(texts))]


def _dates(rng) -> list[dict]:
    texts = [
        "May 5, 2026", "January 1, 2000", "December 31, 1999", "July 4, 1776",
        "Feb 29, 2024", "Oct 15, 2025", "March 3, 1993", "Aug 21, 2019",
        "5/5/2026", "12/31/1999", "1/1/2000", "10/10/2010", "3/14/2015",
        "The meeting is on June 9, 2026.", "Born on April 12, 1985.",
        "Sep 1, 2023 was a Friday.",
    ]
    months = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
    for _ in range(14):
        texts.append(f"{rng.choice(months)} {rng.randrange(1, 28)}, {rng.randrange(1900, 2030)}")
    return [_mk("dates", i, t, STRICT, category_hint="date_time")
            for i, t in enumerate(dict.fromkeys(texts))]


def _iso_dates() -> list[dict]:
    texts = ["2026-07-10", "1999-12-31", "2000-01-01", "2024-02-29",
             "Deployed on 2025-11-05.", "Log entry 2023-06-15.",
             "2026-01-31T14:30:00Z", "Backup at 2024-12-24T23:59:59",
             "The file 2022-03-08.txt is missing."]
    return [_mk("iso_dates", i, t, KEYWORDS) for i, t in enumerate(texts)]


def _times(rng) -> list[dict]:
    texts = ["3:30 PM", "12:00 AM", "12:00 PM", "9:05 AM", "11:59 PM",
             "6:00", "18:45", "0:30", "10:10",
             "The train leaves at 7:15 AM.", "Dinner at 8:30 PM.",
             "Alarm set for 5:45 AM.", "It ended at 23:15."]
    for _ in range(10):
        texts.append(f"{rng.randrange(1, 12)}:{rng.randrange(0, 59):02d} {rng.choice(['AM', 'PM'])}")
    return [_mk("times", i, t, STRICT, category_hint="date_time")
            for i, t in enumerate(dict.fromkeys(texts))]


def _phones(rng) -> list[dict]:
    texts = ["555-0134", "(555) 010-4477", "+1 555 010 9922", "+47 22 33 44 55",
             "+30 210 555 0199", "Call 555-0100 now.",
             "Our number is (555) 010-8844.", "Text +1-555-010-3311 to join."]
    for _ in range(10):
        texts.append(f"555-{rng.randrange(100, 999):03d}-{rng.randrange(1000, 9999):04d}")
    return [_mk("phones", i, t, KEYWORDS) for i, t in enumerate(dict.fromkeys(texts))]


def _urls() -> list[dict]:
    texts = ["example.com", "www.example.com", "https://example.com",
             "https://docs.example.com/guide", "github.com/user/repo",
             "Visit example.com for details.", "See https://api.example.com/v2/users",
             "Download from files.example.org/latest.zip",
             "The docs live at readthedocs.io."]
    return [_mk("urls", i, t, KEYWORDS) for i, t in enumerate(texts)]


def _emails() -> list[dict]:
    texts = ["hello@example.com", "support@company.co.uk", "first.last@mail.org",
             "Write to team@example.com today.", "CC admin@server.net on that.",
             "user+tag@gmail.com", "Contact sales@big-corp.io"]
    return [_mk("emails", i, t, KEYWORDS) for i, t in enumerate(texts)]


def _network() -> list[dict]:
    texts = ["192.168.1.1", "10.0.0.255", "127.0.0.1", "8.8.8.8",
             "The server is at 192.168.0.100.", "Ping 172.16.254.1 first.",
             "2001:0db8:85a3:0000:0000:8a2e:0370:7334", "fe80::1",
             "00:1B:44:11:3A:B7", "The MAC is AA:BB:CC:DD:EE:FF."]
    return [_mk("network", i, t, KEYWORDS) for i, t in enumerate(texts)]


def _roman() -> list[dict]:
    texts = ["Chapter IV", "Henry VIII", "World War II", "Rocky III",
             "Section XII", "Pope John Paul II", "Louis XIV", "Act V Scene II",
             "Super Bowl XLII", "The year MMXXVI"]
    return [_mk("roman_numerals", i, t, KEYWORDS) for i, t in enumerate(texts)]


def _abbreviations() -> list[dict]:
    texts = ["Dr. Smith lives on Main St.", "Meet Mr. Jones at 5 p.m.",
             "Mrs. Brown vs. Ms. Green", "etc.", "e.g. apples and pears",
             "i.e. the second option", "approx. 40 units", "Prof. Miller's Ph.D.",
             "St. Patrick's Day", "Ave. B and 3rd St.", "no. 42", "vol. 3, ch. 7"]
    return [_mk("abbreviations", i, t, KEYWORDS) for i, t in enumerate(texts)]


def _acronyms() -> list[dict]:
    known = ["API", "EU", "USA", "NASA", "CPU", "GPU", "HTTP", "TTS", "AM", "PM"]
    unknown = ["QRZ", "XJV", "BKP", "ZWL", "FDT", "MHX", "PQR", "VNB", "KLM", "WXY"]
    sentences = ["The API returned an error.", "NASA launched at dawn.",
                 "My CPU and GPU are busy.", "HTTP requests over TLS.",
                 "The EU and the USA signed it."]
    out = [_mk("acronyms", i, t, STRICT, category_hint="acronym")
           for i, t in enumerate(known + unknown)]
    out += [_mk("acronyms", len(out) + i, t, STRICT) for i, t in enumerate(sentences)]
    return out


def _letters() -> list[dict]:
    return [_mk("letters", i, ch, STRICT, category_hint="letter")
            for i, ch in enumerate(sorted(LETTER_WORDS))]


def _greek() -> list[dict]:
    letters = [_mk("greek_letters", i, ch, STRICT, "el", category_hint="greek_letter")
               for i, ch in enumerate(sorted(GREEK_LETTERS))]
    words = ["καλημέρα", "ευχαριστώ", "παρακαλώ", "ναι", "όχι", "νερό",
             "ελευθερία", "θάλασσα", "ουρανός", "αγάπη",
             "Καλημέρα, τι κάνεις σήμερα;", "Το τρένο φεύγει στις οκτώ."]
    return letters + [_mk("greek_words", i, w, STRICT, "el") for i, w in enumerate(words)]


def _norwegian() -> list[dict]:
    texts = ["hei", "takk", "kjærlighet", "øy", "ærlig", "å", "blåbær",
             "sjø", "kjøkken", "tjue", "sytti", "hundre",
             "Jeg heter Panos og bor i Hellas.", "Toget går klokka åtte.",
             "Det regner i Bergen i dag.", "Hun leser en bok om kvelden.",
             "Vi spiser middag sammen på lørdag.", "Tusen takk for hjelpen!",
             "Han kjøpte tre røde epler.", "Barna leker utenfor huset."]
    return [_mk("norwegian", i, t, STRICT, "no") for i, t in enumerate(texts)]


def _english_sentences() -> list[dict]:
    texts = [
        "The quick brown fox jumps over the lazy dog.",
        "She sells seashells by the seashore.",
        "How much wood would a woodchuck chuck if a woodchuck could chuck wood?",
        "Peter Piper picked a peck of pickled peppers.",
        "The sixth sick sheikh's sixth sheep is sick.",
        "Red lorry, yellow lorry.",
        "I scream, you scream, we all scream for ice cream.",
        "A proper copper coffee pot.",
        "Round the rugged rocks the ragged rascal ran.",
        "Good morning, and welcome to the show.",
        "Please leave a message after the tone.",
        "Thank you for calling; your call is important to us.",
        "The weather today is sunny with a chance of rain.",
        "Once upon a time, in a land far away, there lived a king.",
        "To be, or not to be, that is the question.",
        "The report is due by the end of the week.",
        "Turn left at the second traffic light.",
        "The results were better than expected.",
        "He read the read book he had already read.",
        "The wind was too strong to wind the sail.",
        "I object to that object.",
        "The bandage was wound around the wound.",
        "Lead paint is heavier than a lead pencil.",
        "Live wires are dangerous where you live.",
    ]
    return [_mk("english", i, t, STRICT) for i, t in enumerate(texts)]


def _mixed_language() -> list[dict]:
    texts = ["The word for thank you is takk.",
             "She said καλημέρα and smiled.",
             "We ordered a croissant and an espresso.",
             "His favorite word is kjærlighet.",
             "In Greek, water is νερό.",
             "The sign said Herzlich Willkommen.",
             "They shouted encore after the show.",
             "Departures: Oslo, Αθήνα, New York."]
    return [_mk("mixed_language", i, t, KEYWORDS) for i, t in enumerate(texts)]


def _math() -> list[dict]:
    texts = ["2 + 2 = 4", "10 - 3 = 7", "5 × 6 = 30", "100 ÷ 4 = 25",
             "x = y + 1", "E = mc²", "a² + b² = c²", "3 < 5 and 7 > 2",
             "50% of 200 is 100", "The ratio is 3:2.", "2^10 = 1024",
             "√16 = 4"]
    return [_mk("math", i, t, KEYWORDS) for i, t in enumerate(texts)]


def _punctuation_abuse() -> list[dict]:
    texts = ["!!!", "???", "?!?!?!", "...", "......", "—", "***", ";;;",
             "Hello!!!!!!", "What?!?!", "Wait... what... no...",
             "\"Quotes\" and 'quotes' and \"nested 'quotes' here\"",
             "(parentheses (inside (parentheses)))", "dash — dash — dash",
             "comma,,, comma", "#hashtag @mention"]
    return [_mk("punctuation_abuse", i, t, STRUCTURAL) for i, t in enumerate(texts)]


def _single_words() -> list[dict]:
    texts = ["yes", "no", "stop", "go", "hello", "goodbye", "wait", "help",
             "one", "why", "okay", "sure", "never", "always", "maybe",
             "strength", "squirrel", "rhythm", "sixth", "worlds"]
    return [_mk("single_words", i, t, STRICT) for i, t in enumerate(texts)]


def _vocalizations() -> list[dict]:
    texts = ["Ahh", "ahh", "Ooh", "ugh", "hmm", "Mhm", "hm", "aah",
             "ha", "ohh", "mmm", "Hmmm"]
    return [_mk("vocalizations", i, t, STRICT, category_hint="vocalization")
            for i, t in enumerate(texts)]


def _hallucination_traps() -> list[dict]:
    """Inputs known to trigger loops, replays, or invented content."""
    texts = ["buy now buy now buy now buy now",
             "the the the the the",
             "a a a a a a a a",
             "word",
             "and", "the", "of",
             "na na na na na na na na",
             "very very very very very long",
             "repeat after me repeat after me",
             "ha ha ha ha ha ha ha ha ha",
             "one two one two one two one two",
             "hello hello hello hello hello hello",
             "no no no no no no no no no no"]
    return [_mk("hallucination_traps", i, t, STRUCTURAL) for i, t in enumerate(texts)]


def _unicode_emoji() -> list[dict]:
    texts = ["🎉", "I love it 😍", "Great job 👍👍👍", "→ ← ↑ ↓", "☆★☆★",
             "café", "naïve", "résumé", "Zürich", "señor", "smörgåsbord",
             "①②③"]
    return [_mk("unicode_emoji", i, t, STRUCTURAL) for i, t in enumerate(texts)]


def _code() -> list[dict]:
    texts = ["print('hello')", "for i in range(10):", "x += 1",
             "SELECT * FROM users;", "git commit -m 'fix'",
             "sudo apt-get install", "npm run build",
             "if (a == b) { return true; }", "def main():", "</div>"]
    return [_mk("code", i, t, STRUCTURAL) for i, t in enumerate(texts)]


def _long_sentences() -> list[dict]:
    base = ("The committee, having considered the report submitted by the "
            "subcommittee on the twelfth of March, decided, after a long and "
            "at times heated discussion that touched on budgets, staffing, "
            "timelines, and the ever-present question of scope, to postpone "
            "the final decision until the following quarter")
    texts = [
        base + ".",
        base + ", when more data would be available and the new director "
               "would have taken office, allowing a fuller picture to emerge.",
        "He packed shirts, socks, shoes, belts, hats, gloves, scarves, "
        "jackets, trousers, sweaters, towels, books, chargers, cables, "
        "adapters, bottles, snacks, maps, tickets, and his passport.",
        " ".join(["The story continued without a single pause"] * 6) + ".",
    ]
    return [_mk("long_sentences", i, t, KEYWORDS) for i, t in enumerate(texts)]


def _ordinals_fractions(rng) -> list[dict]:
    texts = ["1st place", "2nd floor", "3rd time", "4th of July", "21st century",
             "the 5th element", "1/2 cup of sugar", "3/4 of the students",
             "a 2/3 majority", "1/4 mile ahead"]
    texts += [f"the {rng.randrange(5, 99)}th item" for _ in range(6)]
    return [_mk("ordinals_fractions", i, t, KEYWORDS) for i, t in enumerate(dict.fromkeys(texts))]


def _units(rng) -> list[dict]:
    texts = ["5 km", "100 m", "3.5 kg", "70 mph", "20°C", "98.6°F",
             "500 MB", "2 TB", "16 GB of RAM", "a 4 GHz processor",
             "220 V", "60 Hz", "10 cm of snow", "level 5 dB"]
    texts += [f"{rng.randrange(1, 500)} km" for _ in range(6)]
    return [_mk("units", i, t, KEYWORDS) for i, t in enumerate(dict.fromkeys(texts))]


def builtin_cases(categories: list[str] | None = None,
                  limit_per_category: int = 0,
                  seed: int = 20260710) -> list[dict[str, Any]]:
    """The full built-in corpus (deterministic for a given seed)."""
    rng = random.Random(seed)
    groups = [
        _numbers(rng), _decimals(rng), _currencies(rng), _percentages(rng),
        _dates(rng), _iso_dates(), _times(rng), _phones(rng), _urls(),
        _emails(), _network(), _roman(), _abbreviations(), _acronyms(),
        _letters(), _greek(), _norwegian(), _english_sentences(),
        _mixed_language(), _math(), _punctuation_abuse(), _single_words(),
        _vocalizations(), _hallucination_traps(), _unicode_emoji(), _code(),
        _long_sentences(), _ordinals_fractions(rng), _units(rng),
    ]
    cases: list[dict[str, Any]] = []
    for group in groups:
        if categories and group and group[0]["category"] not in categories:
            continue
        cases.extend(group[:limit_per_category] if limit_per_category else group)
    seen = set()
    for case in cases:
        if case["id"] in seen:
            raise ValueError(f"duplicate case id: {case['id']}")
        seen.add(case["id"])
    return cases


def list_categories() -> list[str]:
    return sorted({c["category"] for c in builtin_cases()})


def write_jsonl(cases: list[dict[str, Any]], path: str | Path) -> None:
    with Path(path).open("w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False) + "\n")
