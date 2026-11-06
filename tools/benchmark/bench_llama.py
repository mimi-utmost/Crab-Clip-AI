"""Benchmark do LLM de análise semântica: llama.cpp CPU vs Vulkan via llama-bench.

Mede apenas velocidade (prompt processing pp512 e geração tg128, em tokens/s).
Adequação ao português exige avaliação qualitativa posterior — não é medida aqui.
Binários do llama.cpp são baixados do release oficial (ggml-org/llama.cpp) para
tools/benchmark/.work/. Após decidir o modelo, rode com --choose para manter
apenas o vencedor instalado.
"""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

from common import (MODELS_DIR, WORK_DIR, BenchSkip, download, escolher_modelo,
                    fetch_json, find_exe, load_config, registrar_modelo,
                    run_timed, save_results)

RELEASE_API = "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=15"
CANDIDATOS_DIR = MODELS_DIR / "candidates" / "llama"
PROPOSITO = "analise_semantica"

MODELOS_PADRAO = [
    {"nome": "qwen2.5-7b-instruct-q4_k_m",
     "base_url": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/",
     "arquivos": ["qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf",
                  "qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf"]},
    {"nome": "llama-3.1-8b-instruct-q4_k_m",
     "base_url": "https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/",
     "arquivos": ["Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"]},
    {"nome": "qwen2.5-3b-instruct-q4_k_m",
     "base_url": "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/",
     "arquivos": ["qwen2.5-3b-instruct-q4_k_m.gguf"]},
]

SETUP = """\
llama-bench não encontrado. Opções:
  1. Deixe "llama.auto_download_binaries": true no config.json (baixa os zips
     win-cpu-x64 e win-vulkan-x64 do release oficial para tools/benchmark/.work/)
  2. Ou aponte "llama.cpu_bench_exe" e "llama.vulkan_bench_exe" para binários
     llama-bench.exe já existentes."""


def _release_com_binarios(alvos, releases_url: str = RELEASE_API) -> tuple[str, dict[str, str]]:
    """Retorna (tag, {nome: url}) do release mais recente que tenha os zips procurados.

    O /releases/latest desses projetos ggml-org aponta para um meta-release sem
    binários; os zips vivem nos releases de build (tags bNNNN).
    """
    alvos = list(alvos)
    for release in fetch_json(releases_url):
        assets = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}
        if any(alvo in n for alvo in alvos for n in assets if n.endswith(".zip")):
            return release.get("tag_name", "?"), assets
    raise BenchSkip(f"nenhum release recente com os binários procurados ({', '.join(alvos)})")


def _bench_exe_cacheado(backend: str) -> Path | None:
    base = WORK_DIR / "llama" / backend
    if base.is_dir():
        for exe in sorted(base.rglob("llama-bench.exe")):
            return exe
    return None


def _garantir_binarios(cfg: dict) -> dict[str, str]:
    l = cfg.get("llama", {})
    exes: dict[str, str] = {}
    if exe := find_exe(l.get("cpu_bench_exe")):
        exes["cpu"] = exe
    if exe := find_exe(l.get("vulkan_bench_exe")):
        exes["vulkan"] = exe
    faltam = {"cpu", "vulkan"} - exes.keys()
    if faltam and l.get("auto_download_binaries", True):
        alvos = {"cpu": "win-cpu-x64", "vulkan": "win-vulkan-x64"}
        tag, assets = _release_com_binarios(alvos.values())
        for backend in sorted(faltam):
            nome = next((n for n in assets if alvos[backend] in n and n.endswith(".zip")), None)
            if not nome:
                print(f"  aviso: asset {alvos[backend]} não encontrado no release {tag}")
                continue
            zip_path = download(assets[nome], WORK_DIR / "llama" / nome, label=nome)
            dest = WORK_DIR / "llama" / backend
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(dest)
            zip_path.unlink()
            if exe := _bench_exe_cacheado(backend):
                exes[backend] = str(exe)
    for backend in list(faltam):
        if exe := _bench_exe_cacheado(backend):
            exes.setdefault(backend, str(exe))
    if not exes:
        raise BenchSkip(SETUP)
    return exes


def _tps(entrada: dict | None) -> float | None:
    if not entrada:
        return None
    if entrada.get("avg_ts"):
        return round(entrada["avg_ts"], 1)
    ns = entrada.get("avg_ns")
    n = entrada.get("n_gen") or entrada.get("n_prompt")
    if ns and n:
        return round(n / (ns / 1e9), 1)
    return None


def _rodar_bench(exe: str, modelo: Path, ngl: str, extra: list[str],
                 sample_vram: bool) -> dict:
    # llama-bench moderno imprime o relatório em stdout com `-o <formato>`
    r = run_timed([exe, "-m", str(modelo), "-ngl", ngl, "-p", "512", "-n", "128",
                   "-r", "2", "-o", "json", *extra],
                  sample_vram=sample_vram, timeout=3600)
    if r.returncode != 0:
        return {"disponivel": False,
                "erro": (r.stderr or r.stdout).strip()[-400:] or f"exit {r.returncode}"}
    try:
        dados = json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"disponivel": False,
                "erro": f"saída não-JSON do llama-bench: {r.stdout.strip()[-300:]}"}
    pp = next((e for e in dados if not e.get("n_gen")), None)
    tg = next((e for e in dados if e.get("n_gen")), None)
    return {
        "disponivel": True,
        "pp512_tps": _tps(pp),
        "tg128_tps": _tps(tg),
        "pico_vram_mb": r.peak_vram_mb,
        "tempo_total_s": round(r.wall_s, 1),
    }


def run(cfg: dict) -> dict:
    l = cfg.get("llama", {})
    exes = _garantir_binarios(cfg)
    auto = bool(l.get("auto_download_models", True))
    arquivos: dict[str, Path] = {}
    indisponiveis = []
    for m in l.get("models", MODELOS_PADRAO):
        try:
            caminhos = []
            for arq in m["arquivos"]:
                destino = CANDIDATOS_DIR / arq
                if not destino.exists():
                    if not auto:
                        raise BenchSkip(f"modelo ausente e auto_download desligado: {destino}")
                    download(m["base_url"] + arq, destino, label=arq)
                caminhos.append(destino)
        except BenchSkip as exc:
            print(f"  aviso: {m['nome']} indisponível — {exc}")
            indisponiveis.append({"modelo": m["nome"], "disponivel": False, "erro": str(exc)})
            continue
        registrar_modelo(m["nome"], caminhos[0], PROPOSITO, arquivos=caminhos)
        arquivos[m["nome"]] = caminhos[0]
    if not arquivos:
        raise BenchSkip("nenhum modelo candidato pôde ser baixado")

    threads = str(l.get("threads", 12))
    resultados = []
    for backend, exe in exes.items():
        ngl = "999" if backend == "vulkan" else "0"
        extra = ["-t", threads] if backend == "cpu" else []
        for nome, modelo in arquivos.items():
            entrada = {"backend": backend, "modelo": nome,
                       **_rodar_bench(exe, modelo, ngl, extra, backend == "vulkan")}
            resultados.append(entrada)
            if entrada["disponivel"]:
                print(f"  llama/{backend}/{nome}: tg128 {entrada['tg128_tps']} t/s")
            else:
                print(f"  llama/{backend}/{nome}: indisponível")
    return {
        "observacao": "mede apenas velocidade (llama-bench pp512/tg128); "
                      "qualidade em PT exige avaliação manual posterior",
        "resultados": indisponiveis + resultados,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--choose", metavar="MODELO",
                    help="marca o modelo vencedor e remove os demais candidatos")
    args = ap.parse_args()
    if args.choose:
        removidos = escolher_modelo(args.choose, PROPOSITO)
        for p in removidos:
            print(f"removido: {p}")
        print(f"modelo escolhido: {args.choose}")
        return
    payload = run(load_config())
    path = save_results("llama", payload)
    print(f"resultados salvos em {path}")


if __name__ == "__main__":
    main()
