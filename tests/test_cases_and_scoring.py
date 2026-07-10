"""Corpus integrity + policy scoring + regression math."""

import json

import numpy as np
import soundfile as sf

from ttsproof import (builtin_cases, category_scores, keyword_coverage,
                      list_categories, qa_sample, regression, summarize)

SR = 24000


def speechlike_wav(path, seconds=1.5, seed=5):
    rng = np.random.default_rng(seed)
    t = np.linspace(0, seconds, int(SR * seconds), endpoint=False)
    env = 0.55 + 0.45 * np.sin(2 * np.pi * 2.1 * t)
    audio = (rng.standard_normal(len(t)) * 0.25 + np.sin(2 * np.pi * 180 * t)) * env * 0.15
    fade = max(1, int(SR * 0.2))          # natural fade-out so the tail check stays quiet
    audio[-fade:] *= np.linspace(1.0, 0.05, fade)
    sf.write(str(path), audio.astype("float32"), SR)
    return path


class FakeASR:
    def __init__(self, transcript):
        self.transcript = transcript

    def transcribe(self, audio_path, language="en"):
        return self.transcript


def test_corpus_size_and_unique_ids():
    cases = builtin_cases()
    assert len(cases) >= 500, f"corpus too small: {len(cases)}"
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids))


def test_corpus_policies_valid():
    for case in builtin_cases():
        assert case["policy"] in {"strict", "keywords", "structural"}
        assert case["text"].strip()
        assert case["category"]


def test_corpus_deterministic():
    a = [c["text"] for c in builtin_cases()]
    b = [c["text"] for c in builtin_cases()]
    assert a == b


def test_categories_cover_the_promises():
    cats = set(list_categories())
    for expected in ["numbers", "dates", "currencies", "urls", "phones",
                     "norwegian", "greek_letters", "hallucination_traps",
                     "punctuation_abuse", "letters"]:
        assert expected in cats


def test_keyword_coverage():
    assert keyword_coverage("Visit example.com for details", "visit example com for details") == 1.0
    assert keyword_coverage("github.com/user/repo", "totally unrelated words") < 0.5


def test_keywords_policy_pass(tmp_path):
    wav = speechlike_wav(tmp_path / "kw.wav")
    row = qa_sample("The price is $49.99 today.", wav, policy="keywords",
                    asr=FakeASR("the price is forty nine ninety nine today"))
    assert row["verdict"] == "pass", row["error_reason"]


def test_keywords_policy_fail(tmp_path):
    wav = speechlike_wav(tmp_path / "kw2.wav")
    row = qa_sample("The price is $49.99 today.", wav, policy="keywords",
                    asr=FakeASR("completely different words entirely"))
    assert row["verdict"] == "hard_fail"


def test_structural_policy_ignores_asr(tmp_path):
    wav = speechlike_wav(tmp_path / "st.wav")
    row = qa_sample("!!!", wav, policy="structural", asr=FakeASR("anything"))
    assert row["verdict"] == "pass"
    assert row["asr_text"] == ""


def test_strict_quarantine_short(tmp_path):
    wav = speechlike_wav(tmp_path / "q.wav", seconds=0.5)
    row = qa_sample("B", wav, category_hint="letter", policy="strict",
                    asr=FakeASR("dee"))
    assert row["verdict"] == "quarantine"


def test_category_scores_and_regression(tmp_path):
    wav = speechlike_wav(tmp_path / "s.wav")
    rows = [
        qa_sample("hello world", wav, sample_id="a1", category="english",
                  policy="strict", asr=FakeASR("hello world")),
        qa_sample("hello world", wav, sample_id="a2", category="english",
                  policy="strict", asr=FakeASR("goodbye moon")),
    ]
    cats = category_scores(rows)
    assert cats["english"]["score"] == 0.5
    old = {"summary": {"overall_score": 0.9}, "categories": {"english": {"score": 0.9}}}
    new = {"summary": summarize(rows), "categories": cats}
    findings = regression(old, new, tolerance_pp=1.0)
    assert findings, "expected a regression finding"
    assert any("english" in f for f in findings)
