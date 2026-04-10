const REPO =
  "https://github.com/fr4iser90/AgentLayer_-_Jetson-Orin-Nano-Super-Developer-Kit-dedicated";

const LINKS: { label: string; href: string }[] = [
  { label: "Repository", href: REPO },
  { label: "docs/ (folder)", href: `${REPO}/tree/main/docs` },
  { label: "WEBUI_CONTRACT.md", href: `${REPO}/blob/main/docs/WEBUI_CONTRACT.md` },
  { label: "FRONTEND_AGENT_UI_PLAN.md", href: `${REPO}/blob/main/docs/FRONTEND_AGENT_UI_PLAN.md` },
];

export function DocsPage() {
  return (
    <div className="h-full min-h-0 overflow-y-auto px-6 py-8">
      <div className="mx-auto max-w-xl">
        <h1 className="text-lg font-semibold text-white">Documentation</h1>
        <p className="mt-2 text-sm text-surface-muted">
          API and UI contracts live in the repo under{" "}
          <code className="rounded bg-white/5 px-1 py-0.5 text-xs text-neutral-300">docs/</code>.
          Open a file on GitHub or clone the project to edit locally.
        </p>
        <ul className="mt-6 flex flex-col gap-2">
          {LINKS.map((item) => (
            <li key={item.href}>
              <a
                href={item.href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-sky-400 hover:text-sky-300 hover:underline"
              >
                {item.label}
              </a>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
