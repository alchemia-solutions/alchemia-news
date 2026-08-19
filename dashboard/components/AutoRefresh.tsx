'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/**
 * Auto-refresh real do painel, a pedido do fundador (2026-08-17).
 *
 * Usa `router.refresh()` do App Router em vez de recarregar a página: isso **revalida os server
 * components** (que leem `pipeline/data/*.json` em tempo de requisição — ver `lib/data.ts`) e
 * troca a árvore no lugar, **sem perder scroll nem estado de cliente** e sem o "piscar" de um
 * reload. Um `<meta http-equiv="refresh">` faria o oposto: recarrega tudo e joga o usuário de
 * volta ao topo.
 *
 * Duas decisões que evitam trabalho inútil:
 *  - **Pausa com a aba oculta** (`visibilitychange`): uma aba esquecida em segundo plano não fica
 *    revalidando a noite inteira.
 *  - **Revalida ao voltar para a aba**, imediatamente — é o que a pessoa espera ao retomar, em vez
 *    de esperar o próximo tick.
 *
 * Não é streaming nem websocket: o dado só muda quando o pipeline roda (3x/dia via cron do
 * `baker-bot`). O intervalo curto existe para que a mudança apareça sozinha logo depois da coleta,
 * não para dar impressão de fluxo contínuo — mesma disciplina anti-overclaiming de
 * `.claude/skills/realtime-dashboard/SKILL.md`.
 */
export default function AutoRefresh({ intervalMs = 60_000 }: { intervalMs?: number }) {
  const router = useRouter();

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;

    const start = () => {
      if (timer !== null) return;
      timer = setInterval(() => router.refresh(), intervalMs);
    };

    const stop = () => {
      if (timer === null) return;
      clearInterval(timer);
      timer = null;
    };

    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        router.refresh(); // pega de imediato o que mudou enquanto a aba esteve oculta
        start();
      } else {
        stop();
      }
    };

    if (document.visibilityState === 'visible') start();
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      stop();
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [router, intervalMs]);

  return null;
}
