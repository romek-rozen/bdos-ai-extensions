#!/usr/bin/env python3
"""
install_into_bdos.py — link this extensions repo into a BDOS installation.

Point BDOS at a public repo and install it with one command:

    git clone https://github.com/romek-rozen/bdos-ai-extensions.git
    python bdos-ai-extensions/install_into_bdos.py

What it does:
  1. Locates your BDOS-AI directory (arg > $BDOS_DIR > auto-detect > CWD).
  2. Links every extension package (top-level dir with __init__.py) into my/extensions/.
  3. Links every skill under skills/ into my/skills/.
  4. Prints the next step (`bdos update --regenerate`) and optional per-extension install.

Modes:
  --copy          copy files instead of symlinking (use if symlinks are awkward)
  --bdos <path>   explicit path to the BDOS-AI directory
  --install-deps  also run each extension's install() (may download browsers etc.)

Symlink vs copy: a symlink keeps ONE source of truth (this repo) — `git pull` updates
BDOS instantly and there are no duplicate copies to sync. Copy is simpler mentally but
you must re-run this script after every `git pull`.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
SKIP_DIRS = {".git", ".github", "tests", "skills", "__pycache__"}


def find_bdos(explicit: str | None) -> Path | None:
    """Locate the BDOS-AI directory."""
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    if os.environ.get("BDOS_DIR"):
        candidates.append(Path(os.environ["BDOS_DIR"]).expanduser())
    # Walk up from CWD
    cur = Path.cwd()
    for _ in range(6):
        candidates.append(cur)
        cur = cur.parent
    for c in candidates:
        if (c / "bdos").is_dir() and (c / "my").is_dir():
            return c
    return None


def link(src: Path, dst: Path, copy: bool) -> str:
    """Create a symlink (or copy) at dst pointing to src. Returns a status word."""
    if dst.is_symlink() or dst.exists():
        # Replace existing link/dir to keep it in sync
        if dst.is_symlink() or dst.is_file():
            dst.unlink()
        else:
            shutil.rmtree(dst)
    if copy:
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
            ".venv", "outputs", ".crawl4ai", "__pycache__"))
        return "copied"
    try:
        dst.symlink_to(src, target_is_directory=True)
        return "linked"
    except OSError as e:
        # Windows without admin/developer mode can't symlink → fall back to copy
        print(f"  ! symlink failed ({e}); copying instead", flush=True)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
            ".venv", "outputs", ".crawl4ai", "__pycache__"))
        return "copied (fallback)"


def discover_extensions() -> list[Path]:
    return [
        p for p in REPO.iterdir()
        if p.is_dir() and p.name not in SKIP_DIRS and (p / "__init__.py").exists()
    ]


def _env_var_names(example: Path) -> list[str]:
    """Variable names declared in a .env.example (KEY=... lines)."""
    names = []
    for line in example.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            names.append(line.split("=", 1)[0].strip())
    return names


def ensure_env(ext: Path) -> dict | None:
    """For an extension shipping a `.env.example`, make sure a `.env` exists next to
    it (copied from the template, never overwritten) and report the keys to fill.

    Returns {"name", "env_path", "vars", "created"} or None if the extension needs
    no credentials. Editing this `.env` in the repo is what BDOS reads (it's symlinked).
    """
    example = ext / ".env.example"
    if not example.exists():
        return None
    env = ext / ".env"
    created = False
    if not env.exists():
        shutil.copyfile(example, env)
        created = True
    return {"name": ext.name, "env_path": str(env),
            "vars": _env_var_names(example), "created": created}


def discover_skills() -> list[Path]:
    skills_root = REPO / "skills"
    if not skills_root.is_dir():
        return []
    return [p for p in skills_root.iterdir() if p.is_dir() and (p / "SKILL.md").exists()]


def main() -> int:
    ap = argparse.ArgumentParser(description="Install bdos-ai-extensions into BDOS")
    ap.add_argument("--bdos", help="Path to the BDOS-AI directory")
    ap.add_argument("--copy", action="store_true", help="Copy instead of symlink")
    ap.add_argument("--install-deps", action="store_true",
                    help="Run each extension's install() after linking")
    args = ap.parse_args()

    bdos = find_bdos(args.bdos)
    if not bdos:
        print("ERROR: could not locate BDOS-AI (a dir containing both `bdos/` and `my/`).")
        print("Pass it explicitly:  python install_into_bdos.py --bdos /path/to/BDOS-AI")
        return 1

    print(f"BDOS-AI: {bdos}")
    ext_dst = bdos / "my" / "extensions"
    skill_dst = bdos / "my" / "skills"
    ext_dst.mkdir(parents=True, exist_ok=True)
    skill_dst.mkdir(parents=True, exist_ok=True)

    extensions = discover_extensions()
    skills = discover_skills()

    print("\nExtensions:")
    for ext in extensions:
        status = link(ext, ext_dst / ext.name, args.copy)
        print(f"  {ext.name:20s} → my/extensions/{ext.name}  [{status}]")

    print("\nSkills:")
    for sk in skills:
        status = link(sk, skill_dst / sk.name, args.copy)
        print(f"  {sk.name:20s} → my/skills/{sk.name}  [{status}]")

    if args.install_deps:
        print("\nRunning extension installers…")
        sys.path.insert(0, str(REPO))
        for ext in extensions:
            try:
                mod = __import__(f"{ext.name}.install", fromlist=["install"])
                r = mod.install()
                print(f"  {ext.name}: {r}")
            except Exception as e:  # noqa: BLE001
                print(f"  {ext.name}: no installer or failed ({e})")

    # API-key onboarding: create .env from .env.example for every extension that
    # needs credentials, and print a clear checklist of what to fill in.
    creds = [c for c in (ensure_env(ext) for ext in extensions) if c]
    if creds:
        print("\n🔑 API keys — some extensions need credentials to work:")
        for c in creds:
            tag = " (created for you)" if c["created"] else ""
            print(f"  • {c['name']}: edit {c['env_path']}{tag}")
            print(f"      set: {', '.join(c['vars'])}")
            print(f"      details: {c['name']}/README.md")
        print("  (.env files are gitignored — your keys stay on this machine.)")

    print("\nNext step — register the skills/commands with BDOS:")
    print("  bdos update --regenerate")
    if not args.install_deps:
        print("\nEach extension may need its own one-time setup (e.g. crawl4ai downloads a")
        print("browser). Re-run with --install-deps, or follow the extension's README.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
