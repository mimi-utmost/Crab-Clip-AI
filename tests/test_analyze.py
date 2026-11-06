from engine.stages.analyze import extrair_json, formatar_bloco, janelar


def test_janelar_com_sobreposicao():
    segs = [{"start": float(i * 10), "end": float(i * 10 + 9), "text": f"s{i}"}
            for i in range(150)]  # 1500 s
    janelas = janelar(segs, duracao_s=1500, bloco_s=600, sobreposicao_s=60)
    assert len(janelas) == 3
    assert janelas[0][0]["start"] == 0.0
    assert janelas[0][-1]["end"] <= 609
    # sobreposição: segunda janela começa antes de 600
    assert janelas[1][0]["start"] < 600
    assert janelas[-1][-1]["end"] == 1499.0


def test_janelar_video_curto_uma_janela():
    segs = [{"start": 0.0, "end": 100.0, "text": "oi"}]
    assert len(janelar(segs, duracao_s=100)) == 1


def test_formatar_bloco():
    texto = formatar_bloco([{"start": 65.0, "end": 70.0, "text": "olá"}])
    assert texto == "[01:05] olá"


def test_extrair_json_array_direto():
    saida = extrair_json('[{"start": 10, "end": 40, "score": 9, "titulo": "x", "motivo": "y"}]')
    assert saida == [{"start": 10.0, "end": 40.0, "score": 9.0, "titulo": "x", "motivo": "y"}]


def test_extrair_json_embrulhado_em_objeto():
    saida = extrair_json('{"momentos": [{"start": 5, "end": 30, "score": 7}]}')
    assert len(saida) == 1
    assert saida[0]["start"] == 5.0


def test_extrair_json_com_prosa_em_volta():
    conteudo = 'Aqui estão os momentos:\n[{"start": 1, "end": 20, "score": 8}]\nFim.'
    assert extrair_json(conteudo)[0]["end"] == 20.0


def test_extrair_json_lixo_retorna_vazio():
    assert extrair_json("não sei responder") == []
    assert extrair_json('[{"start": "abc"}]') == []
    assert extrair_json('[{"start": 50, "end": 10}]') == []  # fim antes do início
