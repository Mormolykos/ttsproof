from ttsproof import classify_input, is_vocalization, normalize_text


def test_single_letter():
    assert classify_input("B") == "letter"
    assert normalize_text("B") == "bee"


def test_acronym():
    assert classify_input("GPU") == "acronym"
    assert normalize_text("GPU") == "gee pee you"


def test_unknown_acronym_spelled_out():
    assert normalize_text("QRZ") == "cue are zee"


def test_number():
    assert classify_input("42") == "number"
    assert normalize_text("42") == "forty two"


def test_grouped_number():
    # ASR backends transcribe spoken numbers with thousands separators, so the
    # grouped form must expand identically to the bare form.
    assert normalize_text("1,000") == normalize_text("1000") == "one thousand"
    assert normalize_text("10,000") == "ten thousand"
    assert normalize_text("1,234,567") == (
        "one million two hundred thirty four thousand five hundred sixty seven"
    )


def test_grouped_number_in_context():
    assert normalize_text("$1,500") == "$one thousand five hundred"
    assert normalize_text("3,000 km") == "three thousand km"
    assert normalize_text("1,000.50") == "one thousand point fifty"


def test_comma_as_punctuation_is_not_a_separator():
    # Only a comma followed by exactly three digits groups a number; ordinary
    # punctuation and digit lists must survive untouched.
    assert normalize_text("In 1995, we shipped") == (
        "In one thousand nine hundred ninety five, we shipped"
    )
    assert normalize_text("Chapter 5, page 12") == "Chapter five, page twelve"
    assert normalize_text("options 1,2,3") == "options one,two,three"


def test_decimal():
    assert classify_input("3.14") == "decimal"
    # two-digit fractions read as one number (paper-validated behavior)
    assert normalize_text("3.14") == "three point fourteen"


def test_time():
    assert normalize_text("Meet me at 3:30 PM") == "Meet me at three thirty pee em"


def test_date():
    assert normalize_text("May 5, 2026") == "May fifth two thousand twenty six"


def test_vocalization_untouched():
    assert is_vocalization("Ahh")
    assert normalize_text("Ahh") == "Ahh"


def test_greek_letter():
    assert classify_input("Ω") == "greek_letter"
    assert normalize_text("Ω") == "ωμέγα"


def test_normal_sentence_numbers_expanded():
    assert normalize_text("I bought 3 apples") == "I bought three apples"
