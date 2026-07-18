"""TTSProof — automated failure-mode QA and benchmarking for text-to-speech.

Structural audio checks (no model required), equivalence-aware WER/CER,
ASR-uncertainty quarantine, a ~700-case built-in benchmark corpus, HTML
reports, and CI regression gating.

Method evaluated in: "An Automated Failure-Mode QA Framework for Neural
Text-to-Speech Systems" — DOI 10.5281/zenodo.20757553.
"""

from .audio import AudioReport, check_wav
from .cases import CORPUS_VERSION, builtin_cases, list_categories, write_jsonl
from .config import Config, DEFAULT
from .metrics import (cer, compare_text, equivalence_compare, keyword_coverage,
                      levenshtein, wer)
from .normalize import classify_input, is_vocalization, normalize_text, retry_text
from .runner import (
    category_scores,
    compare_reports,
    load_cases_jsonl,
    qa_pairs,
    qa_sample,
    qa_synthesize,
    regression,
    summarize,
    write_reports,
)

__version__ = "0.3.1"

__all__ = [
    "AudioReport", "check_wav", "Config", "DEFAULT",
    "CORPUS_VERSION", "builtin_cases", "list_categories", "write_jsonl",
    "cer", "compare_text", "equivalence_compare", "keyword_coverage",
    "levenshtein", "wer",
    "classify_input", "is_vocalization", "normalize_text", "retry_text",
    "category_scores", "compare_reports", "load_cases_jsonl",
    "qa_pairs", "qa_sample", "qa_synthesize", "regression",
    "summarize", "write_reports",
    "__version__",
]
