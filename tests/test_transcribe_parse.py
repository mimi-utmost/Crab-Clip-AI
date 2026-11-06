import json

from engine.stages.transcribe import parsear_saida_whisper

AMOSTRA = {
    "transcription": [
        {
            "offsets": {"from": 0, "to": 2400},
            "text": " e aí chat, beleza?",
            "words": [
                {"word": " e", "offsets": {"from": 0, "to": 300}},
                {"word": " aí", "offsets": {"from": 300, "to": 600}},
                {"word": " chat,", "offsets": {"from": 600, "to": 1100}},
                {"word": " beleza?", "offsets": {"from": 1100, "to": 2400}},
            ],
        },
        {
            "offsets": {"from": 2600, "to": 4200},
            "text": " hoje tem novidade.",
            "words": [
                {"word": " hoje", "offsets": {"from": 2600, "to": 3100}},
                {"word": " tem", "offsets": {"from": 3100, "to": 3400}},
                {"word": " novidade.", "offsets": {"from": 3400, "to": 4200}},
            ],
        },
    ]
}


def test_parser_normaliza_tempos_e_palavras():
    parsed = parsear_saida_whisper(AMOSTRA)
    segs = parsed["segments"]
    assert len(segs) == 2
    assert segs[0]["start"] == 0.0
    assert segs[0]["end"] == 2.4
    assert segs[0]["text"] == "e aí chat, beleza?"
    assert segs[0]["words"][0] == {"word": "e", "start": 0.0, "end": 0.3}
    assert segs[1]["words"][-1]["word"] == "novidade."
    assert json.dumps(parsed)  # serializável


def test_parser_ignora_palavras_vazias():
    dados = {"transcription": [{"offsets": {"from": 0, "to": 100}, "text": " x",
                                "words": [{"word": "  ", "offsets": {"from": 0, "to": 50}},
                                          {"word": " x", "offsets": {"from": 50, "to": 100}}]}]}
    parsed = parsear_saida_whisper(dados)
    assert [p["word"] for p in parsed["segments"][0]["words"]] == ["x"]
