export type ItemKind = 'article' | 'news';

export interface NewsItem {
  kind: ItemKind;
  title: string;
  url: string;
  source: string;
  source_type: string;
  published_date: string | null;
  collected_at: string;
  authors: string[];
  summary: string;
  doi: string | null;
  company_slug: string | null;
  keywords_matched: string[];
  extra: Record<string, unknown>;
  dedupe_key: string;
}

export interface CompanyConfig {
  slug: string;
  name: string;
  url: string;
  category: string;
  method: string;
  filter_relevance: boolean;
  logo_hint?: string;
}

export interface ResourceConfig {
  slug: string;
  name: string;
  full_name: string;
  url: string;
  type: string;
  description: string;
  license_note: string;
}

export interface CollectorResult {
  count?: number;
  seconds?: number;
  error?: string | null;
  skipped?: boolean;
}

export interface PipelineMeta {
  last_run_started: string;
  last_run_finished: string;
  duration_seconds: number;
  collectors: Record<string, CollectorResult>;
  totals: {
    articles: number;
    news: number;
    companies_activity: number;
    new_articles_this_run: number;
    new_news_this_run: number;
    new_companies_activity_this_run: number;
  };
}

export const CATEGORY_LABELS: Record<string, string> = {
  ai_drug_discovery: 'AI Drug Discovery',
  cadd_platform: 'Plataforma CADD',
  biotech_ai: 'Biotech + IA',
  big_tech_ai: 'Big Tech / IA Geral',
  br_institution: 'Instituição Brasileira',
  bioinformatics_resource: 'Recurso de Bioinformática',
};

export const RESOURCE_TYPE_LABELS: Record<string, string> = {
  molecule_database: 'Banco de Moléculas',
  cadd_tool: 'Ferramenta CADD',
  tool_directory: 'Diretório de Ferramentas',
};

export const SOURCE_TYPE_LABELS: Record<string, string> = {
  journal: 'Periódico',
  preprint: 'Preprint',
  news: 'Notícia',
  company_blog: 'Blog Oficial',
  press: 'Imprensa',
  // Adicionado 2026-08-18 junto da seção `newsletter_feeds` do pipeline (Drug Hunter,
  // Longevity.Technology, Fierce Biotech, BioPharma Dive, Labiotech). Tipo próprio de propósito:
  // newsletter curada tem sinal bem mais alto que o feed genérico do Google News, e precisa ser
  // distinguível na interface e no radar diário.
  newsletter: 'Newsletter',
};
