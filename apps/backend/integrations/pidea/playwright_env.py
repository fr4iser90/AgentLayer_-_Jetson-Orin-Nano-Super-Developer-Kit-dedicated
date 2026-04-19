"""Playwright-Verfügbarkeit und Installation (nur für PIDEA / IDE-Agent API)."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys


def _clear_playwright_modules() -> None:
    """Nach ``pip install`` im gleichen Prozess: alte Module aus ``sys.modules`` entfernen."""
    drop = [k for k in sys.modules if k == "playwright" or k.startswith("playwright.")]
    for k in drop:
        del sys.modules[k]
    importlib.invalidate_caches()


def reload_playwright_import_state() -> None:
    """Nach erfolgreichem Web-UI-Install aufrufen, damit ``playwright_import_ok()`` sofort stimmt."""
    _clear_playwright_modules()


def ensure_playwright_pip_target_on_syspath() -> None:
    """Wenn ``PIDEA_PLAYWRIGHT_PIP_TARGET`` gesetzt ist (Docker-Volume), Paket von dort importieren."""
    t = (os.environ.get("PIDEA_PLAYWRIGHT_PIP_TARGET") or "").strip()
    if t and os.path.isdir(t) and t not in sys.path:
        sys.path.insert(0, t)


def playwright_import_ok() -> bool:
    """Prüft die gleiche API wie PIDEA (``sync_api``), nicht nur das Top-Level-Paket."""
    ensure_playwright_pip_target_on_syspath()
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401

        return True
    except ImportError:
        return False


def install_playwright_on_server_sync() -> tuple[bool, str]:
    """``pip install playwright`` dann ``playwright install chromium`` (gleiches Python wie die API).

    Optional: ``PIDEA_PLAYWRIGHT_PIP_TARGET`` → ``pip install --target`` (Named Volume in Compose).
    Optional: ``PLAYWRIGHT_BROWSERS_PATH`` → Browser-Cache auf Volume (Compose).

    Ohne ``--with-deps``: vermeidet ``apt-get`` in Docker (Overlay/Cache-Probleme).
    """
    ensure_playwright_pip_target_on_syspath()
    chunks: list[str] = []
    pip_target = (os.environ.get("PIDEA_PLAYWRIGHT_PIP_TARGET") or "").strip()
    env = os.environ.copy()
    browsers = (env.get("PLAYWRIGHT_BROWSERS_PATH") or env.get("PIDEA_PLAYWRIGHT_BROWSERS_PATH") or "").strip()
    if browsers:
        os.makedirs(browsers, exist_ok=True)
        env["PLAYWRIGHT_BROWSERS_PATH"] = browsers

    if pip_target:
        os.makedirs(pip_target, exist_ok=True)
        # --target legt Pakete nicht in site-packages; python -m playwright braucht PYTHONPATH.
        _prev = env.get("PYTHONPATH", "").strip()
        env["PYTHONPATH"] = pip_target if not _prev else f"{pip_target}{os.pathsep}{_prev}"
        pip_cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "playwright>=1.49.0,<2",
            "--target",
            pip_target,
        ]
    else:
        pip_cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "playwright>=1.49.0,<2"]
    try:
        p1 = subprocess.run(pip_cmd, capture_output=True, text=True, timeout=600, env=env)
    except subprocess.TimeoutExpired:
        return False, "pip install playwright: timed out (10 min)"
    chunks.append(p1.stdout or "")
    chunks.append(p1.stderr or "")
    if p1.returncode != 0:
        return False, "\n".join(chunks)[-12000:]
    pw_cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
    try:
        p2 = subprocess.run(pw_cmd, capture_output=True, text=True, timeout=1200, env=env)
    except subprocess.TimeoutExpired:
        return False, ("\n".join(chunks) + "\nplaywright install chromium: timed out (20 min)")[-12000:]
    chunks.append(p2.stdout or "")
    chunks.append(p2.stderr or "")
    if p2.returncode != 0:
        return False, "\n".join(chunks)[-12000:]
    return True, "\n".join(chunks)[-12000:]
