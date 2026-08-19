export default function PageHeader({
  title,
  description,
  right,
}: {
  title: string;
  description?: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-wrap items-start justify-between gap-4 border-b border-white/5 pb-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-white">
          <span className="text-gradient-cyan">{title}</span>
        </h1>
        {description ? <p className="mt-1.5 max-w-2xl text-sm text-slate-400">{description}</p> : null}
      </div>
      {right ? <div>{right}</div> : null}
    </div>
  );
}
