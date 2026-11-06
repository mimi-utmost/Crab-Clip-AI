"""CLI do engine do Crab Clip AI.

Uso:
    py -3 -m engine.cli new <caminho-do-video>   # registra um vídeo
    py -3 -m engine.cli run [--id N] [--from etapa] [--no-vad]
    py -3 -m engine.cli status                   # visão das etapas por vídeo
    py -3 -m engine.cli clips [--id N]           # clipes gerados
"""
from __future__ import annotations

import argparse
from pathlib import Path

from engine.config import Config, ConfigError
from engine.db import DB, ETAPAS
from engine.pipeline import executar


def _abrir() -> tuple[Config, DB]:
    cfg = Config.load()
    return cfg, DB(cfg.db_path)


def cmd_new(args: argparse.Namespace) -> None:
    cfg, db = _abrir()
    caminho = Path(args.video).resolve()
    if not caminho.is_file():
        raise SystemExit(f"arquivo não encontrado: {caminho}")
    video_id = db.add_video(str(caminho), title=caminho.stem)
    print(f"vídeo registrado: id={video_id} — {caminho.name}")
    print(f"agora rode: py -3 -m engine.cli run --id {video_id}")


def cmd_run(args: argparse.Namespace) -> None:
    cfg, db = _abrir()
    if args.no_vad:
        cfg.use_vad = False
    if args.id is not None:
        ids = [args.id]
    else:
        ids = [v["id"] for v in db.videos()]
    if not ids:
        raise SystemExit("nenhum vídeo registrado — use: py -3 -m engine.cli new <video>")
    for video_id in ids:
        print(f"### vídeo {video_id} ###")
        executar(cfg, db, video_id, a_partir_de=args.de)
    print("pipeline concluído")


def cmd_status(args: argparse.Namespace) -> None:
    _, db = _abrir()
    for v in db.videos():
        dur = f"{v['duration_s']:.0f}s" if v["duration_s"] else "?"
        print(f"[{v['id']}] {v['title']} ({dur}) — {v['path']}")
        estados = {s["stage"]: s for s in db.stages_do_video(v["id"])}
        linha = "  ".join(f"{e}:{estados[e]['status']}" for e in ETAPAS)
        print(f"    {linha}")
        falhas = [s for s in estados.values() if s["status"] == "failed" and s["error"]]
        for f in falhas:
            print(f"    erro em {f['stage']}: {f['error']}")


def cmd_clips(args: argparse.Namespace) -> None:
    _, db = _abrir()
    clips = db.clips(args.id)
    if not clips:
        print("nenhum clipe renderizado ainda")
        return
    for c in clips:
        print(f"[{c['id']}] vídeo {c['video_id']} — {c['title'] or '(sem título)'}"
              f" [{c['encoder']}] → {c['path']}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="crab-engine", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("new", help="registra um vídeo")
    p_new.add_argument("video")
    p_new.set_defaults(func=cmd_new)

    p_run = sub.add_parser("run", help="executa o pipeline")
    p_run.add_argument("--id", type=int, default=None,
                       help="id do vídeo (default: todos)")
    p_run.add_argument("--from", dest="de", choices=ETAPAS, default=None,
                       help="reforça execução a partir de uma etapa")
    p_run.add_argument("--no-vad", action="store_true",
                       help="desliga o VAD Silero na transcrição")
    p_run.set_defaults(func=cmd_run)

    p_status = sub.add_parser("status", help="mostra o estado dos jobs")
    p_status.set_defaults(func=cmd_status)

    p_clips = sub.add_parser("clips", help="lista clipes renderizados")
    p_clips.add_argument("--id", type=int, default=None)
    p_clips.set_defaults(func=cmd_clips)

    args = ap.parse_args()
    try:
        args.func(args)
    except ConfigError as exc:
        raise SystemExit(f"configuração inválida: {exc}")


if __name__ == "__main__":
    main()
