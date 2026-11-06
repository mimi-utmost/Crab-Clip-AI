"""Etapa transcribe: whisper-cli (-ojf) com timestamps derivados de tokens.

Roda o whisper.cpp em CPU (decisão da fase 0: RTF 0.547 medido) e normaliza a
saída para work/<id>/transcript.json:
{"segments": [{"start": s, "end": s, "text": str, "confidence": 0-1,
               "words": [{"word": str, "start": s, "end": s}]}]}

Os timestamps por palavra NÃO vêm prontos: o JSON completo (-ojf) traz tokens
com offsets em ms; agrupamos tokens em palavras (token com espaço inicial abre
palavra nova). O `-owts` do whisper-cli gera um .wts vazio neste build — não usar.
"""
from __future__ import annotations

import json
from pathlib import Path

from engine.config import Config
from engine.db import DB
from engine.proc import run


def palavras_de_tokens(tokens: list[dict]) -> list[dict]:
    palavras: list[dict] = []
    atual: dict | None = None
    for t in tokens:
        texto = t.get("text", "")
        if texto.startswith("[_"):
            continue
        off = t.get("offsets", {})
        ini, fim = off.get("from", 0) / 1000, off.get("to", 0) / 1000
        if texto.startswith(" ") or atual is None:
            if atual and atual["word"].strip():
                palavras.append(atual)
            atual = {"word": texto, "start": ini, "end": fim}
        else:
            atual["word"] += texto
            atual["end"] = fim
    if atual and atual["word"].strip():
        palavras.append(atual)
    for p in palavras:
        p["word"] = p["word"].strip()
    return palavras


def parsear_saida_whisper(dados: dict) -> dict:
    """Normaliza o JSON completo do whisper-cli (-ojf) para o contrato do engine."""
    segmentos = []
    for seg in dados.get("transcription", []):
        off = seg.get("offsets", {})
        tokens = seg.get("tokens", [])
        probabilidades = [t["p"] for t in tokens
                          if not t.get("text", "").startswith("[_") and t.get("p") is not None]
        segmentos.append({
            "start": off.get("from", 0) / 1000,
            "end": off.get("to", 0) / 1000,
            "text": seg.get("text", "").strip(),
            "confidence": round(sum(probabilidades) / len(probabilidades), 3)
                          if probabilidades else None,
            "words": palavras_de_tokens(tokens),
        })
    return {"segments": segmentos}


def run_stage(cfg: Config, db: DB, video_id: int) -> None:
    video_dir = cfg.video_dir(video_id)
    wav = video_dir / "audio-16k.wav"
    dest = video_dir / "transcript.json"
    if dest.exists():
        return
    out_base = video_dir / "transcript-raw"
    cmd = [cfg.whisper_cli, "-m", cfg.whisper_model, "-f", wav,
           "-l", "auto", "-t", str(cfg.whisper_threads), "-ojf",
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
