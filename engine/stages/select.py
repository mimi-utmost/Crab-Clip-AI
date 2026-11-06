"""Etapa select: dedup, clamp de 60 s, snap em fronteiras de fala e ranking.

Os candidatos do LLM são higienizados antes de virar clipe:
1. dedup por sobreposição (IoU > 0.5 → fica o de maior score)
2. clamp duro na duração máxima (60 s default)
3. bordas ajustadas para o início/fim de palavra mais próximo (±2 s), evitando
   cortes no meio de uma palavra
4. descarte dos que ficaram abaixo da duração mínima
5. ranking por score, top-N
"""
from __future__ import annotations

import json

from engine.config import Config
from engine.db import DB

TOLERANCIA_SNAP_S = 2.0
IOU_DEDUP = 0.5


def _iou(a: dict, b: dict) -> float:
    inter = max(0.0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
    uniao = max(a["end"], b["end"]) - min(a["start"], b["start"])
    return inter / uniao if uniao > 0 else 0.0


def dedup(candidatos: list[dict], iou_max: float = IOU_DEDUP) -> list[dict]:
    ordenados = sorted(candidatos, key=lambda m: m["score"], reverse=True)
    mantidos: list[dict] = []
    for m in ordenados:
        if all(_iou(m, k) <= iou_max for k in mantidos):
            mantidos.append(m)
    return mantidos


def _snap(valor: float, bordas: list[float], tolerancia: float) -> float:
    if not bordas:
        return valor
    mais_proxima = min(bordas, key=lambda b: abs(b - valor))
    return mais_proxima if abs(mais_proxima - valor) <= tolerancia else valor


def selecionar(candidatos: list[dict], palavras: list[dict], max_s: float,
               min_s: float, top_n: int) -> list[dict]:
    inicios = [p["start"] for p in palavras]
    fins = [p["end"] for p in palavras]
    selecionados = []
    for m in dedup(candidatos):
        inicio = _snap(m["start"], inicios, TOLERANCIA_SNAP_S)
        fim = _snap(min(m["end"], m["start"] + max_s), fins, TOLERANCIA_SNAP_S)
        fim = min(fim, inicio + max_s)
        if fim - inicio < min_s:
            continue
        selecionados.append({**m, "start": round(inicio, 2), "end": round(fim, 2)})
    selecionados.sort(key=lambda m: m["score"], reverse=True)
    return selecionados[:top_n]


def run_stage(cfg: Config, db: DB, video_id: int) -> None:
    video_dir = cfg.video_dir(video_id)
    candidatos = json.loads((video_dir / "momentos-candidatos.json").read_text(encoding="utf-8"))
    transcript = json.loads((video_dir / "transcript.json").read_text(encoding="utf-8"))
    palavras = [p for s in transcript["segments"] for p in s["words"]]
    selecionados = selecionar(candidatos, palavras, cfg.clip_max_s,
                              cfg.clip_min_s, cfg.top_n)
    db.clear_moments(video_id)
    for m in selecionados:
        db.add_moment(video_id, m["start"], m["end"], m["score"],
                      m.get("titulo", ""), m.get("motivo", ""))
    (video_dir / "momentos.json").write_text(
        json.dumps(selecionados, ensure_ascii=False, indent=1), encoding="utf-8")
