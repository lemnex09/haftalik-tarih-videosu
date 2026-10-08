"""Check a script.json before spending money on generation."""
from __future__ import annotations

import re

from .common import Episode, log

WPM = 150  # Turkish narration pace of the reference video (~1150 words / 7.8 min)


def validate(ep: Episode) -> bool:
    s = ep.script
    errs, warns = [], []
    for k in ("title", "sections", "youtube", "thumbnail"):
        if k not in s:
            errs.append(f"eksik alan: {k}")
    if errs:
        for e in errs:
            log("HATA", e)
        return False
    chars = set(s.get("characters", {}))
    scenes = ep.scenes()
    ids = {sc["id"] for sc in scenes}
    words = 0
    for sc in scenes:
        say = sc.get("say", "").strip()
        if not say:
            errs.append(f"{sc['id']}: 'say' boş")
        if not sc.get("image") and not sc.get("reuse"):
            errs.append(f"{sc['id']}: 'image' veya 'reuse' gerekli")
        if sc.get("reuse") and sc["reuse"] not in ids:
            errs.append(f"{sc['id']}: reuse hedefi yok ({sc['reuse']})")
        for tok in re.findall(r"\{([A-Z0-9_]+)\}", sc.get("image", "")):
            if tok not in chars:
                errs.append(f"{sc['id']}: tanımsız karakter {{{tok}}}")
        if sc.get("overlay") and len(sc["overlay"]) > 22:
            warns.append(f"{sc['id']}: ekran yazısı uzun ({sc['overlay']})")
        if re.search(r"\d", say):
            warns.append(f"{sc['id']}: rakam var, okunuşu kontrol et → {say[:60]}")
        words += len(say.split())
    n_img = sum(1 for sc in scenes if not sc.get("reuse"))
    est = words / WPM
    log(f"{len(s['sections'])} bölüm, {len(scenes)} sahne, {n_img} yeni görsel, {words} kelime ≈ {est:.1f} dk")
    if not 5.5 <= est <= 10.5:
        warns.append(f"tahmini süre {est:.1f} dk (hedef 7–9)")
    avg = est * 60 / max(len(scenes), 1)
    if avg > 3.5:
        warns.append(f"sahne başına ort. {avg:.1f} sn — referans tempo ~2.2-3 sn")
    for w in warns:
        log("UYARI", w)
    for e in errs:
        log("HATA", e)
    return not errs
