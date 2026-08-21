import PageHeader from '@/components/PageHeader';
import ItemCard from '@/components/ItemCard';
import Pagination, { lerPagina, paginar } from '@/components/Pagination';
import { getNews } from '@/lib/data';

// Achado de performance (2026-08-20): medido ao vivo em ~3.1s/requisição antes desta
// correção -- esta página consultava a tabela `news` inteira (~2.000 linhas) no Supabase
// a cada clique (`force-dynamic`), sem nenhum cache. O pipeline só sincroniza 3x/dia, então
// reconsultar a cada request não trazia frescor real. `revalidate` serve a mesma resposta
// cacheada por até 5 min e regenera em segundo plano -- ver o mesmo achado em
// app/artigos/page.tsx e app/page.tsx.
export const revalidate = 300;

export default async function NoticiasPage({
  searchParams,
}: {
  searchParams: Promise<{ fonte?: string; page?: string }>;
}) {
  const all = await getNews();
  const params = await searchParams;
  const fonteFiltro = params.fonte;
  const filtered = fonteFiltro ? all.filter((i) => i.source === fonteFiltro) : all;
  // Paginacao (2026-08-21, achados N1/N2): renderizar a lista inteira entregava MB de HTML
  // por requisicao. `paginar` fatia depois do filtro, para a contagem refletir o filtro ativo.
  const { fatia, total, paginas, atual } = paginar(filtered, lerPagina(params.page));

  const sourceCounts = Object.entries(
    all.reduce<Record<string, number>>((acc, i) => {
      acc[i.source] = (acc[i.source] ?? 0) + 1;
      return acc;
    }, {})
  ).sort((a, b) => b[1] - a[1]);

  return (
    <div>
      <PageHeader
        title="Notícias"
        description="Cobertura agregada de notícias sobre CADD, AI Drug Discovery e o nicho da Alchemia — Google News, feeds de periódicos e blogs oficiais. Cada card linka direto para a fonte original; nenhum conteúdo de terceiro é reproduzido aqui. Mostrando as mais recentes (não o histórico completo)."
      />

      <div className="mb-6 flex flex-wrap gap-2">
        <a
          href="/noticias"
          className={`rounded-full border px-3 py-1 font-mono text-[11px] ${
            !fonteFiltro ? 'border-cyan-accent bg-cyan-accent/10 text-cyan-accent' : 'border-white/10 text-slate-400 hover:border-white/30'
          }`}
        >
          Recentes ({all.length})
        </a>
        {sourceCounts.slice(0, 14).map(([source, count]) => (
          <a
            key={source}
            href={`/noticias?fonte=${encodeURIComponent(source)}`}
            className={`rounded-full border px-3 py-1 font-mono text-[11px] ${
              fonteFiltro === source
                ? 'border-cyan-accent bg-cyan-accent/10 text-cyan-accent'
                : 'border-white/10 text-slate-400 hover:border-white/30'
            }`}
          >
            {source} ({count})
          </a>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {fatia.map((item) => (
          <ItemCard key={item.dedupe_key} item={item} />
        ))}
      </div>
      <Pagination base="/noticias" fonte={fonteFiltro} atual={atual} paginas={paginas} total={total} />
      {filtered.length === 0 ? <p className="text-sm text-slate-400">Nenhuma notícia encontrada para este filtro.</p> : null}
    </div>
  );
}
