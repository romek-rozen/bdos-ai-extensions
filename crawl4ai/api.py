"""
api.py — high-level crawl4ai API for BDOS.

Functions return a dict with content and metadata. Cache is enabled by default
(cache_mode=enabled), matching the pi-crawl4ai workflow.

Examples (import path inside BDOS):
    from my.extensions.crawl4ai import scrape, deep_crawl, extract
    r = scrape("https://example.com")
    print(r["content"])

    r = deep_crawl("https://docs.example.com", strategy="bfs", max_pages=10)
    r = extract("https://shop.example.com", prompt="Extract product names and prices")
"""

from __future__ import annotations

import shutil

from . import resolve
from .runner import run_crawl

# Inline limit — longer results are written to a file and the path is returned
INLINE_LIMIT = 60_000


def _build_args(
    url: str,
    output_format: str | None = None,
    deep_crawl: str | None = None,
    max_pages: int | None = None,
    question: str | None = None,
    json_extract: str | None = None,
    schema_path: str | None = None,
    extraction_config: str | None = None,
    browser_config: str | None = None,
    crawler_config: str | None = None,
    bypass_cache: bool = False,
    output_file: str | None = None,
) -> list[str]:
    args: list[str] = ["crawl"]
    if output_format:
        args += ["-o", output_format]
    if deep_crawl:
        args += ["--deep-crawl", deep_crawl]
    if max_pages is not None:
        args += ["--max-pages", str(max_pages)]
    if question:
        args += ["-q", question]
    if json_extract:
        args += ["-j", json_extract]
    if schema_path:
        args += ["-s", schema_path]
    if extraction_config:
        args += ["-e", extraction_config]
    if browser_config:
        args += ["-b", browser_config]

    # Cache enabled by default (crwl starts with BYPASS)
    if bypass_cache:
        args.append("--bypass-cache")
    elif crawler_config:
        cc = crawler_config if "cache_mode=" in crawler_config else f"{crawler_config},cache_mode=enabled"
        args += ["-c", cc]
    else:
        args += ["-c", "cache_mode=enabled"]

    if output_file:
        args += ["-O", output_file]
    args.append(url)
    return args


def _execute(url: str, fmt: str | None, timeout: int, save: bool | None = None, **kwargs) -> dict:
    """Run a crawl, handle file saving, and return a unified dict."""
    args = _build_args(url, output_format=fmt, **kwargs)
    result = run_crawl(args, timeout_sec=timeout)

    ok = result.exit_code == 0 and not result.timed_out
    content = result.stdout.strip()

    saved_path = None
    # Save to a file if the content is long or save was forced
    if ok and content and (save or (save is None and len(content) > INLINE_LIMIT)):
        path = resolve.output_path(url, fmt)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        saved_path = str(path)

    truncated = False
    inline = content
    if saved_path and len(content) > INLINE_LIMIT:
        inline = content[:INLINE_LIMIT]
        truncated = True

    return {
        "ok": ok,
        "url": url,
        "format": resolve.normalize_format(fmt),
        "content": inline,
        "chars": len(content),
        "truncated": truncated,
        "saved_path": saved_path,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "error": None if ok else (result.stderr.strip()[:500] or "crawl failed"),
        "command": " ".join(result.args),
    }


def scrape(url: str, fit: bool = False, timeout: int = 60, save: bool | None = None,
           bypass_cache: bool = False) -> dict:
    """Single page → clean markdown.

    Args:
        url: page address.
        fit: markdown-fit (trimmed, main content only) instead of full markdown.
        timeout: time limit in seconds.
        save: True=save to file, False=don't, None=auto (save when long).
        bypass_cache: skip the cache.
    """
    return _execute(url, "markdown-fit" if fit else "markdown", timeout, save=save,
                    bypass_cache=bypass_cache)


def deep_crawl(url: str, strategy: str = "bfs", max_pages: int = 10, fmt: str = "markdown",
               timeout: int = 300, save: bool | None = True, bypass_cache: bool = False) -> dict:
    """Deep crawl across many sub-pages.

    Args:
        strategy: "bfs" | "dfs" | "best-first".
        max_pages: maximum number of sub-pages.
        fmt: "markdown" | "markdown-fit" | "json".
    """
    return _execute(url, fmt, timeout, save=save, deep_crawl=strategy,
                    max_pages=max_pages, bypass_cache=bypass_cache)


def extract(url: str, prompt: str | None = None, schema_path: str | None = None,
            extraction_config: str | None = None, timeout: int = 120,
            save: bool | None = None, bypass_cache: bool = False) -> dict:
    """Structured extraction → JSON.

    Two modes:
      - LLM: pass `prompt` (e.g. "Extract product names and prices"). Requires a
        configured LLM provider in crawl4ai (API key in env).
      - CSS/schema: pass `schema_path` + `extraction_config` (no LLM).
    """
    return _execute(url, "json", timeout, save=save, json_extract=prompt,
                    schema_path=schema_path, extraction_config=extraction_config,
                    bypass_cache=bypass_cache)


def ask(url: str, question: str, timeout: int = 120, bypass_cache: bool = False) -> dict:
    """Ask a question about the page content (Q&A). Requires an LLM provider in crawl4ai."""
    return _execute(url, "markdown", timeout, save=False, question=question,
                    bypass_cache=bypass_cache)


def status() -> dict:
    """Installation state: installed?, paths, version."""
    installed = resolve.is_installed()
    version = None
    if installed:
        import subprocess
        r = subprocess.run([str(resolve.crwl_path()), "--version"],
                           capture_output=True, text=True, env=resolve.venv_env())
        version = (r.stdout or r.stderr).strip().split("\n")[0] if r.returncode == 0 else None
    return {
        "installed": installed,
        "crwl": str(resolve.crwl_path()),
        "venv": str(resolve.VENV_DIR),
        "outputs": str(resolve.OUTPUTS_DIR),
        "version": version,
    }


def clear_cache() -> dict:
    """Clear the local crawl4ai cache (.crawl4ai/cache + .crawl4ai/robots)."""
    removed = []
    for sub in ("cache", "robots"):
        target = resolve.CACHE_BASE / sub
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
            removed.append(str(target))
    return {"ok": True, "removed": removed}
