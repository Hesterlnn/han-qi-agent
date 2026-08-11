#!/usr/bin/env python3
"""Convert the Han Qi Markdown guide into a formatted dependency-free DOCX."""

from __future__ import annotations

import argparse
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape


NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def xml_text(value: str) -> str:
    preserve = ' xml:space="preserve"' if value[:1].isspace() or value[-1:].isspace() else ""
    return f"<w:t{preserve}>{escape(value)}</w:t>"


def run(
    text: str,
    *,
    bold: bool = False,
    italic: bool = False,
    code: bool = False,
    color: str | None = None,
    underline: bool = False,
) -> str:
    props: list[str] = []
    if bold:
        props.append("<w:b/><w:bCs/>")
    if italic:
        props.append("<w:i/><w:iCs/>")
    if code:
        props.append('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="Microsoft YaHei"/>')
        props.append('<w:sz w:val="19"/><w:szCs w:val="19"/>')
    if color:
        props.append(f'<w:color w:val="{color}"/>')
    if underline:
        props.append('<w:u w:val="single"/>')
    prop_xml = f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""
    return f"<w:r>{prop_xml}{xml_text(text)}</w:r>"


INLINE = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))")


def inline_runs(text: str) -> str:
    result: list[str] = []
    cursor = 0
    for match in INLINE.finditer(text):
        if match.start() > cursor:
            result.append(run(text[cursor : match.start()]))
        token = match.group(0)
        if token.startswith("**"):
            result.append(run(token[2:-2], bold=True))
        elif token.startswith("`"):
            result.append(run(token[1:-1], code=True, color="7A3028"))
        else:
            label, url = re.match(r"\[([^\]]+)\]\(([^)]+)\)", token).groups()  # type: ignore[union-attr]
            result.append(run(label, color="8D3028", underline=True))
            result.append(run(f"（{url}）", color="666666"))
        cursor = match.end()
    if cursor < len(text):
        result.append(run(text[cursor:]))
    return "".join(result)


def paragraph(
    text: str = "",
    *,
    style: str | None = None,
    align: str | None = None,
    before: int | None = None,
    after: int | None = None,
    indent_left: int | None = None,
    hanging: int | None = None,
    shade: str | None = None,
    border_left: str | None = None,
    raw_runs: str | None = None,
) -> str:
    props: list[str] = []
    if style:
        props.append(f'<w:pStyle w:val="{style}"/>')
    if align:
        props.append(f'<w:jc w:val="{align}"/>')
    if before is not None or after is not None:
        attrs = []
        if before is not None:
            attrs.append(f'w:before="{before}"')
        if after is not None:
            attrs.append(f'w:after="{after}"')
        props.append(f"<w:spacing {' '.join(attrs)}/>")
    if indent_left is not None:
        hanging_attr = f' w:hanging="{hanging}"' if hanging else ""
        props.append(f'<w:ind w:left="{indent_left}"{hanging_attr}/>' )
    if shade:
        props.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>')
    if border_left:
        props.append(
            f'<w:pBdr><w:left w:val="single" w:sz="16" w:space="8" w:color="{border_left}"/></w:pBdr>'
        )
    prop_xml = f"<w:pPr>{''.join(props)}</w:pPr>" if props else ""
    content = raw_runs if raw_runs is not None else inline_runs(text)
    return f"<w:p>{prop_xml}{content}</w:p>"


def page_break() -> str:
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def toc_field() -> str:
    return (
        '<w:p><w:pPr><w:pStyle w:val="TOCHeading"/></w:pPr>'
        '<w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r>'
        '<w:r><w:instrText xml:space="preserve"> TOC \\o "1-3" \\h \\z \\u </w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
        '<w:r><w:t>在 Word 中右键此处并选择“更新域”以生成目录。</w:t></w:r>'
        '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
    )


def table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    columns = max(len(row) for row in rows)
    width = 9000 // max(columns, 1)
    grid = "".join(f'<w:gridCol w:w="{width}"/>' for _ in range(columns))
    body: list[str] = []
    for row_index, row in enumerate(rows):
        cells: list[str] = []
        for index in range(columns):
            value = row[index] if index < len(row) else ""
            shade = '<w:shd w:val="clear" w:color="auto" w:fill="EADCC8"/>' if row_index == 0 else ""
            cell_props = f'<w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{shade}</w:tcPr>'
            cell_runs = inline_runs(value)
            if row_index == 0:
                cell_runs = run(value, bold=True)
            cells.append(f"<w:tc>{cell_props}<w:p>{cell_runs}</w:p></w:tc>")
        body.append(f"<w:tr>{''.join(cells)}</w:tr>")
    borders = (
        '<w:tblBorders><w:top w:val="single" w:sz="6" w:color="B7A58D"/>'
        '<w:left w:val="single" w:sz="6" w:color="B7A58D"/>'
        '<w:bottom w:val="single" w:sz="6" w:color="B7A58D"/>'
        '<w:right w:val="single" w:sz="6" w:color="B7A58D"/>'
        '<w:insideH w:val="single" w:sz="4" w:color="D8CAB7"/>'
        '<w:insideV w:val="single" w:sz="4" w:color="D8CAB7"/></w:tblBorders>'
    )
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="9000" w:type="dxa"/>'
        f'{borders}<w:tblCellMar><w:top w:w="80" w:type="dxa"/><w:left w:w="100" w:type="dxa"/>'
        '<w:bottom w:w="80" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar>'
        f"</w:tblPr><w:tblGrid>{grid}</w:tblGrid>{''.join(body)}</w:tbl>"
    )


def parse_table(lines: list[str], start: int) -> tuple[list[list[str]], int]:
    rows: list[list[str]] = []
    index = start
    while index < len(lines) and lines[index].strip().startswith("|"):
        values = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
        if not all(re.fullmatch(r":?-{3,}:?", value) for value in values):
            rows.append(values)
        index += 1
    return rows, index


def markdown_to_body(
    markdown: str,
    subtitle: str = "角色对话、情境推演、现代任事与文献研究",
) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    index = 0
    in_code = False
    code_lines: list[str] = []
    title_seen = False
    toc_active = False
    toc_completed = False

    while index < len(lines):
        raw = lines[index]
        stripped = raw.strip()

        if stripped.startswith("```"):
            if not in_code:
                in_code = True
                code_lines = []
            else:
                for code_line in code_lines or [""]:
                    output.append(
                        paragraph(
                            raw_runs=run(code_line or " ", code=True),
                            style="CodeBlock",
                            shade="F2EBDD",
                        )
                    )
                output.append(paragraph("", after=80))
                in_code = False
            index += 1
            continue
        if in_code:
            code_lines.append(raw)
            index += 1
            continue

        heading = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if heading:
            level = len(heading.group(1))
            text = heading.group(2)
            if level == 1 and not title_seen:
                output.append(paragraph(text, style="Title", align="center", after=220))
                output.append(
                    paragraph(
                        subtitle,
                        style="Subtitle",
                        align="center",
                        after=260,
                    )
                )
                output.append(
                    paragraph(
                        f"Word版生成日期：{datetime.now().astimezone().strftime('%Y-%m-%d')}",
                        style="Subtitle",
                        align="center",
                    )
                )
                title_seen = True
            elif text == "目录" and not toc_completed:
                output.append(paragraph("目录", style="Heading1"))
                output.append(toc_field())
                toc_active = True
            else:
                output.append(paragraph(text, style=f"Heading{level}"))
            index += 1
            continue

        if toc_active:
            if stripped == "---":
                toc_active = False
                toc_completed = True
            index += 1
            continue

        if stripped == "---":
            output.append(paragraph("", after=80))
            index += 1
            continue

        if stripped.startswith("|") and index + 1 < len(lines) and lines[index + 1].strip().startswith("|"):
            rows, index = parse_table(lines, index)
            output.append(table(rows))
            output.append(paragraph("", after=100))
            continue

        if not stripped:
            index += 1
            continue

        if stripped.startswith(">"):
            text = stripped.lstrip("> ")
            output.append(
                paragraph(
                    text,
                    style="Quote",
                    shade="F7F1E8",
                    border_left="8D3028",
                    indent_left=420,
                )
            )
            index += 1
            continue

        bullet = re.match(r"^[-*]\s+(.+)$", stripped)
        if bullet:
            output.append(
                paragraph(
                    f"•  {bullet.group(1)}",
                    style="ListParagraph",
                    indent_left=560,
                    hanging=300,
                )
            )
            index += 1
            continue

        numbered = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if numbered:
            output.append(
                paragraph(
                    f"{numbered.group(1)}.  {numbered.group(2)}",
                    style="ListParagraph",
                    indent_left=560,
                    hanging=300,
                )
            )
            index += 1
            continue

        paragraph_lines = [stripped]
        index += 1
        while index < len(lines):
            candidate = lines[index].strip()
            if not candidate:
                break
            if re.match(r"^(#{1,3})\s+", candidate) or candidate.startswith(("```", ">", "|", "---")):
                break
            if re.match(r"^[-*]\s+", candidate) or re.match(r"^\d+\.\s+", candidate):
                break
            paragraph_lines.append(candidate)
            index += 1
        output.append(paragraph(" ".join(paragraph_lines), style="Normal"))

    return "".join(output)


def styles_xml() -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{NS}">
  <w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Aptos" w:hAnsi="Aptos" w:eastAsia="Microsoft YaHei"/><w:lang w:val="en-US" w:eastAsia="zh-CN"/><w:sz w:val="21"/><w:szCs w:val="21"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="360" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:after="120" w:line="360" w:lineRule="auto"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="1200" w:after="240"/><w:jc w:val="center"/></w:pPr><w:rPr><w:rFonts w:eastAsia="STZhongsong"/><w:b/><w:color w:val="57251F"/><w:sz w:val="48"/><w:szCs w:val="48"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/><w:pPr><w:jc w:val="center"/><w:spacing w:after="120"/></w:pPr><w:rPr><w:color w:val="756756"/><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:keepLines/><w:pageBreakBefore/><w:spacing w:before="240" w:after="180"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:rFonts w:eastAsia="Microsoft YaHei"/><w:b/><w:color w:val="8D3028"/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="260" w:after="140"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:color w:val="623A31"/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="220" w:after="100"/><w:outlineLvl w:val="2"/></w:pPr><w:rPr><w:b/><w:color w:val="5E5144"/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="70"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="CodeBlock"><w:name w:val="Code Block"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="0" w:line="280" w:lineRule="auto"/><w:ind w:left="280" w:right="280"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="100" w:after="100"/></w:pPr><w:rPr><w:i/><w:color w:val="594B40"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="TOCHeading"><w:name w:val="TOC Heading"/><w:basedOn w:val="Heading1"/><w:qFormat/></w:style>
</w:styles>'''


def document_xml(body: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{NS}" xmlns:r="{RNS}"><w:body>{body}
<w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/><w:footerReference w:type="default" r:id="rIdFooter"/>
<w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1276" w:header="567" w:footer="567" w:gutter="0"/>
<w:cols w:space="425"/><w:docGrid w:linePitch="312"/></w:sectPr></w:body></w:document>'''


def header_xml(title: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:hdr xmlns:w="{NS}"><w:p><w:pPr><w:jc w:val="right"/><w:pBdr><w:bottom w:val="single" w:sz="4" w:space="4" w:color="D8CAB7"/></w:pBdr></w:pPr><w:r><w:rPr><w:color w:val="887A68"/><w:sz w:val="18"/></w:rPr><w:t>{escape(title)}</w:t></w:r></w:p></w:hdr>'''


def footer_xml() -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="{NS}"><w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:color w:val="887A68"/><w:sz w:val="18"/></w:rPr><w:t>— </w:t></w:r><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText> PAGE </w:instrText></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r><w:r><w:t> —</w:t></w:r></w:p></w:ftr>'''


def build_docx(
    source: Path,
    output: Path,
    *,
    title: str | None = None,
    subtitle: str = "角色对话、情境推演、现代任事与文献研究",
) -> None:
    markdown = source.read_text(encoding="utf-8")
    title_match = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
    document_title = title or (title_match.group(1).strip() if title_match else source.stem)
    body = markdown_to_body(markdown, subtitle)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    files = {
        "[Content_Types].xml": f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/><Override PartName="/word/fontTable.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"/><Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/><Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>''',
        "_rels/.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>''',
        "word/document.xml": document_xml(body),
        "word/styles.xml": styles_xml(),
        "word/settings.xml": f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:settings xmlns:w="{NS}"><w:zoom w:percent="100"/><w:updateFields w:val="true"/><w:defaultTabStop w:val="420"/><w:characterSpacingControl w:val="doNotCompress"/></w:settings>''',
        "word/fontTable.xml": f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:fonts xmlns:w="{NS}"><w:font w:name="Microsoft YaHei"/><w:font w:name="STZhongsong"/><w:font w:name="Aptos"/><w:font w:name="Consolas"/></w:fonts>''',
        "word/header1.xml": header_xml(document_title),
        "word/footer1.xml": footer_xml(),
        "word/_rels/document.xml.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rIdHeader" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/><Relationship Id="rIdFooter" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/><Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rIdSettings" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/><Relationship Id="rIdFonts" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable" Target="fontTable.xml"/></Relationships>''',
        "docProps/core.xml": f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>{escape(document_title)}</dc:title><dc:subject>韩琦智能体项目文档</dc:subject><dc:creator>韩琦智能体项目</dc:creator><cp:keywords>韩琦; 智能体; 文献研究; 自动测试</cp:keywords><dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified></cp:coreProperties>''',
        "docProps/app.xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Han Qi Agent Documentation Builder</Application><AppVersion>2.0</AppVersion></Properties>''',
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content.encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--title")
    parser.add_argument(
        "--subtitle",
        default="角色对话、情境推演、现代任事与文献研究",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    if not source.is_file():
        raise SystemExit(f"Source does not exist: {source}")
    if output.exists() and not args.force:
        raise SystemExit(f"Output already exists: {output}. Pass --force to replace it.")
    build_docx(source, output, title=args.title, subtitle=args.subtitle)
    print(f"Built {output} ({output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
