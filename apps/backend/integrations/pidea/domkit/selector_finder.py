"""Heuristic discovery of replacement CSS selectors from live DOM."""

from __future__ import annotations

import json
import logging
from typing import Any

from apps.backend.integrations.pidea.domkit.models import SelectorCandidate
from apps.backend.integrations.pidea.domkit.selector_ranker import rank_candidates

logger = logging.getLogger(__name__)

_FIND_CANDIDATES_JS = """
(key) => {
  const out = [];
  const seen = new Set();

  function push(css, source, el) {
    if (!css || seen.has(css)) return;
    seen.add(css);
    let count = 0;
    try { count = document.querySelectorAll(css).length; } catch (e) { return; }
    if (count < 1) return;
    out.push({ css, source, count });
  }

  const hints = [];
  if (key === "aiMessages" || key === "assistant") {
    hints.push(
      '[data-message-role="ai"] .markdown-root',
      '[data-message-role="ai"] .rendered-markdown',
      '[data-message-role="ai"][data-message-kind="assistant"] .markdown-root',
      '.composer-rendered-message[data-message-kind="assistant"] .markdown-root',
      '.composer-rendered-message[data-message-kind="assistant"] .rendered-markdown',
      '[data-message-kind="assistant"] .markdown-root',
      '[data-message-kind="assistant"] .rendered-markdown',
      '[data-message-role="ai"] [class*="MarkdownRender"]',
      '[data-message-kind="assistant"] [class*="MarkdownRender"]',
    );
  }
  if (key === "userMessages" || key === "user") {
    hints.push(
      '[data-message-role="human"] .aislash-editor-input-readonly',
      'div.aislash-editor-input-readonly[data-lexical-editor="true"]',
      '.composer-human-message .aislash-editor-input-readonly',
    );
  }
  if (key === "input") {
    hints.push(
      '.aislash-editor-input[contenteditable="true"]',
      '[data-composer-input="true"]',
    );
  }

  for (const css of hints) {
    push(css, "hint-template", null);
  }

  // Scan data-* on composer messages
  const nodes = document.querySelectorAll('[data-message-role], [data-message-kind], [role="button"]');
  nodes.forEach((el, i) => {
    if (i > 400) return;
    const role = el.getAttribute && el.getAttribute("data-message-role");
    const kind = el.getAttribute && el.getAttribute("data-message-kind");
    if (key === "aiMessages" && role === "ai" && kind === "assistant") {
      const id = el.id;
      if (id) push(`#${CSS.escape(id)}`, "id", el);
      const cls = (el.className && String(el.className).split(/\\s+/).find(c => c && c.length < 80)) || "";
      if (cls) {
        push(`.${CSS.escape(cls)}[data-message-role="ai"][data-message-kind="assistant"]`, "class+data", el);
      }
    }
  });

  return out.slice(0, 40);
}
"""


def find_replacement_candidates(page: Any, key: str) -> list[SelectorCandidate]:
    """Return ranked selector candidates for a logical key (e.g. ``aiMessages``)."""
    try:
        raw = page.evaluate(_FIND_CANDIDATES_JS, key)
    except Exception as e:
        logger.warning("finder JS failed: %s", e)
        return []

    if not isinstance(raw, list):
        return []

    candidates: list[SelectorCandidate] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        css = item.get("css")
        if not isinstance(css, str):
            continue
        src = str(item.get("source", "unknown"))
        cnt = int(item.get("count", 0) or 0)
        candidates.append(
            SelectorCandidate(css=css.strip(), source=src, match_count=cnt, extra={"raw": item})
        )

    return rank_candidates(candidates)


_EXTENDED_FIND_JS = """
(key) => {
  const out = [];
  const seen = new Set();
  function push(css, source) {
    if (!css || seen.has(css)) return;
    seen.add(css);
    let count = 0;
    try { count = document.querySelectorAll(css).length; } catch (e) { return; }
    if (count < 1) return;
    out.push({ css, source, count });
  }
  const k = (key || "").toLowerCase();
  if (k.includes("send") || k.includes("codicon") || k.includes("button")) {
    const q = '[aria-label*="Send"], button[title*="Send"], .codicon-send, [data-testid*="send"], .action-label[aria-label*="Send"]';
    document.querySelectorAll(q).forEach((el, i) => {
      if (i > 25) return;
      if (el.id) push("#" + CSS.escape(el.id), "ext-send-id");
      const al = el.getAttribute("aria-label");
      if (al && al.length < 80) {
        const esc = String(al).replace(/"/g, '\\\\"');
        push(`[aria-label="${esc}"]`, "ext-send-aria");
      }
    });
  }
  if (k.includes("markdown") || k.includes("message") || k === "aimessages" || k === "assistant") {
    push('[data-message-role="ai"] .markdown-root', "ext-ai-md");
    push('[data-message-role="ai"] .rendered-markdown', "ext-ai-rm");
    push('[data-message-role="ai"][data-message-kind="assistant"] .markdown-root', "ext-ai-md2");
    push('.composer-rendered-message[data-message-kind="assistant"] .markdown-root', "ext-ai-comp");
    push('.composer-rendered-message[data-message-kind="assistant"] .rendered-markdown', "ext-ai-comp-rm");
    push('[data-message-kind="assistant"] .markdown-root', "ext-ai-kind");
    push('[data-message-kind="assistant"] .rendered-markdown', "ext-ai-kind-rm");
  }
  if (k.includes("user") || k.includes("human")) {
    push('[data-message-role="human"] .aislash-editor-input-readonly', "ext-human");
    push('div.aislash-editor-input-readonly[data-lexical-editor="true"]', "ext-human-lex");
  }
  if (k.includes("monaco") || k.includes("codeline")) {
    push(".monaco-editor .view-lines", "ext-monaco-lines");
    push(".monaco-editor", "ext-monaco");
  }
  return out.slice(0, 35);
}
"""


def find_extended_candidates(page: Any, key: str) -> list[SelectorCandidate]:
    """Extra heuristics for keys not fully covered by :func:`find_replacement_candidates`."""
    try:
        raw = page.evaluate(_EXTENDED_FIND_JS, key)
    except Exception as e:
        logger.warning("extended finder JS failed: %s", e)
        return []
    if not isinstance(raw, list):
        return []
    candidates: list[SelectorCandidate] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        css = item.get("css")
        if not isinstance(css, str):
            continue
        src = str(item.get("source", "extended"))
        cnt = int(item.get("count", 0) or 0)
        candidates.append(
            SelectorCandidate(css=css.strip(), source=src, match_count=cnt, extra={"raw": item})
        )
    return rank_candidates(candidates)


def find_all_candidates(page: Any, key: str) -> list[SelectorCandidate]:
    """Merge primary + extended candidates, dedupe by CSS, then rank."""
    primary = find_replacement_candidates(page, key)
    extended = find_extended_candidates(page, key)
    by_css: dict[str, SelectorCandidate] = {}
    for c in primary + extended:
        if c.css not in by_css:
            by_css[c.css] = c
    merged = list(by_css.values())
    return rank_candidates(merged)


def export_candidates_json(candidates: list[SelectorCandidate]) -> str:
    payload = [
        {"css": c.css, "source": c.source, "stability_score": c.stability_score, "match_count": c.match_count}
        for c in candidates
    ]
    return json.dumps(payload, indent=2, ensure_ascii=False)
