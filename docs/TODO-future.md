# Future work (tracked goals)

English-only backlog for product and research ideas—not a commitment order.

---

## Chat feedback (UX)

- [ ] Add explicit **feedback controls** in chat UI: **thumbs up / thumbs down** (or equivalent) so users can mark responses as helpful or not.
- [ ] Persist feedback with **message/thread identifiers** and optional short comment (later).
- [ ] Expose feedback in **admin/analytics** for quality review (privacy/access rules TBD).

---

## Optional “monitor layer” (observability)

- [ ] Add a **toggleable monitor layer** (opt-in) that records structured traces for debugging and improvement loops.
- [ ] Let operators choose **which stack is monitored** (non-exclusive list; each may have limits):
  - **IDE Agent** (Playwright/CDP path, tool actions tied to IDE).
  - **External** API models (hosted LLMs).
  - **Ollama** (local)—note: may **not** support the same depth of hooks (prompt/tool capture depends on integration); treat as best-effort or out-of-scope for v1.
- [ ] For supported paths, capture at minimum: **prompts** (user + system where applicable), **tool calls / tool results**, **model identifiers**, **timestamps**, **session/thread id**, **errors**.

---

## Goals, outcomes, and follow-up analysis

- [ ] Define a lightweight **goal / outcome** model (e.g. task completed, user satisfied, escalation)—even if heuristic at first.
- [ ] Support **multi-turn context**: attach **follow-up prompts** so analysis can tell whether the user **retried**, **changed approach**, or **abandoned** a line of inquiry.
- [ ] Use aggregated traces + feedback to:
  - refine **routing/heuristic triggers** (when to suggest tools, when to hand off, etc.);
  - detect **systematic failure modes** (repeated thumbs-down on same flows).

---

## Data pipeline (collect → analyze → improve)

- [ ] **Store** monitor + feedback data in a queryable store (respect retention, PII, and admin-only access).
- [ ] **Offline or batch analysis** jobs: clustering, simple dashboards, export for human review.
- [ ] **Close the loop**: translate insights into **config/code changes** (prompt tweaks, tool policies, IDE selector maintenance)—with versioning and rollback.

---

## Notes

- Ollama monitoring may remain **limited** until a clear hook surface exists; document constraints when implementing.
- All monitoring should stay **opt-in** and **documented** for operators and end-users where required.
