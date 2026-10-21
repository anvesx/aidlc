#!/usr/bin/env python3
"""Turn an AIDLC markdown document into HTML in the google-document style.

Google Drive turns this HTML into a Google Doc that keeps the style: navy title and
headings, black text, bordered tables with a light blue header row. Drive drops the
Manrope font on the way in, so after uploading, set it with one Google Docs edit (see
skills/google-document/SKILL.md).

Usage:
  doc_html.py DOC.md [--subtitle "Context | Scope"] > DOC.html

The first "# " heading is the title. Other headings, tables, "- " bullets, numbered
lists and paragraphs are kept. Inline **bold**, `code` and [text](https://link) are
kept; other markdown is shown as plain text. Standard library only.
"""

import argparse
import html
import re
import sys

BRAND = "#1F3B4D"   # title and headings only
LIGHT = "#EEF3F7"   # table header fill
BLACK = "#000000"   # all other text
BORDER = "#BFBFBF"
FONT = "Manrope"

BASE = "font-family:{};color:{};".format(FONT, BLACK)
STYLE = {
    "title": "font-family:{};font-size:24pt;font-weight:bold;color:{};margin:0 0 3pt 0".format(FONT, BRAND),
    "subtitle": BASE + "font-size:11pt;margin:0 0 15pt 0",
    1: "font-family:{};font-size:16pt;font-weight:bold;color:{};margin:18pt 0 8pt 0".format(FONT, BRAND),
    2: "font-family:{};font-size:13pt;font-weight:bold;color:{};margin:14pt 0 6pt 0".format(FONT, BRAND),
    3: "font-family:{};font-size:11pt;font-weight:bold;color:{};margin:10pt 0 4pt 0".format(FONT, BRAND),
    "p": BASE + "font-size:11pt;margin:0 0 6pt 0",
    "li": BASE + "font-size:11pt;margin:0 0 4pt 0",
    "th": BASE + "font-size:10pt;font-weight:bold;background:{};border:1px solid {};padding:4pt 6pt;"
                 "text-align:left;vertical-align:top".format(LIGHT, BORDER),
    "td": BASE + "font-size:10pt;border:1px solid {};padding:4pt 6pt;vertical-align:top".format(BORDER),
}

TABLE_SEPARATOR = re.compile(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def inline(text):
    """Escape the text, then turn **bold**, `code` and [text](link) into HTML."""
    parts = []
    last = 0
    for m in LINK.finditer(text):
        parts.append(_marks(html.escape(text[last:m.start()], quote=False)))
        parts.append('<a href="{}">{}</a>'.format(html.escape(m.group(2)), _marks(html.escape(m.group(1), quote=False))))
        last = m.end()
    parts.append(_marks(html.escape(text[last:], quote=False)))
    return "".join(parts)


def _marks(text):
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r'<span style="font-family:Consolas,monospace">\1</span>', text)
    return text


def split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line)]


def column_widths(header, rows):
    """Percent widths: short columns (IDs) narrow, long text wide, never squeezed to nothing."""
    n = len(header)
    weights = []
    for i in range(n):
        cells = [r[i] if i < len(r) else "" for r in rows]
        average = sum(len(c) for c in cells) / len(cells) if cells else 0
        weights.append(max(4.0, len(header[i]) + 2, average) ** 0.5)
    total = sum(weights)
    widths = [max(8, round(100 * w / total)) for w in weights]
    widths[widths.index(max(widths))] -= sum(widths) - 100
    return widths


def table(header, rows):
    widths = column_widths(header, rows)
    out = ['<table style="border-collapse:collapse;width:100%">']
    out.append("<tr>" + "".join(
        '<th style="{};width:{}%">{}</th>'.format(STYLE["th"], w, inline(c)) for c, w in zip(header, widths)) + "</tr>")
    for r in rows:
        r = (r + [""] * len(header))[:len(header)]
        out.append("<tr>" + "".join('<td style="{}">{}</td>'.format(STYLE["td"], inline(c)) for c in r) + "</tr>")
    out.append("</table>")
    return "\n".join(out)


def convert(markdown, subtitle=None):
    lines = markdown.splitlines()
    out = []
    title_done = False
    i = 0
    para = []

    def flush():
        if para:
            out.append('<p style="{}">{}</p>'.format(STYLE["p"], inline(" ".join(para))))
            para.clear()

    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if not stripped:
            flush()
        elif heading:
            flush()
            level, text = len(heading.group(1)), heading.group(2).strip()
            if level == 1 and not title_done:
                out.append('<p style="{}">{}</p>'.format(STYLE["title"], inline(text)))
                if subtitle:
                    out.append('<p style="{}">{}</p>'.format(STYLE["subtitle"], inline(subtitle)))
                title_done = True
            else:
                tag = min(max(level - 1, 1), 3)
                out.append('<h{0} style="{1}">{2}</h{0}>'.format(tag, STYLE[tag], inline(text)))
        elif stripped.startswith("|") and TABLE_SEPARATOR.match(nxt):
            flush()
            header = split_row(stripped)
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            out.append(table(header, rows))
            continue
        elif re.match(r"^[-*]\s+", stripped) or re.match(r"^\d+\.\s+", stripped):
            flush()
            ordered = bool(re.match(r"^\d+\.\s+", stripped))
            items = []
            while i < len(lines):
                s = lines[i].strip()
                m = re.match(r"^\d+\.\s+(.*)$", s) if ordered else re.match(r"^[-*]\s+(.*)$", s)
                if not m:
                    break
                items.append('<li style="{}">{}</li>'.format(STYLE["li"], inline(m.group(1))))
                i += 1
            tag = "ol" if ordered else "ul"
            out.append("<{0}>{1}</{0}>".format(tag, "".join(items)))
            continue
        else:
            para.append(stripped)
        i += 1
    flush()
    body = "\n".join(out)
    return '<html><body style="{}font-size:11pt">\n{}\n</body></html>\n'.format(BASE, body)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("doc")
    parser.add_argument("--subtitle")
    args = parser.parse_args(argv)
    try:
        with open(args.doc, encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        print("can't read {}: {}".format(args.doc, exc), file=sys.stderr)
        return 2
    sys.stdout.write(convert(text, args.subtitle))
    return 0


if __name__ == "__main__":
    sys.exit(main())
