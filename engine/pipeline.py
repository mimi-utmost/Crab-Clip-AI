"""Orquestrador do pipeline: executa as etapas com checkpoint/resume no SQLite."""
from __future__ import annotations

from engine.config import Config
from engine.db import DB, ETAPAS
from engine.stages import analyze, audio, ingest, render, select, transcribe

STAGES = {
    "ingest": ingest.run_stage,
    "audio": audio.run_stage,
    "transcribe": transcribe.run_stage,
    "analyze": analyze.run_stage,
    "select": select.run_stage,
    "render": render.run_stage,
}


def executar(cfg: Config, db: DB, video_id: int, a_partir_de: str | None = None) -> None:
    etapas = ETAPAS[ETAPAS.index(a_partir_de):] if a_partir_de else ETAPAS
    for etapa in etapas:
        if db.stage_status(video_id, etapa) == "done" and not a_partir_de:
            print(f"== {etapa}: já concluída, pulando")
            continue
        print(f"== {etapa} ==")
        db.set_stage(video_id, etapa, "running")
        try:
            STAGES[etapa](cfg, db, video_id)
        except Exception as exc:
            db.set_stage(video_id, etapa, "failed", str(exc))
            raise
        db.set_stage(video_id, etapa, "done")
