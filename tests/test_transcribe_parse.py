import json

from engine.stages.transcribe import palavras_de_tokens, parsear_saida_whisper

# Formato real observado do whisper-cli -ojf (build b5454, large-v3-turbo)
AMOSTRA = {
    "transcription": [
        {
            "timestamps": {"from": "00:00:00,000", "to": "00:00:02,700"},
            "offsets": {"from": 0, "to": 2700},
            "text": " Salve, salve família!",
            "tokens": [
                {"text": "[_BEG_]", "offsets": {"from": 0, "to": 0}, "p": 0.51},
                {"text": " Sal", "offsets": {"from": 50, "to": 150}, "p": 0.80},
                {"text": "ve", "offsets": {"from": 250, "to": 250}, "p": 0.99},
                {"text": ",", "offsets": {"from": 280, "to": 350}, "p": 0.66},
                {"text": " sal", "offsets": {"from": 350, "to": 500}, "p": 0.99},
                {"text": "ve", "offsets": {"from": 500, "to": 600}, "p": 0.99},
                {"text": " família", "offsets": {"from": 620, "to": 980}, "p": 0.97},
                {"text": "!", "offsets": {"from": 980, "to": 1020}, "p": 0.91},
            ],
        }
    ]
}


def test_agrupa_tokens_em_palavras():
    palavras = palavras_de_tokens(AMOSTRA["transcription"][0]["tokens"])
    assert [p["word"] for p in palavras] == ["Salve,", "salve", "família!"]
    assert palavras[0]["start"] == 0.05
    assert palavras[0]["end"] == 0.35
    assert palavras[-1]["end"] == 1.02


def test_parser_normaliza_segmento():
    parsed = parsear_saida_whisper(AMOSTRA)
    seg = parsed["segments"][0]
    assert seg["start"] == 0.0
    assert seg["end"] == 2.7
    assert seg["text"] == "Salve, salve família!"
    assert 0.8 < seg["confidence"] < 1.0
    assert len(seg["words"]) == 3
    assert json.dumps(parsed)  # serializável


def test_parser_sem_tokens_retorna_palavras_vazias():
    dados = {"transcription": [{"offsets": {"from": 0, "to": 100}, "text": "x"}]}
    parsed = parsear_saida_whisper(dados)
    assert parsed["segments"][0]["words"] == []
    assert parsed["segments"][0]["confidence"] is None
