from ttsproof import cer, compare_text, equivalence_compare, wer


def test_wer_exact():
    assert wer("hello world", "hello world") == 0.0


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
