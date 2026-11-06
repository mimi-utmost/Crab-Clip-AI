# Escolha de modelos — Fase 0 (2026-11-06)

Decisões tomadas pelo usuário com base nos benchmarks medidos no hardware alvo
(Ryzen 5 5500 / RX 7600 8 GB / 16 GB RAM). Evidências: `raw/20261106-025014-llama.json`,
`raw/20261106-030425-whisper.json`, `raw/20261106-020234-ffmpeg.json`.

## Decidido

| Componente | Escolha | Base |
|---|---|---|
| Backend de IA (LLM) | **Vulkan** | ~10× mais rápido que CPU na RX 7600 (tg128) |
| LLM de análise semântica | **Qwen2.5-7B-Instruct Q4_K_M** | 56.7 t/s tg / 924.7 t/s pp em Vulkan; empate de velocidade com Llama-8B com boa reputação em PT |
| Transcrição | **whisper.cpp large-v3-turbo (CPU)** | RTF 0.547 — mais rápido que o medium (0.598) e de família superior |
| Encode de vídeo | **AMD AMF (h264_amf)** | 319 fps vs 144 fps do x264 medium em 1080p60; render vertical 9:16 em ~2.2× o tempo real |

## Pendências conhecidas

- Pico de VRAM do llama-bench não foi capturado pelo amostrador (limitação do
  contador via PowerShell). Validar consumo real na primeira execução do pipeline.
- whisper.cpp em Vulkan não foi medido (sem build pré-compilada; exige cmake +
  Vulkan SDK). Adiado por decisão do usuário — CPU com RTF 0.55 atende o MVP.
- Qualidade (WER do whisper, adequação do LLM ao PT) exige checagem manual sobre
  os artefatos gerados na primeira execução real do pipeline.

## Limpeza aplicada

Candidatos perdedores removidos do disco (~7 GB): Llama-3.1-8B, Qwen2.5-3B,
whisper medium. Permanecem apenas os escolhidos em `models/candidates/`
(4.4 GB LLM + 1.6 GB whisper).
