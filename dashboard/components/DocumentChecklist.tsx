'use client';

import { useEffect, useState } from 'react';

/**
 * Checklist de documentos "que vale para 90% dos programas" -- transcrito da seção 11 do guia
 * `guia-captacao-programas-corporativos-startups.md` ("Prepare uma vez, reutilize sempre").
 * Persistido em `localStorage`, uma chave só, deliberadamente compartilhada entre `/fomento` e
 * `/programas` -- é um preparo único da empresa, não algo específico de uma página.
 */

const STORAGE_KEY = 'alchemia-news:document-checklist';

interface ChecklistItem {
  id: string;
  label: string;
}

const CHECKLIST_ITEMS: ChecklistItem[] = [
  { id: 'cnpj-cnae', label: 'CNPJ ativo com CNAE compatível (pesquisa e desenvolvimento / atividades de biotecnologia)' },
  { id: 'site-institucional', label: 'Site institucional funcional em domínio próprio' },
  { id: 'email-corporativo', label: 'E-mail corporativo no domínio da empresa (não Gmail)' },
  { id: 'descricao-produto-en', label: 'Descrição do produto em inglês (150 e 500 palavras)' },
  { id: 'pitch-deck-en', label: 'Pitch deck em inglês (10–12 slides)' },
  { id: 'data-constituicao', label: 'Data de constituição e comprovante' },
  { id: 'headcount-fundadores', label: 'Headcount e nomes dos fundadores com LinkedIn' },
  { id: 'estagio-funding', label: 'Estágio de funding e comprovação (term sheet, SAFE, extrato de aporte)' },
  { id: 'descricao-tecnica', label: 'Descrição técnica da arquitetura e da carga computacional prevista' },
  { id: 'perfil-uso-gpu', label: 'Perfil de uso de GPU (para NVIDIA e tiers de IA)' },
  { id: 'lattes-atualizado', label: 'Currículo Lattes atualizado dos pesquisadores-chave (para os programas nacionais)' },
  { id: 'carta-ict', label: 'Comprovante de vínculo ou carta de anuência de ICT parceira, se houver' },
];

function readChecked(): Set<string> {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? new Set(parsed.filter((x) => typeof x === 'string')) : new Set();
  } catch {
    return new Set();
  }
}

export default function DocumentChecklist() {
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setChecked(readChecked());
    setHydrated(true);
  }, []);

  function toggle(id: string) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify([...next]));
      } catch {
        // best-effort -- sem persistência não é erro fatal
      }
      return next;
    });
  }

  const total = CHECKLIST_ITEMS.length;
  const done = hydrated ? checked.size : 0;

  return (
    <div className="alchemia-card p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-mono text-[13px] uppercase tracking-wide text-cyan-accent">Checklist de documentos</h2>
        <span className="font-mono text-[12px] text-slate-400">
          {done}/{total} completos
        </span>
      </div>
      <p className="mb-4 text-[12px] leading-relaxed text-slate-400">
        Documentos que valem para ~90% dos programas (guia de captação, seção 11) — prepare uma vez,
        reutilize em toda candidatura. Salvo só neste navegador.
      </p>
      <ul className="space-y-2">
        {CHECKLIST_ITEMS.map((item) => {
          const isChecked = hydrated && checked.has(item.id);
          return (
            <li key={item.id}>
              <label className="flex cursor-pointer items-start gap-2.5 text-[13px] text-slate-300">
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={() => toggle(item.id)}
                  className="mt-0.5 h-4 w-4 shrink-0 rounded border-white/20 bg-navy-800/60 accent-cyan-400"
                />
                <span className={isChecked ? 'text-slate-400 line-through decoration-slate-600' : ''}>
                  {item.label}
                </span>
              </label>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
