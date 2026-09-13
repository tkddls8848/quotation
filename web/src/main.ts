/**
 * 셸 — 도구를 탭으로 세우는 것까지만 한다.
 *
 * 여기에는 어떤 도구의 논리도 없다. 각 도구는 제 폴더(`quotation/web`,
 * `fire/web`, `converters/web`)에 화면·스타일·논리를 다 갖고 있고, 셸은 빈 칸을 내주며 처음
 * 열릴 때 불러올 뿐이다.
 *
 *   - 도구끼리는 서로를 import 하지 않는다. 한 도구를 고쳐도 다른 도구가
 *     흔들리지 않게 하기 위함이다
 *   - 도구는 제 탭이 처음 열릴 때 받아 온다. 견적서만 쓰는 사람이 FIRE
 *     계산기 코드를 내려받을 이유가 없다
 */

import './styles.css';

import { setupTabs } from './tabs';

const el = (id: string): HTMLElement => {
  const found = document.getElementById(id);
  if (!found) throw new Error(`요소를 찾지 못했습니다: #${id}`);
  return found;
};

setupTabs([
  {
    id: 'quote',
    title: '견적서 작성기',
    onFirstShow: async () => {
      const { mountQuotation } = await import('@quotation/panel');
      mountQuotation(el('quote-root'), __DEPLOYMENT_VERSION__);
    },
  },
  {
    id: 'fire',
    title: 'FIRE 계산기',
    onFirstShow: async () => {
      const { mountFire } = await import('@fire/view');
      mountFire(el('fire-root'));
    },
  },
  {
    id: 'converters',
    title: '문서 변환기',
    onFirstShow: async () => {
      const { mountConverters } = await import('@converters/panel');
      mountConverters(el('converters-root'));
    },
  },
]);
