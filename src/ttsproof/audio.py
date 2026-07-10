"""ASR-independent structural audio checks.

These catch the failure modes that no transcript can see: empty or truncated
audio, duration explosions, long internal silences, clipping, repeated-chunk
loops, and end-of-clip artifacts. They require only numpy + soundfile and no
model of any kind.

Ported from the QA harness evaluated in DOI 10.5281/zenodo.20757553
(390 samples across 3 voices: zero structural defects escaped these checks).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Config, DEFAULT
from .normalize import SHORT_TYPES


@dataclass
class AudioReport:
    audio_path: str
    duration_sec: float = 0.0
    max_silence_sec: float = 0.0
    peak: float = 0.0
    rms: float = 0.0
    empty_audio: bool = False
    too_short: bool = False
    too_long: bool = False
    duration_explosion: bool = False
    long_silence: bool = False
    clipping: bool = False
    loop_suspicion: bool = False
    tail_artifact_suspected: bool = False
    tail_rms_last_30ms: float = 0.0
    tail_peak_last_30ms: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "audio_ok": self.ok,
            "empty_audio": self.empty_audio,
            "too_short": self.too_short,
            "too_long": self.too_long,
            "duration_explosion": self.duration_explosion,
            "long_silence": self.long_silence,
            "clipping": self.clipping,
            "loop_suspicion": self.loop_suspicion,
            "tail_artifact_suspected": self.tail_artifact_suspected,
            "tail_rms_last_30ms": round(self.tail_rms_last_30ms, 6),
            "tail_peak_last_30ms": round(self.tail_peak_last_30ms, 6),
            "duration_sec": round(self.duration_sec, 4),
            "max_silence_sec": round(self.max_silence_sec, 4),
            "audio_errors": "; ".join(self.errors),
        }


def _max_silence_sec(mono, sr: int, np, silence_amplitude: float) -> float:
    silent = np.abs(mono) <= silence_amplitude
    max_run = 0
    current = 0
    for is_silent in silent:
        if bool(is_silent):
            current += 1
            max_run = max(max_run, current)
        else:
            current = 0
    return float(max_run / float(sr))


def _loop_suspected(mono, sr: int, np) -> bool:
    """Detect near-identical consecutive 450 ms chunks (repeated-output loops)."""
    if len(mono) < int(sr * 2.0):
        return False
    window = max(1, int(sr * 0.45))
    chunks = []
    for start in range(0, len(mono) - window + 1, window):
        chunk = mono[start : start + window]
        if float(np.sqrt(np.mean(chunk * chunk) + 1e-12)) > 0.01:
            chunks.append(chunk)
    if len(chunks) < 3:
        return False
    similar = 0
    for left, right in zip(chunks, chunks[1:]):
        left = left - float(np.mean(left))
        right = right - float(np.mean(right))
        denom = float(np.linalg.norm(left) * np.linalg.norm(right) + 1e-12)
        if float(np.dot(left, right) / denom) > 0.985:
            similar += 1
    return similar >= 2


def check_wav(
    audio_path: str | Path,
    text_type: str = "normal",
    config: Config = DEFAULT,
) -> AudioReport:
    """Run all structural checks on one WAV file.

    ``text_type`` (see :func:`ttsproof.normalize.classify_input`) selects the
    duration bounds: single letters and vocalizations are allowed to be much
    shorter than sentences.
    """
    path = Path(audio_path)
    report = AudioReport(audio_path=str(path.resolve()))
    if not path.exists() or path.stat().st_size <= 44:
        report.empty_audio = True
        report.errors.append("empty_audio")
        return report

    import numpy as np
    import soundfile as sf

    try:
        audio, sr = sf.read(str(path), dtype="float32", always_2d=True)
    except Exception as exc:
        report.empty_audio = True
        report.errors.append(f"wav_read_failed: {exc}")
        return report

    if audio.size == 0 or int(sr) <= 0:
        report.empty_audio = True
        report.errors.append("empty_audio")
        return report

    mono = np.mean(audio, axis=1).astype("float32")
    report.duration_sec = float(len(mono) / float(sr))
    report.peak = float(np.max(np.abs(mono))) if len(mono) else 0.0
    report.rms = float(np.sqrt(np.mean(mono * mono) + 1e-12)) if len(mono) else 0.0
    report.max_silence_sec = _max_silence_sec(mono, int(sr), np, config.silence_amplitude)

    short_type = text_type in SHORT_TYPES
    min_duration = config.min_short_sec if short_type else config.min_general_sec
    max_duration = config.max_short_sec if short_type else config.max_general_sec

    if report.duration_sec < min_duration:
        report.too_short = True
        report.errors.append(f"too_short:{report.duration_sec:.3f}s")
    if report.duration_sec > max_duration:
        report.too_long = True
        report.duration_explosion = True
        report.errors.append(f"duration_explosion:{report.duration_sec:.3f}s")
    if report.max_silence_sec > config.long_silence_sec:
        report.long_silence = True
        report.errors.append(f"long_silence:{report.max_silence_sec:.3f}s")
    if report.peak >= config.clipping_peak:
        report.clipping = True
        report.errors.append(f"clipping:{report.peak:.4f}")
    if _loop_suspected(mono, int(sr), np):
        report.loop_suspicion = True
        report.errors.append("loop_suspicion")

    tail_len = max(1, int(int(sr) * config.tail_window_sec))
    context_len = max(tail_len + 1, int(int(sr) * config.tail_context_sec))
    if len(mono) > tail_len:
        tail = mono[-tail_len:]
        context_start = max(0, len(mono) - context_len - tail_len)
        context = mono[context_start:-tail_len]
        report.tail_rms_last_30ms = float(np.sqrt(np.mean(tail * tail) + 1e-12))
        report.tail_peak_last_30ms = float(np.max(np.abs(tail)))
        if short_type and len(context) > 0:
            context_rms = float(np.sqrt(np.mean(context * context) + 1e-12))
            context_peak = float(np.max(np.abs(context)) + 1e-12)
            energy_rise = report.tail_rms_last_30ms > max(0.025, context_rms * 1.8)
            peak_rise = report.tail_peak_last_30ms > max(0.12, context_peak * 1.5)
            if energy_rise and peak_rise:
                report.tail_artifact_suspected = True
                report.errors.append("dirty_tail")

    return report
