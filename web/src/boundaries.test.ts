/**
 * 기능 경계를 코드로 지킨다.
 *
 * 별칭(`@quotation`, `@fire`, `@converters`)을 셸에만 둔 것은 **관례**일 뿐이다.
 * 관례는 샌다 — 누군가 `../../fire/web/src/model` 이라고 적으면 별칭을 거치지
 * 않고 그대로 붙고, 빌드도 타입 검사도 통과한다. 그 순간 한 도구의 변경이 다른
 * 도구를 무너뜨릴 수 있게 된다 (결정 0012).
 *
 * 그래서 여기서 실제로 읽어 본다. 허용되는 것은 한 방향뿐이다.
 *
 *     셸(web/src) ──▶ 기능        (별칭으로, 진입점 하나만)
 *     기능 ──▶ 기능               금지
 *     기능 ──▶ 셸                 금지
 *
 * 이 검사가 붉으면 고칠 곳은 이 파일이 아니라 그 import 다.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve, sep } from 'node:path';

import { describe, expect, it } from 'vitest';

/** vitest 는 셸(web/)에서 돈다. 기능은 그 바깥, 저장소 최상위에 있다. */
const FEATURES: Record<string, string> = {
  quotation: resolve('../quotation/web/src'),
  fire: resolve('../fire/web/src'),
  converters: resolve('../converters/web/src'),
};

const SHELL = resolve('src');

/** 셸이 기능에서 가져다 쓰는 **진입점**. 이것 말고는 속을 들여다보지 않는다. */
const ENTRY_POINTS = ['@quotation/panel', '@fire/view', '@converters/panel'];

const SOURCE = /\.(ts|tsx|js|mjs|css|html)$/;

function sourcesUnder(dir: string): string[] {
  let found: string[] = [];
  for (const name of readdirSync(dir)) {
    if (name === 'node_modules' || name.startsWith('.')) continue;
    const path = join(dir, name);
    if (statSync(path).isDirectory()) found = found.concat(sourcesUnder(path));
    else if (SOURCE.test(name)) found.push(path);
  }
  return found;
}

/** 그 파일이 바깥에서 끌어오는 것들. import·동적 import·CSS @import·url() 까지. */
function specifiers(file: string): string[] {
  const text = readFileSync(file, 'utf-8');
  const out: string[] = [];
  const patterns = [
    /\bfrom\s+['"]([^'"]+)['"]/g,
    /\bimport\s+['"]([^'"]+)['"]/g,
    /\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)/g,
    /@import\s+(?:url\()?['"]([^'"]+)['"]/g,
    /\burl\(\s*['"]?([^'")]+)['"]?\s*\)/g,
  ];
  for (const pattern of patterns) {
    for (const match of text.matchAll(pattern)) {
      const spec = match[1];
      if (spec && !spec.startsWith('data:') && !spec.startsWith('http')) out.push(spec);
    }
  }
  return out;
}

/** 상대 경로가 그 기능 폴더 밖으로 나가는가. */
function escapes(file: string, spec: string, root: string): boolean {
  if (!spec.startsWith('.')) return false;
  const target = resolve(dirname(file), spec);
  const inside = relative(root, target);
  return inside.startsWith('..' + sep) || inside === '..';
}

describe('기능 경계', () => {
  for (const [name, root] of Object.entries(FEATURES)) {
    const others = Object.keys(FEATURES).filter((other) => other !== name);

    it(`${name} 은 다른 기능을 부르지 않는다`, () => {
      const crossed: string[] = [];
      for (const file of sourcesUnder(root)) {
        for (const spec of specifiers(file)) {
          const alias = others.find(
            (other) => spec === `@${other}` || spec.startsWith(`@${other}/`),
          );
          if (alias) crossed.push(`${relative(root, file)} -> ${spec}`);
        }
      }
      expect(crossed, '기능끼리는 서로를 부르지 않는다 (결정 0012)').toEqual([]);
    });

    it(`${name} 은 제 폴더 밖을 상대 경로로 건드리지 않는다`, () => {
      // 별칭을 피해 ../../ 로 돌아 들어오는 길을 막는다. 셸도 포함해서다.
      const crossed: string[] = [];
      for (const file of sourcesUnder(root)) {
        for (const spec of specifiers(file)) {
          if (escapes(file, spec, root)) crossed.push(`${relative(root, file)} -> ${spec}`);
        }
      }
      expect(crossed, '기능은 제 폴더 안에서만 가져다 쓴다 (결정 0012)').toEqual([]);
    });
  }

  it('셸은 기능의 진입점만 부른다', () => {
    const wrong: string[] = [];
    for (const file of sourcesUnder(SHELL)) {
      for (const spec of specifiers(file)) {
        if (!spec.startsWith('@')) continue;
        const feature = Object.keys(FEATURES).find(
          (name) => spec === `@${name}` || spec.startsWith(`@${name}/`),
        );
        if (feature && !ENTRY_POINTS.includes(spec)) wrong.push(`${relative(SHELL, file)} -> ${spec}`);
      }
    }
    expect(wrong, '기능의 속이 아니라 진입점 하나만 부른다').toEqual([]);
  });

  it('기능은 셸을 부르지 않는다', () => {
    const crossed: string[] = [];
    for (const [name, root] of Object.entries(FEATURES)) {
      for (const file of sourcesUnder(root)) {
        for (const spec of specifiers(file)) {
          if (escapes(file, spec, root) && resolve(dirname(file), spec).startsWith(SHELL)) {
            crossed.push(`${name}: ${relative(root, file)} -> ${spec}`);
          }
        }
      }
    }
    expect(crossed, '셸이 기능을 부르지, 기능이 셸을 부르지 않는다').toEqual([]);
  });
});
