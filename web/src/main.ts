/**
 * 셸 — 도구가 설 빈 칸을 내주는 것까지만 한다.
 *
 * 여기에는 도구의 논리가 없다. 견적서는 제 폴더(`quotation/web`)에 화면·스타일·
 * 논리를 다 갖고 있고, 셸은 칸을 내주며 부를 뿐이다.
 *
 * 문서 변환기가 함께 서 있던 동안에는 탭이 있었고, 도구는 제 탭이 처음 열릴 때
 * 받아 왔다. 도구가 하나만 남은 지금 탭 한 개짜리 막대도, 늦춰 받을 이유도
 * 없다 — 그 도구가 곧 이 화면이다 (결정 0021).
 */

import './styles.css';

import { mountQuotation } from '@quotation/panel';

const root = document.getElementById('quote-root');
if (!root) throw new Error('요소를 찾지 못했습니다: #quote-root');

mountQuotation(root, __DEPLOYMENT_VERSION__);
