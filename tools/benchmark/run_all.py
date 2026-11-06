"""Executa os benchmarks disponíveis e gera o relatório em docs/benchmarks/.

Uso:
    py -3 tools/benchmark/run_all.py              # roda todos os configurados
    py -3 tools/benchmark/run_all.py --only ffmpeg
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import bench_ffmpeg
import bench_llama
import bench_whisper
from common import DOCS_DIR, ROOT, BenchSkip, load_config, save_results, system_info

BENCHES = {"ffmpeg": bench_ffmpeg, "whisper": bench_whisper, "llama": bench_llama}


def _tabela(linhas: list[dict], colunas: list[tuple[str, str]]) -> str:
    out = ["| " + " | ".join(titulo for titulo, _ in colunas) + " |",
           "|" + "---|" * len(colunas)]
    for l in linhas:
        out.append("| " + " | ".join(str(l.get(chave) if l.get(chave) is not None else "—")
                                      for _, chave in colunas) + " |")
    return "\n".join(out)


def _fmt_ffmpeg(p: dict) -> str:
    colunas = [("Teste", "teste"), ("Disponível", "disponivel"), ("Tempo (s)", "tempo_s"),
               ("FPS médio", "fps_medio"), ("Tamanho (bytes)", "tamanho_bytes"),
               ("Pico VRAM (MB)", "pico_vram_mb"), ("Erro", "erro")]
    return (_tabela(p["testes"], colunas) +
            f"\n\nMétodo: `{p['metodo_fps']}`. Amostra: `{p['amostra']}` "
            f"({p['quadros']} quadros). Origem do ffmpeg: {p['origem_ffmpeg']}.")


def _fmt_whisper(p: dict) -> str:
    colunas = [("Backend", "backend"), ("Modelo", "modelo"), ("Disponível", "disponivel"),
               ("Execuções (s)", "execucoes_s"), ("Mediana (s)", "mediana_s"),
               ("RTF", "rtf"), ("Pico VRAM (MB)", "pico_vram_mb"), ("Erro", "erro")]
    return (_tabela(p["resultados"], colunas) +
            f"\n\nAmostra: `{p['amostra']}` → `{p['amostra_wav']}` ({p['duracao_audio_s']} s). "
            f"{p['observacao']}.")


def _fmt_llama(p: dict) -> str:
    colunas = [("Backend", "backend"), ("Modelo", "modelo"), ("Disponível", "disponivel"),
               ("pp512 (t/s)", "pp512_tps"), ("tg128 (t/s)", "tg128_tps"),
               ("Pico VRAM (MB)", "pico_vram_mb"), ("Tempo total (s)", "tempo_total_s"),
               ("Erro", "erro")]
    return _tabela(p["resultados"], colunas) + f"\n\n{p['observacao']}."


_FORMATTERS = {"ffmpeg": _fmt_ffmpeg, "whisper": _fmt_whisper, "llama": _fmt_llama}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", choices=sorted(BENCHES), action="append",
                    help="roda apenas os benchmarks listados (pode repetir)")
    args = ap.parse_args()
    cfg = load_config()
    escolhidos = args.only or list(BENCHES)

    relatorio = [f"# Relatório de benchmark — {datetime.now():%Y-%m-%d %H:%M}", ""]
    info = system_info()
    relatorio += ["## Sistema", "", "```json",
                  json.dumps(info, ensure_ascii=False, indent=2), "```", ""]

    for nome in escolhidos:
        print(f"== {nome} ==")
        try:
            payload = BENCHES[nome].run(cfg)
        except BenchSkip as exc:
            payload = {"pulado": str(exc)}
            print(f"  pulado (pré-requisito ausente)")
        raw = save_results(nome, payload)
        relatorio += [f"## {nome}", ""]
        if "pulado" in payload:
            relatorio += [f"**Pulado:** {payload['pulado']}", ""]
        else:
            relatorio += [_FORMATTERS[nome](payload), ""]
        relatorio += [f"_Dados brutos: `{raw.relative_to(ROOT)}`_", ""]

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for destino in (DOCS_DIR / f"report-{stamp}.md", DOCS_DIR / "report-latest.md"):
        destino.write_text("\n".join(relatorio), encoding="utf-8")
    print(f"relatório: {DOCS_DIR / 'report-latest.md'}")


if __name__ == "__main__":
    main()
