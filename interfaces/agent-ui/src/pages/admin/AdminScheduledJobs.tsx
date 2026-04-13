export function AdminScheduledJobs() {
  return (
    <div className="mx-auto max-w-xl px-6 py-10">
      <h1 className="text-2xl font-semibold text-white">Scheduled jobs</h1>
      <p className="mt-4 text-sm text-surface-muted">
        This section is for <strong className="text-neutral-200">background cron jobs</strong>, not
        for ComfyUI image graphs and not for future user-defined step workflows (n8n-style). Those
        jobs are discovered from the same scan paths as tools: any <span className="font-mono">.py</span>{" "}
        file that defines <span className="font-mono">HANDLERS</span> and{" "}
        <span className="font-mono">RUN_EVERY_MINUTES</span> is registered by{" "}
        <span className="font-mono">scheduled_job_registry</span> and run by the in-process cron
        thread (<span className="font-mono">src/infrastructure/cron.py</span>).
      </p>
      <p className="mt-4 text-sm text-surface-muted">
        <strong className="text-neutral-200">LLM tools</strong> stay separate: they use the normal
        tool registry and are invoked by the agent per chat round — see Admin → Tools.
      </p>
      <p className="mt-4 text-sm text-amber-200/90">
        No admin API is wired here yet (list jobs, enable/disable). Use logs and code until this
        page is extended.
      </p>
    </div>
  );
}
