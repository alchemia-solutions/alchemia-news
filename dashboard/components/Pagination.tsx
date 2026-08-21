import Link from 'next/link';

/**
 * Paginação por `?page=N` para as listas longas (/noticias, /artigos).
 *
 * Por que existe (2026-08-21): as duas rotas renderizavam a lista inteira no servidor — 491 e 500
 * cartões — entregando **3,36 MB e 1,94 MB de HTML** em 3,2 s e 2,5 s, medidos mornos com o cache
 * do Supabase quente (achados N1/N2, `docs/qc/2026-08-21-frontend-quality-dashboard.md`). As outras
 * sete rotas do app ficam entre 23 KB e 280 KB, o que prova que não era arquitetura — eram essas
 * duas telas. Em 4G real, 3,36 MB são mais de 13 s só de transferência.
 *
 * O teto de 500 itens de 2026-08-20 resolveu o custo *da consulta* ao Supabase; o custo de
 * *renderizar e transmitir* continuou inteiro. Paginar resolve os dois de uma vez, e — diferente
 * de virtualizar no cliente — mantém o histórico inteiro alcançável, cada página com URL própria,
 * compartilhável e indexável.
 *
 * Server component de propósito: nenhum JavaScript de cliente é necessário para navegar entre
 * páginas, e a navegação continua funcionando com JS desabilitado.
 */
export const PAGE_SIZE = 60;

export function paginar<T>(itens: T[], pagina: number): { fatia: T[]; total: number; paginas: number; atual: number } {
  const total = itens.length;
  const paginas = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const atual = Math.min(Math.max(1, pagina), paginas);
  const inicio = (atual - 1) * PAGE_SIZE;
  return { fatia: itens.slice(inicio, inicio + PAGE_SIZE), total, paginas, atual };
}

/** Lê `?page=` com tolerância: valor ausente, vazio, não-numérico ou <= 0 vira 1. */
export function lerPagina(valor: string | undefined): number {
  const n = Number.parseInt(valor ?? '', 10);
  return Number.isFinite(n) && n > 0 ? n : 1;
}

function href(base: string, pagina: number, fonte?: string): string {
  const p = new URLSearchParams();
  if (fonte) p.set('fonte', fonte);
  if (pagina > 1) p.set('page', String(pagina));
  const qs = p.toString();
  return qs ? `${base}?${qs}` : base;
}

/** Janela curta de páginas ao redor da atual — nunca imprime 40 links de página. */
function janela(atual: number, paginas: number): number[] {
  const raio = 2;
  const inicio = Math.max(1, Math.min(atual - raio, paginas - raio * 2));
  const fim = Math.min(paginas, Math.max(atual + raio, raio * 2 + 1));
  const out: number[] = [];
  for (let i = inicio; i <= fim; i++) out.push(i);
  return out;
}

const BASE =
  'rounded-lg border px-3 py-1.5 font-mono text-[12px] transition-colors ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-accent focus-visible:ring-offset-2 focus-visible:ring-offset-navy-950';
const IDLE = 'border-white/10 text-slate-400 hover:border-cyan-accent/40 hover:text-white';
const ATIVO = 'border-cyan-accent/40 bg-cyan-accent/10 text-cyan-accent';
const INERTE = 'border-white/5 text-slate-600';

export default function Pagination({
  base,
  fonte,
  atual,
  paginas,
  total,
}: {
  base: string;
  fonte?: string;
  atual: number;
  paginas: number;
  total: number;
}) {
  if (paginas <= 1) return null;

  const primeiro = (atual - 1) * PAGE_SIZE + 1;
  const ultimo = Math.min(atual * PAGE_SIZE, total);

  return (
    <nav aria-label="Paginação" className="mt-8 flex flex-wrap items-center gap-2 border-t border-white/5 pt-6">
      <p className="mr-auto font-mono text-[12px] text-slate-400">
        <span className="tabular-nums">
          {primeiro}–{ultimo}
        </span>{' '}
        de <span className="tabular-nums">{total}</span>
      </p>

      {atual > 1 ? (
        <Link href={href(base, atual - 1, fonte)} className={`${BASE} ${IDLE}`} rel="prev">
          ← Anterior
        </Link>
      ) : (
        <span className={`${BASE} ${INERTE}`} aria-hidden="true">
          ← Anterior
        </span>
      )}

      {janela(atual, paginas).map((p) => (
        <Link
          key={p}
          href={href(base, p, fonte)}
          aria-current={p === atual ? 'page' : undefined}
          className={`${BASE} ${p === atual ? ATIVO : IDLE} tabular-nums`}
        >
          {p}
        </Link>
      ))}

      {atual < paginas ? (
        <Link href={href(base, atual + 1, fonte)} className={`${BASE} ${IDLE}`} rel="next">
          Próxima →
        </Link>
      ) : (
        <span className={`${BASE} ${INERTE}`} aria-hidden="true">
          Próxima →
        </span>
      )}
    </nav>
  );
}
