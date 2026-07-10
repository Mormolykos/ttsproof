"""Command-line interface.

  ttsproof check out.wav                     structural checks on one file
  ttsproof run --manifest cases.jsonl        QA a batch of existing wav files
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import Config, DEFAULT
from .runner import load_cases_jsonl, qa_pairs, qa_sample, summarize, write_reports


def _add_asr_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--asr", action="store_true",
                        help='Enable ASR pronunciation checks (needs pip install "ttsproof[asr]").')
    parser.add_argument("--asr-model", default="small")
    parser.add_argument("--asr-device", default="auto")


def _build_asr(args: argparse.Namespace):
    if not getattr(args, "asr", False):
        return None
    from .asr import ASR
    return ASR(model_name=args.asr_model, device=args.asr_device)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ttsproof",
                                     description="Automated failure-mode QA for TTS output.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="Structural checks on a single wav file.")
    p_check.add_argument("wav", type=Path)
    p_check.add_argument("--text", default="", help="Expected text (used to pick duration bounds).")
    p_check.add_argument("--type", dest="text_type", default="",
                         help="Force a text type (letter, acronym, number, normal, ...).")

    p_run = sub.add_parser("run", help="QA a batch of (text, wav) pairs from a JSONL manifest.")
    p_run.add_argument("--manifest", type=Path, required=True,
                       help='JSONL: {"id": ..., "text": ..., "wav": ...} per line. '
                            '"wav" may be relative to --wav-dir or default to <wav-dir>/<id>.wav')
    p_run.add_argument("--wav-dir", type=Path, default=Path("."))
    p_run.add_argument("--out", type=Path, default=Path("ttsproof_reports"))
    _add_asr_args(p_run)

    args = parser.parse_args(argv)

    if args.command == "check":
        from .normalize import classify_input
        text_type = args.text_type or (classify_input(args.text) if args.text else "normal")
        report = qa_sample(args.text or "", args.wav, category=args.text_type)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["verdict"] != "hard_fail" else 1

    if args.command == "run":
        cases = load_cases_jsonl(args.manifest)
        pairs = []
        for case in cases:
            wav = Path(str(case.get("wav", "")).strip() or f"{case['id']}.wav")
            if not wav.is_absolute():
                wav = args.wav_dir / wav
            pairs.append({**case, "wav": wav})
        try:
            asr = _build_asr(args)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        rows = qa_pairs(pairs, asr=asr)
        report = write_reports(rows, args.out)
        summary = report["summary"]
        print(f"reports: {args.out.resolve()}")
        print(f"total={summary['total']} pass={summary['pass']} "
              f"hard_fail={summary['hard_fail']} quarantine={summary['quarantine']}")
        return 0 if report["ok"] else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
