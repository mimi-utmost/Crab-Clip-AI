# Crab Clip AI

Aplicação desktop open source para Windows que processa **localmente** gravações
de lives (Twitch/Kick), identifica momentos interessantes com IA e gera cortes
verticais legendados prontos para TikTok, YouTube Shorts e Instagram Reels —
com revisão humana antes da exportação.

Sem SaaS, sem nuvem, sem APIs comerciais pagas.

## Status

**Fase 1 — engine funcional validada.** O pipeline completo (vídeo → transcrição
→ análise semântica → cortes 9:16 legendados via AMF) já roda ponta a ponta no
hardware alvo. Modelos e backends foram escolhidos por benchmark real — ver
`docs/benchmarks/escolha-de-modelos.md`. Próxima fase: interface Tauri 2 + React.

## Estrutura

```
engine/             motor de processamento (Python stdlib; ver seção abaixo)
tests/              testes unitários do engine (pytest, dev-only)
tools/benchmark/    harness de benchmark (Python stdlib apenas)
docs/benchmarks/    relatórios, dados brutos e decisões (evidência versionada)
models/             modelos locais (não versionados; só o escolhido permanece)
work/               artefatos por vídeo + engine.db (não versionado)
app/                (futuro) aplicação Tauri 2 + React/TypeScript
```

## Rodando o engine

Requer que a fase 0 tenha sido executada (binários em `tools/benchmark/.work/`
e modelos escolhidos em `models/manifest.json`).

```bash
py -3 -m engine.cli new "D:\caminho\live.mp4"   # registra o vídeo
py -3 -m engine.cli run --id 1                  # roda o pipeline completo
py -3 -m engine.cli run --id 1 --from render    # retoma de uma etapa
py -3 -m engine.cli status                      # estado das etapas por vídeo
py -3 -m engine.cli clips                       # clipes gerados
```

Etapas: `ingest` → `audio` → `transcribe` (whisper.cpp + VAD) → `analyze`
(Qwen2.5-7B em Vulkan) → `select` (dedup, teto de 60 s, bordas em fim de
palavra) → `render` (crop 9:16 + karaokê ASS + h264_amf, fallback x264).
Os clipes saem em `work/<id>/clips/`.

Testes:

```bash
py -3 -m pip install -e ".[dev]"   # ou: py -3 -m pip install pytest
py -3 -m pytest tests/
```

## Rodando os benchmarks

Requer Python 3.10+ (`py -3` no Windows). Nenhuma dependência externa.

```bash
py -3 tools/benchmark/run_all.py                # roda tudo que estiver configurado
py -3 tools/benchmark/run_all.py --only ffmpeg  # só encode AMF vs x264
```

- **ffmpeg**: funciona sem configuração — baixa uma build portátil para
  `tools/benchmark/.work/` (não instala nada no sistema).
- **whisper** e **llama**: copie `tools/benchmark/config.example.json` para
  `tools/benchmark/config.json` e ajuste os caminhos. O llama baixa binários e
  modelos candidatos automaticamente; o whisper exige os binários do
  whisper.cpp (instruções no erro de pré-requisito) e um áudio de amostra real.

Após decidir os modelos vencedores:

```bash
py -3 tools/benchmark/bench_whisper.py --choose large-v3-turbo
py -3 tools/benchmark/bench_llama.py --choose qwen2.5-7b-instruct-q4_k_m
```

Os candidatos perdedores são apagados — apenas o escolhido permanece em `models/`.

Relatórios saem em `docs/benchmarks/report-latest.md`, com JSON bruto em
`docs/benchmarks/raw/`.
