"""Timeline + per-scene clips (Ken Burns + text pop) + final mux."""
from __future__ import annotations

import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .common import ROOT, Episode, ffprobe_duration, load_config, log, run

MOVES = ["in", "out", "left", "right", "in", "up"]


def build_timeline(ep: Episode) -> dict:
    cfg = load_config()["video"]
    gap = cfg["section_gap"]
    scenes = ep.scenes()
    t, items, sections = 0.0, [], []
    by_sec: dict[int, list] = {}
    for sc in scenes:
        by_sec.setdefault(sc["section_index"], []).append(sc)
    for si, sec in enumerate(ep.script["sections"], 1):
        meta = json.loads((ep.audio / f"sec_{si:02d}.json").read_text())
        dur = min(meta["duration"], meta["speech_end"] + 0.25)
        g = meta.get("gap", gap)
        sections.append({"title": sec["title"], "start": t, "audio": f"sec_{si:02d}.mp3", "dur": dur, "gap": g})
        starts = meta["scene_starts"]
        scs = by_sec[si]
        for k, sc in enumerate(scs):
            s = t + starts[k]
            e = t + (starts[k + 1] if k + 1 < len(scs) else dur + g)
            items.append({**sc, "start": s, "end": e})
        t += dur + g
    tl = {"total": t, "sections": sections, "scenes": items}
    ep.timeline_path().write_text(json.dumps(tl, ensure_ascii=False, indent=1))
    short = [f"{i['id']}({i['end'] - i['start']:.1f}s)" for i in items if i["end"] - i["start"] < cfg["min_scene"]]
    if short:
        log("UYARI kısa sahneler:", ", ".join(short[:20]))
    log(f"zaman çizelgesi: {len(items)} sahne, {t / 60:.1f} dk")
    return tl


def overlay_png(text: str, pos: str, path: Path, W: int, H: int):
    ocfg = load_config()["overlay"]
    text = text.replace("i", "İ").replace("ı", "I").upper()  # Türkçe büyük harf
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    size = int(ocfg["size"] * (W / 1920))
    font = ImageFont.truetype(str(ROOT / ocfg["font"]), size)
    while d.textlength(text, font=font) > W * 0.86 and size > 40:
        size -= 6
        font = ImageFont.truetype(str(ROOT / ocfg["font"]), size)
    tw = d.textlength(text, font=font)
    sw = int(ocfg["stroke_width"] * (W / 1920))
    x = {"top-left": W * 0.05}.get(pos, (W - tw) / 2)
    y = {"top": H * 0.07, "top-left": H * 0.07, "center": (H - size) / 2, "bottom": H * 0.78}.get(pos, H * 0.07)
    d.text((x, y), text, font=font, fill=ocfg["color"], stroke_width=sw, stroke_fill=ocfg["stroke_color"])
    im.save(path)


def prep_image(src: Path, dst: Path, W: int, H: int):
    """Center-crop to 16:9 and upscale 1.5x once (smooth sub-pixel motion)."""
    im = Image.open(src).convert("RGB")
    w, h = im.size
    th = int(w * 9 / 16)
    if th <= h:
        top = (h - th) // 2
        im = im.crop((0, top, w, top + th))
    else:
        tw = int(h * 16 / 9)
        left = (w - tw) // 2
        im = im.crop((left, 0, left + tw, h))
    im.resize((int(W * 1.5), int(H * 1.5)), Image.LANCZOS).save(dst)


def clip_cmd(img: Path, ovl: Path | None, frames: int, out: Path, move: str, cfg: dict) -> list[str]:
    W, H, fps = cfg["width"], cfg["height"], cfg["fps"]
    m = cfg["motion"]
    N = max(frames - 1, 1)
    p = f"(on/{N})"
    if move == "in":
        z, x, y = f"1+{m}*{p}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif move == "out":
        z, x, y = f"1+{m}-{m}*{p}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif move == "left":
        z, x, y = f"{1 + m}", f"(iw-iw/zoom)*(1-{p})", "ih/2-(ih/zoom/2)"
    elif move == "right":
        z, x, y = f"{1 + m}", f"(iw-iw/zoom)*{p}", "ih/2-(ih/zoom/2)"
    else:  # up
        z, x, y = f"{1 + m}", "iw/2-(iw/zoom/2)", f"(ih-ih/zoom)*(1-{p})"
    # decode the still once and repeat it in memory (much faster than -loop 1)
    rep = f"loop=loop={frames}:size=1:start=0,setpts=N/{fps}/TB"
    vf = f"[0:v]{rep},zoompan=z='{z}':x='{x}':y='{y}':d=1:s={W}x{H}:fps={fps},setsar=1[bg]"
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(img)]
    if ovl:
        cmd += ["-i", str(ovl)]
        vf += (f";[1:v]format=rgba,{rep},fade=t=in:st=0.12:d=0.22:alpha=1[t];"
               "[bg][t]overlay=0:0:format=auto[v]")
    else:
        vf += ";[bg]null[v]"
    cmd += ["-filter_complex", vf, "-map", "[v]", "-frames:v", str(frames),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(cfg["crf"]),
            "-pix_fmt", "yuv420p", "-r", str(fps), str(out)]
    return cmd


def render(ep: Episode, workers: int = 2):
    cfg = load_config()["video"]
    W, H, fps = cfg["width"], cfg["height"], cfg["fps"]
    tl = build_timeline(ep)
    prep = ep.build / "prep"
    prep.mkdir(exist_ok=True)
    rnd = random.Random(ep.slug)
    jobs = []
    last_move = None
    for sc in tl["scenes"]:
        f0, f1 = round(sc["start"] * fps), round(sc["end"] * fps)
        frames = max(1, f1 - f0)
        src_id = sc.get("reuse") or sc["id"]
        big = prep / f"{src_id}.png"
        if not big.exists():
            prep_image(ep.images / f"{src_id}.png", big, W, H)
        ovl = None
        if sc.get("overlay"):
            ovl = prep / f"{sc['id']}_txt.png"
            overlay_png(sc["overlay"], sc.get("overlay_pos", load_config()["overlay"]["default_position"]), ovl, W, H)
        move = sc.get("move") or rnd.choice([mv for mv in MOVES if mv != last_move])
        last_move = move
        out = ep.clips / f"{sc['id']}.mp4"
        jobs.append((sc["id"], clip_cmd(big, ovl, frames, out, move, cfg), out))

    def do(j):
        run(j[1])
        return j[0]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, _ in enumerate(pool.map(do, jobs), 1):
            if i % 20 == 0:
                log(f"klipler {i}/{len(jobs)}")

    # video concat (stream copy)
    lst = ep.build / "clips.txt"
    lst.write_text("".join(f"file '{j[2].as_posix()}'\n" for j in jobs))
    silent = ep.build / "video_silent.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent)])

    # narration track: sections + gaps, then loudness normalise
    gap = cfg["section_gap"]
    inputs, parts = [], []
    for k, s in enumerate(tl["sections"]):
        inputs += ["-i", str(ep.audio / s["audio"])]
        parts.append(f"[{k}:a]atrim=0:{s['dur']:.3f},aformat=sample_rates=48000:channel_layouts=stereo,"
                     f"apad=pad_dur={s.get('gap', gap)}[a{k}]")
    fc = ";".join(parts) + ";" + "".join(f"[a{k}]" for k in range(len(parts))) + \
        f"concat=n={len(parts)}:v=0:a=1,loudnorm=I={cfg['loudness_lufs']}:TP=-1.5:LRA=11[out]"
    narr = ep.build / "narration.m4a"
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc, "-map", "[out]",
         "-ar", "48000", "-c:a", "aac", "-b:a", "192k", str(narr)])

    final = ep.out / f"{ep.slug}.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(narr), "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(final)])
    log(f"VİDEO HAZIR: {final} ({ffprobe_duration(final) / 60:.2f} dk)")
    return final
