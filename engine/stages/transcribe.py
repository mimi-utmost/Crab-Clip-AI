"""Etapa transcribe: whisper-cli com timestamps por palavra (+ VAD Silero).

Roda o whisper.cpp em CPU (decisão da fase 0: RTF 0.547 medido) e normaliza a
saída para work/<id>/transcript.json:
{"segments": [{"start": s, "end": s, "text": str,
               "words": [{"word": str, "start": s, "end": s}]}]}
"""
from __future__ import annotations

import json
from pathlib import Path

from engine.config import Config
from engine.db import DB
from engine.proc import run


def parsear_saida_whisper(dados: dict) -> dict:
    """Normaliza o JSON do whisper-cli (-oj -owts) para o contrato do engine."""
    segmentos = []
    for seg in dados.get("transcription", []):
        off = seg.get("offsets", {})
        palavras = [
            {"word": w.get("word", "").strip(),
             "start": w.get("offsets", {}).get("from", 0) / 1000,
             "end": w.get("offsets", {}).get("to", 0) / 1000}
            for w in seg.get("words", [])
        ]
        palavras = [p for p in palavras if p["word"]]
        segmentos.append({
            "start": off.get("from", 0) / 1000,
            "end": off.get("to", 0) / 1000,
            "text": seg.get("text", "").strip(),
            "words": palavras,
        })
    return {"segments": segmentos}


def run_stage(cfg: Config, db: DB, video_id: int) -> None:
    video_dir = cfg.video_dir(video_id)
    wav = video_dir / "audio-16k.wav"
    dest = video_dir / "transcript.json"
    if dest.exists():
        return
    out_base = video_dir / "transcript"
    cmd = [cfg.whisper_cli, "-m", cfg.whisper_model, "-f", wav,
           "-l", "auto", "-t", str(cfg.whisper_threads), "-owts", "-oj",
           "-of", out_base]
    if cfg.use_vad and cfg.vad_model:
        cmd += ["--vad", "-vm", cfg.vad_model]
    r = run(cmd, timeout=None)
    bruto = out_base.with_suffix(".json")
    if r.returncode != 0 or not bruto.exists():
        raise RuntimeError(f"whisper-cli falhou: {r.stderr.strip()[-400:]}")
    parsed = parsear_saida_whisper(json.loads(bruto.read_text(encoding="utf-8")))
    dest.write_text(json.dumps(parsed, ensure_ascii=False, indent=1), encoding="utf-8")
    bruto.unlink()
