import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { mkdir } from 'node:fs/promises';
import assert from 'node:assert/strict';
const require = createRequire(new URL('../../../web/package.json', import.meta.url));
const { chromium } = require('playwright');
const { PDFDocument, rgb } = require('pdf-lib');
const { unzipSync, zipSync, strToU8, strFromU8 } = require('fflate');
const base = process.env.HWPX_TEST_URL ?? 'http://127.0.0.1:18574';
const out = new URL('../../../.cache/hwpx-validation/', import.meta.url);
await mkdir(out, { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(`${base}/#converters`);
  await page.getByRole('heading', { name: 'PDF 편집기', exact: true }).waitFor();
  const doc = await PDFDocument.create();
  const first = doc.addPage([400, 500]);
  first.drawText('Title < & >', { x: 30, y: 450, size: 12 });
  for (const [text, x, y] of [['A',30,400],['B',200,400],['C',30,375],['D',200,375]]) first.drawText(text, { x, y, size: 10 });
  doc.addPage([500, 300]).drawText('Second page', { x: 20, y: 100, size: 12 });
  doc.addPage([300, 400]).drawRectangle({ x: 0, y: 0, width: 300, height: 400, color: rgb(0.2,0.4,0.9) });
  await page.locator('#conv-pdf-file').setInputFiles({ name: 'synthetic.pdf', mimeType: 'application/pdf', buffer: Buffer.from(await doc.save()) });
  await page.getByText('1개 파일에서 3쪽을 추가했습니다.', { exact: true }).waitFor();
  const result = page.locator('.pdf-outputs a');
  // 링크를 눌러 실제로 내려받고, 같은 바이트를 검사용으로도 가져온다.
  const grab = async (link, name) => {
    await link.waitFor();
    const pending = page.waitForEvent('download'); await link.click();
    await (await pending).saveAs(fileURLToPath(new URL(name, out)));
    return Uint8Array.from(await link.evaluate(async a => Array.from(new Uint8Array(await (await fetch(a.href)).arrayBuffer()))));
  };
  const save = async name => unzipSync(await grab(result, name));
  await page.getByRole('button', { name: 'HWPX 이미지로 저장', exact: true }).click();
  const images = await save('multi-image.hwpx');
  assert.equal(Object.keys(images).filter(n => /section\d+.xml$/.test(n)).length, 3);
  assert.equal(Object.keys(images).filter(n => n.startsWith('BinData/')).length, 3);
  assert.match(strFromU8(images['Contents/header.xml']), /secCnt="3"/);
  await page.getByRole('button', { name: 'HWPX 텍스트로 저장', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('.conv-pdf .conv-status').textContent.includes('3쪽에서 텍스트를 찾지 못했습니다'));
  assert.equal(await result.count(), 0);
  await page.locator('#pdf-hwpx-empty').selectOption('image');
  await page.locator('#pdf-hwpx-tables').check();
  await page.getByRole('button', { name: 'HWPX 텍스트로 저장', exact: true }).click();
  const text = await save('multi-text.hwpx');
  const xml = strFromU8(text['Contents/section0.xml']);
  assert.match(xml, /Title &lt; &amp; &gt;/);
  assert.match(xml, /<hp:tbl/);
  assert.match(xml, /rowCnt="2" colCnt="2"/);
  assert.equal(Object.keys(text).filter(n => n.startsWith('BinData/')).length, 1);
  assert.match(await page.locator('.pdf-hwpx-warnings').innerText(), /3쪽: 텍스트 없음 → 이미지로 저장/);
  await page.locator('#pdf-hwpx-empty').selectOption('skip');
  await page.getByRole('button', { name: 'HWPX 텍스트로 저장', exact: true }).click();
  assert.match(strFromU8((await save('skip-text.hwpx'))['Contents/header.xml']), /secCnt="2"/);

  await page.locator('.pdf-pages input').nth(1).check();
  await page.getByRole('button', { name: '선택 쪽 ↻ 90°', exact: true }).click();
  await page.getByRole('button', { name: 'HWPX 이미지로 저장', exact: true }).click();
  const selected = await save('selected-image.hwpx');
  assert.match(strFromU8(selected['Contents/section0.xml']), /width="30000" height="50000"/);
  assert.match(strFromU8(selected['Contents/header.xml']), /secCnt="1"/);
  await page.getByRole('button', { name: 'HWPX 이미지로 저장', exact: true }).click();
  await page.getByRole('button', { name: '변환 취소', exact: true }).click();
  await page.getByText('HWPX 변환을 취소했습니다.', { exact: true }).waitFor();

  // PDF → 이미지: 여러 쪽이면 ZIP, 한 쪽이면 그림 하나.
  await page.getByRole('button', { name: '선택 해제', exact: true }).click();
  await page.locator('#pdf-image-dpi').selectOption('150');
  await page.getByRole('button', { name: '이미지로 저장', exact: true }).click();
  const pack = unzipSync(await grab(result, 'pages.zip'));
  assert.deepEqual(Object.keys(pack), ['page-1.png', 'page-2.png', 'page-3.png']);
  // PNG 서명이 있어야 진짜 그림이다.
  assert.deepEqual([...pack['page-1.png'].subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
  await page.locator('.pdf-pages input').first().check();
  await page.locator('#pdf-image-format').selectOption('jpeg');
  await page.getByRole('button', { name: '이미지로 저장', exact: true }).click();
  const jpeg = await grab(result, 'page-1.jpg');
  assert.deepEqual([...jpeg.subarray(0, 3)], [0xff, 0xd8, 0xff]);
  assert.match(await page.locator('.conv-pdf .conv-status').innerText(), /1장을 만들었습니다/);

  // 이미지 → PDF: 방금 만든 PNG 두 장을 도로 PDF 로 묶는다.
  const imgTool = page.locator('.conv-images-pdf');
  await imgTool.locator('#conv-img-file').setInputFiles([
    { name: 'a.png', mimeType: 'image/png', buffer: Buffer.from(pack['page-1.png']) },
    { name: 'b.png', mimeType: 'image/png', buffer: Buffer.from(pack['page-2.png']) },
  ]);
  await imgTool.getByText('2장을 추가했습니다.', { exact: true }).waitFor();
  await imgTool.getByRole('button', { name: 'PDF 로 묶기', exact: true }).click();
  const bundled = await PDFDocument.load(await grab(imgTool.locator('.img-outputs a'), 'images.pdf'));
  assert.equal(bundled.getPageCount(), 2);
  // '그림 크기 그대로' 는 쪽을 그림 픽셀에 맞춘다. 150 DPI 로 그린 400×500pt 쪽이다.
  assert.deepEqual(bundled.getPage(0).getSize(), { width: 834, height: 1042 });
  await imgTool.locator('.img-fit').selectOption('a4');
  await imgTool.getByRole('button', { name: 'PDF 로 묶기', exact: true }).click();
  const a4 = await PDFDocument.load(await grab(imgTool.locator('.img-outputs a'), 'images-a4.pdf'));
  assert.equal(Math.round(a4.getPage(0).getSize().width), 595);

  // 텍스트 → HWPX: 표와 제목이 든 Markdown 을 한글 문서로 짓는다.
  const textTool = page.locator('.conv-text-hwpx');
  await textTool.locator('#conv-text-input').fill('# 과업 내용\n\n| 품목 | 수량 |\n| --- | --- |\n| 볼펜 | 3 |');
  await textTool.getByRole('button', { name: 'HWPX 로 저장', exact: true }).click();
  const hwpx = unzipSync(await grab(textTool.locator('.text-outputs a'), 'text.hwpx'));
  const section = strFromU8(hwpx['Contents/section0.xml']);
  assert.match(section, /과업 내용/);
  assert.match(section, /<hp:tbl/);
  assert.match(section, /rowCnt="2" colCnt="2"/);
  assert.match(strFromU8(hwpx['Contents/header.xml']), /secCnt="1"/);
  // 그림이 없는 문서에는 BinData 가 없어야 한다.
  assert.equal(Object.keys(hwpx).filter(n => n.startsWith('BinData/')).length, 0);
  assert.match(await textTool.locator('.text-notes').innerText(), /제목은 문단으로 들어갑니다/);

  // 인코딩: CP949 CSV 를 읽어 UTF-8 로 내보낸다.
  const enc = page.locator('.conv-encoding');
  const cp949 = Buffer.from([0xc7, 0xd1, 0xb1, 0xdb, 0x2c, 0x31, 0x0d, 0x0a]); // "한글,1\r\n"
  await enc.locator('#conv-enc-file').setInputFiles({ name: '명부.csv', mimeType: 'text/csv', buffer: cp949 });
  await enc.getByText('명부.csv 를 읽었습니다.', { exact: true }).waitFor();
  assert.match(await enc.locator('.enc-detected').innerText(), /CP949 \(EUC-KR·완성형\).*추정입니다/);
  assert.match(await enc.locator('.enc-preview').innerText(), /한글,1/);
  assert.equal(await enc.locator('.enc-target').inputValue(), 'utf-8');
  await enc.locator('.enc-newline').selectOption('lf');
  await enc.getByRole('button', { name: '변환해 내려받기', exact: true }).click();
  const converted = await grab(enc.locator('.enc-outputs a'), 'encoded.csv');
  assert.deepEqual([...converted], [0xef, 0xbb, 0xbf, ...Buffer.from('한글,1\n', 'utf8')]);
  // 거꾸로 CP949 로 내보낼 때, 담을 수 없는 글자는 조용히 버리지 않고 멈춘다.
  await enc.locator('#conv-enc-file').setInputFiles({ name: 'emoji.txt', mimeType: 'text/plain', buffer: Buffer.from('값 😀', 'utf8') });
  await enc.getByText('emoji.txt 를 읽었습니다.', { exact: true }).waitFor();
  assert.equal(await enc.locator('.enc-target').inputValue(), 'euc-kr');
  await enc.getByRole('button', { name: '변환해 내려받기', exact: true }).click();
  await enc.getByText(/CP949로 적을 수 없는 글자가 1종 있습니다/).waitFor();
  assert.equal(await enc.locator('.enc-outputs a').count(), 0);

  // ZIP: 묶고, 그것을 도로 풀어 같은 내용인지 본다.
  const zip = page.locator('.conv-zip');
  await zip.locator('#conv-zip-pack').setInputFiles([
    { name: '보고서.txt', mimeType: 'text/plain', buffer: Buffer.from('내용', 'utf8') },
    { name: '표.csv', mimeType: 'text/csv', buffer: Buffer.from('a,b\n1,2\n', 'utf8') },
  ]);
  await zip.getByRole('button', { name: 'ZIP 으로 묶기', exact: true }).click();
  const packed = unzipSync(await grab(zip.locator('.zip-pack-outputs a'), 'archive.zip'));
  assert.deepEqual(Object.keys(packed).sort(), ['보고서.txt', '표.csv']);
  assert.equal(strFromU8(packed['보고서.txt']), '내용');
  await zip.locator('#conv-zip-open').setInputFiles({
    name: 'sample.zip', mimeType: 'application/zip',
    buffer: Buffer.from(zipSync({ 'doc/메모.txt': strToU8('한 줄'), 'bin.dat': new Uint8Array([1, 2, 3]) })),
  });
  await zip.getByText('2개 파일을 풀었습니다. 이름을 눌러 하나씩 내려받으세요.', { exact: true }).waitFor();
  assert.deepEqual(await zip.locator('.zip-open-list a').allInnerTexts(), ['doc/메모.txt (7B)', 'bin.dat (3B)']);

  await page.setViewportSize({ width: 375, height: 812 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.screenshot({ path: fileURLToPath(new URL('converters-mobile.png', out)), fullPage: true });
  assert.deepEqual(errors, []);
  console.log('PASS: HWPX image/text exports, tables, mixed page sizes, scanned-page error/image/skip, selection/rotation, cancellation, PDF→image (zip/single), image→PDF (native/A4), text→HWPX, encoding detect/convert/refuse, ZIP pack/unpack, mobile layout.');
} finally { await browser.close(); }
