"""Exercise the real API/engine with explicitly supplied public/synthetic HWP fixtures.

Reports one row per document. A document the engine refuses is reported and counted:
that failure reaches the user as a failure too. A document that converts but drops
body text fails this run — silent loss is the failure this check exists to catch.
"""
import argparse
from io import BytesIO
import json
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from pypdf import PdfReader

from hwptext import hwp_text

# Document text goes to this console. Escape what its code page cannot show
# rather than dying on one character after a long run of real conversions.
sys.stdout.reconfigure(errors='backslashreplace')

parser = argparse.ArgumentParser()
parser.add_argument('files', type=Path, nargs='+')
parser.add_argument('--api', default='http://127.0.0.1:8788')
parser.add_argument('--out', type=Path, default=Path('.cache/hwp-validation'))
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)


def call(path, method='GET', data=None, token=''):
    req = Request(args.api + path, data=data, method=method, headers={
        'Content-Type': 'application/octet-stream', 'Authorization': 'Bearer ' + token,
    })
    with urlopen(req, timeout=60) as response:
        raw = response.read()
        return raw if response.headers['Content-Type'] == 'application/pdf' else json.loads(raw)


def refused(path, method='GET', data=None, token=''):
    """The status the API answers a call that must not succeed with. 0 means it did."""
    try:
        call(path, method, data, token)
    except HTTPError as error:
        return error.code
    return 0


def condense(text):
    return re.sub(r'\s+', '', text)


def delivered(line, text):
    """The line's characters survive, in order.

    A contiguous match would be wrong: the engine inserts caption and page numbers
    between them, and tab leaders around them. This says the words came through,
    not that the page looks the same — that comparison needs Hangul's own PDF.
    """
    at = 0
    for character in line:
        at = text.find(character, at)
        if at < 0:
            return False
        at += 1
    return True


assert call('/health')['ready'], 'the conversion engine is not ready'
assert refused('/jobs', 'POST', b'not a HWP') == 400, 'invalid input accepted'

rows, refusals, lost = [], 0, 0
for source in args.files:
    start = time.monotonic()
    try:
        job = call('/jobs', 'POST', source.read_bytes())
    except HTTPError as error:
        rows.append(f'{source.name}: rejected on upload - {json.loads(error.read())["error"]}')
        refusals += 1
        continue
    path = '/jobs/' + job['id']
    assert refused(path, token='wrong') == 404, 'wrong token accepted'
    status = {'state': 'queued', 'message': 'the job never finished'}
    while time.monotonic() - start < 150:
        status = call(path, token=job['token'])
        if status['state'] in ('done', 'failed', 'cancelled'):
            break
        time.sleep(0.5)
    if status['state'] != 'done':
        call(path, 'DELETE', token=job['token'])
        rows.append(f'{source.name}: {status["state"]} - {status["message"]}')
        refusals += 1
        continue
    pdf = call(path + '/result', token=job['token'])
    document = PdfReader(BytesIO(pdf))
    assert not document.is_encrypted and len(document.pages), 'unusable PDF was served'
    texts = [page.extract_text() for page in document.pages]
    lines = [line for line in (condense(line) for line in hwp_text(source).splitlines()) if len(line) >= 2]
    missing = [line for line in lines if not delivered(line, condense(''.join(texts)))]
    lost += len(missing)
    (args.out / (source.stem + '.pdf')).write_bytes(pdf)
    (args.out / (source.stem + '.txt')).write_text('\n'.join(texts), encoding='utf-8')
    rows.append(f'{source.name}: {len(document.pages)} pages, {len(pdf)} bytes, '
                f'body text {len(lines) - len(missing)}/{len(lines)} lines, {time.monotonic() - start:.1f}s'
                + (' - DROPPED: ' + ' | '.join(line[:30] for line in missing) if missing else ''))
    assert call(path, 'DELETE', token=job['token'])['state'] == 'cancelled'
    assert refused(path + '/result', token=job['token']) == 404, 'deleted result was downloadable'

summary = (f'{len(args.files) - refusals}/{len(args.files)} converted, {refusals} refused, '
           f'{lost} body text lines dropped.')
# The console may be on a legacy code page; this file always keeps the document text.
(args.out / 'report.txt').write_text('\n'.join(rows + [summary]), encoding='utf-8')
print('\n'.join(rows))
print(summary)
print('Checked: real conversions, PDF parsing, body text survival, token isolation, invalid input, result deletion.')
sys.exit(1 if lost else 0)
