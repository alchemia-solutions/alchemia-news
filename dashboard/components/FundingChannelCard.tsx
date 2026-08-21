import type { FundingChannel } from '@/lib/types';
import { PRIORITY_LABELS } from '@/lib/types';
import StatusTracker from '@/components/StatusTracker';

const PRIORITY_BADGE: Record<FundingChannel['priority_alchemia'], string> = {
  alta: 'text-cyan-accent border-cyan-accent/30 bg-cyan-accent/10',
  media: 'text-status-progress border-status-progress/30 bg-status-progress/10',
  complementar: 'text-slate-400 border-slate-500/30 bg-slate-500/5',
};

// Componente server-safe (sem 'use client') -- renderiza o cartão inteiro em tempo de
// requisição, exceto o <StatusTracker> embutido, que é client component e hidrata por conta
// própria. Nenhuma função é passada como prop entre fronteiras Server/Client aqui.
export default function FundingChannelCard({ channel }: { channel: FundingChannel }) {
  return (
    <div className="alchemia-card flex h-full flex-col p-5">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div>
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <h3 className="font-medium text-slate-100">{channel.name}</h3>
            <span
              className={`rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide ${PRIORITY_BADGE[channel.priority_alchemia]}`}
            >
              {PRIORITY_LABELS[channel.priority_alchemia]}
            </span>
          </div>
          <p className="font-mono text-[11px] text-slate-400">{channel.full_name}</p>
        </div>
        <a
          href={channel.calls_url || channel.portal_url}
          target="_blank"
          rel="noopener noreferrer"
          className="whitespace-nowrap rounded border border-cyan-accent/30 px-2 py-1 font-mono text-[11px] text-cyan-accent hover:bg-cyan-accent/10"
        >
          chamadas ↗
        </a>
      </div>

      <p className="mb-3 text-[13px] leading-relaxed text-slate-400">{channel.priority_note}</p>

      {channel.programs && channel.programs.length > 0 ? (
        <div className="mb-3">
          <p className="mb-1.5 font-mono text-[10px] uppercase tracking-wide text-slate-400">Programas</p>
          <ul className="space-y-1">
            {channel.programs.map((p) => (
              <li key={p.name} className="text-[12px] leading-snug text-slate-400">
                <span className="text-slate-200">{p.name}</span>
                {p.note ? <span className="text-slate-400"> — {p.note}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {channel.requires && channel.requires.length > 0 ? (
        <p className="mb-3 font-mono text-[11px] text-status-start">
          ⚑ Requer: {channel.requires.join(' · ')}
        </p>
      ) : null}

      <div className="mt-auto flex items-center justify-between gap-3 border-t border-white/5 pt-3">
        <div className="flex flex-wrap items-center gap-2 font-mono text-[10px] text-slate-400">
          <a href={channel.portal_url} target="_blank" rel="noopener noreferrer" className="hover:text-cyan-accent">
            portal ↗
          </a>
          <span>· direcional, confirmar na fonte oficial · rev. {channel.last_reviewed}</span>
        </div>
        <StatusTracker slug={channel.slug} />
      </div>
    </div>
  );
}
