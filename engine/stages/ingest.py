"""Etapa ingest: sonda o vídeo com ffprobe e grava metadados no banco."""
from __future__ import annotations

import json

from engine.config import Config
from engine.db import DB
from engine.proc import run


def sondar(cfg: Config, caminho: str) -> dict:
    exe = cfg.ffprobe or cfg.ffmpeg
    r = run([exe, "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", caminho], timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe falhou: {r.stderr.strip()[-400:]}")
    info = json.loads(r.stdout)
    stream = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if not stream:
        raise RuntimeError("nenhuma stream de vídeo encontrada no arquivo")
    return {
        "duration_s": float(info["format"]["duration"]),
        "width": int(stream["width"]),
        "height": int(stream["height"]),
    }


def run_stage(cfg: Config, db: DB, video_id: int) -> None:
    video = db.get_video(video_id)
    info = sondar(cfg, video["path"])
    db.update_video_probe(video_id, info["duration_s"], info["width"], info["height"])
