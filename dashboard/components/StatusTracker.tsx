'use client';

import { useEffect, useState } from 'react';

/**
 * Tracker de status por oportunidade (edital/programa), persistido em `localStorage` no
 * navegador de quem usa -- Fase 1 da spec 2026-08-19 é explicitamente client-side, sem backend
 * novo, sem multiusuário (isso é Fase 3, backlog). Cada instância é independente, chaveada pelo
 * `slug` da oportunidade -- funciona igual em `/fomento` e `/programas` sem coordenação entre as
 * duas páginas.
 */

const STATUSES = ['nao_aplicado', 'em_preparacao', 'submetido', 'aprovado', 'rejeitado'] as const;
export type OpportunityStatus = (typeof STATUSES)[number];

const STATUS_LABELS: Record<OpportunityStatus, string> = {
  nao_aplicado: 'Não aplicado',
  em_preparacao: 'Em preparação',
  submetido: 'Submetido',
  aprovado: 'Aprovado',
  rejeitado: 'Rejeitado',
};

const STATUS_COLOR: Record<OpportunityStatus, string> = {
  nao_aplicado: 'text-slate-400 border-slate-500/30 bg-slate-500/5',
  em_preparacao: 'text-status-start border-status-start/30 bg-status-start/10',
  submetido: 'text-status-progress border-status-progress/30 bg-status-progress/10',
  aprovado: 'text-status-done border-status-done/30 bg-status-done/10',
  rejeitado: 'text-status-risk border-status-risk/30 bg-status-risk/10',
};

function storageKey(slug: string): string {
  return `alchemia-news:opportunity-status:${slug}`;
}

function isStatus(value: string | null): value is OpportunityStatus {
  return value !== null && (STATUSES as readonly string[]).includes(value);
}

export default function StatusTracker({ slug }: { slug: string }) {
  const [status, setStatus] = useState<OpportunityStatus>('nao_aplicado');
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(storageKey(slug));
      if (isStatus(raw)) setStatus(raw);
    } catch {
      // localStorage indisponível (modo privado etc.) -- segue com o estado padrão em memória
    }
    setHydrated(true);
  }, [slug]);

  function update(next: OpportunityStatus) {
    setStatus(next);
    try {
      window.localStorage.setItem(storageKey(slug), next);
    } catch {
      // best-effort -- sem persistência não é erro fatal, só não sobrevive ao reload
    }
  }

  // Placeholder de mesma altura antes da hidratação -- evita "flash" trocando de nao_aplicado
  // para o valor salvo assim que o localStorage é lido.
  if (!hydrated) {
    return <div className="h-[26px] w-full max-w-[160px] rounded border border-transparent" aria-hidden />;
  }

  return (
    <select
      value={status}
      onChange={(e) => update(e.target.value as OpportunityStatus)}
      aria-label={`Status da candidatura — ${slug}`}
      className={`w-full max-w-[160px] cursor-pointer rounded border px-2 py-1 font-mono text-[11px] focus:outline-none ${STATUS_COLOR[status]}`}
    >
      {STATUSES.map((s) => (
        <option key={s} value={s} className="bg-navy-900 text-slate-200">
          {STATUS_LABELS[s]}
        </option>
      ))}
    </select>
  );
}
