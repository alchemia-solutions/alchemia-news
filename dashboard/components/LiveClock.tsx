'use client';

import { useEffect, useState } from 'react';

/**
 * Pill "ao vivo" com relógio de idade desde a última coleta -- mesma convenção honesta já
 * validada em .claude/skills/realtime-dashboard/SKILL.md: nunca promete polling que não existe,
 * só mostra há quanto tempo o snapshot (meta.json) foi gerado e marca como desatualizado depois
 * de um limiar (aqui: 12h, já que o pipeline roda 3x/dia -- passar disso é sinal real de atraso).
 *
 * **Atualização 2026-08-17:** o polling agora existe de fato — `components/AutoRefresh.tsx`
 * revalida os server components a cada 60s (pausando com a aba oculta). Este relógio deixou de
 * ser a única coisa "viva" da tela, e o título do pill passou a dizer isso explicitamente. A
 * convenção segue valendo ao pé da letra: o que se anuncia é exatamente o que acontece — 60s de
 * revalidação de página, não streaming, e o dado só muda quando o pipeline roda (3x/dia).
 */
export default function LiveClock({ lastRunFinished }: { lastRunFinished: string | null }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(id);
  }, []);

  if (!lastRunFinished) {
    return (
      <span className="inline-flex items-center gap-2 rounded-full border border-status-risk/40 bg-status-risk/10 px-3 py-1 font-mono text-[11px] text-status-risk">
        <span className="h-1.5 w-1.5 rounded-full bg-status-risk" />
        sem execução registrada ainda
      </span>
    );
  }

  const then = new Date(lastRunFinished).getTime();
  const diffMin = Math.max(0, Math.floor((now - then) / 60000));
  const stale = diffMin > 12 * 60;

  let label: string;
  if (diffMin < 1) label = 'agora mesmo';
  else if (diffMin < 60) label = `${diffMin} min atrás`;
  else label = `${Math.floor(diffMin / 60)}h${diffMin % 60}min atrás`;

  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 font-mono text-[11px] ${
        stale
          ? 'border-status-start/40 bg-status-start/10 text-status-start'
          : 'border-status-done/40 bg-status-done/10 text-status-done'
      }`}
      title={`${new Date(lastRunFinished).toLocaleString('pt-BR')} — página revalida sozinha a cada 60s (pausa com a aba oculta)`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${stale ? 'bg-status-start' : 'bg-status-done animate-pulse'}`} />
      última coleta: {label}
      {stale ? ' (atrasada — esperado 3x/dia)' : ''}
    </span>
  );
}
