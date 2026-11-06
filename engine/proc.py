"""Execução de subprocessos com captura e timeout."""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Run:
    argv: list[str]
    returncode: int
    wall_s: float
    stdout: str
    stderr: str


def run(argv: list[str | Path], *, timeout: int | None = None,
        cwd: Path | None = None) -> Run:
    args = [str(a) for a in argv]
    start = time.perf_counter()
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace", cwd=cwd)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        return Run(args, -9, time.perf_counter() - start, out, err)
    return Run(args, proc.returncode, time.perf_counter() - start, out, err)
