# Results

These are the results from the published technical report that ttsproof's method
comes from — readable here in the browser, no download required. Full report
(method, plots, per-sample data) with a citable DOI:
**[10.5281/zenodo.20757553](https://doi.org/10.5281/zenodo.20757553)** (CC-BY-4.0).

The evaluation ran the QA method (packaged here as ttsproof) as a black-box
harness against a production neural TTS service — **130 edge cases × 3 neutral
voices = 390 samples** — plus a one-time blinded human validation of the
ASR-uncertain subset. The harness itself is fully automated; the human step only
characterizes the quarantine zone.

## Overall (N = 390)

- **0 structural audio-integrity defects** across all 390 samples — empty /
  too-short / too-long / long-silence / clipping / loop / tail. The audio was
  always structurally clean.
- Exact-match rate: **0.769**
- Auto-classification: **300 pass**, **48 hard_fail** (text-comparison
  mismatches — ASR errors + normalizer gaps in ordinals/currency/grouped-numbers/
  times; **not** audio defects), **42 manual_review** (ASR-uncertain short
  letters/acronyms the harness refuses to auto-judge because ASR is unreliable
  there).

## By text type

| text_type | n | exact | exact% | hard_fail | manual_review |
|---|---|---|---|---|---|
| acronym | 66 | 36 | 54% | 0 | 30 |
| decimal | 15 | 13 | 86% | 2 | 0 |
| letter | 36 | 25 | 69% | 0 | 11 |
| normal | 201 | 167 | 83% | 34 | 0 |
| number | 42 | 35 | 83% | 6 | 1 |
| time | 30 | 24 | 80% | 6 | 0 |

## By voice

| voice | n | exact | exact% | hard_fail | manual_review |
|---|---|---|---|---|---|
| chrisa | 130 | 94 | 72% | 19 | 17 |
| fotis | 130 | 105 | 80% | 16 | 9 |
| synovia | 130 | 101 | 77% | 13 | 16 |

## Human validation of the ASR-uncertain zone

Blinded, single rater: the **42** ASR-uncertain clips + **15** ASR-passed
controls, shuffled; clips drawn from the archive (no new audio).

- **Controls: 15/15 correct (100%)** → rater reliable.
- Of the 42 ASR-uncertain cases: **23 (55%) were ASR false-negatives** (the TTS
  said it right, ASR misheard) and **19 (45%) were genuine TTS mispronunciations.**

This is why the harness **quarantines** that zone for review instead of guessing:
auto-passing it would ship 19 real mispronunciations; auto-failing it (naive
ASR-WER) would wrongly kill 23 correct ones. The zone is a real ~45/55 mix, now
shown with data rather than asserted.

## Where the TTS actually failed (the 19)

All 19 genuine failures were short isolated letters / acronyms:

| mode | n | example |
|---|---|---|
| A-vowel substitution (A → "I" / other vowel) | 7 | `NATO`→"NITO", `USA`→"USI", `CIA`→"CII" |
| trailing appended phoneme | 7 | `GPU`→"GPUB", `EU`→"EUU", `PC`/`UN`/`UK` + extra sound |
| early truncation / cut | 1 | `R` chopped |
| doubling / repeat | 1 | `X` said twice |
| other substitution | 3 | `CEO`→"CEE", `Z`→"SZ" |

Note: the structural tail-artifact and too-short detectors did **not** fire on
these — an appended phoneme ("GPUB") is intelligible speech, not the click/pop the
tail detector targets. Structural checks and ASR-quarantine are complementary;
neither alone catches everything.

## Honest caveats

- One TTS system; three voices; 130 cases; single human rater (controls confirm
  reliability).
- The 19 failures are pronunciation/content on short tokens — distinct from the
  (zero) structural audio-integrity defects.
- The human validation is a one-time characterization; the harness runs fully
  automated.

Full method, limitations, and per-sample data are in the report:
[10.5281/zenodo.20757553](https://doi.org/10.5281/zenodo.20757553).