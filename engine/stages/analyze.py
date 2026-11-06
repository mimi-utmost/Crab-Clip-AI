"""Etapa analyze: Qwen2.5-7B via llama-server (Vulkan) identifica momentos.

Ciclo de vida da VRAM: o server sobe aqui, roda todos os blocos e é derrubado
antes do render — nunca coexistindo com outro modelo de IA. Transcrições longas
são analisadas em janelas de ~10 min com 1 min de sobreposição; os tempos
pedidos ao LLM são absolutos do vídeo para evitar erros de offset.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from engine.config import Config
from engine.db import DB

BLOCO_S = 600.0
SOBREPOSICAO_S = 60.0
MAX_MOMENTOS_BLOCO = 5

PROMPT_SISTEMA = """\
Você é um editor de cortes de lives para TikTok, YouTube Shorts e Reels.
Analise a transcrição de um trecho de live e identifique os momentos que
renderiam os melhores clipes curtos verticais: engraçados, surpreendentes,
reações fortes, explicações marcantes, histórias com começo, meio e fim.

Regras:
- Cada momento deve fazer sentido sozinho, com contexto suficiente.
- Duração mínima 10 segundos, máxima 60 segundos (nunca exceda 60).
- Use os tempos absolutos do vídeo, em segundos, como nas linhas [mm:ss].
- Sem sobreposição entre momentos. No máximo {max_momentos} momentos.
- Responda APENAS com JSON válido, um array de objetos:
  [{{"start": <segundos>, "end": <segundos>, "score": <0 a 10>,
     "titulo": "<título curto do clipe>", "motivo": "<por que rende>"}}]
- Se não houver momento que valha a pena, responda []."""


def janelar(segmentos: list[dict], duracao_s: float, bloco_s: float = BLOCO_S,
            sobreposicao_s: float = SOBREPOSICAO_S) -> list[list[dict]]:
    """Divide os segmentos em janelas com sobreposição, sem cortar segmento."""
    janelas: list[list[dict]] = []
    inicio = 0.0
    while inicio < duracao_s:
        fim = inicio + bloco_s
        bloco = [s for s in segmentos if s["end"] > inicio and s["start"] < fim]
        if bloco:
            janelas.append(bloco)
        if fim >= duracao_s:
            break
        inicio = fim - sobreposicao_s
    return janelas


def formatar_bloco(bloco: list[dict]) -> str:
    linhas = []
    for s in bloco:
        mm, ss = divmod(int(s["start"]), 60)
        linhas.append(f"[{mm:02d}:{ss:02d}] {s['text']}")
    return "\n".join(linhas)


def extrair_json(conteudo: str) -> list[dict]:
    """Parse tolerante: aceita array direto, objeto embrulhando um array,
    ou o primeiro array JSON encontrado no texto."""
    conteudo = conteudo.strip()
    dados = None
    try:
        dados = json.loads(conteudo)
    except json.JSONDecodeError:
        pass
    if isinstance(dados, dict):
        dados = next((v for v in dados.values() if isinstance(v, list)), None)
    if not isinstance(dados, list):
        match = re.search(r"\[.*\]", conteudo, re.DOTALL)
        if match:
            try:
                dados = json.loads(match.group(0))
            except json.JSONDecodeError:
                dados = None
    if not isinstance(dados, list):
        return []
    if not isinstance(dados, list):
        return []
    momentos = []
    for m in dados:
        try:
            inicio, fim = float(m["start"]), float(m["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if fim <= inicio:
            continue
        momentos.append({
            "start": inicio,
            "end": fim,
            "score": float(m.get("score", 5)),
            "titulo": str(m.get("titulo", ""))[:120],
            "motivo": str(m.get("motivo", ""))[:500],
        })
    return momentos


class LlamaServer:
    """Sobe o llama-server (Vulkan), espera o /health e derruba ao sair."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.base = f"http://{cfg.llm_host}:{cfg.llm_port}"
        self._proc: subprocess.Popen | None = None

    def __enter__(self) -> "LlamaServer":
        self._proc = subprocess.Popen(
            [str(self.cfg.llama_server), "-m", str(self.cfg.llm_model),
             "-ngl", "999", "-c", str(self.cfg.llm_ctx),
             "--host", self.cfg.llm_host, "--port", str(self.cfg.llm_port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        prazo = time.time() + 300
        while time.time() < prazo:
            if self._proc.poll() is not None:
                raise RuntimeError("llama-server morreu ao iniciar "
                                   f"(exit {self._proc.returncode})")
            try:
                with urllib.request.urlopen(self.base + "/health", timeout=5) as r:
                    if r.status == 200:
                        return self
            except (urllib.error.URLError, OSError):
                time.sleep(1)
        self.__exit__(None, None, None)
        raise RuntimeError("llama-server não respondeu ao /health em 300 s")

    def __exit__(self, *exc: object) -> None:
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    def analisar_bloco(self, texto_bloco: str) -> list[dict]:
        payload = {
            "messages": [
                {"role": "system",
                 "content": PROMPT_SISTEMA.format(max_momentos=MAX_MOMENTOS_BLOCO)},
                {"role": "user",
                 "content": f"Transcrição do trecho (tempos absolutos [mm:ss]):\n\n{texto_bloco}"},
            ],
            "temperature": 0.2,
            "max_tokens": 1024,
            "response_format": {"type": "json_object"},
        }
        req = urllib.request.Request(
            self.base + "/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
        conteudo = dados["choices"][0]["message"]["content"]
        return extrair_json(conteudo)


def run_stage(cfg: Config, db: DB, video_id: int) -> None:
    video_dir = cfg.video_dir(video_id)
    dest = video_dir / "momentos-candidatos.json"
    if dest.exists():
        return
    transcript = json.loads((video_dir / "transcript.json").read_text(encoding="utf-8"))
    video = db.get_video(video_id)
    duracao = video["duration_s"] or (transcript["segments"][-1]["end"] if transcript["segments"] else 0)
    janelas = janelar(transcript["segments"], duracao)
    candidatos: list[dict] = []
    with LlamaServer(cfg) as server:
        for i, bloco in enumerate(janelas, 1):
            print(f"  analyze: bloco {i}/{len(janelas)} "
                  f"({bloco[0]['start']:.0f}s–{bloco[-1]['end']:.0f}s)")
            try:
                momentos = server.analisar_bloco(formatar_bloco(bloco))
            except (urllib.error.URLError, OSError, KeyError, json.JSONDecodeError) as exc:
                print(f"  analyze: bloco {i} falhou ({exc}); continuando")
                continue
            candidatos.extend(momentos)
    dest.write_text(json.dumps(candidatos, ensure_ascii=False, indent=1),
                    encoding="utf-8")
