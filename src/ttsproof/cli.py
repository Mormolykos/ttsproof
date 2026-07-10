"""Command-line interface.

  ttsproof check out.wav                       structural checks on one file
  ttsproof run --manifest cases.jsonl          QA existing wav files
  ttsproof benchmark --cmd "mytts {text} {out}"   stress-test any TTS engine
  ttsproof benchmark --wav-dir ./audio         score pre-generated audio
  ttsproof generate --out cases.jsonl          export the built-in corpus
  ttsproof compare a/report.json b/report.json    side-by-side scores
  ttsproof regress old/report.json new/report.json   CI regression gate
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

from . import __version__
from .cases import CORPUS_VERSION, builtin_cases, list_categories, write_jsonl
from .runner import (compare_reports, load_cases_jsonl, qa_pairs, qa_sample,
                     qa_synthesize, regression, write_reports)


def _add_asr_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--no-asr", action="store_true",
                        help="Structural checks only (skip transcription).")
    parser.add_argument("--asr-model", default="small")
    parser.add_argument("--asr-device", default="auto")


def _build_asr(args: argparse.Namespace):
    if getattr(args, "no_asr", False):
        return None
    try:
        from .asr import ASR
        return ASR(model_name=args.asr_model, device=args.asr_device)
    except RuntimeError as exc:
        print(f"note: {exc}\ncontinuing with structural checks only (--no-asr).",
              file=sys.stderr)
        return None


def _select_cases(args: argparse.Namespace) -> list[dict]:
    categories = [c.strip() for c in (args.categories or "").split(",") if c.strip()] or None
    cases = builtin_cases(categories=categories,
                          limit_per_category=args.limit_per_category)
    if args.limit:
        cases = cases[: args.limit]
    return cases


def _print_scoreboard(report: dict) -> None:
    s = report["summary"]
    meta = report.get("meta", {})
    corpus = f" · Corpus {meta['corpus_version']}" if meta.get("corpus_version") else ""
    print("\n" + "=" * 58)
    print(f"  TTSProof {__version__}{corpus} — {s['total']} samples")
    print("=" * 58)
    for cat, c in report["categories"].items():
        score = f"{c['score']*100:5.1f}%" if c.get("score") is not None else "  n/a "
        quar = f"  (+{c['quarantine']} quarantined)" if c["quarantine"] else ""
        print(f"  {cat:<22s} {score}   {c['pass']}/{c['pass']+c['hard_fail']} decided{quar}")
    print("-" * 58)
    overall = s.get("overall_score")
    print(f"  OVERALL {'%.1f%%' % (overall*100) if overall is not None else 'n/a'}"
          f"   pass={s['pass']} fail={s['hard_fail']} quarantine={s['quarantine']}")
    print("=" * 58)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ttsproof",
                                     description="Automated failure-mode QA for TTS output.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="Structural checks on a single wav file.")
    p_check.add_argument("wav", type=Path)
    p_check.add_argument("--text", default="", help="Expected text (picks duration bounds).")
    p_check.add_argument("--type", dest="text_type", default="",
                         help="Force a text type (letter, acronym, number, ...).")

    p_run = sub.add_parser("run", help="QA a batch of (text, wav) pairs from a JSONL manifest.")
    p_run.add_argument("--manifest", type=Path, required=True)
    p_run.add_argument("--wav-dir", type=Path, default=Path("."))
    p_run.add_argument("--out", type=Path, default=Path("ttsproof_reports"))
    _add_asr_args(p_run)

    p_bench = sub.add_parser("benchmark",
                             help="Stress-test a TTS engine with the built-in corpus.")
    src = p_bench.add_mutually_exclusive_group(required=True)
    src.add_argument("--cmd", default="",
                     help='Synthesis command template, e.g. "mytts --text {text} --out {out}". '
                          "Run once per case; must write a wav to {out}.")
    src.add_argument("--wav-dir", type=Path, default=None,
                     help="Directory of pre-generated audio named <case_id>.wav.")
    p_bench.add_argument("--categories", default="",
                         help=f"Comma-separated subset of: {', '.join(list_categories())}")
    p_bench.add_argument("--limit", type=int, default=0, help="First N cases only.")
    p_bench.add_argument("--limit-per-category", type=int, default=0)
    p_bench.add_argument("--out", type=Path, default=Path("ttsproof_benchmark"))
    _add_asr_args(p_bench)

    p_gen = sub.add_parser("generate", help="Export the built-in corpus as JSONL.")
    p_gen.add_argument("--out", type=Path, default=Path("ttsproof_cases.jsonl"))
    p_gen.add_argument("--categories", default="")
    p_gen.add_argument("--limit", type=int, default=0)
    p_gen.add_argument("--limit-per-category", type=int, default=0)

    p_cmp = sub.add_parser("compare", help="Side-by-side category scores of 2+ reports.")
    p_cmp.add_argument("reports", nargs="+", type=Path)

    p_reg = sub.add_parser("regress", help="Fail (exit 1) if new report regressed vs old.")
    p_reg.add_argument("old", type=Path)
    p_reg.add_argument("new", type=Path)
    p_reg.add_argument("--tolerance", type=float, default=1.0,
                       help="Allowed score drop in percentage points (default 1.0).")

    args = parser.parse_args(argv)

    if args.command == "check":
        report = qa_sample(args.text or "", args.wav, category_hint=args.text_type)
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
        rows = qa_pairs(pairs, asr=_build_asr(args))
        report = write_reports(rows, args.out)
        _print_scoreboard(report)
        print(f"reports: {args.out.resolve()}  (report.html for the pretty one)")
        return 0 if report["ok"] else 1

    if args.command == "benchmark":
        cases = _select_cases(args)
        asr = _build_asr(args)
        if args.wav_dir:
            pairs = [{**c, "wav": args.wav_dir / f"{c['id']}.wav"} for c in cases]
            rows = qa_pairs(pairs, asr=asr)
        else:
            template = args.cmd

            def synthesize(text: str) -> bytes:
                with tempfile.TemporaryDirectory() as tmp:
                    out_wav = Path(tmp) / "out.wav"
                    cmd = [part.replace("{text}", text).replace("{out}", str(out_wav))
                           for part in shlex.split(template)]
                    subprocess.run(cmd, check=True, capture_output=True)
                    return out_wav.read_bytes()

            done = {"n": 0}

            def progress(row: dict) -> None:
                done["n"] += 1
                print(f"[{done['n']}/{len(cases)}] {row['id']} -> {row['verdict']}")

            rows = qa_synthesize(cases, synthesize, args.out / "audio",
                                 asr=asr, progress=progress)
        report = write_reports(rows, args.out, meta={
            "ttsproof_version": __version__, "corpus_version": CORPUS_VERSION})
        _print_scoreboard(report)
        print(f"reports: {args.out.resolve()}  (report.html for the pretty one)")
        return 0 if report["ok"] else 1

    if args.command == "generate":
        categories = [c.strip() for c in (args.categories or "").split(",") if c.strip()] or None
        cases = builtin_cases(categories=categories,
                              limit_per_category=args.limit_per_category)
        if args.limit:
            cases = cases[: args.limit]
        write_jsonl(cases, args.out)
        print(f"{len(cases)} cases -> {args.out}")
        return 0

    if args.command == "compare":
        reports = {p.parent.name or p.stem: json.loads(p.read_text(encoding="utf-8"))
                   for p in args.reports}
        table = compare_reports(reports)
        names = list(reports)
        print(f"{'category':<22s} " + " ".join(f"{n[:12]:>12s}" for n in names))
        for entry in table:
            cells = " ".join(
                f"{(entry[n]*100):11.1f}%" if entry.get(n) is not None else f"{'n/a':>12s}"
                for n in names)
            print(f"{entry['category']:<22s} {cells}")
        return 0

    if args.command == "regress":
        old = json.loads(args.old.read_text(encoding="utf-8"))
        new = json.loads(args.new.read_text(encoding="utf-8"))
        findings = regression(old, new, tolerance_pp=args.tolerance)
        if findings:
            print("REGRESSION DETECTED:")
            for f in findings:
                print("  " + f)
            return 1
        print("no regression beyond tolerance.")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
