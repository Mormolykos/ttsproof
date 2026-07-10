"""Self-contained HTML report: category chart, verdict table, failure gallery
with audio players and inline waveforms. No external assets, no JS libraries —
one file you can email or attach to a PR."""

from __future__ import annotations

import html as H
from pathlib import Path
from typing import Any

_MAX_FAILURE_PLAYERS = 60
_WAVE_POINTS = 240


def _waveform_svg(wav_path: str) -> str:
    """Downsampled peak-envelope polyline; empty string if unreadable."""
    try:
        import numpy as np
        import soundfile as sf
        audio, _sr = sf.read(wav_path, dtype="float32", always_2d=True)
        mono = np.mean(audio, axis=1)
        if len(mono) < 2:
            return ""
        hop = max(1, len(mono) // _WAVE_POINTS)
        peaks = [float(np.max(np.abs(mono[i:i + hop]))) for i in range(0, len(mono), hop)][:_WAVE_POINTS]
        top = max(max(peaks), 1e-6)
        pts_up = " ".join(f"{i},{24 - (p / top) * 22:.1f}" for i, p in enumerate(peaks))
        pts_dn = " ".join(f"{i},{24 + (p / top) * 22:.1f}" for i, p in enumerate(reversed(peaks)))
        n = len(peaks)
        return (f'<svg viewBox="0 0 {n} 48" preserveAspectRatio="none" class="wave">'
                f'<polygon points="{pts_up} {pts_dn}" /></svg>')
    except Exception:
        return ""


def _bar(score: float | None) -> str:
    if score is None:
        return '<span class="na">n/a</span>'
    pct = score * 100
    cls = "good" if pct >= 95 else ("mid" if pct >= 80 else "bad")
    return (f'<div class="barwrap"><div class="bar {cls}" style="width:{pct:.1f}%"></div>'
            f'<span class="barlabel">{pct:.1f}%</span></div>')


def write_html(report: dict[str, Any], path: str | Path) -> None:
    s = report.get("summary", {})
    cats = report.get("categories", {})
    rows = report.get("samples", [])
    overall = s.get("overall_score")
    overall_txt = f"{overall*100:.1f}%" if overall is not None else "n/a"

    cat_rows = "\n".join(
        f"<tr><td>{H.escape(cat)}</td><td>{c['total']}</td>"
        f"<td>{c['pass']}</td><td>{c['hard_fail']}</td><td>{c['quarantine']}</td>"
        f"<td>{_bar(c.get('score'))}</td></tr>"
        for cat, c in cats.items())

    failures = [r for r in rows if r.get("verdict") == "hard_fail"]
    quarantined = [r for r in rows if r.get("verdict") == "quarantine"]

    def sample_card(row: dict[str, Any]) -> str:
        wav = str(row.get("audio_path", ""))
        wave = _waveform_svg(wav) if wav else ""
        audio = (f'<audio controls preload="none" src="{H.escape(Path(wav).as_uri())}"></audio>'
                 if wav and Path(wav).exists() else "")
        asr = H.escape(str(row.get("asr_text", "")))
        return (f'<div class="card"><div class="cid">{H.escape(str(row.get("id","")))} '
                f'<span class="cat">{H.escape(str(row.get("category","")))}</span></div>'
                f'<div class="txt">“{H.escape(str(row.get("original_text","")))}”</div>'
                + (f'<div class="asr">ASR heard: “{asr}”</div>' if asr else "")
                + f'<div class="err">{H.escape(str(row.get("error_reason","")))}</div>'
                + wave + audio + "</div>")

    fail_cards = "\n".join(sample_card(r) for r in failures[:_MAX_FAILURE_PLAYERS])
    quar_cards = "\n".join(sample_card(r) for r in quarantined[:_MAX_FAILURE_PLAYERS])

    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>TTSProof report — {H.escape(str(report.get('generated_at','')))}</title>
<style>
 body{{font-family:Segoe UI,Roboto,Arial,sans-serif;margin:0;background:#0d1117;color:#e6edf3;line-height:1.5}}
 .wrap{{max-width:960px;margin:0 auto;padding:28px 18px 60px}}
 h1{{font-size:26px;margin:0 0 4px}} h2{{font-size:19px;margin:32px 0 10px}}
 .sub{{color:#8b949e;font-size:13px;margin-bottom:22px}}
 .stats{{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}}
 .stat{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:12px 18px;min-width:110px}}
 .stat b{{display:block;font-size:22px}} .stat.pass b{{color:#3fb950}} .stat.fail b{{color:#f85149}}
 .stat.quar b{{color:#d29922}} .stat span{{font-size:12px;color:#8b949e}}
 table{{width:100%;border-collapse:collapse;font-size:13.5px}}
 th,td{{text-align:left;padding:7px 10px;border-bottom:1px solid #21262d}}
 th{{color:#8b949e;font-weight:600}}
 .barwrap{{position:relative;background:#21262d;border-radius:6px;height:16px;min-width:150px}}
 .bar{{height:100%;border-radius:6px}} .bar.good{{background:#238636}} .bar.mid{{background:#9e6a03}}
 .bar.bad{{background:#da3633}}
 .barlabel{{position:absolute;left:8px;top:0;font-size:11px;line-height:16px;color:#fff}}
 .na{{color:#8b949e;font-size:12px}}
 .card{{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:12px 14px;margin:10px 0}}
 .cid{{font-weight:700;font-size:13px}} .cat{{color:#8b949e;font-weight:400;margin-left:8px}}
 .txt{{margin:6px 0 2px}} .asr{{color:#79c0ff;font-size:13px}} .err{{color:#f85149;font-size:12.5px;margin:4px 0}}
 .wave{{display:block;width:100%;height:48px;margin:8px 0 4px}} .wave polygon{{fill:#388bfd66}}
 audio{{width:100%;height:32px}}
 footer{{margin-top:40px;color:#8b949e;font-size:12px}}
 footer a{{color:#58a6ff}}
</style></head><body><div class="wrap">
<h1>TTSProof report</h1>
<div class="sub">{H.escape(str(report.get('generated_at','')))} · verdicts: pass / hard_fail / quarantine
 (quarantine = clean audio, short utterance, ASR uncertain — needs human ears)</div>
<div class="stats">
 <div class="stat"><b>{s.get('total','?')}</b><span>samples</span></div>
 <div class="stat pass"><b>{s.get('pass','?')}</b><span>pass</span></div>
 <div class="stat fail"><b>{s.get('hard_fail','?')}</b><span>hard fail</span></div>
 <div class="stat quar"><b>{s.get('quarantine','?')}</b><span>quarantine</span></div>
 <div class="stat"><b>{overall_txt}</b><span>overall score</span></div>
</div>
<h2>Categories</h2>
<table><tr><th>category</th><th>total</th><th>pass</th><th>fail</th><th>quar.</th><th>score</th></tr>
{cat_rows}
</table>
<h2>Hard failures ({len(failures)})</h2>
{fail_cards or '<p class="na">None. 🎯</p>'}
<h2>Quarantined for human review ({len(quarantined)})</h2>
{quar_cards or '<p class="na">None.</p>'}
<footer>Generated by <a href="https://github.com/Mormolykos/ttsproof">TTSProof</a> —
 method: <a href="https://doi.org/10.5281/zenodo.20757553">DOI 10.5281/zenodo.20757553</a></footer>
</div></body></html>"""
    Path(path).write_text(doc, encoding="utf-8")
