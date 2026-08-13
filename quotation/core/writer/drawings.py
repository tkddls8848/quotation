"""템플릿의 그림·도형을 산출물로 옮긴다.

openpyxl 은 워크북을 저장할 때 그림(drawing)·이미지·텍스트박스를 버린다.
견적서 템플릿은 TOTAL 시트 상단에 로고와 도형으로 된 머리글 블록을 두고 있어,
이것이 사라지면 첫 장 상단이 비어 보인다.

골든과 동일하게 **TOTAL 시트에만** 옮긴다. 원본 프로그램도 상세 시트와 잔존
template 시트에는 그림을 남기지 않는다.

openpyxl 이 저장을 끝낸 뒤 xlsx(zip) 를 직접 손보는 방식이다.
"""
from __future__ import annotations

import posixpath
import re
import shutil
import zipfile
from io import BytesIO
from pathlib import Path

CONTENT_TYPES = "[Content_Types].xml"
DRAWING_CT = "application/vnd.openxmlformats-officedocument.drawing+xml"
DRAWING_REL = ("http://schemas.openxmlformats.org/officeDocument/2006/"
               "relationships/drawing")

_SHEET_RE = re.compile(r"<sheet\b[^>]*>")
_RELATIONSHIP_RE = re.compile(r"<Relationship\b[^>]*>")
_TARGET_RE = re.compile(r'Target="([^"]+)"')


def _attr(tag: str, name: str) -> str:
    """속성 순서에 의존하지 않고 값을 읽는다.

    Excel 과 openpyxl 의 속성 순서가 다르다. openpyxl 은 Target 을 Id 보다
    먼저 쓰고, 워크북 관계의 Target 을 '/xl/...' 처럼 절대 경로로 적는다.
    """
    m = re.search(rf'\b{re.escape(name)}="([^"]*)"', tag)
    return m.group(1) if m else ""


def _resolve(base_part: str, target: str) -> str:
    """관계의 Target 을 zip 내부 경로로 바꾼다. 절대/상대 모두 받는다."""
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(base_part),
                                             target))


def _sheet_part(z: zipfile.ZipFile, sheet_name: str) -> str | None:
    """시트 이름 -> xl/worksheets/sheetN.xml"""
    workbook = z.read("xl/workbook.xml").decode("utf-8")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    targets = {_attr(t, "Id"): _attr(t, "Target")
               for t in _RELATIONSHIP_RE.findall(rels)}
    for tag in _SHEET_RE.findall(workbook):
        if _attr(tag, "name") != sheet_name:
            continue
        target = targets.get(_attr(tag, "r:id"), "")
        part = _resolve("xl/workbook.xml", target) if target else ""
        return part if part in z.namelist() else None
    return None


def _rels_part(sheet_part: str) -> str:
    folder, name = posixpath.split(sheet_part)
    return f"{folder}/_rels/{name}.rels"


def _collect(z: zipfile.ZipFile, sheet_part: str) -> dict[str, bytes]:
    """시트에 딸린 drawing 과 그것이 참조하는 media 를 모은다."""
    rels_part = _rels_part(sheet_part)
    if rels_part not in z.namelist():
        return {}

    rels = z.read(rels_part).decode("utf-8")
    parts: dict[str, bytes] = {}
    for target in _TARGET_RE.findall(rels):
        if "drawing" not in target:
            continue
        drawing = _resolve(sheet_part, target)
        if drawing not in z.namelist():
            continue
        parts[drawing] = z.read(drawing)

        # drawing 이 참조하는 이미지까지 따라간다
        drawing_rels = _rels_part(drawing)
        if drawing_rels in z.namelist():
            body = z.read(drawing_rels)
            parts[drawing_rels] = body
            for t in _TARGET_RE.findall(body.decode("utf-8")):
                media = _resolve(drawing, t)
                if media in z.namelist():
                    parts[media] = z.read(media)
    return parts


def _next_rid(rels_xml: str) -> str:
    used = {int(n) for n in re.findall(r'Id="rId(\d+)"', rels_xml)}
    return f"rId{max(used, default=0) + 1}"


def _patch_rels(existing: str | None, rid: str, target: str) -> str:
    entry = (f'<Relationship Id="{rid}" Type="{DRAWING_REL}" '
             f'Target="{target}"/>')
    if existing:
        return existing.replace("</Relationships>", entry + "</Relationships>")
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/'
            f'package/2006/relationships">{entry}</Relationships>')


R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _patch_sheet(sheet_xml: str, rid: str) -> str:
    """<drawing> 은 스키마상 워크시트의 끝부분에 온다.

    openpyxl 은 r: 접두사를 쓸 일이 없으면 네임스페이스를 선언하지 않는다.
    선언 없이 r:id 를 넣으면 'unbound prefix' 로 파일이 깨지므로 함께 넣는다.
    """
    if "<drawing " in sheet_xml:
        return sheet_xml

    if "xmlns:r=" not in sheet_xml:
        m = re.search(r"<worksheet\b[^>]*", sheet_xml)
        if not m:
            return sheet_xml
        head = m.group(0)
        sheet_xml = sheet_xml.replace(head, f'{head} xmlns:r="{R_NS}"', 1)

    return sheet_xml.replace("</worksheet>",
                             f'<drawing r:id="{rid}"/></worksheet>')


def _patch_content_types(xml: str, drawing_parts: list[str],
                         extensions: set[str]) -> str:
    additions = []
    for ext in sorted(extensions):
        if f'Extension="{ext}"' not in xml:
            additions.append(
                f'<Default Extension="{ext}" ContentType="image/{ext}"/>')
    for part in drawing_parts:
        name = "/" + part
        if f'PartName="{name}"' not in xml:
            additions.append(
                f'<Override PartName="{name}" ContentType="{DRAWING_CT}"/>')
    if not additions:
        return xml
    return xml.replace("</Types>", "".join(additions) + "</Types>")


def carry_over_bytes(template: bytes, output: bytes,
                     sheet_name: str = "TOTAL") -> bytes | None:
    """템플릿의 그림·도형을 산출물 바이트의 지정 시트로 옮긴다.

    파일시스템을 쓰지 않는다. Worker 와 데스크톱이 함께 쓰는 실제 구현이다.

    Returns:
        옮길 것이 있어 손본 새 xlsx 바이트. 옮길 것이 없으면 None.
    """
    with zipfile.ZipFile(BytesIO(template)) as z:
        src_sheet = _sheet_part(z, sheet_name)
        parts = _collect(z, src_sheet) if src_sheet else {}
    if not parts:
        return None

    with zipfile.ZipFile(BytesIO(output)) as z:
        entries = {n: z.read(n) for n in z.namelist()}
        dst_sheet = _sheet_part(z, sheet_name)
    if not dst_sheet:
        return None

    rels_part = _rels_part(dst_sheet)
    existing = entries.get(rels_part, b"").decode("utf-8") or None
    rid = _next_rid(existing or "")

    drawings = [p for p in parts if re.fullmatch(r"xl/drawings/drawing\d+\.xml", p)]
    if not drawings:
        return None
    target = posixpath.relpath(drawings[0], posixpath.dirname(dst_sheet))

    entries.update(parts)
    entries[rels_part] = _patch_rels(existing, rid, target).encode("utf-8")
    entries[dst_sheet] = _patch_sheet(
        entries[dst_sheet].decode("utf-8"), rid).encode("utf-8")
    extensions = {posixpath.splitext(p)[1].lstrip(".").lower()
                  for p in parts if p.startswith("xl/media/")}
    entries[CONTENT_TYPES] = _patch_content_types(
        entries[CONTENT_TYPES].decode("utf-8"), drawings,
        extensions).encode("utf-8")

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for name, body in entries.items():
            z.writestr(name, body)
    return buffer.getvalue()


def carry_over(template: str | Path, output: str | Path,
               sheet_name: str = "TOTAL") -> bool:
    """`carry_over_bytes` 의 파일 경로 어댑터 (데스크톱).

    Returns:
        옮길 것이 있어 실제로 손봤으면 True.
    """
    template, output = Path(template), Path(output)
    patched = carry_over_bytes(template.read_bytes(), output.read_bytes(),
                               sheet_name)
    if patched is None:
        return False

    # 쓰다가 실패해도 원본이 반쯤 덮이지 않도록 임시 파일에 쓰고 바꾼다.
    tmp = output.with_suffix(output.suffix + ".tmp")
    tmp.write_bytes(patched)
    shutil.move(str(tmp), str(output))
    return True
