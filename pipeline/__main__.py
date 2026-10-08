"""Usage:
  python -m pipeline validate <slug>
  python -m pipeline all <slug>          # images + voice + render + thumbnail + metadata
  python -m pipeline images <slug> [--force] [--only s01_02,s03_04]
  python -m pipeline voice <slug> [--force]
  python -m pipeline render <slug>
  python -m pipeline publish <slug>
  python -m pipeline style               # one-time: create assets/style/style_ref.png
  python -m pipeline next-topic          # print the next unused topic from topics.yaml
"""
import argparse
import sys

import yaml

from .common import ROOT, Episode, log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()

    if a.cmd == "style":
        from .common import load_config
        if load_config()["images"]["provider"] != "openai":
            log("Stil referansı yalnızca OpenAI için gerekli; atlanıyor")
            return
        from .images import bootstrap_style
        bootstrap_style(ROOT / "assets/style/style_ref.png")
        return
    if a.cmd == "next-topic":
        topics = yaml.safe_load((ROOT / "topics.yaml").read_text(encoding="utf-8"))["queue"]
        for t in topics:
            if not any((ROOT / "episodes" / t["slug"] / f).exists() for f in ("script.yaml", "script.json")):
                print(yaml.safe_dump(t, allow_unicode=True))
                return
        sys.exit("Kuyrukta konu kalmadı")

    ep = Episode(a.slug)
    from . import images, publish, render, validate, voice
    if a.cmd in ("validate", "all"):
        if not validate.validate(ep):
            sys.exit("script.json geçersiz")
    if a.cmd in ("images", "all"):
        rep = images.generate(ep, only=[x for x in a.only.split(",") if x] or None, force=a.force)
        if rep["failed"]:
            log("Eksik görseller yer tutucuyla dolduruldu:", rep["failed"])
    if a.cmd in ("voice", "all"):
        voice.generate(ep, force=a.force)
    if a.cmd in ("render", "all"):
        render.render(ep)
    if a.cmd in ("publish", "all"):
        publish.thumbnail(ep, force=a.force)
        publish.metadata(ep)


if __name__ == "__main__":
    main()
