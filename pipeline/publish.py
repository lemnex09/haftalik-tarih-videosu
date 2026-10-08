"""Thumbnail + YouTube metadata (title, description with real chapter times, tags)."""
from __future__ import annotations

import json

from PIL import Image, ImageDraw, ImageFont

from .common import ROOT, Episode, load_config, log
from . import images


def fmt(t: float) -> str:
    t = int(round(t))
    return f"{t // 60:02d}:{t % 60:02d}"


def metadata(ep: Episode):
    cfg = load_config()
    tl = json.loads(ep.timeline_path().read_text())
    yt = ep.script["youtube"]
    lines = [yt["description"].strip(), ""]
    if cfg["channel"].get("instagram"):
        lines += [f"📷 Instagram: {cfg['channel']['instagram']}", ""]
    lines += ["📖 BÖLÜMLER"]
    for i, s in enumerate(tl["sections"]):
        lines.append(f"{fmt(0 if i == 0 else s['start'])} {s['title']}")
    lines += ["", " ".join(yt.get("hashtags", []))]
    if ep.script.get("sources"):
        lines += ["", "📚 Kaynaklar:"] + [f"- {s}" for s in ep.script["sources"]]
    if cfg["channel"].get("footer"):
        lines += ["", cfg["channel"]["footer"]]
    desc = "\n".join(lines).strip()
    meta = {"title": yt["title"], "description": desc, "tags": yt.get("tags", []),
            "duration_sec": round(tl["total"], 1), "pinned_comment": yt.get("pinned_comment", "")}
    (ep.out / "youtube.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    md = [f"# {yt['title']}", "", "## Açıklama", "", "```", desc, "```", "",
          "## Etiketler", "", ", ".join(meta["tags"])]
    if meta["pinned_comment"]:
        md += ["", "## Sabit yorum", "", meta["pinned_comment"]]
    (ep.out / "YOUTUBE.md").write_text("\n".join(md))
    log("metadata yazıldı")


def thumbnail(ep: Episode, force: bool = False):
    cfg = load_config()
    th = ep.script["thumbnail"]
    base = ep.build / "thumb_base.png"
    if force or not base.exists():
        icfg = cfg["images"]
        prompt = images.build_prompt(th["image"] + " Bold, high-contrast, eye-catching YouTube thumbnail "
                                     "composition, one big expressive main character, simple background, "
                                     "leave the left 45% calm for title text.", ep.characters())
        if icfg["provider"] == "placeholder":
            images.placeholder(base, th["image"], "thumb")
        elif icfg["provider"] in ("cloudflare", "pollinations"):
            p2 = images.build_prompt(th["image"] + " Eye-catching YouTube thumbnail, one big expressive main "
                                     "character on the right side, simple uncluttered background.",
                                     ep.characters(), compact=True)
            base.write_bytes(images.free_image(p2, 1938, icfg))
        else:
            refs = [ROOT / p for p in icfg.get("style_refs", []) if (ROOT / p).exists()]
            base.write_bytes(images._openai_call(prompt, refs, {**icfg, "quality": "high"}))
    im = Image.open(base).convert("RGB")
    w, h = im.size
    th_h = int(w * 9 / 16)
    im = im.crop((0, (h - th_h) // 2, w, (h - th_h) // 2 + th_h)).resize((1280, 720), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    lines = th["text"].upper().split("\n")
    size = 150 if len(lines) <= 2 else 115
    font = ImageFont.truetype(str(ROOT / cfg["thumbnail"]["font"]), size)
    while max(d.textlength(l, font=font) for l in lines) > 640 and size > 60:
        size -= 6
        font = ImageFont.truetype(str(ROOT / cfg["thumbnail"]["font"]), size)
    lh = size * 1.22
    y = (720 - len(lines) * lh) / 2 + size * 0.12
    for l in lines:
        d.text((44, y), l, font=font, fill=cfg["thumbnail"]["text_color"], stroke_width=12,
               stroke_fill=cfg["thumbnail"]["stroke_color"])
        y += lh
    out = ep.out / "thumbnail.jpg"
    im.save(out, quality=92)
    log("kapak hazır:", out)
