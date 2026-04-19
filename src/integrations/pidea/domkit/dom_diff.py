"""Diff two snapshot files (text)."""

from __future__ import annotations

import difflib
from pathlib import Path


def diff_files(a: Path, b: Path) -> str:
    ta = a.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    tb = b.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    return "".join(difflib.unified_diff(ta, tb, fromfile=str(a), tofile=str(b)))


def write_diff(a: Path, b: Path, out: Path) -> None:
    out.write_text(diff_files(a, b), encoding="utf-8")
