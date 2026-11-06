# Relatório de benchmark — 2026-11-06 02:50

## Sistema

```json
{
  "coletado_em": "2026-11-06T05:50:17.302270+00:00",
  "os": "Windows 10.0.26300",
  "python": "3.14.2",
  "cpu": "AMD Ryzen 5 5500",
  "ram_gb": 15.9,
  "gpus": [
    {
      "Name": "AMD Radeon RX 7600",
      "DriverVersion": "32.0.32015.7029"
    }
  ]
}
```

## whisper

| Backend | Modelo | Disponível | Execuções (s) | Mediana (s) | RTF | Pico VRAM (MB) | Erro |
|---|---|---|---|---|---|---|---|
| cpu | medium | True | [184.05, 179.08] | 181.56 | 0.598 | — | — |
| cpu | large-v3-turbo | True | [164.75, 167.41] | 166.08 | 0.547 | — | — |

Amostra: `D:\Sons\PORQUE DAREI UM TEMPO COM AION 2 E O QUE VEM POR AÍ_0_303.mp3` → `D:\Workspace\CrabClipAi\tools\benchmark\.work\PORQUE DAREI UM TEMPO COM AION 2 E O QUE VEM POR AÍ_0_303-16k.wav` (303.5 s). RTF = tempo_de_parede / duracao_do_audio; qualidade (WER) exige checagem manual.

_Dados brutos: `docs\benchmarks\raw\20261106-030425-whisper.json`_
