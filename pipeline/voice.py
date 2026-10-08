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
