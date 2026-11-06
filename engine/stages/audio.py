"""Etapa audio: extrai WAV 16 kHz mono (formato nativo do whisper.cpp)."""
from __future__ import annotations

from engine.config import Config
from engine.db import DB
from engine.proc import run


def run_stage(cfg: Config, db: DB, video_id: int) -> None:
    video = db.get_video(video_id)
    dest = cfg.video_dir(video_id) / "audio-16k.wav"
    if dest.exists():
        return
    r = run([cfg.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
             "-i", video["path"], "-vn", "-ar", "16000", "-ac", "1",
             "-c:a", "pcm_s16le", dest], timeout=3600)
    if r.returncode != 0 or not dest.exists():
        raise RuntimeError(f"extração de áudio falhou: {r.stderr.strip()[-400:]}")
