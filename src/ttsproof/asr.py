"""Optional ASR backend for pronunciation checks.

Structural audio checks need no ASR. Install the extra to enable
transcription-based WER/CER gating:  pip install "ttsproof[asr]"
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class ASR:
    def __init__(
        self,
        model_name: str = "small",
        device: str = "auto",
        compute_type: str = "auto",
    ):
        self.model: Any = None
        self.device = device
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "ASR support requires faster-whisper. "
                'Install with: pip install "ttsproof[asr]"'
            ) from exc

        resolved_device = "auto" if device == "auto" else device
        resolved_compute = "default" if compute_type == "auto" else compute_type
        try:
            self.model = WhisperModel(model_name, device=resolved_device, compute_type=resolved_compute)
        except Exception:
            # CUDA/compute-type mismatch: fall back to CPU int8 rather than dying.
            self.device = "cpu"
            self.model = WhisperModel(model_name, device="cpu", compute_type="int8")

    def transcribe(self, audio_path: str | Path, language: str = "en") -> str:
        segments, _info = self.model.transcribe(
            str(audio_path),
            language=(language or None),
            beam_size=5,
            vad_filter=True,
        )
        return " ".join(str(seg.text or "").strip() for seg in segments).strip()
