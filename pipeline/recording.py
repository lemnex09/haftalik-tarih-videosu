"""Narrator's own recording: episodes/<slug>/kayit.mp3 (whole script read in one go).
faster-whisper finds word times, the script is aligned to them, and the file is
cut into per-section clips so the rest of the pipeline works unchanged."""
from __future__ import annotations

import difflib
import json
import re

from .common import Episode, ffprobe_duration, log, run
from .voice import section_text


def _norm(w: str) -> str:
    w = w.replace("İ", "i").replace("I", "ı").lower()
    return re.sub(r"[^\wçğıöşü]", "", w)


def from_recording(ep: Episode, rec):
    from faster_whisper import WhisperModel

    log(f"kendi kaydın kullanılıyor: {rec.name} — konuşma çözümleniyor")
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = model.transcribe(str(rec), language="tr", word_timestamps=True, vad_filter=False)
    heard = [(w.start, w.end, _norm(w.word)) for s in segs for w in s.words]
    heard = [h for h in heard if h[2]]

    # script words, remembering where each scene starts
    script, scene_first = [], []
    for sec in ep.script["sections"]:
        firsts = []
        for sc in sec["scenes"]:
            firsts.append(len(script))
            script += [_norm(w) for w in sc["say"].split() if _norm(w)]
        scene_first.append(firsts)

    sm = difflib.SequenceMatcher(a=script, b=[h[2] for h in heard], autojunk=False)
    t_of = {}
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            t_of[a + k] = heard[b + k][0]
    matched = len(t_of) / max(len(script), 1)
    log(f"kayıt eşleşmesi: %{matched * 100:.0f}")
    if matched < 0.6:
        raise SystemExit("Kayıt senaryoyla yeterince eşleşmedi — metni senaryoya sadık okuduğundan emin ol")

    known = sorted(t_of)

    def time_at(i):  # interpolate for words whisper missed
        if i in t_of:
            return t_of[i]
        lo = max((k for k in known if k < i), default=None)
        hi = min((k for k in known if k > i), default=None)
        if lo is None:
            return t_of[hi]
        if hi is None:
            return t_of[lo]
        return t_of[lo] + (t_of[hi] - t_of[lo]) * (i - lo) / (hi - lo)

    total = ffprobe_duration(rec)
    sec_starts = [max(0.0, time_at(f[0]) - 0.15) for f in scene_first]
    sec_starts[0] = 0.0
    for si, firsts in enumerate(scene_first, 1):
        st = sec_starts[si - 1]
        en = sec_starts[si] if si < len(sec_starts) else total
        mp3 = ep.audio / f"sec_{si:02d}.mp3"
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{st:.3f}", "-to", f"{en:.3f}", "-i", str(rec),
             "-c:a", "libmp3lame", "-b:a", "192k", str(mp3)])
        starts = [max(0.0, time_at(i) - st) for i in firsts]
        starts[0] = 0.0
        dur = ffprobe_duration(mp3)
        (ep.audio / f"sec_{si:02d}.json").write_text(json.dumps(
            {"hash": "recording", "duration": dur, "speech_end": dur, "scene_starts": starts,
             "gap": 0.0}, ensure_ascii=False))
    log("kayıt bölümlere ayrıldı")
