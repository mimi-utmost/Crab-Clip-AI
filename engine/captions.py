"""Gera legendas ASS estilo karaokê a partir dos timestamps por palavra.

Estilo: linha branca com preenchimento amarelo palavra a palavra (tag \\k do
libass), inferior-central, pensado para 1080x1920. Os tempos são relativos ao
início do clipe (o render corta com -ss, então a legenda começa em zero).
"""
from __future__ import annotations

from pathlib import Path

CABECALHO = """\
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,Arial,88,&H00FFFFFF,&H0000D7FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,5,1,2,60,60,140,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

MAX_PALAVRAS_LINHA = 5
MAX_CARACTERES_LINHA = 30


def _tempo_ass(segundos: float) -> str:
    cs = max(0, round(segundos * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _escapar(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def _agrupar(palavras: list[dict]) -> list[list[dict]]:
    linhas: list[list[dict]] = []
    atual: list[dict] = []
    caracteres = 0
    for p in palavras:
        texto = p["word"]
        if atual and (len(atual) >= MAX_PALAVRAS_LINHA
                      or caracteres + len(texto) > MAX_CARACTERES_LINHA
                      or texto.endswith((".", "!", "?", "…"))):
            linhas.append(atual)
            atual, caracteres = [], 0
        atual.append(p)
        caracteres += len(texto) + 1
    if atual:
        linhas.append(atual)
    return linhas


def gerar_eventos(palavras: list[dict], inicio: float, fim: float) -> list[str]:
    """Gera as linhas Dialogue de um clipe [inicio, fim] (tempos absolutos)."""
    trecho = [p for p in palavras if p["end"] > inicio and p["start"] < fim]
    eventos = []
    for linha in _agrupar(trecho):
        partes = []
        for i, p in enumerate(linha):
            duracao = p["end"] - p["start"]
            if i + 1 < len(linha):
                duracao = linha[i + 1]["start"] - p["start"]
            partes.append(f"{{\\k{max(1, round(duracao * 100))}}}{_escapar(p['word'])}")
        ini = max(linha[0]["start"], inicio) - inicio
        fim_linha = min(linha[-1]["end"], fim) - inicio
        if fim_linha <= ini:
            continue
        eventos.append(f"Dialogue: 0,{_tempo_ass(ini)},{_tempo_ass(fim_linha)},"
                       f"Karaoke,,0,0,0,,{' '.join(partes)}")
    return eventos


def escrever_ass(palavras: list[dict], inicio: float, fim: float,
                 destino: Path) -> Path:
    eventos = gerar_eventos(palavras, inicio, fim)
    destino.write_text(CABECALHO + "\n".join(eventos) + "\n", encoding="utf-8")
    return destino
