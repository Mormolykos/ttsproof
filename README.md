# TTSProof

**Automated failure-mode QA for text-to-speech systems.**

Your TTS pipeline can produce a clip that is empty, half-silent, clipped, stuck
in a loop, or three times longer than it should be — and a WER score alone will
miss most of it, while plain WER *also* fails perfectly good audio because the
input said `3:30 PM` and the transcript said `three thirty pee em`.

TTSProof runs the checks that catch what actually breaks:

- **Structural audio checks (no model needed):** empty/truncated audio,
  duration explosions, long internal silences, clipping, repeated-chunk loop
  detection, end-of-clip artifacts. Just numpy + soundfile.
- **Equivalence-aware WER/CER:** expected text and ASR transcript are both
  canonicalized to spoken form (numbers, decimals, dates, clock times,
  acronyms, single letters) before scoring — so formatting differences don't
  count as pronunciation errors.
- **ASR-uncertainty quarantine:** when audio is structurally clean but ASR
  disagrees on a very short utterance (a letter, an acronym, "ahh"), the sample
  is quarantined for human review instead of counted as a failure — because at
  that length, the ASR is as likely to be wrong as the TTS.

The method was evaluated on a production TTS service — 130 edge cases × 3
voices (390 samples), with a blinded human validation of the quarantine zone —
and published as a citable technical report:

> **An Automated Failure-Mode QA Framework for Neural Text-to-Speech Systems**
> DOI: [10.5281/zenodo.20757553](https://doi.org/10.5281/zenodo.20757553) (CC-BY-4.0)

## Install

```bash
pip install ttsproof            # structural checks + metrics + benchmark corpus
pip install "ttsproof[asr]"     # + faster-whisper for pronunciation gating
```

## Benchmark any TTS engine in one command

TTSProof ships a **built-in corpus of 817 curated edge cases across 39
categories** — numbers, decimals, currencies, dates, ISO timestamps, clock
times, time zones, phone numbers, URLs, emails, IP/MAC addresses, file paths,
Roman numerals, ordinals, units, abbreviations, acronyms, single letters,
**pronunciation torture words** (Worcestershire, synecdoche, colonel…),
**proper names** (Reykjavík, Nguyễn, Tchaikovsky…), scientific/medical
vocabulary, tongue twisters, homographs, Greek, Norwegian, mixed-language
lines, math, punctuation abuse, hallucination traps, emoji, SQL/JSON/markup,
and more.

The corpus is **versioned independently of the software** (this release:
**Benchmark Corpus 1.0**) — published scores stay comparable across tool
updates, and every report records both versions:

```bash
# your engine as a command template ({text} in, {out} wav path out):
ttsproof benchmark --cmd "mytts --text {text} --wav {out}"

# or score audio you already generated (files named <case_id>.wav):
ttsproof generate --out cases.jsonl        # export the corpus, synthesize it your way
ttsproof benchmark --wav-dir ./my_audio
```

You get a category scoreboard in the terminal…

```
  numbers                 98.3%   59/60 decided
  dates                   96.7%   29/30 decided
  urls                    88.9%   8/9 decided   (+0 quarantined)
  norwegian               95.0%   19/20 decided
  ----------------------------------------------------------
  OVERALL 96.1%   pass=485 fail=20 quarantine=23
```

…plus `report.html` — a self-contained page with score bars, every failure's
waveform, an audio player, and what the ASR actually heard.

Each category is scored by an honest **policy**: `strict` (unambiguous spoken
form — equivalence-aware WER), `keywords` (URLs/currencies have many valid
readings — key tokens must survive the round trip), or `structural` (emoji and
punctuation storms have no meaningful transcript — the audio just has to
survive). No fake failures from formatting differences.

**CI regression gate:**

```bash
ttsproof regress baseline/report.json current/report.json --tolerance 1.0
# exit 1 + category-level diff when quality drops:
#   REGRESSION DETECTED:
#     OVERALL: 96.2% -> 94.7%  (-1.5 pp)
#     numbers: 99.1% -> 95.0%  (-4.1 pp)
```

**Compare engines:**

```bash
ttsproof compare xtts/report.json fish/report.json kokoro/report.json
```

## Quickstart

**Check one file (CLI):**

```bash
ttsproof check output.wav --text "Hello there"
```

**QA a folder of generated audio against a manifest:**

```bash
# cases.jsonl — one case per line:
# {"id": "case_001", "text": "Meet me at 3:30 PM", "wav": "case_001.wav"}
ttsproof run --manifest cases.jsonl --wav-dir ./audio --out ./reports --asr
```

You get `report.csv` + `report.json` with one verdict per sample:
`pass` / `hard_fail` / `quarantine`.

**Gate any TTS system in CI (Python):**

```python
import ttsproof

def synthesize(text: str) -> bytes:
    ...  # call your TTS engine, return WAV bytes

cases = ttsproof.load_cases_jsonl("edge_cases.jsonl")
rows = ttsproof.qa_synthesize(cases, synthesize, out_dir="qa_audio")
report = ttsproof.write_reports(rows, "qa_reports")
assert report["ok"], report["summary"]
```

**Or check existing audio with three lines:**

```python
import ttsproof

report = ttsproof.check_wav("output.wav")          # structural only
print(report.ok, report.errors)
```

## Why "quarantine" instead of pass/fail?

Short utterances are where reference-based TTS systems break — and also where
ASR is least reliable. In the published evaluation, a blinded human review of
the ASR-uncertain zone found it was a genuine ~45/55 mix of real TTS failures
and ASR false-negatives. Treating that zone as *"needs human ears"* is the
honest design: hard failures stay automatic, uncertain shorts get a human,
nothing gets silently mislabeled.

## What it doesn't do

- It does not judge naturalness, prosody, or speaker similarity — it catches
  *defects*, not aesthetics.
- ASR-based checks inherit ASR's limits; that is exactly why the quarantine
  verdict exists.
- English-first normalization (with Greek letter support); contributions for
  other languages welcome.

## Cite

```bibtex
@techreport{gkilis2026ttsqa,
  author = {Gkilis, Panagiotis},
  title  = {An Automated Failure-Mode QA Framework for Neural Text-to-Speech
            Systems: A Production Case Study on a Reference-Based TTS Service},
  year   = {2026},
  doi    = {10.5281/zenodo.20757553}
}
```

## License

MIT © Panagiotis Gkilis — [portfolio](https://tts.bedvibe.studio/portfolio/) · part of the *Proof* family with [BookProof](https://tts.bedvibe.studio/bookproof/)
