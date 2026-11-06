# Crab Clip AI

Aplicação desktop open source para Windows que processa **localmente** gravações
de lives (Twitch/Kick), identifica momentos interessantes com IA e gera cortes
verticais legendados prontos para TikTok, YouTube Shorts e Instagram Reels —
com revisão humana antes da exportação.

Sem SaaS, sem nuvem, sem APIs comerciais pagas.

## Status

**Fase 0 — validação de hardware.** Antes de qualquer pipeline, medimos o que o
hardware alvo (Ryzen 5 5500 + RX 7600 8 GB) realmente entrega com Vulkan e AMF.
Nenhum número é assumido: só entra na documentação o que foi medido em
`tools/benchmark/`.

## Estrutura

```
tools/benchmark/    harness de benchmark (Python stdlib apenas)
docs/benchmarks/    relatórios e dados brutos (evidência versionada)
models/             modelos locais (não versionados; só o escolhido permanece)
app/                (futuro) aplicação Tauri 2 + React/TypeScript
engine/             (futuro) motor de processamento em Python
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
