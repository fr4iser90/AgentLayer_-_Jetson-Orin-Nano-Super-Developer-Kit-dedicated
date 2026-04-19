"""Rank selector candidates by heuristic stability (higher = better)."""

from __future__ import annotations

import re

from apps.backend.integrations.pidea.domkit.models import SelectorCandidate

# Prefer data-* / role / aria / id over long nth-child chains
_STABILITY_PATTERNS: tuple[tuple[re.Pattern[str], float], ...] = (
    (re.compile(r"\[data-[a-zA-Z0-9_-]+"), 4.0),
    (re.compile(r"#\w"), 3.5),
    (re.compile(r"\[aria-label"), 3.0),
    (re.compile(r"\[role="), 2.8),
    (re.compile(r"\[placeholder"), 2.5),
    (re.compile(r"\.composer-"), 2.2),
    (re.compile(r":nth-child"), -2.0),
    (re.compile(r">"), -0.5),  # deep child chains slightly worse
)


def base_stability_score(css: str) -> float:
    s = 1.0
    for pat, delta in _STABILITY_PATTERNS:
        if pat.search(css):
            s += delta
    if len(css) > 180:
        s -= 1.5
    if len(css) < 8:
        s -= 2.0
    return max(0.1, s)


def rank_candidates(candidates: list[SelectorCandidate]) -> list[SelectorCandidate]:
    for c in candidates:
        c.stability_score = base_stability_score(c.css) + (0.01 * min(c.match_count, 100))
    return sorted(candidates, key=lambda x: x.stability_score, reverse=True)
