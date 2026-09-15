"""Read the body text out of an HWP 5.0 file, for checking what a conversion kept.

This is deliberately the smallest reader that can answer "did the words survive":
paragraph text records only. It does not read styles, tables or placement, and it
is never used by the conversion path itself.
"""
import zlib

import olefile

PARA_TEXT = 0x10 + 51
# Control codes that occupy one UTF-16 unit. Every other code below 32 is an
# inline or extended control and occupies eight units (HWP 5.0 spec, 문단의 텍스트).
SINGLE = {10, 13, 24, 25, 26, 27, 28, 29, 30, 31}


def records(stream):
    at = 0
    while at + 4 <= len(stream):
        header = int.from_bytes(stream[at:at + 4], 'little')
        at += 4
        tag, size = header & 0x3FF, (header >> 20) & 0xFFF
        if size == 0xFFF:
            size = int.from_bytes(stream[at:at + 4], 'little')
            at += 4
        yield tag, stream[at:at + size]
        at += size


def paragraph(payload):
    text, at = [], 0
    while at + 2 <= len(payload):
        code = int.from_bytes(payload[at:at + 2], 'little')
        if code >= 32:
            text.append(chr(code))
            at += 2
        elif code in SINGLE:
            text.append('\n' if code in (10, 13) else '')
            at += 2
        else:
            at += 16
    return ''.join(text)


def section_number(entry):
    # Section10 must not sort before Section2.
    return int(''.join(character for character in entry[-1] if character.isdigit()) or 0)


def hwp_text(path):
    with olefile.OleFileIO(str(path)) as document:
        compressed = int.from_bytes(document.openstream('FileHeader').read(40)[36:40], 'little') & 1
        out = []
        sections = (entry for entry in document.listdir() if entry[0] == 'BodyText')
        for entry in sorted(sections, key=section_number):
            stream = document.openstream(entry).read()
            if compressed:
                stream = zlib.decompress(stream, -15)
            out.extend(paragraph(payload) for tag, payload in records(stream) if tag == PARA_TEXT)
    return '\n'.join(out)
