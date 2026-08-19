import 'server-only';
import fs from 'fs';
import path from 'path';
import yaml from 'js-yaml';
import type { CompanyConfig, NewsItem, PipelineMeta, ResourceConfig } from './types';

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

export function getArticles(): NewsItem[] {
  return readJsonSafe<NewsItem[]>(path.join(DATA_DIR, 'articles.json'), []);
}

export function getNews(): NewsItem[] {
  return readJsonSafe<NewsItem[]>(path.join(DATA_DIR, 'news.json'), []);
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
