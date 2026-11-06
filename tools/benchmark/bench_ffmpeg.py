"""Benchmark de codificação de vídeo: AMD AMF (GPU) vs x264 (CPU).

Testa encode direto 1080p60 e o caminho real do pipeline (crop 9:16 + scale),
sobre um clipe sintético gerado localmente. Se o ffmpeg não estiver no PATH nem
configurado, baixa uma build portátil para tools/benchmark/.work/ (não instala
nada no sistema).
"""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from common import WORK_DIR, BenchSkip, download, find_exe, load_config, run_timed, save_results

FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def _ffmpeg_cacheado() -> Path | None:
    base = WORK_DIR / "ffmpeg"
    if base.is_dir():
        for exe in sorted(base.rglob("ffmpeg.exe")):
            return exe
    return None


def garantir_ffmpeg(exe_cfg: str | None = None) -> tuple[str, str]:
    """Retorna (caminho_do_ffmpeg, origem). Prefere config, depois PATH, depois cache/download local."""
    if exe := find_exe(exe_cfg):
        return exe, "config.json"
    if exe := find_exe("ffmpeg"):
        return exe, "PATH do sistema"
    if exe := _ffmpeg_cacheado():
        return str(exe), "cache local do projeto"
    zip_path = download(FFMPEG_URL, WORK_DIR / "ffmpeg.zip", label="ffmpeg (build essentials, gyan.dev)")
    dest = WORK_DIR / "ffmpeg"
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)
    zip_path.unlink()
    exe = _ffmpeg_cacheado()
    if not exe:
        raise BenchSkip("download do ffmpeg concluído, mas ffmpeg.exe não foi encontrado no pacote")
    return str(exe), "baixado para o projeto"


def localizar_ffprobe(ffmpeg: str) -> str | None:
    candidato = Path(ffmpeg).with_name("ffprobe.exe")
    if candidato.is_file():
        return str(candidato)
    return find_exe("ffprobe")


def _garantir_amostra(ffmpeg: str, duracao: int, fps: int) -> Path:
    clip = WORK_DIR / f"amostra-1080p{fps}-{duracao}s.mp4"
    if clip.exists():
        return clip
    print(f"gerando clipe sintético de teste ({duracao}s, 1080p{fps})...")
    r = run_timed([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                   "-f", "lavfi", "-i", f"testsrc2=size=1920x1080:rate={fps}:duration={duracao}",
                   "-f", "lavfi", "-i", f"sine=frequency=440:duration={duracao}",
                   "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                   "-c:a", "aac", "-shortest", str(clip)], timeout=600)
    if r.returncode != 0 or not clip.exists():
        raise BenchSkip(f"falha ao gerar clipe de teste: {r.stderr.strip()[-400:]}")
    return clip


def _testes() -> list[tuple[str, list[str]]]:
    vertical = ["-vf", "crop=608:1080,scale=1080:1920,setsar=1"]
    amf = ["-c:v", "h264_amf", "-quality", "balanced", "-rc", "cbr", "-b:v", "8M", "-pix_fmt", "yuv420p"]
    x264 = ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p"]
    return [
        ("amf_h264_1080p60", amf),
        ("x264_medium_1080p60", x264),
        ("amf_h264_vertical_9x16", vertical + amf),
        ("x264_medium_vertical_9x16", vertical + x264),
    ]


def run(cfg: dict) -> dict:
    ff_cfg = cfg.get("ffmpeg", {})
    duracao = int(ff_cfg.get("duration_s", 60))
    fps = int(ff_cfg.get("fps", 60))
    ffmpeg, origem = garantir_ffmpeg(ff_cfg.get("exe"))
    clip = _garantir_amostra(ffmpeg, duracao, fps)
    quadros = duracao * fps
    resultados = []
    for nome, args in _testes():
        out = WORK_DIR / f"saida-{nome}.mp4"
        r = run_timed([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                       "-i", str(clip), "-an", *args, str(out)],
                      sample_vram="amf" in nome, timeout=600)
        entrada: dict = {"teste": nome, "disponivel": r.returncode == 0}
        if r.returncode == 0 and out.exists():
            entrada.update({
                "tempo_s": round(r.wall_s, 2),
                "fps_medio": round(quadros / r.wall_s, 1),
                "tamanho_bytes": out.stat().st_size,
                "pico_vram_mb": r.peak_vram_mb,
            })
        else:
            entrada["erro"] = r.stderr.strip()[-400:] or f"exit {r.returncode}"
        out.unlink(missing_ok=True)
        resultados.append(entrada)
        status = f"{entrada.get('fps_medio')} fps" if entrada["disponivel"] else "indisponível"
        print(f"  {nome}: {status}")
    return {
        "origem_ffmpeg": origem,
        "amostra": clip.name,
        "quadros": quadros,
        "metodo_fps": "quadros_conhecidos / tempo_de_parede",
        "testes": resultados,
    }


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    payload = run(load_config())
    path = save_results("ffmpeg", payload)
    print(f"resultados salvos em {path}")


if __name__ == "__main__":
    main()
