/**
 * Proposal parser — extracts structured option proposals from LLM assistant messages.
 *
 * The LLM can embed a proposal in a code block with language `json-proposal`:
 *
 * ```json-proposal
 * {
 *   "title": "How should I fix this?",
 *   "options": [
 *     {"id": "1", "label": "Quick fix", "description": "Add a null check before..."},
 *     {"id": "2", "label": "Full refactor", "description": "Rewrite the module to..."}
 *   ]
 * }
 * ```
 *
 * The parser extracts this block and returns a typed `Proposal` object.
 */

export interface ProposalOption {
  id: string;
  label: string;
  description: string;
  actions?: string[];
  confidence?: number;
}

export interface Proposal {
  id: string;
  title: string;
  options: ProposalOption[];
}

const PROPOSAL_RE = /```json-proposal\s*\n([\s\S]*?)```/g;

function makeProposalId(): string {
  return `prop-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function extractProposals(content: string): Proposal[] {
  const proposals: Proposal[] = [];
  let match: RegExpExecArray | null;

  PROPOSAL_RE.lastIndex = 0;
  while ((match = PROPOSAL_RE.exec(content)) !== null) {
    try {
      const raw = JSON.parse(match[1]) as Record<string, unknown>;
      if (raw && typeof raw === "object" && Array.isArray(raw.options)) {
        const options = (raw.options as Array<Record<string, unknown>>)
          .filter((o) => o && typeof o === "object" && typeof o.label === "string")
          .map((o, idx) => ({
            id: String(o.id ?? `opt-${idx}`),
            label: o.label as string,
            description: typeof o.description === "string" ? o.description : "",
            actions: Array.isArray(o.actions)
              ? o.actions.filter((a): a is string => typeof a === "string")
              : undefined,
            confidence: typeof o.confidence === "number" ? o.confidence : undefined,
          }));

        if (options.length > 0) {
          proposals.push({
            id: makeProposalId(),
            title: typeof raw.title === "string" ? raw.title : "Choose an approach",
            options,
          });
        }
      }
    } catch {
      /* invalid JSON — skip */
    }
  }

  return proposals;
}

export function stripProposalBlocks(content: string): string {
  return content.replace(PROPOSAL_RE, "").trim();
}

export function hasProposal(content: string): boolean {
  PROPOSAL_RE.lastIndex = 0;
  return PROPOSAL_RE.test(content);
}

export function formatOptionSelection(proposal: Proposal, option: ProposalOption): string {
  const lines = [
    `I'll go with: **${option.label}**`,
    "",
    option.description ? `> ${option.description}` : "",
    "",
    `<!--proposal-selected: ${proposal.id} / ${option.id}-->`,
  ];
  return lines.filter(Boolean).join("\n");
}
