import re

from engine.captions import _tempo_ass, escrever_ass, gerar_eventos

PALAVRAS = [
    {"word": "e", "start": 10.0, "end": 10.3},
    {"word": "aí", "start": 10.3, "end": 10.6},
    {"word": "galera,", "start": 10.6, "end": 11.2},
    {"word": "olha", "start": 11.3, "end": 11.6},
    {"word": "isso.", "start": 11.6, "end": 12.0},
    {"word": "agora", "start": 12.5, "end": 12.9},
    {"word": "vai.", "start": 12.9, "end": 13.3},
]


def test_tempo_ass_formato():
    assert _tempo_ass(0) == "0:00:00.00"
    assert _tempo_ass(83.75) == "0:01:23.75"
    assert _tempo_ass(3661.2) == "1:01:01.20"


def test_eventos_relativos_ao_inicio_do_clipe():
    eventos = gerar_eventos(PALAVRAS, inicio=10.0, fim=13.5)
    assert eventos
    for ev in eventos:
        assert ev.startswith("Dialogue: 0,0:00:0")
    assert all("{\\k" in ev for ev in eventos)
    # palavras fora da janela não entram
    assert not any("fora" in ev for ev in gerar_eventos(PALAVRAS, 10.0, 11.0)
                   if "agora" in ev)


def test_quebra_de_linha_por_pontuacao():
    eventos = gerar_eventos(PALAVRAS, 10.0, 13.5)
    assert len(eventos) >= 2  # "isso." encerra uma linha


def test_ass_completo(tmp_path):
    dest = escrever_ass(PALAVRAS, 10.0, 13.5, tmp_path / "captions.ass")
    conteudo = dest.read_text(encoding="utf-8")
    assert "[V4+ Styles]" in conteudo
    assert "PlayResX: 1080" in conteudo
    assert re.search(r"Dialogue: 0,0:00:00\.00,", conteudo)
