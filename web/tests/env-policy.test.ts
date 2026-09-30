import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { resolveConfig } from 'vite';
import { validateEnvFiles, validateEnvText } from '../scripts/env-policy';
import config from '../vite.config';

describe('credential-only environment policy', () => {
  it('accepts credential assignments, rejects public configuration and malformed lines without echoing values', () => {
    expect(validateEnvText('# comment\nGH_TOKEN=fake\nexport CLOUDFLARE_ACCOUNT_ID=fake')).toEqual([]);
    expect(validateEnvText('PORT=123\nVITE_TOKEN=fake\nDEPLOYMENT_VERSION=fake\nbad')).toEqual([1, 2, 3, 4]);
  });
  it('checks ignored dotenv files and rejects nested browser credentials', () => {
    const root = mkdtempSync(join(tmpdir(), 'quotation-env-policy-'));
    try {
      writeFileSync(join(root, '.env.local'), 'GH_TOKEN=fake');
      validateEnvFiles(root);
      mkdirSync(join(root, 'web'));
      writeFileSync(join(root, 'web/.env'), 'GH_TOKEN=DO_NOT_ECHO_THIS');
      try { validateEnvFiles(root); throw new Error('Expected rejection'); }
      catch (error) {
        expect(String(error)).toContain('credentials belong');
        expect(String(error)).not.toContain('DO_NOT_ECHO_THIS');
      }
    } finally { rmSync(root, { recursive: true, force: true }); }
  });
  it('does not expose an inherited VITE_* credential to browser code', async () => {
    const previous = process.env['VITE_TEST_CREDENTIAL'];
    process.env['VITE_TEST_CREDENTIAL'] = 'DO_NOT_BUNDLE_THIS';
    try {
      const resolved = await resolveConfig({ ...config, configFile: false }, 'build');
      expect(resolved.envDir).toBe(false);
      expect(resolved.env).not.toHaveProperty('VITE_TEST_CREDENTIAL');
      expect(JSON.stringify(resolved.define)).not.toContain('DO_NOT_BUNDLE_THIS');
    } finally {
      if (previous === undefined) delete process.env['VITE_TEST_CREDENTIAL'];
      else process.env['VITE_TEST_CREDENTIAL'] = previous;
    }
  });
});
