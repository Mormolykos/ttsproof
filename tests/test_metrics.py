from ttsproof import cer, compare_text, equivalence_compare, wer
from ttsproof.metrics import expand_numerals_in_context, keyword_coverage


def test_wer_exact():
    assert wer("hello world", "hello world") == 0.0


# --- context-gated roman numerals -------------------------------------------

def test_roman_expands_in_context():
    assert keyword_coverage("Chapter IV", "Chapter 4") == 1.0
    assert keyword_coverage("Section XII", "Section 12") == 1.0
    assert keyword_coverage("Super Bowl XLII", "Super Bowl 42") == 1.0


def test_roman_regnal_ordinal_equivalence():
    # cardinal (from VIII) reconciles with the correct English ordinal reading
    assert keyword_coverage("Henry VIII", "Henry the Eighth") == 1.0
    assert keyword_coverage("Pope John Paul II", "Pope John Paul the Second") == 1.0


def test_roman_long_numeral_by_grammar_not_char_cap():
    assert "one thousand seven hundred seventy six" in compare_text(
        expand_numerals_in_context("Chapter MDCCLXXVI"))
    assert "one thousand nine hundred eighty four" in compare_text(
        expand_numerals_in_context("Part MCMLXXXIV"))


def test_roman_context_gate_does_not_overfire():
    # abbreviations / units / drug names that look like romans must be left alone
    for phrase in ("My CV is attached", "Size XL shirt", "5 CM of rain",
                   "IV drip", "Vitamin C", "Hepatitis C", "Model X", "Plan C",
                   "Then I saw", "When I arrived"):
        assert expand_numerals_in_context(phrase) == phrase


def test_single_char_roman_never_expanded():
    # a lone roman letter is too ambiguous (label vs numeral) and never needs to
    # expand — keyword_coverage drops <2-char tokens, so 'Act V' still passes.
    for phrase in ("Appendix C", "Figure X", "Class D", "Type C", "Grade D",
                   "Table X", "Section C", "Act V", "Chapter I", "Vitamin C"):
        assert expand_numerals_in_context(phrase) == phrase
    # a multi-char roman still expands in context (label or numeric trigger)
    assert expand_numerals_in_context("Figure XII") == "Figure twelve"
    assert keyword_coverage("Act V Scene II", "Act 5 Scene 2") == 1.0


def test_ordinal_reconciliation_is_context_gated_not_global():
    # a non-regnal ordinal must stay an ordinal (metric still catches errors)
    for phrase in ("She came first", "the fourth dimension", "won first place"):
        assert expand_numerals_in_context(phrase) == phrase


def test_mac_address_roman_hex_not_expanded():
    # 'CC' in a MAC address is not a roman numeral in context
    assert expand_numerals_in_context("The MAC is AA:BB:CC:DD:EE:FF.") == \
        "The MAC is AA:BB:CC:DD:EE:FF."


def test_wer_substitution():
    assert wer("hello world", "hello word") == 0.5


def test_cer_empty_expected():
    assert cer("", "") == 0.0
    assert cer("", "x") == 1.0


def test_date_equivalence():
    # ASR engines emit years as digits; both sides canonicalize identically
    eq = equivalence_compare("May 5, 2026", "may fifth, 2026")
    assert eq["equivalent"]
    assert eq["equivalence_pass"]


def test_time_equivalence():
    eq = equivalence_compare("3:30 PM", "three thirty pee em")
    assert eq["equivalent"]


def test_acronym_equivalence():
    eq = equivalence_compare("USA", "u s a")
    assert eq["equivalent"]


def test_real_mismatch_not_equivalent():
    eq = equivalence_compare("hello world", "goodbye world")
    assert not eq["equivalent"]
    assert wer(eq["expected_cmp"], eq["actual_cmp"]) > 0.0


def test_compare_text_canonicalizes_numbers():
    assert compare_text("I have 2 cats") == compare_text("I have two cats")


def test_grouped_number_equivalence():
    # ASR writes "1,000"; the expected text expands to "one thousand". A correct
    # utterance must not hard-fail on the thousands separator alone.
    eq = equivalence_compare("one thousand", "1,000")
    assert eq["equivalent"]
    assert wer(eq["expected_cmp"], eq["actual_cmp"]) == 0.0
    assert compare_text("1,000") == compare_text("1000") == "one thousand"
