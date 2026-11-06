"""Utilitários compartilhados do harness de benchmark do Crab Clip AI."""
from __future__ import annotations

import contextlib
import json
import platform
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
ROOT = BENCH_DIR.parents[1]
WORK_DIR = BENCH_DIR / ".work"
DOCS_DIR = ROOT / "docs" / "benchmarks"
RAW_DIR = DOCS_DIR / "raw"
MODELS_DIR = ROOT / "models"
CONFIG_PATH = BENCH_DIR / "config.json"
MANIFEST_PATH = MODELS_DIR / "manifest.json"

PS = ["powershell", "-NoProfile", "-NonInteractive", "-Command"]


class BenchSkip(RuntimeError):
    """Benchmark pulado por pré-requisito ausente; nunca disfarçar como medição."""


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def find_exe(name_or_path: str | None) -> str | None:
    if not name_or_path:
        return None
    if Path(name_or_path).is_file():
        return str(Path(name_or_path).resolve())
    return shutil.which(name_or_path)


def _ps(command: str, timeout: int = 30) -> str:
    proc = subprocess.run(PS + [command], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)
    return proc.stdout.strip()


def system_info() -> dict:
    info = {
        "coletado_em": datetime.now(timezone.utc).isoformat(),
        "os": f"Windows {platform.version()}",
        "python": platform.python_version(),
    }
    try:
        info["cpu"] = _ps("(Get-CimInstance Win32_Processor).Name")
        ram = _ps("(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory")
        info["ram_gb"] = round(int(ram) / 2**30, 1)
        gpus = _ps("Get-CimInstance Win32_VideoController | "
                   "Select-Object Name,DriverVersion | ConvertTo-Json -Compress")
        parsed = json.loads(gpus)
        info["gpus"] = parsed if isinstance(parsed, list) else [parsed]
    except Exception as exc:
        info["erro_coleta"] = str(exc)
    return info


_VRAM_SCRIPT = r"""
$cs = Get-Counter -ListSet '*gpu*' -ErrorAction SilentlyContinue |
      Where-Object { $_.CounterSetName -match '(?i)process' } | Select-Object -First 1
if (-not $cs) { exit 3 }
$path = $cs.PathsWithInstances | Where-Object { $_ -match '(?i)local' } | Select-Object -First 1
if (-not $path) { exit 4 }
while ($true) {
  try {
    foreach ($s in (Get-Counter $path -ErrorAction Stop).CounterSamples) {
      if ($s.InstanceName -like 'pid_{PID}*') { [Console]::Out.WriteLine([int64]$s.CookedValue) }
    }
    [Console]::Out.Flush()
  } catch {}
  Start-Sleep -Milliseconds 400
}
"""


class VramSampler:
    """Amostra o contador de memória dedicada de GPU por processo (melhor esforço).

    O nome do contador é descoberto em runtime porque contadores do Windows são
    localizados (em PT-BR o nome difere do inglês). Se a descoberta falhar,
    peak_mb retorna None — nunca um número inventado.
    """

    def __init__(self, pid: int):
        self._script = _VRAM_SCRIPT.replace("{PID}", str(pid))
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._peak = 0

    def __enter__(self) -> "VramSampler":
        try:
            self._proc = subprocess.Popen(
                PS + [self._script],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding="utf-8", errors="replace",
            )
        except OSError:
            return self
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()
        return self

    def _read(self) -> None:
        assert self._proc and self._proc.stdout
        for line in self._proc.stdout:
            line = line.strip()
            if line.isdigit():
                self._peak = max(self._peak, int(line))

    def __exit__(self, *exc: object) -> None:
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        if self._thread:
            self._thread.join(timeout=5)

    @property
    def peak_mb(self) -> float | None:
        return round(self._peak / 2**20, 1) if self._peak > 0 else None


@dataclass
class TimedRun:
    argv: list[str]
    returncode: int
    wall_s: float
    stdout: str
    stderr: str
    peak_vram_mb: float | None


def run_timed(argv: list[str], *, sample_vram: bool = False,
              timeout: int | None = None) -> TimedRun:
    start = time.perf_counter()
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace")
    ctx = VramSampler(proc.pid) if sample_vram else contextlib.nullcontext()
    with ctx as sampler:
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, err = proc.communicate()
            wall = time.perf_counter() - start
            peak = sampler.peak_mb if isinstance(sampler, VramSampler) else None
            return TimedRun(argv, -9, wall, out, err, peak)
    wall = time.perf_counter() - start
    peak = sampler.peak_mb if isinstance(sampler, VramSampler) else None
    return TimedRun(argv, proc.returncode, wall, out, err, peak)


def download(url: str, dest: Path, *, label: str = "") -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        print(f"  já em cache: {dest.name}")
        return dest
    tmp = dest.with_name(dest.name + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "crab-clip-ai-bench"})
    print(f"  baixando {label or dest.name}")
    print(f"    {url}")
    try:
        resp = urllib.request.urlopen(req)
    except urllib.error.HTTPError as exc:
        raise BenchSkip(f"download falhou (HTTP {exc.code}): {url}") from exc
    with resp, open(tmp, "wb") as fh:
        total = int(resp.headers.get("Content-Length") or 0)
        recebido = 0
        proximo_aviso = 0.1
        while chunk := resp.read(1 << 20):
            fh.write(chunk)
            recebido += len(chunk)
            if total and recebido / total >= proximo_aviso:
                print(f"    {recebido * 100 // total}% de {total / 2**20:.0f} MiB")
                proximo_aviso += 0.1
    tmp.replace(dest)
    return dest


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "crab-clip-ai-bench"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {"modelos": []}


def save_manifest(data: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                             encoding="utf-8")


def registrar_modelo(nome: str, caminho: Path, proposito: str,
                     arquivos: list[Path] | None = None) -> None:
    data = load_manifest()
    data["modelos"] = [m for m in data["modelos"] if m["nome"] != nome]
    data["modelos"].append({
        "nome": nome,
        "caminho": str(caminho),
        "arquivos": [str(p) for p in (arquivos or [caminho])],
        "proposito": proposito,
        "status": "candidato",
        "registrado_em": datetime.now(timezone.utc).isoformat(),
    })
    save_manifest(data)


def escolher_modelo(nome: str, proposito: str) -> list[Path]:
    """Marca `nome` como escolhido e apaga os demais candidatos do mesmo propósito."""
    data = load_manifest()
    removidos: list[Path] = []
    achou = False
    for m in data["modelos"]:
        if m["proposito"] != proposito:
            continue
        if m["nome"] == nome:
            m["status"] = "escolhido"
            achou = True
        elif m["status"] == "candidato":
            for arq in m.get("arquivos") or [m["caminho"]]:
                p = Path(arq)
                if p.exists():
                    p.unlink()
                    removidos.append(p)
            m["status"] = "removido"
    if not achou:
        raise BenchSkip(f"modelo '{nome}' não está registrado com propósito '{proposito}'")
    save_manifest(data)
    return removidos


def save_results(nome: str, payload: dict) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = RAW_DIR / f"{stamp}-{nome}.json"
    path.write_text(json.dumps({"sistema": system_info(), "resultados": payload},
                               ensure_ascii=False, indent=2), encoding="utf-8")
    return path
