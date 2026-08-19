export default function StatCard({
  label,
  value,
  hint,
  accent = 'cyan',
}: {
  label: string;
  value: string | number;
  hint?: string;
  accent?: 'cyan' | 'done' | 'progress' | 'start';
}) {
  const accentClass = {
    cyan: 'text-cyan-accent',
    done: 'text-status-done',
    progress: 'text-status-progress',
    start: 'text-status-start',
  }[accent];

  return (
    <div className="alchemia-card p-5">
      <p className="font-mono text-[11px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-2 font-mono text-3xl font-semibold ${accentClass}`}>{value}</p>
      {hint ? <p className="mt-1 text-[12px] text-slate-500">{hint}</p> : null}
    </div>
  );
}
