"""Configuração do engine: localiza binários e modelos escolhidos na fase 0.

Fonte única de verdade para modelos: models/manifest.json (status "escolhido",
gravado pelo --choose do harness de benchmark). Binários ficam no cache local
tools/benchmark/.work — o mesmo usado nas medições, sem instalação global.
"""
from __future__ import annotations

import json
import shutil
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK_ROOT = ROOT / "work"
BENCH_WORK = ROOT / "tools" / "benchmark" / ".work"
MODELS_DIR = ROOT / "models"
MANIFEST_PATH = MODELS_DIR / "manifest.json"

VAD_URL = "https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v5.1.2.bin"
VAD_ARQUIVO = "ggml-silero-v5.1.2.bin"


class ConfigError(RuntimeError):
    pass


def _rglob(base: Path, nome: str) -> Path | None:
    if base.is_dir():
        for p in sorted(base.rglob(nome)):
            return p
    return None


def _manifest_escolhido(proposito: str) -> Path:
    if not MANIFEST_PATH.exists():
        raise ConfigError(f"manifest não encontrado: {MANIFEST_PATH} — rode a fase 0 (tools/benchmark)")
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for m in data["modelos"]:
        if m["proposito"] == proposito and m["status"] == "escolhido":
            caminho = Path(m["caminho"])
            if caminho.exists():
                return caminho
    raise ConfigError(f"nenhum modelo escolhido para '{proposito}' no manifest")


def _garantir_vad() -> Path | None:
    dest = MODELS_DIR / VAD_ARQUIVO
    if dest.exists():
        return dest
    try:
        req = urllib.request.Request(VAD_URL, headers={"User-Agent": "crab-clip-ai"})
        with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as fh:
            shutil.copyfileobj(resp, fh)
    except OSError:
        dest.unlink(missing_ok=True)
        return None
    return dest


@dataclass
class Config:
    ffmpeg: Path
    whisper_cli: Path
    llama_server: Path
    whisper_model: Path
    llm_model: Path
    ffprobe: Path | None = None
    vad_model: Path | None = None
    work_root: Path = WORK_ROOT
    db_path: Path = WORK_ROOT / "engine.db"
    llm_host: str = "127.0.0.1"
    llm_port: int = 8085
    llm_ctx: int = 8192
    whisper_threads: int = 12
    clip_max_s: float = 60.0
    clip_min_s: float = 5.0
    top_n: int = 10
    use_vad: bool = True

    @classmethod
    def load(cls) -> "Config":
        ffmpeg = _rglob(BENCH_WORK / "ffmpeg", "ffmpeg.exe") or shutil.which("ffmpeg")
        if not ffmpeg:
            raise ConfigError("ffmpeg não encontrado (nem em tools/benchmark/.work nem no PATH)")
        ffprobe = _rglob(BENCH_WORK / "ffmpeg", "ffprobe.exe") or shutil.which("ffprobe")
        whisper = _rglob(BENCH_WORK / "whisper", "whisper-cli.exe")
        if not whisper:
            raise ConfigError("whisper-cli não encontrado — rode tools/benchmark primeiro")
        server = _rglob(BENCH_WORK / "llama" / "vulkan", "llama-server.exe")
        if not server:
            raise ConfigError("llama-server (Vulkan) não encontrado — rode tools/benchmark primeiro")
        return cls(
            ffmpeg=Path(ffmpeg),
            ffprobe=Path(ffprobe) if ffprobe else None,
            whisper_cli=whisper,
            llama_server=server,
            whisper_model=_manifest_escolhido("transcricao"),
            llm_model=_manifest_escolhido("analise_semantica"),
            vad_model=_garantir_vad(),
        )

    def video_dir(self, video_id: int) -> Path:
        d = self.work_root / str(video_id)
        d.mkdir(parents=True, exist_ok=True)
        return d
