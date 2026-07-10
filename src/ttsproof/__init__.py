"""TTSProof — automated failure-mode QA for text-to-speech systems.

Structural audio checks (no model required), equivalence-aware WER/CER
pronunciation gating, and ASR-uncertainty quarantine.

Method evaluated in: "An Automated Failure-Mode QA Framework for Neural
Text-to-Speech Systems" — DOI 10.5281/zenodo.20757553.
"""

from .audio import AudioReport, check_wav
from .config import Config, DEFAULT
from .metrics import cer, compare_text, equivalence_compare, levenshtein, wer
from .normalize import classify_input, is_vocalization, normalize_text, retry_text
from .runner import (
    load_cases_jsonl,
    qa_pairs,
    qa_sample,
    qa_synthesize,
    summarize,
    write_reports,
)

__version__ = "0.1.0"

__all__ = [
    "AudioReport", "check_wav", "Config", "DEFAULT",
    "cer", "compare_text", "equivalence_compare", "levenshtein", "wer",
    "classify_input", "is_vocalization", "normalize_text", "retry_text",
    "load_cases_jsonl", "qa_pairs", "qa_sample", "qa_synthesize",
    "summarize", "write_reports",
    "__version__",
]
