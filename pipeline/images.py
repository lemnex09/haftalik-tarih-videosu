"""Scene image generation (OpenAI gpt-image) with style references + caching."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

from .common import ROOT, Episode, env, load_config, log

STYLE = (ROOT / "assets/style/style_prompt.txt").read_text(encoding="utf-8").strip()
API = "https://api.openai.com/v1/images"
CF_MODEL = "@cf/black-forest-labs/flux-1-schnell"


class QuotaExceeded(Exception):
    pass


def _cloudflare_call(prompt: str, seed: int, cfg: dict) -> bytes:
    """Cloudflare Workers AI — free daily allocation (~170 FLUX images/day)."""
    acc, tok = env("CLOUDFLARE_ACCOUNT_ID"), env("CLOUDFLARE_API_TOKEN")
    url = f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/{CF_MODEL}"
    body = {"prompt": prompt[:2048], "steps": int(cfg.get("steps", 4)), "seed": seed}
    for attempt in range(5):
        try:
            r = requests.post(url, headers={"Authorization": f"Bearer {tok}"}, json=body, timeout=120)
            if r.status_code == 200:
                return base64.b64decode(r.json()["result"]["image"])
            msg = r.text[:400]
            log(f"Cloudflare {r.status_code}: {msg}")
            low = msg.lower()
            if r.status_code == 429 or "allocation" in low or "neurons" in low or "4006" in msg:
                raise QuotaExceeded(msg)
            if r.status_code in (401, 403):
                raise SystemExit("Cloudflare anahtarı hatalı — CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN kontrol et")
        except requests.RequestException as e:
            log("Cloudflare istek hatası:", e)
        time.sleep(3 * 2 ** attempt)
    raise RuntimeError("Cloudflare görsel üretimi başarısız")


def _pollinations_call(prompt: str, seed: int, cfg: dict) -> bytes:
    """Pollinations.ai — free, no key (anonymous ~1 request / 15 s)."""
    from urllib.parse import quote
    url = (f"https://image.pollinations.ai/prompt/{quote(prompt[:1800])}"
           f"?width=1536&height=1024&model=flux&seed={seed}&nologo=true&private=true")
    headers = {}
    if os.environ.get("POLLINATIONS_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['POLLINATIONS_TOKEN']}"
    for attempt in range(6):
        try:
            r = requests.get(url, headers=headers, timeout=180)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
                return r.content
            log(f"Pollinations {r.status_code}: {r.text[:200]}")
        except requests.RequestException as e:
            log("Pollinations istek hatası:", e)
        time.sleep(16 + 10 * attempt)
    raise RuntimeError("Pollinations görsel üretimi başarısız")


_cf_exhausted = False


def free_image(prompt: str, seed: int, cfg: dict) -> bytes:
    """Cloudflare first; when the daily free quota runs out, Pollinations."""
    global _cf_exhausted
    has_cf = os.environ.get("CLOUDFLARE_ACCOUNT_ID") and os.environ.get("CLOUDFLARE_API_TOKEN")
    if cfg["provider"] == "cloudflare" and not has_cf and not _cf_exhausted:
        log("Cloudflare anahtarı yok → Pollinations kullanılıyor")
        _cf_exhausted = True
    if cfg["provider"] == "cloudflare" and not _cf_exhausted:
        try:
            return _cloudflare_call(prompt, seed, cfg)
        except QuotaExceeded:
            _cf_exhausted = True
            log("Cloudflare günlük ücretsiz kotası doldu → Pollinations'a geçiliyor")
    time.sleep(15)  # anonymous Pollinations rate limit
    return _pollinations_call(prompt, seed, cfg)


FLUX_STYLE = (ROOT / "assets/style/style_prompt_flux.txt").read_text(encoding="utf-8").strip()


def build_prompt(scene_prompt: str, characters: dict, compact: bool = False) -> str:
    txt = scene_prompt
    used = []
    for key, desc in characters.items():
        tok = "{" + key + "}"
        if tok in txt:
            txt = txt.replace(tok, key.replace("_", " ").lower())
            used.append(f"- {key.replace('_', ' ').lower()}: {desc}")
    if compact:  # FLUX: scene first (most weight), then style + character notes
        chars_txt = " ".join(u[2:] + "." for u in used)
        return f"{txt} {chars_txt} {FLUX_STYLE}"
    parts = [STYLE, ""]
    if used:
        parts += ["Recurring characters in this scene (keep their look consistent):", *used, ""]
    parts += ["SCENE:", txt]
    return "\n".join(parts)


def _openai_call(prompt: str, refs: list[Path], cfg: dict) -> bytes:
    key = env("OPENAI_API_KEY")
    headers = {"Authorization": f"Bearer {key}"}
    data = {"model": cfg["model"], "prompt": prompt, "size": cfg["size"],
            "quality": cfg["quality"], "n": "1"}
    for attempt in range(6):
        try:
            if refs:
                files = [("image[]", (p.name, open(p, "rb"), "image/png")) for p in refs]
                r = requests.post(f"{API}/edits", headers=headers, data=data, files=files, timeout=300)
            else:
                r = requests.post(f"{API}/generations", headers={**headers, "Content-Type": "application/json"},
                                  data=json.dumps({**data, "n": 1}), timeout=300)
            if r.status_code == 200:
                return base64.b64decode(r.json()["data"][0]["b64_json"])
            msg = r.text[:600]
            if r.status_code == 400 and ("safety" in msg.lower() or "moderation" in msg.lower()):
                raise ValueError("safety:" + msg)
            log(f"OpenAI {r.status_code}: {msg}")
            if "insufficient_quota" in msg or "billing" in msg.lower():
                raise SystemExit("OpenAI bakiyesi bitti — platform.openai.com/settings/organization/billing adresinden kredi yükle")
            if r.status_code in (400, 401, 403, 404):
                # model not available on this account -> fall back once to gpt-image-1
                if "model" in msg.lower() and data["model"] != "gpt-image-1":
                    log(f"'{data['model']}' kullanılamıyor, gpt-image-1 ile deneniyor")
                    data["model"] = cfg["model"] = "gpt-image-1"
                    continue
                raise SystemExit(f"OpenAI hatası {r.status_code} — anahtar, kuruluş doğrulaması ya da bakiye: {msg}")
        except (requests.RequestException, KeyError) as e:
            log("OpenAI istek hatası:", e)
        time.sleep(min(60, 4 * 2 ** attempt) + random.random())
    raise RuntimeError("OpenAI görsel üretimi başarısız")


def placeholder(path: Path, text: str, seed: str):
    rnd = random.Random(seed)
    im = Image.new("RGB", (1536, 1024), tuple(rnd.randint(120, 230) for _ in range(3)))
    d = ImageDraw.Draw(im)
    for _ in range(6):
        x, y = rnd.randint(0, 1400), rnd.randint(100, 900)
        r = rnd.randint(40, 120)
        d.ellipse([x, y, x + r, y + r], fill="white", outline="black", width=5)
    font = ImageFont.truetype(str(ROOT / "assets/fonts/Baloo2.ttf"), 34)
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) > 70:
            lines.append(cur); cur = ""
        cur += w + " "
    lines.append(cur)
    d.multiline_text((60, 120), "\n".join(lines[:12]), fill="black", font=font)
    im.save(path)


def generate(ep: Episode, only: list[str] | None = None, force: bool = False) -> dict:
    cfg = load_config()["images"]
    chars = ep.characters()
    refs = [ROOT / p for p in cfg.get("style_refs", []) if (ROOT / p).exists()]
    refs += [ep.dir / p for p in ep.script.get("reference_images", []) if (ep.dir / p).exists()]
    scenes = [s for s in ep.scenes() if not s.get("reuse")]
    if only:
        scenes = [s for s in scenes if s["id"] in only]
    report = {"generated": 0, "cached": 0, "failed": []}

    def job(sc):
        out = ep.images / f"{sc['id']}.png"
        free = cfg["provider"] in ("cloudflare", "pollinations")
        prompt = build_prompt(sc["image"], chars, compact=free)
        h = hashlib.sha1((prompt + cfg["model"] + cfg["quality"]).encode()).hexdigest()[:10]
        stamp = out.with_suffix(".hash")
        if out.exists() and not force and stamp.exists() and stamp.read_text() == h:
            return "cached", sc["id"]
        if cfg["provider"] == "placeholder":
            placeholder(out, sc["image"], sc["id"])
        elif free:
            seed = int(hashlib.md5(sc["id"].encode()).hexdigest()[:6], 16)
            out.write_bytes(free_image(prompt, seed, cfg))
        else:
            try:
                png = _openai_call(prompt, refs, cfg)
            except ValueError:
                # safety refusal: retry once with a gentler, shorter prompt
                png = _openai_call(build_prompt("A calm, family-friendly version of: " + sc["image"][:400], chars), refs, cfg)
            out.write_bytes(png)
        stamp.write_text(h)
        return "generated", sc["id"]

    workers = 1 if cfg["provider"] in ("cloudflare", "pollinations") else int(cfg.get("concurrency", 4))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(job, s): s["id"] for s in scenes}
        for i, f in enumerate(as_completed(futs), 1):
            sid = futs[f]
            try:
                kind, _ = f.result()
                report[kind] += 1
            except Exception as e:  # keep going, report at end
                log("görsel başarısız", sid, e)
                report["failed"].append(sid)
                placeholder(ep.images / f"{sid}.png", "EKSİK GÖRSEL: " + sid, sid)
            if i % 10 == 0:
                log(f"görseller {i}/{len(scenes)}")
    log("görsel raporu:", report)
    return report


def bootstrap_style(out: Path, prompt_extra: str = ""):
    """One-time: create the channel's style reference sheet (no refs)."""
    cfg = load_config()["images"]
    prompt = STYLE + "\n\n" + (prompt_extra or (
        "STYLE REFERENCE SHEET: a lively 1940s Anatolian village square scene showing six different characters "
        "in the exact character style (white round heads, dot eyes): an old man with a flat cap and walking stick, "
        "a young man in a vest and flat cap, a woman in a white headscarf and floral dress, a little boy, a little "
        "girl with a headscarf, a schoolteacher in a suit. Stone houses with red tile roofs, a fountain, a plane tree, "
        "a donkey cart. Clear daylight."))
    png = _openai_call(prompt, [], {**cfg, "quality": "high"})
    out.write_bytes(png)
    log("stil referansı kaydedildi:", out)
