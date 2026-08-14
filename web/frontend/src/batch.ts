/**
 * 여러 화일을 고를 때의 판단 — 화면 조작과 떼어 놓아 그대로 시험한다.
 *
 * 변환 자체는 한 건씩 한다. 브라우저가 `entry.convert` 를 파일 수만큼 되풀이할
 * 뿐이고, 한 건의 산출물은 한 개만 변환할 때와 바이트가 같다. 여기 있는 것은
 * "무엇을 받아들이고 무엇을 거를 것인가" 와 "결과를 어떻게 알릴 것인가" 뿐이다.
 */

import type { AppConfig } from './api';

const MiB = 1024 * 1024;

export interface Rejected {
  name: string;
  reason: string;
}

export interface Selection {
  accepted: File[];
  rejected: Rejected[];
}

/** 고른 화일 중 변환할 수 있는 것만 추린다. 거른 것은 이유와 함께 돌려준다. */
export function selectFiles(files: readonly File[], config: AppConfig): Selection {
  const accepted: File[] = [];
  const rejected: Rejected[] = [];
  const seen = new Set<string>();

  for (const file of files) {
    const reason = rejectReason(file, config);
    if (reason) {
      rejected.push({ name: file.name, reason });
      continue;
    }
    // 같은 이름을 두 번 고르면 결과 화일이 서로를 덮는다. 앞의 것만 남긴다.
    if (seen.has(file.name)) {
      rejected.push({ name: file.name, reason: '같은 이름을 두 번 골랐습니다.' });
      continue;
    }
    seen.add(file.name);

    if (accepted.length >= config.max_batch_files) {
      rejected.push({
        name: file.name,
        reason: `한 번에 ${config.max_batch_files}개까지만 변환합니다.`,
      });
      continue;
    }
    accepted.push(file);
  }
  return { accepted, rejected };
}

/** 화일 하나를 받아들일 수 없는 이유. 받아들일 수 있으면 null. */
export function rejectReason(file: File, config: AppConfig): string | null {
  const name = file.name.toLowerCase();
  if (!config.allowed_suffixes.some((suffix) => name.endsWith(suffix))) {
    return 'XML 화일만 변환할 수 있습니다.';
  }
  if (file.size === 0) return '빈 화일입니다.';
  if (file.size > config.max_upload_bytes) {
    return `너무 큽니다. 한 개당 최대 ${Math.floor(config.max_upload_bytes / MiB)} MiB 입니다.`;
  }
  return null;
}

export interface Tally {
  done: number;
  failed: number;
  total: number;
  cancelled: boolean;
}

/** 끝난 뒤 한 줄로 알린다. 실패가 있으면 그것을 먼저 말한다. */
export function summarize(tally: Tally): string {
  const { done, failed, total, cancelled } = tally;

  if (cancelled) {
    return done > 0
      ? `취소했습니다. ${total}개 중 ${done}개까지 내려받았습니다.`
      : '변환을 취소했습니다.';
  }
  if (failed > 0 && done > 0) {
    return `${total}개 중 ${done}개를 내려받았고 ${failed}개는 실패했습니다.`;
  }
  if (failed > 0) {
    return `${total}개 모두 실패했습니다.`;
  }
  return total === 1
    ? '견적서를 내려받았습니다.'
    : `${total}개를 모두 내려받았습니다.`;
}

/** 진행 표시. 몇 번째를 하고 있는지 알려 준다. */
export function progressLabel(index: number, total: number, name: string): string {
  return total === 1 ? `${name} 변환 중…` : `(${index + 1}/${total}) ${name} 변환 중…`;
}
