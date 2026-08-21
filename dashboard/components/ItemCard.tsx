import type { NewsItem } from '@/lib/types';
import { SOURCE_TYPE_LABELS } from '@/lib/types';
import { formatDate } from '@/lib/data';

const SOURCE_TYPE_COLOR: Record<string, string> = {
  journal: 'text-status-progress border-status-progress/30 bg-status-progress/10',
  preprint: 'text-status-start border-status-start/30 bg-status-start/10',
  news: 'text-cyan-accent border-cyan-accent/30 bg-cyan-accent/10',
  company_blog: 'text-status-done border-status-done/30 bg-status-done/10',
  press: 'text-slate-300 border-slate-500/30 bg-slate-500/10',
  // Newsletter curada (Drug Hunter, Longevity.Technology...) — cor própria, alto sinal.
  newsletter: 'text-amber-300 border-amber-400/30 bg-amber-400/10',
};

export default function ItemCard({ item }: { item: NewsItem }) {
  const badgeClass = SOURCE_TYPE_COLOR[item.source_type] ?? SOURCE_TYPE_COLOR.news;
  return (
    <a
      href={item.url}
      target="_blank"
      rel="noopener noreferrer"
      className="alchemia-card group block p-4 transition-all hover:-translate-y-0.5 hover:shadow-[0_0_24px_rgba(41,211,245,0.12)]"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={`rounded border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide ${badgeClass}`}>
            {SOURCE_TYPE_LABELS[item.source_type] ?? item.source_type}
          </span>
          <span className="font-mono text-[11px] text-slate-400">{item.source}</span>
        </div>
        <span className="font-mono text-[11px] text-slate-400">{formatDate(item.published_date)}</span>
      </div>

      <h3 className="mb-1.5 text-[15px] font-medium leading-snug text-slate-100 group-hover:text-cyan-accent">
        {item.title}
      </h3>

      {item.summary ? (
        <p className="line-clamp-2 text-[13px] leading-relaxed text-slate-400">{item.summary}</p>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {item.authors.slice(0, 3).map((a) => (
          <span key={a} className="font-mono text-[10px] text-slate-400">
            {a}
          </span>
        ))}
        {item.keywords_matched.slice(0, 3).map((k) => (
          <span
            key={k}
            className="rounded-full border border-cyan-accent/20 bg-cyan-accent/5 px-2 py-0.5 font-mono text-[10px] text-cyan-accent/80"
          >
            {k}
          </span>
        ))}
      </div>
    </a>
  );
}
