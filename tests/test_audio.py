"""Structural checks against synthetic WAVs manufactured to fail one way each."""

import numpy as np
import pytest
import soundfile as sf

from ttsproof import check_wav
from ttsproof.config import Config

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


# --- a number that was never measured must not read as a measurement --------
#
# Every numeric field defaulted to 0.0, so a clip too short for the 30 ms tail
# window reported `tail_rms_last_30ms: 0.0` and `tail_peak_last_30ms: 0.0`, and
# a file that could not be read at all reported `duration_sec: 0.0`. Those are
# values a real clip can carry. They are None now, which reaches report.json as
# null and report.csv as a blank cell -- the same way WER is already reported
# when no ASR ran. Found 2026-09-02.


class TestUnmeasuredIsNotZero:
    def test_a_clip_shorter_than_the_tail_window_has_no_tail_numbers(self, tmp_path):
        # 20 ms against a 30 ms window: the tail block never runs.
        wav = write_wav(tmp_path / "tiny.wav", speechlike(seconds=0.02))
        report = check_wav(wav, text_type="letter")

        assert report.tail_rms_last_30ms is None
        assert report.tail_peak_last_30ms is None
        assert report.as_dict()["tail_rms_last_30ms"] is None
        # Under the DEFAULT config this case always trips too_short as well
        # (the duration floor is 80 ms, above the 30 ms window), so the row had
        # something else to give it away. That is not true under a custom
        # window -- see the next test -- and the number lied either way.
        assert report.too_short

    def test_a_custom_tail_window_leaves_no_other_signal(self, tmp_path):
        """The case with nothing else in the row to give it away."""
        cfg = Config(tail_window_sec=0.5)
        wav = write_wav(tmp_path / "ok.wav", speechlike(seconds=0.4))
        report = check_wav(wav, text_type="letter", config=cfg)

        assert report.ok, report.errors
        assert report.errors == []
        assert report.tail_rms_last_30ms is None, (
            "a clean clip reported a tail measurement that was never taken, "
            "with no error beside it to say so"
        )
        assert report.tail_peak_last_30ms is None

    def test_an_unreadable_file_has_no_duration(self, tmp_path):
        path = tmp_path / "empty.wav"
        path.write_bytes(b"")
        report = check_wav(path)

        assert report.empty_audio
        for field_name in ("duration_sec", "max_silence_sec", "peak", "rms"):
            assert getattr(report, field_name) is None, field_name
        row = report.as_dict()
        assert row["duration_sec"] is None
        assert row["max_silence_sec"] is None

    def test_a_measured_clip_still_reports_real_numbers(self, tmp_path):
        """The control: nothing above may turn a measurement into a None."""
        wav = write_wav(tmp_path / "clean.wav", speechlike())
        report = check_wav(wav)

        assert report.ok, report.errors
        assert report.duration_sec == pytest.approx(2.0, abs=0.01)
        assert report.tail_rms_last_30ms is not None
        assert report.tail_peak_last_30ms is not None
        assert report.as_dict()["duration_sec"] == pytest.approx(2.0, abs=0.01)

    def test_not_measured_reaches_the_csv_as_a_blank_not_a_zero(self, tmp_path):
        """The reporting pattern ttsproof already uses for WER without ASR."""
        import csv
        import io

        path = tmp_path / "empty.wav"
        path.write_bytes(b"")
        row = check_wav(path).as_dict()

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["duration_sec", "max_silence_sec"])
        writer.writeheader()
        writer.writerow({k: row[k] for k in ("duration_sec", "max_silence_sec")})
        assert buf.getvalue().splitlines()[1] == ","
