import { getPipelineMeta, timeAgo } from '@/lib/data';

// Faixa de estado do pipeline, em todas as rotas (montada no layout raiz).
//
// Por que existe (2026-08-21): em 21/08 a coleta agendada das 12:40 morreu no meio do coletor
// `biorxiv` (Ctrl+C, exit 0xC000013A). As etapas 2 e 3 da cadeia -- radar do alchemia-science e
// sincronização com o Supabase -- nunca rodaram naquele ciclo. A rotina do Baker cobriu a falha
// dez minutos depois e o banco ficou correto, mas **nada disso ficou visível para ninguém**: a
// Tarefa Agendada segue marcada como `Ready`, e o código de falha só aparece para quem abrir o
// Task Scheduler. Se o Baker não tivesse coberto, o site teria congelado mostrando dado velho
// sem nenhum sinal.
//
// Esta faixa é a metade "estado" do alarme; a metade "evento" é a mensagem do Axel num canal
// privado do Discord (ver alchemia-ai/alchemia-bots/scripts/). As duas são deliberadamente
// diferentes: a faixa responde "como está agora?" a qualquer momento, o Discord avisa uma vez
// quando muda. Nenhuma das duas dispara em sucesso -- alarme que toca sempre é alarme ignorado.
//
// Silenciosa quando está tudo bem: sem `meta` (Supabase fora do ar) ou dentro da janela normal,
// não renderiza nada. Não vale ocupar espaço permanente para dizer "ok".

// A coleta roda 3x/dia (06:40 · 12:40 · 18:40), ou seja, a cada 6h. `STALE_HOURS` precisa ser
// maior que o intervalo (senão alarma falso entre ciclos normais) e menor que dois intervalos
// (senão um ciclo inteiro perdido passa despercebido) -- que era exatamente o buraco do passo 3b
// da rotina do Baker, cuja tolerância de ~7h é maior que os 6h entre ciclos.
const STALE_HOURS = 8;
const CRITICAL_HOURS = 14; // dois ciclos perdidos

type Health =
  | { level: 'ok' }
  | { level: 'stale' | 'critical'; hours: number; when: string }
  | { level: 'collector'; failed: string[]; when: string };

function assess(
  meta: Awaited<ReturnType<typeof getPipelineMeta>>,
  now: number
): Health {
  if (!meta?.last_run_finished) return { level: 'ok' };

  const finished = new Date(meta.last_run_finished).getTime();
  if (Number.isNaN(finished)) return { level: 'ok' };

  const hours = (now - finished) / 3_600_000;
  const when = timeAgo(meta.last_run_finished);

  if (hours >= CRITICAL_HOURS) return { level: 'critical', hours, when };
  if (hours >= STALE_HOURS) return { level: 'stale', hours, when };

  // Coleta recente, mas algum coletor devolveu erro. Desde 2026-08-18 um feed bloqueado sobe
  // como `error` de verdade em vez de "0 itens, tudo bem" -- então isto pega bloqueio de fonte,
  // não só queda de rede.
  const failed = Object.entries(meta.collectors ?? {})
    .filter(([, result]) => result?.error)
    .map(([name]) => name);

  if (failed.length > 0) return { level: 'collector', failed, when };
  return { level: 'ok' };
}

const STYLES = {
  stale: 'border-status-start/40 bg-status-start/10 text-status-start',
  critical: 'border-status-risk/40 bg-status-risk/10 text-status-risk',
  collector: 'border-status-start/40 bg-status-start/10 text-status-start',
} as const;

export default async function PipelineHealthBanner() {
  const meta = await getPipelineMeta();
  const health = assess(meta, Date.now());

  if (health.level === 'ok') return null;

  const { title, detail } =
    health.level === 'collector'
      ? {
          title: `${health.failed.length} coletor(es) com erro na última coleta`,
          detail: `${health.failed.join(', ')} · coleta de ${health.when}. Os demais coletores rodaram normalmente.`,
        }
      : {
          title:
            health.level === 'critical'
              ? 'A coleta não roda há mais de dois ciclos'
              : 'A coleta está atrasada',
          detail: `Última coleta concluída ${health.when} (esperado a cada 6h — 06:40, 12:40 e 18:40). Os números abaixo podem não refletir o dia de hoje.`,
        };

  return (
    <div
      role="status"
      className={`mb-6 flex items-start gap-3 rounded-xl border px-4 py-3 ${STYLES[health.level]}`}
    >
      <span aria-hidden="true" className="mt-0.5 flex-none font-mono text-sm leading-none">
        ▲
      </span>
      <div className="min-w-0">
        <p className="font-mono text-[13px] font-semibold leading-snug">{title}</p>
        <p className="mt-1 text-[13px] leading-relaxed text-slate-300">{detail}</p>
      </div>
    </div>
  );
}
