"""QA runner: verdicts, quarantine, and reports.

The central design decision (validated by blinded human review in the
technical report, DOI 10.5281/zenodo.20757553): when the audio is structurally
clean but ASR disagrees with the expected text on a very short utterance —
a single letter, an acronym, a vocalization — the sample is *quarantined for
human review* instead of being counted as a failure, because at that length
ASR itself is unreliable. Hard structural defects always fail.

Verdicts per sample:
  pass          — clean audio; transcript matches (if ASR used)
  hard_fail     — structural defect, or a real pronunciation mismatch
  quarantine    — clean audio, short utterance, ASR disagrees: human review
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any, Callable, Iterable

from .audio import check_wav
from .config import Config, DEFAULT
from .metrics import cer, equivalence_compare, wer
from .normalize import classify_input, is_vocalization, normalize_text

QUARANTINE_TYPES = {"letter", "vocalization", "greek_letter", "acronym"}

REPORT_FIELDS = [
    "id", "text_type", "verdict", "original_text", "normalized_text",
    "asr_text", "wer", "cer", "exact_match", "equivalence_pass",
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
    language: str = "en",
    asr: Any = None,
    config: Config = DEFAULT,
) -> dict[str, Any]:
    """QA one (text, wav) pair. Pass an ``ttsproof.asr.ASR`` instance to add
    pronunciation checks; without it only structural checks run."""
    text_type = classify_input(text, category)
    normalized = normalize_text(text, category)
    row: dict[str, Any] = {
        "id": sample_id or Path(audio_path).stem,
        "text_type": text_type,
        "verdict": "",
        "original_text": text,
        "normalized_text": normalized,
        "asr_text": "",
        "wer": "",
        "cer": "",
        "exact_match": "",
        "equivalence_pass": "",
        "error_reason": "",
    }

    audio_report = check_wav(audio_path, text_type, config)
    row.update(audio_report.as_dict())
    errors = list(audio_report.errors)
    quarantined = False

    if asr is not None and audio_report.ok:
        transcript = asr.transcribe(audio_path, language)
        row["asr_text"] = transcript
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


def qa_pairs(
    pairs: Iterable[tuple[str, str | Path] | dict[str, Any]],
    *,
    asr: Any = None,
    config: Config = DEFAULT,
) -> list[dict[str, Any]]:
    """QA existing audio. Each pair is ``(text, wav_path)`` or a dict with
    keys ``text``, ``wav`` and optional ``id``, ``category``, ``language``."""
    rows = []
    for pair in pairs:
        if isinstance(pair, dict):
            rows.append(qa_sample(
                str(pair["text"]), pair["wav"],
                sample_id=str(pair.get("id", "")),
                category=str(pair.get("category", "")),
                language=str(pair.get("language", "en")),
                asr=asr, config=config,
            ))
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
) -> list[dict[str, Any]]:
    """Drive any TTS system through QA. ``synthesize(text) -> wav bytes`` is
    the only integration point; cases are dicts with ``id``/``text`` and
    optional ``category``/``language``."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for case in cases:
        case_id = str(case["id"])
        text = str(case["text"])
        normalized = normalize_text(text, str(case.get("category", "")))
        wav_path = out / f"{case_id}.wav"
        wav_path.write_bytes(synthesize(normalized))
        rows.append(qa_sample(
            text, wav_path,
            sample_id=case_id,
            category=str(case.get("category", "")),
            language=str(case.get("language", "en")),
            asr=asr, config=config,
        ))
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
    return {
        "total": total,
        "pass": verdicts.get("pass", 0),
        "hard_fail": verdicts.get("hard_fail", 0),
        "quarantine": verdicts.get("quarantine", 0),
        "structural_defects": structural,
        "ok": verdicts.get("hard_fail", 0) == 0,
    }


def write_reports(rows: list[dict[str, Any]], report_dir: str | Path) -> dict[str, Any]:
    out = Path(report_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "report.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in REPORT_FIELDS})
    summary = summarize(rows)
    report = {"ok": summary["ok"], "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "summary": summary, "samples": rows}
    (out / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
