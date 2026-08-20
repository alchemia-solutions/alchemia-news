import 'server-only';
import fs from 'fs';
import path from 'path';
import yaml from 'js-yaml';
import { unstable_cache } from 'next/cache';
import type { CompanyConfig, CorporateProgram, FundingChannel, ItemKind, NewsItem, PipelineMeta, ResourceConfig } from './types';
import {
  countItemsByKind,
  fetchAllNewsletters,
  fetchCompanies,
  fetchCompanyActivity,
  fetchCorporatePrograms,
  fetchFundingChannels,
  fetchItemsByKind,
  fetchNewsletterByDate,
  fetchPipelineMeta,
  fetchResources,
} from './supabase';

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

// Fase 2 (2026-08-20, mais tarde) -- expande a leitura do Supabase para o resto do
// dashboard (antes só articles/news). "sem precisar commitar nada depois" era o
// pedido explícito do fundador -- companies/resources/funding_channels/
// corporate_programs/meta/newsletter agora vêm todos do Supabase, sincronizados
// pelo pipeline (ou pela rotina do Axel, no caso da newsletter) 3x/dia. Os arquivos
// locais (readJsonSafe/readYamlSafe acima) viram **rede de segurança**: se o
// Supabase não responder ou a tabela vier vazia, cai para o último snapshot local
// conhecido em vez de mostrar a página em branco -- mesmo princípio já usado no
// fallback pipeline ao vivo -> `.pipeline-data` (ver DATA_DIR/CONFIG_DIR acima).
// Todas cacheadas por 5min via unstable_cache, mesmo padrão de getArticles/getNews.

const getCachedCompanyActivity = unstable_cache(
  async () => fetchCompanyActivity(),
  ['company-activity'],
  { revalidate: 300 }
);

export async function getCompaniesActivity(): Promise<NewsItem[]> {
  const rows = await getCachedCompanyActivity();
  if (rows.length > 0) return rows;
  return readJsonSafe<NewsItem[]>(path.join(DATA_DIR, 'companies_activity.json'), []);
}

const getCachedPipelineMeta = unstable_cache(
  async () => fetchPipelineMeta(),
  ['pipeline-meta'],
  { revalidate: 300 }
);

export async function getPipelineMeta(): Promise<PipelineMeta | null> {
  const meta = await getCachedPipelineMeta();
  if (meta) return meta;
  return readJsonSafe<PipelineMeta | null>(path.join(DATA_DIR, 'meta.json'), null);
}

const getCachedCompanies = unstable_cache(async () => fetchCompanies(), ['companies-catalog'], { revalidate: 300 });

export async function getCompanies(): Promise<CompanyConfig[]> {
  const rows = await getCachedCompanies();
  if (rows.length > 0) return rows;
  const parsed = readYamlSafe<{ companies?: CompanyConfig[] }>(path.join(CONFIG_DIR, 'companies.yaml'), {});
  return parsed.companies ?? [];
}

const getCachedResources = unstable_cache(async () => fetchResources(), ['resources-catalog'], { revalidate: 300 });

export async function getResources(): Promise<ResourceConfig[]> {
  const rows = await getCachedResources();
  if (rows.length > 0) return rows;
  const parsed = readYamlSafe<{ resources?: ResourceConfig[] }>(path.join(CONFIG_DIR, 'resources.yaml'), {});
  return parsed.resources ?? [];
}

// Fase 2 (2026-08-19) -- catálogo estático, curado a partir dos dois guias de referência do
// fundador; nenhuma coleta/LLM envolvida. Ver docs/specs/2026-08-19-funding-opportunities-and-app-restructure.md.
const getCachedFundingChannels = unstable_cache(
  async () => fetchFundingChannels(),
  ['funding-channels-catalog'],
  { revalidate: 300 }
);

export async function getFundingChannels(): Promise<FundingChannel[]> {
  const rows = await getCachedFundingChannels();
  if (rows.length > 0) return rows;
  const parsed = readYamlSafe<{ funding_channels?: FundingChannel[] }>(
    path.join(CONFIG_DIR, 'funding_channels.yaml'),
    {}
  );
  return parsed.funding_channels ?? [];
}

const getCachedCorporatePrograms = unstable_cache(
  async () => fetchCorporatePrograms(),
  ['corporate-programs-catalog'],
  { revalidate: 300 }
);

export async function getCorporatePrograms(): Promise<CorporateProgram[]> {
  const rows = await getCachedCorporatePrograms();
  if (rows.length > 0) return rows;
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

function listLocalNewsletterFiles(): string[] {
  const dir = path.join(DATA_DIR, 'newsletter');
  try {
    if (!fs.existsSync(dir)) return [];
    return fs
      .readdirSync(dir)
      .filter((f) => /^\d{4}-\d{2}-\d{2}\.md$/.test(f))
      .sort()
      .reverse(); // mais recente primeiro -- nome AAAA-MM-DD.md ordena lexicograficamente como data
  } catch {
    return [];
  }
}

function readLocalNewsletter(dateStr: string): NewsletterEdition | null {
  const dir = path.join(DATA_DIR, 'newsletter');
  try {
    const content = fs.readFileSync(path.join(dir, `${dateStr}.md`), 'utf-8');
    return { date: dateStr, content };
  } catch {
    return null;
  }
}

const getCachedAllNewsletters = unstable_cache(async () => fetchAllNewsletters(), ['all-newsletters'], {
  revalidate: 300,
});

// Rota /newsletter (lista) -- 2026-08-20 (mais tarde): virou uma lista navegável por
// data, não mais só a edição mais recente com o texto inteiro exposto (achado do
// fundador: mostrar prévia, abrir completo só ao clicar -- ver app/newsletter/page.tsx
// e app/newsletter/[date]/page.tsx). Lê do Supabase (tabela `newsletters`, escrita pela
// rotina do Axel); cai para a lista de arquivos locais se a tabela vier vazia.
export async function getNewsletters(): Promise<NewsletterEdition[]> {
  const fromSupabase = await getCachedAllNewsletters();
  if (fromSupabase.length > 0) return fromSupabase;
  return listLocalNewsletterFiles()
    .map((file) => readLocalNewsletter(file.replace(/\.md$/, '')))
    .filter((edition): edition is NewsletterEdition => edition !== null);
}

const getCachedNewsletterByDate = unstable_cache(
  async (dateStr: string) => fetchNewsletterByDate(dateStr),
  ['newsletter-by-date'],
  { revalidate: 300 }
);

// Rota /newsletter/[date] (detalhe) -- conteúdo completo de uma edição específica.
export async function getNewsletterByDate(dateStr: string): Promise<NewsletterEdition | null> {
  const fromSupabase = await getCachedNewsletterByDate(dateStr);
  if (fromSupabase) return fromSupabase;
  return readLocalNewsletter(dateStr);
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

// Prévia curta de uma edição de newsletter para a lista (/newsletter) -- extrai a
// linha de metadado ("_Atualizado às HH:MM · N achados..._") como subtítulo, e as
// primeiras ~200 caracteres de texto corrido depois dela como resumo, com sintaxe de
// markdown removida (não precisa de MarkdownLite para um trecho curto e sem link).
export function previewNewsletter(content: string): { meta: string; excerpt: string } {
  const lines = content.replace(/\r\n/g, '\n').split('\n');
  const metaLine = lines.find((l) => l.trim().startsWith('_Atualizado'));
  const meta = metaLine ? metaLine.trim().replace(/^_|_$/g, '') : '';

  const bodyLines = lines
    .filter((l) => {
      const t = l.trim();
      if (!t) return false;
      if (t.startsWith('#')) return false; // títulos
      if (t === metaLine?.trim()) return false;
      if (/^(---|\*\*\*)$/.test(t)) return false;
      return true;
    })
    .join(' ')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/\s+/g, ' ')
    .trim();

  const excerpt = bodyLines.length > 220 ? `${bodyLines.slice(0, 220).trimEnd()}…` : bodyLines;
  return { meta, excerpt };
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return 'Data desconhecida';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'Data desconhecida';
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' });
}
