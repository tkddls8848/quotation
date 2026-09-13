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
 *     셸(web/) ──▶ 기능           (별칭으로, 진입점만)
 *     기능 ──▶ 기능               금지
 *     기능 ──▶ 셸                 금지
 *
 * 화면(`web/src`)뿐 아니라 Worker(`web/worker`)도 셸이고, 기능도 화면
 * (`<기능>/web/src`)과 Worker(`<기능>/worker`)를 함께 갖는다. 같은 규칙이
 * 양쪽에 다 걸린다 — 규칙이 한쪽에만 걸리면 다른 쪽으로 새기 때문이다.
 *
 * 이 검사가 붉으면 고칠 곳은 이 파일이 아니라 그 import 다.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve, sep } from 'node:path';

import { describe, expect, it } from 'vitest';

interface Feature {
  /** 이 기능의 울타리. 상대 경로가 여기를 벗어나면 샌 것이다. */
  root: string;
  /** 그 안에서 실제로 읽어 볼 자리. */
  dirs: string[];
}

/** vitest 는 셸(web/)에서 돈다. 기능은 그 바깥, 저장소 최상위에 있다. */
const FEATURES: Record<string, Feature> = {
  quotation: { root: resolve('../quotation'), dirs: [resolve('../quotation/web/src')] },
  // FIRE 계산기는 화면 말고 Worker 도 갖는다 — 예적금 공시를 받아 오는 창구다.
  fire: { root: resolve('../fire'), dirs: [resolve('../fire/web/src'), resolve('../fire/worker')] },
  converters: { root: resolve('../converters'), dirs: [resolve('../converters/web/src')] },
};

/** 셸도 화면과 Worker 를 갖는다. 둘 다 같은 규칙을 받는다. */
const SHELL = resolve('.');
const SHELL_DIRS = [resolve('src'), resolve('worker')];

/** 셸이 기능에서 가져다 쓰는 **진입점**. 이것 말고는 속을 들여다보지 않는다. */
const ENTRY_POINTS = [
  '@quotation/panel',
  '@fire/view',
  '@converters/panel',
  // 화면이 아니라 Worker 쪽 진입점 (wrangler.jsonc 의 alias).
  '@fire/worker/products',
];

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

/** 여러 자리를 한꺼번에 읽는다. */
const sourcesIn = (dirs: string[]): string[] => dirs.flatMap((dir) => sourcesUnder(dir));

describe('기능 경계', () => {
  for (const [name, feature] of Object.entries(FEATURES)) {
    const { root, dirs } = feature;
    const others = Object.keys(FEATURES).filter((other) => other !== name);

    it(`${name} 은 다른 기능을 부르지 않는다`, () => {
      const crossed: string[] = [];
      for (const file of sourcesIn(dirs)) {
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
      for (const file of sourcesIn(dirs)) {
        for (const spec of specifiers(file)) {
          if (escapes(file, spec, root)) crossed.push(`${relative(root, file)} -> ${spec}`);
        }
      }
      expect(crossed, '기능은 제 폴더 안에서만 가져다 쓴다 (결정 0012)').toEqual([]);
    });
  }

  it('셸은 기능의 진입점만 부른다', () => {
    const wrong: string[] = [];
    for (const file of sourcesIn(SHELL_DIRS)) {
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

  it('셸도 기능을 상대 경로로 건드리지 않는다', () => {
    // Worker 는 vite 를 거치지 않아 별칭을 wrangler.jsonc 에 따로 적어야 한다.
    // 그게 번거롭다고 ../../fire/... 로 질러가면 규칙이 그 자리에서 무너진다.
    const crossed: string[] = [];
    for (const file of sourcesIn(SHELL_DIRS)) {
      for (const spec of specifiers(file)) {
        if (escapes(file, spec, SHELL)) crossed.push(`${relative(SHELL, file)} -> ${spec}`);
      }
    }
    expect(crossed, '셸은 별칭으로만 기능에 닿는다 (결정 0012)').toEqual([]);
  });

  it('기능은 셸을 부르지 않는다', () => {
    const crossed: string[] = [];
    for (const [name, { root, dirs }] of Object.entries(FEATURES)) {
      for (const file of sourcesIn(dirs)) {
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
