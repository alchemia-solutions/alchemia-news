'use client';

import { useMemo, useState } from 'react';
import type { PriorityAlchemia } from '@/lib/types';
import { PRIORITY_LABELS } from '@/lib/types';

/**
 * Filtro + busca reutilizável para os catálogos de oportunidade (`/fomento` e `/programas`).
 *
 * Server Components não podem passar funções como prop para Client Components (a fronteira RSC
 * só serializa dado + elementos React já renderizados) -- por isso este componente não recebe um
 * "render prop" de cartão. Em vez disso, cada página server-renderiza o cartão de cada item
 * (`node`) e passa junto o metadado de filtragem (`category`/`priority`/`searchText`) já
 * serializado. O componente decide, no cliente, quais `node`s mostrar -- o cartão em si nunca é
 * re-renderizado no cliente, só mostrado/escondido.
 */

export interface OpportunityFilterEntry {
  slug: string;
  category: string;
  priority: PriorityAlchemia;
  searchText: string;
  node: React.ReactNode;
}

const PRIORITY_ORDER: PriorityAlchemia[] = ['alta', 'media', 'complementar'];

export default function OpportunityFilterBar({
  entries,
  categoryLabels,
  categoryFieldLabel = 'Categoria',
}: {
  entries: OpportunityFilterEntry[];
  categoryLabels: Record<string, string>;
  categoryFieldLabel?: string;
}) {
  const [category, setCategory] = useState('all');
  const [priority, setPriority] = useState<'all' | PriorityAlchemia>('all');
  const [query, setQuery] = useState('');

  const categories = useMemo(() => {
    const seen = new Set<string>();
    const ordered: string[] = [];
    for (const e of entries) {
      if (!seen.has(e.category)) {
        seen.add(e.category);
        ordered.push(e.category);
      }
    }
    return ordered;
  }, [entries]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return entries.filter((e) => {
      if (category !== 'all' && e.category !== category) return false;
      if (priority !== 'all' && e.priority !== priority) return false;
      if (q && !e.searchText.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [entries, category, priority, query]);

  const grouped = useMemo(() => {
    const acc: Record<string, OpportunityFilterEntry[]> = {};
    for (const e of filtered) {
      (acc[e.category] ??= []).push(e);
    }
    return acc;
  }, [filtered]);

  const hasActiveFilter = category !== 'all' || priority !== 'all' || query.trim() !== '';

  return (
    <div>
      <div className="alchemia-card mb-6 flex flex-wrap items-center gap-3 p-4">
        <div className="flex-1 min-w-[200px]">
          <label className="mb-1 block font-mono text-[10px] uppercase tracking-wide text-slate-400">
            Buscar
          </label>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Nome, órgão, programa…"
            aria-label="Buscar oportunidade"
            className="w-full rounded border border-white/10 bg-navy-800/60 px-3 py-1.5 text-[13px] text-slate-200 placeholder:text-slate-400 focus:border-cyan-accent/50 focus:outline-none"
          />
        </div>

        <div>
          <label className="mb-1 block font-mono text-[10px] uppercase tracking-wide text-slate-400">
            {categoryFieldLabel}
          </label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            aria-label={categoryFieldLabel}
            className="rounded border border-white/10 bg-navy-800/60 px-3 py-1.5 text-[13px] text-slate-200 focus:border-cyan-accent/50 focus:outline-none"
          >
            <option value="all">Todas</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {categoryLabels[c] ?? c}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1 block font-mono text-[10px] uppercase tracking-wide text-slate-400">
            Prioridade
          </label>
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value as 'all' | PriorityAlchemia)}
            aria-label="Prioridade"
            className="rounded border border-white/10 bg-navy-800/60 px-3 py-1.5 text-[13px] text-slate-200 focus:border-cyan-accent/50 focus:outline-none"
          >
            <option value="all">Todas</option>
            {PRIORITY_ORDER.map((p) => (
              <option key={p} value={p}>
                {PRIORITY_LABELS[p]}
              </option>
            ))}
          </select>
        </div>

        <div className="ml-auto flex items-center gap-3">
          <span className="font-mono text-[11px] text-slate-400">
            {filtered.length} de {entries.length}
          </span>
          {hasActiveFilter ? (
            <button
              type="button"
              onClick={() => {
                setCategory('all');
                setPriority('all');
                setQuery('');
              }}
              className="rounded border border-white/10 px-2.5 py-1 font-mono text-[11px] text-slate-400 hover:border-cyan-accent/30 hover:text-cyan-accent"
            >
              limpar filtros
            </button>
          ) : null}
        </div>
      </div>

      {filtered.length === 0 ? (
        <p className="text-sm text-slate-400">Nenhuma oportunidade encontrada com esses filtros.</p>
      ) : (
        Object.entries(grouped).map(([cat, list]) => (
          <div key={cat} className="mb-8">
            <h2 className="mb-3 font-mono text-[12px] uppercase tracking-wide text-slate-400">
              {categoryLabels[cat] ?? cat}
            </h2>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {list.map((e) => (
                <div key={e.slug}>{e.node}</div>
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
}
