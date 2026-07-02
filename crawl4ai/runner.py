"""
runner.py — low-level execution of `crwl crawl <args>` via subprocess.

Handles timeout and stdout/stderr collection. Port of runner.ts.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from . import resolve


@dataclass
class CrawlResult:
    stdout: str
    stderr: str
    exit_code: int | None
    args: list[str]
    timed_out: bool = False


def run_crawl(args: list[str], timeout_sec: int = 60) -> CrawlResult:
    """Run `crwl <args>` in the dedicated venv with a time limit.

    Args:
        args: CLI arguments excluding "crwl" itself
              (e.g. ["crawl", "-o", "markdown", url]).
        timeout_sec: time limit in seconds.
    """
    if not resolve.is_installed():
        raise RuntimeError(
            "crawl4ai is not installed. Run install.install() "
            "or the /crawl4ai-install command."
        )

    cmd = [str(resolve.crwl_path()), *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_sec,
            env=resolve.venv_env(),
        )
        return CrawlResult(
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            exit_code=proc.returncode,
            args=cmd,
        )
    except subprocess.TimeoutExpired as e:
        return CrawlResult(
            stdout=(e.stdout or "") if isinstance(e.stdout, str) else "",
            stderr=f"Crawl exceeded the {timeout_sec}s limit",
            exit_code=None,
            args=cmd,
            timed_out=True,
        )
