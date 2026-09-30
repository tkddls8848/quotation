import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { expect, it } from 'vitest';

const root = fileURLToPath(new URL('../../', import.meta.url));
const gitFiles = (args: string[]): string[] => execFileSync('git', ['ls-files', '-z', ...args], { cwd: root, encoding: 'utf8' }).split('\0').filter(Boolean);

it('운영 소스는 책임별 500줄 이내로 유지한다 (생성물·테스트 제외)', () => {
  const files = gitFiles(['--cached', '--others', '--exclude-standard']);
  const oversized = files.filter(p => /^(quotation\/(rust\/[^/]+\/src|desktop\/src|web\/src)|web\/src)\/.*\.(rs|ts|js|mjs|css)$/.test(p) && !/\.test\./.test(p))
    .flatMap(p => {
      const count = readFileSync(resolve(root, p), 'utf8').trimEnd().split('\n').length;
      return count > 500 ? [`${p}: ${count} lines`] : [];
    });
  expect(oversized).toEqual([]);
});

it('실제 dotenv/Cloudflare 로컬 비밀 파일은 Git에 추적하지 않는다', () => {
  const tracked = gitFiles([]).filter(p => /(^|\/)\.(env|dev\.vars)(\.|$)/.test(p) && !p.endsWith('/.env.example') && p !== '.env.example');
  expect(tracked).toEqual([]);
});
