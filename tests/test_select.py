from engine.stages.select import dedup, selecionar

PALAVRAS = [{"word": f"p{i}", "start": float(i), "end": float(i) + 0.8}
            for i in range(300)]


def test_dedup_sobreposicao_fica_o_maior_score():
    candidatos = [
        {"start": 10, "end": 50, "score": 6.0},
        {"start": 15, "end": 55, "score": 9.0},
        {"start": 200, "end": 240, "score": 5.0},
    ]
    mantidos = dedup(candidatos)
    assert len(mantidos) == 2
    assert any(m["start"] == 15 for m in mantidos)


def test_clamp_em_60s_e_snap_em_palavras():
    candidatos = [{"start": 10.3, "end": 200.0, "score": 9.0,
                   "titulo": "t", "motivo": "m"}]
    sel = selecionar(candidatos, PALAVRAS, max_s=60.0, min_s=5.0, top_n=10)
    assert len(sel) == 1
    m = sel[0]
    assert m["start"] == 10.0  # snap para o início da palavra
    assert m["end"] - m["start"] <= 60.0


def test_descarta_curto_demais_apos_snap():
    candidatos = [{"start": 10.0, "end": 12.0, "score": 9.0, "titulo": "", "motivo": ""}]
    assert selecionar(candidatos, PALAVRAS, 60.0, min_s=5.0, top_n=10) == []


def test_ranking_top_n():
    candidatos = [{"start": float(i * 100), "end": float(i * 100) + 30,
                   "score": float(i), "titulo": str(i), "motivo": ""}
                  for i in range(5)]
    sel = selecionar(candidatos, PALAVRAS + [{"word": "z", "start": 499.0, "end": 499.8}],
                     60.0, 5.0, top_n=3)
    assert [m["score"] for m in sel] == [4.0, 3.0, 2.0]
