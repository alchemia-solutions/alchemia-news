import type { CorporateProgram } from '@/lib/types';
import { CORPORATE_REGION_LABELS, PRIORITY_LABELS } from '@/lib/types';
import StatusTracker from '@/components/StatusTracker';

const PRIORITY_BADGE: Record<CorporateProgram['priority_alchemia'], string> = {
  alta: 'text-cyan-accent border-cyan-accent/30 bg-cyan-accent/10',
  media: 'text-status-progress border-status-progress/30 bg-status-progress/10',
  complementar: 'text-slate-400 border-slate-500/30 bg-slate-500/5',
};

export default function CorporateProgramCard({ program }: { program: CorporateProgram }) {
  return (
    <div className="alchemia-card flex h-full flex-col p-5">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div>
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <h3 className="font-medium text-slate-100">{program.name}</h3>
            <span
              className={`rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide ${PRIORITY_BADGE[program.priority_alchemia]}`}
            >
              {PRIORITY_LABELS[program.priority_alchemia]}
            </span>
          </div>
          <p className="font-mono text-[11px] text-slate-400">{CORPORATE_REGION_LABELS[program.region]}</p>
        </div>
        <a
          href={program.portal_url}
          target="_blank"
          rel="noopener noreferrer"
          className="whitespace-nowrap rounded border border-cyan-accent/30 px-2 py-1 font-mono text-[11px] text-cyan-accent hover:bg-cyan-accent/10"
        >
          abrir ↗
        </a>
      </div>

      <p className="mb-2 font-mono text-[11px] text-cyan-accent/80">{program.priority_note}</p>

      <p className="mb-3 text-[13px] leading-relaxed text-slate-400">{program.benefit_summary}</p>

      <div className="mb-3">
        <p className="mb-1 font-mono text-[10px] uppercase tracking-wide text-slate-400">Elegibilidade</p>
        <p className="text-[12px] leading-relaxed text-slate-400">{program.eligibility_summary}</p>
      </div>

      <div className="mt-auto flex items-center justify-between gap-3 border-t border-white/5 pt-3">
        <p className="font-mono text-[10px] text-slate-400">
          direcional, confirmar na fonte oficial · rev. {program.last_reviewed}
        </p>
        <StatusTracker slug={program.slug} />
      </div>
    </div>
  );
}
