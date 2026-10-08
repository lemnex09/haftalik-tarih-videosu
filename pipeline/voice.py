"""Narration: one TTS call per section (natural prosody), scene timings from
character-level timestamps."""
from __future__ import annotations

import base64
import hashlib
import json
import time

import requests

from .common import Episode, env, ffprobe_duration, load_config, log, run


def section_text(sec) -> tuple[str, list[int]]:
    """Join scene narration; return text and each scene's char offset."""
    text, offs = "", []
    for sc in sec["scenes"]:
        say = sc.get("say", "").strip()
        if text and say:
            text += " "
        offs.append(len(text))
        text += say
    return text, offs


def _eleven(text: str, prev: str, nxt: str, cfg: dict) -> tuple[bytes, dict]:
    key = env("ELEVENLABS_API_KEY")
    voice_id = env("ELEVENLABS_VOICE_ID")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps?output_format=mp3_44100_128"
    body = {
        "text": text,
        "model_id": cfg["model"],
        "previous_text": prev[-400:] or None,
        "next_text": nxt[:400] or None,
        "voice_settings": {"stability": cfg["stability"], "similarity_boost": cfg["similarity_boost"],
                           "style": cfg["style"], "speed": cfg.get("speed", 1.0), "use_speaker_boost": True},
    }
    body = {k: v for k, v in body.items() if v is not None}
    if cfg.get("language_code") and "multilingual_v2" not in cfg["model"]:
        body["language_code"] = cfg["language_code"]
    for attempt in range(6):
        try:
            r = requests.post(url, json=body, headers={"xi-api-key": key}, timeout=300)
            if r.status_code == 200:
                j = r.json()
                return base64.b64decode(j["audio_base64"]), j["alignment"]
            log(f"ElevenLabs {r.status_code}: {r.text[:300]}")
            if r.status_code in (401, 403, 422):
                raise SystemExit("ElevenLabs anahtarı/ses kimliği/plan hatası — yukarıdaki mesaja bak")
        except requests.RequestException as e:
            log("ElevenLabs istek hatası:", e)
        time.sleep(min(60, 4 * 2 ** attempt))
    raise RuntimeError("ElevenLabs başarısız")


def _words(text: str) -> list[str]:
    return [w for w in text.split() if any(ch.isalnum() for ch in w)]


def _edge(text: str, path, cfg: dict) -> dict:
    """Microsoft Edge neural TTS (free). Returns a char-level alignment built
    from word boundaries so the rest of the pipeline works unchanged."""
    import asyncio
    import edge_tts

    async def go():
        comm = edge_tts.Communicate(text, cfg.get("edge_voice", "tr-TR-AhmetNeural"),
                                    rate=cfg.get("edge_rate", "+5%"), pitch=cfg.get("edge_pitch", "+0Hz"),
                                    boundary="WordBoundary")
        audio, marks = bytearray(), []
        async for ch in comm.stream():
            if ch["type"] == "audio":
                audio.extend(ch["data"])
            elif ch["type"] == "WordBoundary":
                marks.append((ch["offset"] / 1e7, (ch["offset"] + ch["duration"]) / 1e7))
        return bytes(audio), marks

    for attempt in range(5):
        try:
            audio, marks = asyncio.run(go())
            if audio:
                break
        except Exception as e:  # network hiccups
            log("edge-tts hatası:", e)
        time.sleep(5 * (attempt + 1))
    else:
        raise RuntimeError("edge-tts başarısız")
    path.write_bytes(audio)
    return _align_from_words(text, marks)


def _align_from_words(text: str, marks: list[tuple[float, float]]) -> dict:
    """Map word timings onto characters: every char of word i gets word i's start."""
    starts = [0.0] * len(text)
    ends = [0.0] * len(text)
    i, pos = 0, 0
    tokens = text.split(" ")
    for tok in tokens:
        if any(ch.isalnum() for ch in tok):
            st, en = marks[min(i, len(marks) - 1)] if marks else (0.0, 0.0)
            i += 1
        else:
            st, en = (starts[pos - 1], ends[pos - 1]) if pos else (0.0, 0.0)
        for k in range(pos, min(pos + len(tok) + 1, len(text))):
            starts[k], ends[k] = st, en
        pos += len(tok) + 1
    return {"characters": list(text), "character_start_times_seconds": starts,
            "character_end_times_seconds": ends}


def _dummy(text: str, path):
    dur = max(1.0, len(text) * 0.062)
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
         "-t", f"{dur:.3f}", "-c:a", "libmp3lame", "-b:a", "128k", str(path)])
    n = len(text)
    return {"characters": list(text),
            "character_start_times_seconds": [dur * i / n for i in range(n)],
            "character_end_times_seconds": [dur * (i + 1) / n for i in range(n)]}


def generate(ep: Episode, force: bool = False):
    cfg = load_config()["voice"]
    rec = next((ep.dir / f for f in ("kayit.mp3", "kayit.m4a", "kayit.wav") if (ep.dir / f).exists()), None)
    if rec:  # the narrator's own recording wins over any TTS
        from .recording import from_recording
        return from_recording(ep, rec)
    secs = ep.script["sections"]
    texts = [section_text(s) for s in secs]
    for i, (sec, (text, offs)) in enumerate(zip(secs, texts), 1):
        mp3 = ep.audio / f"sec_{i:02d}.mp3"
        meta = ep.audio / f"sec_{i:02d}.json"
        h = hashlib.sha1((text + json.dumps(cfg, sort_keys=True)).encode()).hexdigest()[:10]
        if mp3.exists() and meta.exists() and not force and json.loads(meta.read_text()).get("hash") == h:
            continue
        log(f"seslendirme bölüm {i}/{len(secs)} ({len(text)} karakter)")
        if cfg["provider"] == "dummy":
            align = _dummy(text, mp3)
        elif cfg["provider"] == "edge":
            align = _edge(text, mp3, cfg)
        else:
            prev = texts[i - 2][0] if i > 1 else ""
            nxt = texts[i][0] if i < len(texts) else ""
            audio, align = _eleven(text, prev, nxt, cfg)
            mp3.write_bytes(audio)
        starts = align["character_start_times_seconds"]
        ends = align["character_end_times_seconds"]
        # first spoken char of each scene (skip spaces/punctuation)
        scene_starts = []
        for o in offs:
            j = o
            while j < len(text) - 1 and not text[j].isalnum():
                j += 1
            j = min(j, len(starts) - 1)
            scene_starts.append(starts[j])
        scene_starts[0] = 0.0
        dur = ffprobe_duration(mp3)
        speech_end = ends[-1] if ends else dur
        meta.write_text(json.dumps({"hash": h, "duration": dur, "speech_end": speech_end,
                                    "scene_starts": scene_starts}, ensure_ascii=False))
    log("seslendirme tamam")
