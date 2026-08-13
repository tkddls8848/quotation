/**
 * 다운로드 파일명 처리.
 *
 * 서버가 `Content-Disposition` 에 RFC 5987 형식으로 한글 이름을 담아 준다.
 * 브라우저 다운로드 정책상 기존 파일 덮어쓰기 확인은 브라우저에 맡긴다.
 */

const STAR_PARAM = /filename\*\s*=\s*([^']*)'([^']*)'([^;]+)/i;
const PLAIN_PARAM = /filename\s*=\s*"([^"]*)"|filename\s*=\s*([^;]+)/i;

/** `Content-Disposition` 헤더에서 파일명을 뽑는다. 못 뽑으면 fallback. */
export function filenameFromDisposition(
  header: string | null,
  fallback: string,
): string {
  if (!header) return fallback;

  const starred = STAR_PARAM.exec(header);
  if (starred) {
    try {
      const decoded = decodeURIComponent(starred[3].trim());
      if (decoded) return decoded;
    } catch {
      // 잘못 인코딩된 헤더는 무시하고 아래 형식으로 넘어간다
    }
  }

  const plain = PLAIN_PARAM.exec(header);
  if (plain) {
    const value = (plain[1] ?? plain[2] ?? '').trim();
    if (value) return value;
  }
  return fallback;
}

/** 입력 파일명에서 확장자만 .xlsx 로 바꾼다 (헤더가 없을 때 쓸 대비책). */
export function outputNameFor(inputName: string): string {
  const base = inputName.replace(/\\/g, '/').split('/').pop() ?? '';
  const stem = base.replace(/\.[^.]*$/, '');
  return `${stem || 'quotation'}.xlsx`;
}

/** 받은 blob 을 파일로 내려 준다. */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // 클릭 직후 해제하면 일부 브라우저가 저장을 못 끝낸다.
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
