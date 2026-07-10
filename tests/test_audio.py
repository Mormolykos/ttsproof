"""Structural checks against synthetic WAVs manufactured to fail one way each."""

import numpy as np
import pytest
import soundfile as sf

from ttsproof import check_wav

SR = 24000


def write_wav(path, samples):
    sf.write(str(path), samples.astype("float32"), SR)
    return path


def speechlike(seconds=2.0, amp=0.3, seed=7):
    """Amplitude-modulated noise: passes every structural check."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0, seconds, int(SR * seconds), endpoint=False)
    envelope = 0.55 + 0.45 * np.sin(2 * np.pi * 2.1 * t)
    return (rng.standard_normal(len(t)) * 0.25 + np.sin(2 * np.pi * 180 * t)) * envelope * amp * 0.5


def test_clean_audio_passes(tmp_path):
    wav = write_wav(tmp_path / "clean.wav", speechlike())
    report = check_wav(wav)
    assert report.ok, report.errors
    assert report.duration_sec == pytest.approx(2.0, abs=0.01)


def test_empty_file_fails(tmp_path):
    path = tmp_path / "empty.wav"
    path.write_bytes(b"")
    report = check_wav(path)
    assert report.empty_audio
    assert not report.ok


def test_too_short_fails(tmp_path):
    wav = write_wav(tmp_path / "short.wav", speechlike(seconds=0.05))
    report = check_wav(wav, text_type="normal")
    assert report.too_short


def test_short_type_allows_short_audio(tmp_path):
    wav = write_wav(tmp_path / "letter.wav", speechlike(seconds=0.3))
    report = check_wav(wav, text_type="letter")
    assert not report.too_short


def test_duration_explosion_fails(tmp_path):
    wav = write_wav(tmp_path / "letter_long.wav", speechlike(seconds=4.0))
    report = check_wav(wav, text_type="letter")
    assert report.duration_explosion


def test_long_silence_fails(tmp_path):
    audio = np.concatenate([speechlike(1.0), np.zeros(int(SR * 3.0)), speechlike(1.0)])
    wav = write_wav(tmp_path / "silence.wav", audio)
    report = check_wav(wav)
    assert report.long_silence
    assert report.max_silence_sec > 2.5


def test_clipping_fails(tmp_path):
    audio = speechlike()
    audio[SR // 2 : SR // 2 + 200] = 1.0
    wav = write_wav(tmp_path / "clipped.wav", audio)
    report = check_wav(wav)
    assert report.clipping


def test_loop_detected(tmp_path):
    chunk = speechlike(seconds=0.45, seed=3)
    audio = np.tile(chunk, 8)
    wav = write_wav(tmp_path / "loop.wav", audio)
    report = check_wav(wav)
    assert report.loop_suspicion
