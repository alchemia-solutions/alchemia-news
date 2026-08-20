import 'server-only';
import fs from 'fs';
import path from 'path';
import yaml from 'js-yaml';
import { unstable_cache } from 'next/cache';
import type { CompanyConfig, CorporateProgram, FundingChannel, ItemKind, NewsItem, PipelineMeta, ResourceConfig } from './types';
import { countItemsByKind, fetchItemsByKind } from './supabase';

// Este dashboard lê os JSONs produzidos pelo pipeline Python em tempo de requisição
// (server components, sem client-side fetch) -- qualquer execução nova do pipeline aparece aqui
// sem rebuild do Next.js. Ver docs/specs/2026-08-17-alchemia-news-intelligence-platform.md,
// "Estado Alvo".
const PIPELINE_DATA_DIR = path.join(process.cwd(), '..', 'pipeline', 'data');
const PIPELINE_CONFIG_DIR = path.join(process.cwd(), '..', 'pipeline', 'config');
const SNAPSHOT_DATA_DIR = path.join(process.cwd(), '.pipeline-data', 'data');
const SNAPSHOT_CONFIG_DIR = path.join(process.cwd(), '.pipeline-data', 'config');

// Rede de segurança para deploy (Vercel com Root Directory = dashboard/, ver
// scripts/copy-pipeline-data.js): se o caminho ao vivo não existir nesta árvore, cai para o
// snapshot copiado no prebuild. Em dev local o caminho ao vivo normalmente existe e é
// priorizado -- preserva o design deliberado de refletir o pipeline sem rebuild.
const DATA_DIR = fs.existsSync(PIPELINE_DATA_DIR) ? PIPELINE_DATA_DIR : SNAPSHOT_DATA_DIR;
const CONFIG_DIR = fs.existsSync(PIPELINE_CONFIG_DIR) ? PIPELINE_CONFIG_DIR : SNAPSHOT_CONFIG_DIR;

function readJsonSafe<T>(filePath: string, fallback: T): T {
  try {
    const raw = fs.readFileSync(filePath, 'utf-8');
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function readYamlSafe<T>(filePath: string, fallback: T): T {
  try {
    const raw = fs.readFileSync(filePath, 'utf-8');
    return yaml.load(raw) as T;
  } catch {
    return fallback;
  }
}

// 2026-08-20 -- lê do Supabase (tabela `items`, kind='article'/'news'), não mais de
// pipeline/data/articles.json e news.json. Isso é o que elimina a espera de
// redeploy: pipeline/sync_supabase.py escreve no Supabase logo após cada coleta, e
// este dashboard lê em tempo de requisição. Os JSONs locais continuam sendo
// escritos pelo pipeline (nada mudou lá) e continuam servindo companies_activity/
// meta/config -- só articles/news trocaram de fonte de leitura aqui. Ver
// dashboard/lib/supabase.ts.
//
// Achado de performance (2026-08-20, medido ao vivo): /noticias e /artigos usam
// `searchParams` (filtro por fonte), o que força renderização dinâmica no Next.js e
// ignora `export const revalidate` da página inteira (só funciona em rota sem
// searchParams/cookies/headers -- ver app/page.tsx). Por isso o cache é aplicado
// aqui, na função de busca em si, com `unstable_cache` -- ainda suportado nesta
// versão (substituído por `use cache`/Cache Components, que exige flag experimental
// não habilitada neste projeto; ver node_modules/next/dist/docs/.../unstable_cache.md).
// `kind` entra no array de keyParts porque unstable_cache também usa os argumentos
// da função na chave, mas ser explícito evita qualquer colisão entre 'article'/'news'.
const getCachedItemsByKind = unstable_cache(
  async (kind: ItemKind) => fetchItemsByKind(kind),
  ['items-by-kind'],
  { revalidate: 300 }
);

export async function getArticles(): Promise<NewsItem[]> {
  return getCachedItemsByKind('article');
}

export async function getNews(): Promise<NewsItem[]> {
  return getCachedItemsByKind('news');
}

// Contagem exata (não o tamanho da lista limitada acima) -- para números que
// precisam ser o total real, como os StatCard da home. `count: 'exact', head: true`
// no Postgres não transfere nenhuma linha, então é barato mesmo sem cache -- ainda
// assim cacheado pela mesma janela de 5min, para não gerar uma consulta extra por
// requisição à toa.
const getCachedCountByKind = unstable_cache(
  async (kind: ItemKind) => countItemsByKind(kind),
  ['items-count-by-kind'],
  { revalidate: 300 }
);

export async function getArticlesCount(): Promise<number> {
  return getCachedCountByKind('article');
}

export async function getNewsCount(): Promise<number> {
  return getCachedCountByKind('news');
}

export function getCompaniesActivity(): NewsItem[] {
  return readJsonSafe<NewsItem[]>(path.join(DATA_DIR, 'companies_activity.json'), []);
}

export function getPipelineMeta(): PipelineMeta | null {
  return readJsonSafe<PipelineMeta | null>(path.join(DATA_DIR, 'meta.json'), null);
}

export function getCompanies(): CompanyConfig[] {
  const parsed = readYamlSafe<{ companies?: CompanyConfig[] }>(
    path.join(CONFIG_DIR, 'companies.yaml'),
    {}
  );
  return parsed.companies ?? [];
}

export function getResources(): ResourceConfig[] {
  const parsed = readYamlSafe<{ resources?: ResourceConfig[] }>(
    path.join(CONFIG_DIR, 'resources.yaml'),
    {}
  );
  return parsed.resources ?? [];
}

// Fase 2 (2026-08-19) -- mesmo padrão de readYamlSafe já usado por getResources(). Catálogo
// estático, curado a partir dos dois guias de referência do fundador; nenhuma coleta/LLM
// envolvida. Ver docs/specs/2026-08-19-funding-opportunities-and-app-restructure.md.
export function getFundingChannels(): FundingChannel[] {
  const parsed = readYamlSafe<{ funding_channels?: FundingChannel[] }>(
    path.join(CONFIG_DIR, 'funding_channels.yaml'),
    {}
  );
  return parsed.funding_channels ?? [];
}

export function getCorporatePrograms(): CorporateProgram[] {
  const parsed = readYamlSafe<{ corporate_programs?: CorporateProgram[] }>(
    path.join(CONFIG_DIR, 'corporate_programs.yaml'),
    {}
  );
  return parsed.corporate_programs ?? [];
}

export interface NewsletterEdition {
  date: string;
  content: string;
}

// Rota /newsletter (2026-08-19) -- somente leitura. `pipeline/data/newsletter/AAAA-MM-DD.md` é
// populado por outro setor (alchemia-bots), rodando em paralelo -- este dashboard nunca escreve
// aqui. Se o diretório não existir ainda, ou estiver vazio, retorna null sem quebrar a rota (ver
// app/newsletter/page.tsx, estado vazio).
export function getLatestNewsletter(): NewsletterEdition | null {
  const dir = path.join(DATA_DIR, 'newsletter');
  try {
    if (!fs.existsSync(dir)) return null;
    const files = fs.readdirSync(dir).filter((f) => /^\d{4}-\d{2}-\d{2}\.md$/.test(f));
    if (files.length === 0) return null;
    files.sort(); // nome AAAA-MM-DD.md ordena lexicograficamente na mesma ordem que a data
    const latest = files[files.length - 1];
    const content = fs.readFileSync(path.join(dir, latest), 'utf-8');
    return { date: latest.replace(/\.md$/, ''), content };
  } catch {
    return null;
  }
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return 'data desconhecida';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return 'data desconhecida';
  const now = Date.now();
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'agora mesmo';
  if (diffMin < 60) return `${diffMin} min atrás`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH}h atrás`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 30) return `${diffD}d atrás`;
  const diffMonth = Math.floor(diffD / 30);
  return `${diffMonth}mês atrás`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return 'Data desconhecida';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'Data desconhecida';
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' });
}
