/** Credentials stay outside the browser. Errors contain paths/line numbers, never values. */
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';

export const SECRET_KEYS = new Set([
  'CLOUDFLARE_ACCOUNT_ID', 'CLOUDFLARE_API_TOKEN', 'GITHUB_TOKEN', 'GH_TOKEN',
]);
const SKIP = new Set(['.git', 'node_modules', 'target', '.cache', '.venv', '.pytest_cache', '__pycache__', '.wrangler', 'dist']);

export function validateEnvText(text: string): number[] {
  const invalid: number[] = [];
  text.split(/\r?\n/).forEach((line, index) => {
    if (!line.trim() || line.trimStart().startsWith('#')) return;
    const key = /^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=/.exec(line)?.[1];
    if (!key || !SECRET_KEYS.has(key)) invalid.push(index + 1);
  });
  return invalid;
}

export function validateEnvFiles(root: string): void {
  const problems: string[] = [];
  const walk = (dir: string): void => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isSymbolicLink()) {
        if (/^\.(env|dev\.vars)(\.|$)/.test(entry.name)) problems.push(`${relative(root, path)}: credential symlinks are not allowed`);
        continue;
      }
      if (entry.isDirectory()) { if (!SKIP.has(entry.name)) walk(path); continue; }
      if (!/^\.(env|dev\.vars)(\.|$)/.test(entry.name)) continue;
      const label = relative(root, path);
      if (dir !== root || entry.name.startsWith('.dev.vars')) {
        problems.push(`${label}: credentials belong in repository-root .env files only`);
        continue;
      }
      const lines = validateEnvText(readFileSync(path, 'utf8'));
      if (lines.length) problems.push(`${label}: non-credential or malformed entries at lines ${lines.join(', ')}`);
    }
  };
  walk(root);
  if (problems.length) throw new Error(`Environment policy failed (values withheld):\n${problems.join('\n')}`);
}
