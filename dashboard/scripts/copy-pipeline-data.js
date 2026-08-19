#!/usr/bin/env node
/**
 * Snapshot de segurança para deploy na Vercel.
 *
 * Se o "Root Directory" do projeto Vercel estiver configurado como `dashboard/` (padrão para
 * monorepo), o build NÃO tem acesso a `../pipeline/data` nem `../pipeline/config` -- eles ficam
 * fora da árvore que a Vercel baixa/empacota. `lib/data.ts` lia esse caminho relativo direto e
 * tinha fallback silencioso para `[]`/`{}` em qualquer erro -- ou seja, o site publicado
 * renderizaria vazio, sem erro nenhum aparente. Ver AGENTS.md deste setor, "Estado real vs.
 * spec", item 5.
 *
 * Este script roda como `prebuild` (hook npm automático antes de `next build`) e copia os JSONs
 * de dado e os YAMLs de config para `dashboard/.pipeline-data/{data,config}` -- dentro da árvore
 * do dashboard, portanto sempre disponível no build da Vercel independente do Root Directory.
 *
 * Em dev local, `../pipeline/data` normalmente já existe e `lib/data.ts` prioriza esse caminho
 * ao vivo (comportamento deliberado: pipeline roda, dashboard reflete sem rebuild -- não mudar).
 * O snapshot é só a rede de segurança para quando o caminho ao vivo não existe.
 */
const fs = require('fs');
const path = require('path');

const LIVE_DATA_DIR = path.join(__dirname, '..', '..', 'pipeline', 'data');
const LIVE_CONFIG_DIR = path.join(__dirname, '..', '..', 'pipeline', 'config');
const SNAPSHOT_DATA_DIR = path.join(__dirname, '..', '.pipeline-data', 'data');
const SNAPSHOT_CONFIG_DIR = path.join(__dirname, '..', '.pipeline-data', 'config');

function copyDir(srcDir, destDir, extensions) {
  if (!fs.existsSync(srcDir)) {
    console.warn(`[copy-pipeline-data] Aviso: origem não encontrada, pulando: ${srcDir}`);
    return 0;
  }
  fs.mkdirSync(destDir, { recursive: true });
  let count = 0;
  for (const entry of fs.readdirSync(srcDir)) {
    if (!extensions.some((ext) => entry.endsWith(ext))) continue;
    fs.copyFileSync(path.join(srcDir, entry), path.join(destDir, entry));
    count += 1;
  }
  return count;
}

const dataCount = copyDir(LIVE_DATA_DIR, SNAPSHOT_DATA_DIR, ['.json']);
const configCount = copyDir(LIVE_CONFIG_DIR, SNAPSHOT_CONFIG_DIR, ['.yaml', '.yml']);

console.log(
  `[copy-pipeline-data] Snapshot criado: ${dataCount} arquivo(s) de dado, ${configCount} arquivo(s) de config.`
);
