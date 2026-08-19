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

// Fase 2 (2026-08-19) -- editais de fomento e programas corporativos. Família de dado separada
// de `NewsItem`/`ResourceConfig`: catálogo de referência de vida longa, não evento datado que se
// acumula/dedupe. Ver docs/specs/2026-08-19-funding-opportunities-and-app-restructure.md,
// "Arquitetura/Stack" -- deliberadamente NÃO é um union type de ItemKind.

export type FundingScope =
  | 'federal'
  | 'estadual_sp'
  | 'saude'
  | 'universidade_ict'
  | 'fundacao_privada'
  | 'internacional';

export type PriorityAlchemia = 'alta' | 'media' | 'complementar';

export interface FundingProgramNote {
  name: string;
  note: string;
}

export interface FundingChannel {
  slug: string;
  name: string;
  full_name: string;
  scope: FundingScope;
  portal_url: string;
  calls_url: string;
  programs?: FundingProgramNote[];
  priority_alchemia: PriorityAlchemia;
  priority_note: string;
  requires?: string[];
  source_guide: string;
  last_reviewed: string;
}

export type CorporateProgramCategory =
  | 'cloud_credits'
  | 'saas_discount'
  | 'accelerator_no_equity'
  | 'accelerator_equity'
  | 'habitat_nacional'
  | 'hub_corporativo';

export type CorporateProgramRegion = 'global' | 'brasil' | 'sp';

export interface CorporateProgram {
  slug: string;
  name: string;
  category: CorporateProgramCategory;
  region: CorporateProgramRegion;
  portal_url: string;
  benefit_summary: string;
  eligibility_summary: string;
  priority_alchemia: PriorityAlchemia;
  priority_note: string;
  source_guide: string;
  last_reviewed: string;
}

export const FUNDING_SCOPE_LABELS: Record<FundingScope, string> = {
  federal: 'Federal',
  estadual_sp: 'Estadual — São Paulo',
  saude: 'Saúde',
  universidade_ict: 'Universidades & ICTs',
  fundacao_privada: 'Fundações Privadas',
  internacional: 'Internacional',
};

export const CORPORATE_CATEGORY_LABELS: Record<CorporateProgramCategory, string> = {
  cloud_credits: 'Créditos de Nuvem',
  saas_discount: 'SaaS para Startups',
  accelerator_no_equity: 'Aceleradora (sem equity)',
  accelerator_equity: 'Aceleradora (com equity)',
  habitat_nacional: 'Habitat/Parque Nacional',
  hub_corporativo: 'Hub Corporativo',
};

export const CORPORATE_REGION_LABELS: Record<CorporateProgramRegion, string> = {
  global: 'Global',
  brasil: 'Brasil',
  sp: 'São Paulo',
};

export const PRIORITY_LABELS: Record<PriorityAlchemia, string> = {
  alta: 'Recomendado para a Alchemia',
  media: 'Prioridade média',
  complementar: 'Complementar',
};

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
