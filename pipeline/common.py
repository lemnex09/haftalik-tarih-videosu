"""Shared helpers: config, episode loading, logging."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def log(*a):
    print("[pipeline]", *a, flush=True)


def load_config() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # test/CI overrides: IMAGES_PROVIDER=placeholder VOICE_PROVIDER=dummy
    if os.environ.get("IMAGES_PROVIDER"):
        cfg["images"]["provider"] = os.environ["IMAGES_PROVIDER"]
    if os.environ.get("VOICE_PROVIDER"):
        cfg["voice"]["provider"] = os.environ["VOICE_PROVIDER"]
    if os.environ.get("IMAGES_QUALITY"):
        cfg["images"]["quality"] = os.environ["IMAGES_QUALITY"]
    return cfg


class Episode:
    """An episode folder: episodes/<slug>/script.json plus build/ outputs."""

    def __init__(self, slug: str):
        self.slug = slug
        self.dir = ROOT / "episodes" / slug
        y, j = self.dir / "script.yaml", self.dir / "script.json"
        if y.exists():  # YAML is the authoring format; JSON is kept in sync
            with open(y, encoding="utf-8") as f:
                self.script = yaml.safe_load(f)
            j.write_text(json.dumps(self.script, ensure_ascii=False, indent=1), encoding="utf-8")
        elif j.exists():
            with open(j, encoding="utf-8") as f:
                self.script = json.load(f)
        else:
            sys.exit(f"script.yaml/json yok: {self.dir}")
        self.script_path = y if y.exists() else j
        self.build = self.dir / "build"
        self.images = self.build / "images"
        self.audio = self.build / "audio"
        self.clips = self.build / "clips"
        self.out = self.dir / "output"
        for p in (self.images, self.audio, self.clips, self.out):
            p.mkdir(parents=True, exist_ok=True)

    # flat list of scenes with ids "s03_07" (section 3, scene 7)
    def scenes(self):
        out = []
        for si, sec in enumerate(self.script["sections"], 1):
            for ci, sc in enumerate(sec["scenes"], 1):
                sc = dict(sc)
                sc["id"] = f"s{si:02d}_{ci:02d}"
                sc["section_index"] = si
                out.append(sc)
        return out

    def characters(self) -> dict:
        return self.script.get("characters", {})

    def timeline_path(self) -> Path:
        return self.build / "timeline.json"


def run(cmd: list[str], **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        log("KOMUT HATASI:", " ".join(map(str, cmd))[:500])
        log(r.stderr[-3000:])
        raise RuntimeError("command failed")
    return r


def ffprobe_duration(path: Path) -> float:
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)])
    return float(r.stdout.strip())


def env(name: str, required: bool = True) -> str | None:
    v = os.environ.get(name)
    if required and not v:
        sys.exit(f"Ortam değişkeni eksik: {name} (GitHub > Settings > Secrets'a ekle)")
    return v
