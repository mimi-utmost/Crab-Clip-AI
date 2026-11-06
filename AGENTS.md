# Crab Clip AI — Regras do projeto

Aplicação desktop open source (Windows) que processa gravações de lives localmente
e gera cortes verticais legendados para TikTok/Shorts/Reels. Uso pessoal, sem SaaS,
sem nuvem, sem APIs comerciais pagas.

## Restrições permanentes

- Execução local em primeiro lugar; nunca assumir disponibilidade de rede em runtime.
- **Não presumir compatibilidade de hardware sem testes.** Toda afirmação sobre
  Vulkan/AMF/VRAM precisa vir de medição real em `tools/benchmark/`.
- **Não inventar resultados de benchmark.** Se não rodou, não tem número.
- **Não implementar funcionalidades futuras antes de validar suas dependências.**
- Higiene de artefatos: manter instalados apenas os modelos escolhidos; candidatos
  perdedores são removidos (ver `--choose` nos scripts de benchmark).
- Não introduzir dependências desnecessárias. O harness de benchmark usa apenas a
  stdlib do Python; dependências novas precisam de justificativa.
- Arquitetura modular: interface (Tauri/React), backend e motor de processamento
  (Python) separados; processamento assíncrono.
- Hardware alvo: Ryzen 5 5500, RX 7600 8 GB, 16 GB RAM. VRAM é o recurso mais
  escasso — modelos de IA são carregados sequencialmente, nunca todos juntos.

## Convenções

- Documentação e mensagens em português (PT-BR).
- Commits em inglês, mensagens curtas no imperativo.
- Resultados de benchmark são evidência: JSON bruto em `docs/benchmarks/raw/`
  é versionado junto com o relatório.
- Fixtures de teste para parsers de saída externa (whisper, ffmpeg, llama)
  devem ser capturadas de uma execução real — nunca escritas de cabeça.
  Ver `gotchas` na memória do projeto (ex.: word timestamps do whisper.cpp).

## Fluxo de branches

- `develop`: todo trabalho em desenvolvimento é commitado e enviado aqui.
- `main`: só recebe o que o usuário aprovar explicitamente. Nunca commitar ou
  fazer merge direto na `main` sem aprovação.
