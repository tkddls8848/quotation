/**
 * 탭 전환.
 *
 * 도구가 여럿인 화면이라 탭이 필요하다. 규칙 셋을 코드로 못박는다.
 *
 *   - 키보드로만도 다닐 수 있어야 한다 (WAI-ARIA 의 탭 관행: 좌우·Home·End)
 *   - 주소의 #해시가 지금 탭을 가리킨다. 새로 고쳐도 보던 탭이 열리고
 *     링크로 바로 그 탭을 열 수 있다
 *   - 탭 내용은 **처음 열릴 때** 만든다. 안 쓰는 도구의 코드를 미리 내려받게
 *     하지 않기 위함이다 (견적서 엔진과 예산을 나눠 쓰지 않는다)
 */

export interface Tab {
  /** `#tab-<id>` 단추와 `#panel-<id>` 칸을 찾는 이름. */
  id: string;
  /** 이 탭일 때 창 제목. */
  title: string;
  /** 처음 열릴 때 한 번 부른다. */
  onFirstShow?: () => void | Promise<void>;
}

export function setupTabs(tabs: Tab[]): void {
  const entries = tabs.map((tab) => {
    const button = document.getElementById(`tab-${tab.id}`) as HTMLButtonElement | null;
    const panel = document.getElementById(`panel-${tab.id}`);
    if (!button || !panel) throw new Error(`탭을 찾지 못했습니다: ${tab.id}`);
    return { tab, button, panel, shown: false };
  });

  const show = (id: string, focus = false): void => {
    const target = entries.find((entry) => entry.tab.id === id) ?? entries[0];
    if (!target) return;

    for (const entry of entries) {
      const current = entry === target;
      entry.button.setAttribute('aria-selected', String(current));
      entry.button.tabIndex = current ? 0 : -1;
      entry.panel.hidden = !current;
    }
    if (focus) target.button.focus();

    document.title = target.tab.title;
    if (location.hash !== `#${target.tab.id}`) {
      history.replaceState(null, '', `#${target.tab.id}`);
    }

    if (!target.shown) {
      target.shown = true;
      void target.tab.onFirstShow?.();
    }
  };

  for (const [index, entry] of entries.entries()) {
    entry.button.addEventListener('click', () => show(entry.tab.id));
    entry.button.addEventListener('keydown', (event) => {
      const step =
        event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
      let next = index;
      if (step !== 0) next = (index + step + entries.length) % entries.length;
      else if (event.key === 'Home') next = 0;
      else if (event.key === 'End') next = entries.length - 1;
      else return;
      event.preventDefault();
      show(entries[next]!.tab.id, true);
    });
  }

  const wanted = location.hash.replace('#', '');
  show(entries.some((entry) => entry.tab.id === wanted) ? wanted : entries[0]!.tab.id);
  window.addEventListener('hashchange', () => show(location.hash.replace('#', '')));
}
