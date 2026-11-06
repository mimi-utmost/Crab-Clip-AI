"""Etapa render: corte + 9:16 + legendas karaokê queimadas + encode AMF.

Um comando ffmpeg por clipe. Crop central calculado da geometria real do vídeo
(origem registrada no ingest). AMF falhando, cai para libx264 e registra o
encoder efetivamente usado no banco. O filtro subtitles usa caminho relativo
com cwd na pasta do clipe — escaping de filtro no Windows não é confiável com
caminhos absolutos.
"""
from __future__ import annotations

import json
from pathlib import Path

from engine import captions
from engine.config import Config
from engine.db import DB
from engine.proc import run


def _filtro_video(width: int, height: int, ass_nome: str) -> str:
    crop_w = round(height * 9 / 16)
    crop_w -= crop_w % 2
    x = max(0, (width - crop_w) // 2)
    return (f"crop={crop_w}:{height}:{x}:0,scale=1080:1920,setsar=1,"
            f"subtitles='{ass_nome}'")


def _args_encoder(encoder: str) -> list[str]:
    if encoder == "h264_amf":
        return ["-c:v", "h264_amf", "-quality", "balanced", "-rc", "cbr",
                "-b:v", "8M", "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-pix_fmt", "yuv420p"]


def montar_comando(cfg: Config, video_path: str, inicio: float, fim: float,
                   width: int, height: int, ass_nome: str, out_nome: str,
                   encoder: str) -> list[str]:
    return [str(cfg.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{inicio:.2f}", "-to", f"{fim:.2f}", "-i", video_path,
            "-vf", _filtro_video(width, height, ass_nome),
            *_args_encoder(encoder), "-c:a", "aac", "-b:a", "128k", out_nome]


def render_clipe(cfg: Config, video: dict, momento, workdir: Path,
                 palavras: list[dict]) -> tuple[Path, str]:
    clips_dir = workdir / "clips"
    clips_dir.mkdir(exist_ok=True)
    ass = captions.escrever_ass(palavras, momento["start_s"], momento["end_s"],
                                clips_dir / f"captions-{momento['id']}.ass")
    out = clips_dir / f"clip-{momento['id']:03d}.mp4"
    for encoder in ("h264_amf", "libx264"):
        cmd = montar_comando(cfg, video["path"], momento["start_s"], momento["end_s"],
                             video["width"], video["height"], ass.name, out.name, encoder)
        r = run(cmd, cwd=clips_dir, timeout=1800)
        if r.returncode == 0 and out.exists():
            return out, encoder
        out.unlink(missing_ok=True)
    raise RuntimeError(f"render do clipe {momento['id']} falhou nos dois encoders: "
                       f"{r.stderr.strip()[-300:]}")


def run_stage(cfg: Config, db: DB, video_id: int) -> None:
    video = dict(db.get_video(video_id))
    pendentes = [m for m in db.moments(video_id) if m["status"] == "pending"]
    if not pendentes:
        return
    workdir = cfg.video_dir(video_id)
    transcript = json.loads((workdir / "transcript.json").read_text(encoding="utf-8"))
    palavras = [p for s in transcript["segments"] for p in s["words"]]
    for momento in pendentes:
        out, encoder = render_clipe(cfg, video, momento, workdir, palavras)
        db.add_clip(momento["id"], str(out), encoder)
        db.set_moment_status(momento["id"], "rendered")
        print(f"  render: clipe {momento['id']} ({momento['end_s'] - momento['start_s']:.0f}s, "
              f"{encoder}) -> {out.name}")
