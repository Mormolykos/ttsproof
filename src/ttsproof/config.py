"""Tunable thresholds for TTSProof checks.

Defaults match the values evaluated in the technical report
"An Automated Failure-Mode QA Framework for Neural Text-to-Speech Systems"
(DOI: 10.5281/zenodo.20757553).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # amplitude at or below which a sample counts as silence
    silence_amplitude: float = 0.003
    # a continuous silent run longer than this fails the clip
    long_silence_sec: float = 2.0
    # absolute peak at or above this counts as clipping
    clipping_peak: float = 0.995
    # duration bounds; "short" types are single letters / vocalizations
    min_short_sec: float = 0.08
    min_general_sec: float = 0.18
    max_short_sec: float = 3.0
    max_general_sec: float = 30.0
    # end-of-clip artifact detection window
    tail_window_sec: float = 0.03
    tail_context_sec: float = 0.12
    # pronunciation gate
    wer_threshold: float = 0.03


DEFAULT = Config()
