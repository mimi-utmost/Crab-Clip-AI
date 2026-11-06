"""Benchmark de transcrição: whisper.cpp CPU vs Vulkan, modelos candidatos.

Mede velocidade (RTF = tempo de parede / duração do áudio) sobre um áudio real
configurado pelo usuário. Qualidade (WER) não é medida aqui — exige checagem
manual posterior. Após decidir o modelo, rode com --choose para manter apenas
o vencedor instalado.
"""
from __future__ import annotations

import argparse
import contextlib
import statistics
import wave
import zipfile
from pathlib import Path

from bench_ffmpeg import garantir_ffmpeg, localizar_ffprobe
from bench_llama import _release_com_binarios
from common import (MODELS_DIR, WORK_DIR, BenchSkip, download, escolher_modelo,
                    find_exe, load_config, registrar_modelo, run_timed, save_results)

MODELOS_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{nome}.bin"
WHISPER_RELEASE_API = "https://api.github.com/repos/ggml-org/whisper.cpp/releases?per_page=5"
CANDIDATOS_DIR = MODELS_DIR / "candidates" / "whisper"
PROPOSITO = "transcricao"

SETUP = """\
whisper.cpp não configurado. Para habilitar este benchmark:
  1. CPU: deixe "whisper.auto_download_binaries": true (baixa whisper-bin-x64.zip
     do release oficial) ou aponte "whisper.cpu_exe" para um whisper-cli.exe
  2. Vulkan: não há build pré-compilada; compile a partir do código-fonte com
     `cmake -B build -DGGML_VULKAN=1` e aponte "whisper.vulkan_exe"
  3. Grave um áudio de amostra real (~5 min de live em PT, com fala e ruído típicos)
     e aponte "whisper.sample_audio" para ele
  Edite tools/benchmark/config.json (referência: config.example.json)."""


def _cli_cacheado() -> Path | None:
    base = WORK_DIR / "whisper" / "cpu"
    if base.is_dir():
        for exe in sorted(base.rglob("whisper-cli.exe")):
            return exe
    return None


def _garantir_binarios(w: dict) -> dict[str, str]:
    backends: dict[str, str] = {}
    if exe := find_exe(w.get("cpu_exe")):
        backends["cpu"] = exe
    if exe := find_exe(w.get("vulkan_exe")):
        backends["vulkan"] = exe
    if "cpu" not in backends and w.get("auto_download_binaries", True):
        exe = _cli_cacheado()
        if not exe:
            tag, assets = _release_com_binarios(["whisper-bin-x64.zip"],
                                                 WHISPER_RELEASE_API)
            zip_path = download(assets["whisper-bin-x64.zip"],
                                WORK_DIR / "whisper" / "whisper-bin-x64.zip",
                                label=f"whisper.cpp {tag} (CPU)")
            dest = WORK_DIR / "whisper" / "cpu"
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(dest)
            zip_path.unlink()
            exe = _cli_cacheado()
        if exe:
            backends["cpu"] = str(exe)
    return backends


def _garantir_wav(amostra: str, ffmpeg: str) -> Path:
    """O whisper-cli exige WAV 16 kHz mono; converte se necessário (cache em .work)."""
    src = Path(amostra)
    if src.suffix.lower() == ".wav":
        return src
    dest = WORK_DIR / (src.stem + "-16k.wav")
    if dest.exists():
        return dest
    print("convertendo amostra para WAV 16 kHz mono...")
    r = run_timed([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
                   "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(dest)], timeout=600)
    if r.returncode != 0 or not dest.exists():
        raise BenchSkip(f"falha ao converter amostra: {r.stderr.strip()[-400:]}")
    return dest


def _duracao_audio(caminho: Path, ffprobe: str | None) -> float:
    if caminho.suffix.lower() == ".wav":
        with contextlib.closing(wave.open(str(caminho), "rb")) as w:
            return w.getnframes() / w.getframerate()
    if ffprobe:
        r = run_timed([ffprobe, "-v", "error", "-show_entries", "format=duration",
                       "-of", "csv=p=0", str(caminho)])
        try:
            return float(r.stdout.strip())
        except ValueError:
            pass
    raise BenchSkip("não foi possível determinar a duração do áudio "
                    "(use .wav PCM ou disponibilize o ffprobe)")


def run(cfg: dict) -> dict:
    w = cfg.get("whisper", {})
    backends = _garantir_binarios(w)
    if not backends:
        raise BenchSkip(SETUP)
    amostra = w.get("sample_audio")
    if not amostra or not Path(amostra).is_file():
        raise BenchSkip("configure whisper.sample_audio com um áudio real "
                        "(ver config.example.json)")
    ffmpeg, _ = garantir_ffmpeg(cfg.get("ffmpeg", {}).get("exe"))
    amostra_wav = _garantir_wav(amostra, ffmpeg)
    duracao = _duracao_audio(amostra_wav, localizar_ffprobe(ffmpeg))

    auto = bool(w.get("auto_download_models", True))
    modelos: dict[str, Path] = {}
    for nome in w.get("models", ["medium", "large-v3-turbo"]):
        destino = CANDIDATOS_DIR / f"ggml-{nome}.bin"
        if not destino.exists():
            if not auto:
                raise BenchSkip(f"modelo ausente e auto_download desligado: {destino}")
            download(MODELOS_URL.format(nome=nome), destino, label=f"whisper {nome}")
        registrar_modelo(f"whisper-{nome}", destino, PROPOSITO)
        modelos[nome] = destino

    threads = str(w.get("threads", 12))
    lang = str(w.get("language", "auto"))
    resultados = []
    for backend, exe in backends.items():
        for nome, modelo in modelos.items():
            paredes: list[float] = []
            pico: float | None = None
            erro: str | None = None
            for _ in range(2):
                r = run_timed([exe, "-m", str(modelo), "-f", str(amostra_wav),
                               "-l", lang, "-t", threads, "-owts"],
                              sample_vram=(backend == "vulkan"), timeout=3600)
                if r.returncode != 0:
                    erro = r.stderr.strip()[-400:] or f"exit {r.returncode}"
                    paredes = []
                    break
                paredes.append(round(r.wall_s, 2))
                pico = r.peak_vram_mb or pico
            if paredes:
                mediana = statistics.median(paredes)
                resultados.append({
                    "backend": backend, "modelo": nome, "disponivel": True,
                    "execucoes_s": paredes, "mediana_s": round(mediana, 2),
                    "rtf": round(mediana / duracao, 3), "pico_vram_mb": pico,
                })
                print(f"  whisper/{backend}/{nome}: RTF {round(mediana / duracao, 3)}")
            else:
                resultados.append({"backend": backend, "modelo": nome,
                                   "disponivel": False, "erro": erro})
                print(f"  whisper/{backend}/{nome}: indisponível")
    return {
        "amostra": amostra,
        "amostra_wav": str(amostra_wav),
        "duracao_audio_s": round(duracao, 1),
        "observacao": "RTF = tempo_de_parede / duracao_do_audio; qualidade (WER) exige checagem manual",
        "resultados": resultados,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--choose", metavar="MODELO",
                    help="marca o modelo vencedor (ex.: large-v3-turbo) e remove os demais candidatos")
    args = ap.parse_args()
    if args.choose:
        removidos = escolher_modelo(f"whisper-{args.choose}", PROPOSITO)
        for p in removidos:
            print(f"removido: {p}")
        print(f"modelo escolhido: whisper-{args.choose}")
        return
    payload = run(load_config())
    path = save_results("whisper", payload)
    print(f"resultados salvos em {path}")


if __name__ == "__main__":
    main()
