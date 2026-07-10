"""QA runner: verdicts, quarantine, scoring policies, and reports.

The central design decision (validated by blinded human review in the
technical report, DOI 10.5281/zenodo.20757553): when the audio is structurally
clean but ASR disagrees with the expected text on a very short utterance —
a single letter, an acronym, a vocalization — the sample is *quarantined for
human review* instead of being counted as a failure, because at that length
ASR itself is unreliable. Hard structural defects always fail.

Scoring policies (per case, see ttsproof.cases):
  strict      — equivalence-aware WER gate on the canonical spoken form
  keywords    — salient tokens must survive the TTS -> ASR round trip
  structural  — audio checks only (no meaningful transcript exists)

Verdicts per sample: pass · hard_fail · quarantine
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any, Callable, Iterable

from .audio import check_wav
from .config import Config, DEFAULT
from .metrics import cer, equivalence_compare, keyword_coverage, wer
from .normalize import classify_input, normalize_text

QUARANTINE_TYPES = {"letter", "vocalization", "greek_letter", "acronym"}
KEYWORD_PASS_THRESHOLD = 0.6

REPORT_FIELDS = [
    "id", "category", "policy", "text_type", "verdict", "original_text",
    "normalized_text", "asr_text", "wer", "cer", "exact_match",
    "equivalence_pass", "keyword_coverage",
    "audio_ok", "empty_audio", "too_short", "too_long", "duration_explosion",
    "long_silence", "clipping", "loop_suspicion", "tail_artifact_suspected",
    "duration_sec", "max_silence_sec", "audio_path", "error_reason",
]


def qa_sample(
    text: str,
    audio_path: str | Path,
    *,
    sample_id: str = "",
    category: str = "",
    category_hint: str = "",
    language: str = "en",
    policy: str = "strict",
    asr: Any = None,
    config: Config = DEFAULT,
) -> dict[str, Any]:
    """QA one (text, wav) pair under a scoring policy."""
    text_type = classify_input(text, category_hint)
    normalized = normalize_text(text, category_hint)
    row: dict[str, Any] = {
        "id": sample_id or Path(audio_path).stem,
        "category": category,
        "policy": policy,
        "text_type": text_type,
        "verdict": "",
        "original_text": text,
        "normalized_text": normalized,
        "asr_text": "",
        "wer": "",
        "cer": "",
        "exact_match": "",
        "equivalence_pass": "",
        "keyword_coverage": "",
        "error_reason": "",
    }

    audio_report = check_wav(audio_path, text_type, config)
    row.update(audio_report.as_dict())
    errors = list(audio_report.errors)
    quarantined = False

    if asr is not None and audio_report.ok and policy != "structural":
        transcript = asr.transcribe(audio_path, language)
        row["asr_text"] = transcript

        if policy == "keywords":
            coverage = keyword_coverage(text, transcript)
            row["keyword_coverage"] = round(coverage, 4)
            if coverage < KEYWORD_PASS_THRESHOLD:
                errors.append(f"keyword_coverage {coverage:.2f} < {KEYWORD_PASS_THRESHOLD}")
        else:  # strict
            eq = equivalence_compare(normalized, transcript)
            sample_wer = wer(str(eq["expected_cmp"]), str(eq["actual_cmp"]))
            sample_cer = cer(str(eq["expected_cmp"]), str(eq["actual_cmp"]))
            row["wer"] = round(sample_wer, 6)
            row["cer"] = round(sample_cer, 6)
            row["exact_match"] = bool(eq["equivalent"])
            row["equivalence_pass"] = bool(eq["equivalence_pass"])
            if sample_wer > config.wer_threshold:
                if text_type in QUARANTINE_TYPES:
                    quarantined = True
                    errors.append("asr_uncertain_short_utterance")
                else:
                    errors.append(f"wer {sample_wer:.6f} > {config.wer_threshold:.6f}")

    if quarantined:
        row["verdict"] = "quarantine"
    elif errors:
        row["verdict"] = "hard_fail"
    else:
        row["verdict"] = "pass"
    row["error_reason"] = "; ".join(errors)
    return row


def _case_kwargs(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "sample_id": str(case.get("id", "")),
        "category": str(case.get("category", "")),
        "category_hint": str(case.get("category_hint", "")),
        "language": str(case.get("language", "en")),
        "policy": str(case.get("policy", "strict")),
    }


def qa_pairs(
    pairs: Iterable[tuple[str, str | Path] | dict[str, Any]],
    *,
    asr: Any = None,
    config: Config = DEFAULT,
) -> list[dict[str, Any]]:
    """QA existing audio. Each pair is ``(text, wav_path)`` or a dict with
    keys ``text``, ``wav`` and optional id/category/policy/language."""
    rows = []
    for pair in pairs:
        if isinstance(pair, dict):
            rows.append(qa_sample(str(pair["text"]), pair["wav"],
                                  asr=asr, config=config, **_case_kwargs(pair)))
        else:
            text, wav = pair
            rows.append(qa_sample(text, wav, asr=asr, config=config))
    return rows


def qa_synthesize(
    cases: Iterable[dict[str, Any]],
    synthesize: Callable[[str], bytes],
    out_dir: str | Path,
    *,
    asr: Any = None,
    config: Config = DEFAULT,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    """Drive any TTS system through QA. ``synthesize(text) -> wav bytes`` is
    the only integration point."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in cases:
        case_id = str(case["id"])
        text = str(case["text"])
        normalized = normalize_text(text, str(case.get("category_hint", "")))
        wav_path = out / f"{case_id}.wav"
        wav_path.write_bytes(synthesize(normalized))
        row = qa_sample(text, wav_path, asr=asr, config=config, **_case_kwargs(case))
        rows.append(row)
        if progress:
            progress(row)
    return rows


def load_cases_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Load QA cases from JSONL: one {"id", "text", ...} object per line."""
    cases = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            row = json.loads(line)
            if not str(row.get("id", "")).strip() or not str(row.get("text", "")).strip():
                raise ValueError(f"{path}:{line_no}: each case needs non-empty id and text")
            cases.append(row)
    if not cases:
        raise ValueError(f"No QA cases found in {path}")
    return cases


def category_scores(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per-category tallies. ``score`` = pass / (pass + hard_fail) — quarantined
    samples are excluded from the denominator because they await human review."""
    cats: dict[str, dict[str, Any]] = {}
    for row in rows:
        cat = str(row.get("category") or "uncategorized")
        c = cats.setdefault(cat, {"total": 0, "pass": 0, "hard_fail": 0, "quarantine": 0})
        c["total"] += 1
        c[str(row.get("verdict", "hard_fail"))] = c.get(str(row.get("verdict")), 0) + 1
    for c in cats.values():
        decided = c["pass"] + c["hard_fail"]
        c["score"] = round(c["pass"] / decided, 4) if decided else None
    return dict(sorted(cats.items()))


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    verdicts = {"pass": 0, "hard_fail": 0, "quarantine": 0}
    for row in rows:
        verdicts[str(row.get("verdict", "hard_fail"))] = verdicts.get(str(row.get("verdict")), 0) + 1
    structural = sum(
        1 for row in rows
        if any(row.get(k) for k in (
            "empty_audio", "too_short", "duration_explosion", "long_silence",
            "clipping", "loop_suspicion", "tail_artifact_suspected"))
    )
    decided = verdicts["pass"] + verdicts["hard_fail"]
    return {
        "total": total,
        "pass": verdicts["pass"],
        "hard_fail": verdicts["hard_fail"],
        "quarantine": verdicts["quarantine"],
        "structural_defects": structural,
        "overall_score": round(verdicts["pass"] / decided, 4) if decided else None,
        "ok": verdicts["hard_fail"] == 0,
    }


def write_reports(rows: list[dict[str, Any]], report_dir: str | Path,
                  html: bool = True, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    out = Path(report_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "report.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in REPORT_FIELDS})
    report = {
        "ok": summarize(rows)["ok"],
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        **({"meta": meta} if meta else {}),
        "summary": summarize(rows),
        "categories": category_scores(rows),
        "samples": rows,
    }
    (out / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if html:
        from .report_html import write_html
        write_html(report, out / "report.html")
    return report


def compare_reports(reports: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Side-by-side category scores for named reports (name -> report dict)."""
    all_cats: list[str] = []
    for rep in reports.values():
        for cat in rep.get("categories", {}):
            if cat not in all_cats:
                all_cats.append(cat)
    table = []
    for cat in sorted(all_cats):
        entry: dict[str, Any] = {"category": cat}
        for name, rep in reports.items():
            entry[name] = rep.get("categories", {}).get(cat, {}).get("score")
        table.append(entry)
    return table


def regression(old: dict[str, Any], new: dict[str, Any],
               tolerance_pp: float = 1.0) -> list[str]:
    """Category-level regressions between two reports (score drops beyond
    ``tolerance_pp`` percentage points). Returns human-readable findings."""
    findings = []
    old_cats = old.get("categories", {})
    new_cats = new.get("categories", {})
    for cat, new_c in new_cats.items():
        old_score = (old_cats.get(cat) or {}).get("score")
        new_score = new_c.get("score")
        if old_score is None or new_score is None:
            continue
        drop = (old_score - new_score) * 100
        if drop > tolerance_pp:
            findings.append(f"{cat}: {old_score*100:.1f}% -> {new_score*100:.1f}%  (-{drop:.1f} pp)")
    old_overall = old.get("summary", {}).get("overall_score")
    new_overall = new.get("summary", {}).get("overall_score")
    if old_overall is not None and new_overall is not None:
        drop = (old_overall - new_overall) * 100
        if drop > tolerance_pp:
            findings.insert(0, f"OVERALL: {old_overall*100:.1f}% -> {new_overall*100:.1f}%  (-{drop:.1f} pp)")
    return findings
