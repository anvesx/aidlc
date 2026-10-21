---
name: google-document
description: The devx document style (Manrope font, black body text, navy headings, bordered tables with light blue header rows), for Google Docs and Word files. Use whenever creating a PRD, TDD or any other Google Doc or .docx for devx, including AIDLC's PRD and TDD.
---

# devx documents

Every document follows the same look, whether it is a Google Doc or a Word file. Follow it exactly and don't improvise a different look.

## Golden rules

1. Font is always Manrope, normal weight, for every run in the document. Bold is allowed only for headings, table header rows, and short inline labels. Never use italics unless the person asks.
2. All general/body text color is black (000000). This includes subtitles, table cell text, and bullet text.
3. Headings and the document title use navy 1F3B4D as the accent color. Nothing else in the document is colored.
4. Never use em dashes anywhere in the document. Use commas, periods, or the word "to" instead.
5. Keep the document scannable: short intro sentence under each heading, then a table or bullets. Avoid long paragraphs.

## Style constants

```
BRAND = 1F3B4D   headings and title only
LIGHT = EEF3F7   table header row fill
BLACK = 000000   all general text
FONT  = Manrope  every run, normal weight
Sizes: title 24pt bold, subtitle 11pt, heading 1 16pt bold, heading 2 13pt bold, body 11pt, table text 10pt.
```

## Document structure

1. Title block: document title (bold, 24pt, navy), then one subtitle line (11pt, black) with context separated by `|`, for example "Ticket 86abc | Project Escape Plan | PM: <name>".
2. Sections as headings (16pt bold, navy). For a general document, number them "1. Section Name" and end with a short "Summary" of 3 to 5 bullets. For an AIDLC template (PRD, TDD), keep the template's headings and IDs exactly, with no extra numbers and no Summary: units and checks point to them.
3. H2 only if needed (13pt bold, navy).
4. Content under each heading: one short lead-in paragraph, then a table or bullet list.

## A Google Doc (the usual case)

Uploading a Word file through the Drive tool means passing the whole file as one long base64 string, which breaks. So a Google Doc is made from HTML in this style, which Drive turns into a Google Doc:

1. Write the document as markdown (for AIDLC, from its template) and save it to a file.
2. Turn it into HTML in this style:
   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doc_html.py" <doc.md> --subtitle "<context | context>" > <doc.html>`
3. Create the Google Doc with the Google Drive connector: `create_file` with `title`, `parentId` (the folder), `contentMimeType: "text/html"` and the HTML as `textContent`. Keep the returned file `id`.
4. Drive keeps the colors, sizes, bold, table borders, header fill and column widths, but sets the font to Arial and the margins to 1 inch. Fix both with one Google Docs connector `update_doc` call. It needs the body's last `endIndex`: `read_doc` gives it (`tabs[0].documentTab.body.content`, last element). `read_doc`'s answer is very long even for a short doc; if the tool saves it to a file, read just that number from the file with a short script.
   ```
   [{"updateTextStyle": {"range": {"startIndex": 1, "endIndex": <last endIndex>},
      "textStyle": {"weightedFontFamily": {"fontFamily": "Manrope", "weight": 400}}, "fields": "weightedFontFamily"}},
    {"updateDocumentStyle": {"documentStyle": {"marginTop": {"magnitude": 54, "unit": "PT"},
      "marginBottom": {"magnitude": 54, "unit": "PT"}, "marginLeft": {"magnitude": 54, "unit": "PT"},
      "marginRight": {"magnitude": 54, "unit": "PT"}},
      "fields": "marginTop,marginBottom,marginLeft,marginRight"}}]
   ```
   The answer's `writeControl.requiredRevisionId` is the doc's revision ID after the fix.
5. To change the doc later, edit it in place with `update_doc` (the link stays the same), then run step 4's font fix again on the whole body. If most of it changes, make a new doc from steps 1 to 4 instead.

## A Word file (only when the person asks for .docx)

- US Letter: `page: { size: { width: 12240, height: 15840 } }`, margins 1080 DXA (0.75 inch) on all four sides, default run `font: "Manrope", size: 22` (11pt).
- Tables: `docx` (npm) Table with `columnWidths` on the table and `width` on every cell, both `WidthType.DXA`, summing to 10080. Header row bold, shading fill `EEF3F7` with `ShadingType.CLEAR`, `tableHeader: true`. Cell margins `{ top: 80, bottom: 80, left: 120, right: 120 }`. Cell text size 20 (10pt), black. Two columns roughly 3000 / 7080; three roughly 2600 / 2900 / 4580.
- Bullets: never a literal bullet character; use a numbering config with `LevelFormat.BULLET`.
- How to build:
  1. Read the docx skill's SKILL.md for library gotchas if it is available.
  2. Copy `${CLAUDE_PLUGIN_ROOT}/skills/google-document/templates/build_doc_template.js`, replace the content arrays and title, keep the style constants and helpers unchanged.
  3. Run it with node. If `require('docx')` fails, `npm install docx` first.
  4. Check: convert to PDF with LibreOffice, render pages with `pdftoppm`, and look at them before handing it over. If Manrope isn't installed there, the preview may show another font; the .docx is still correct.
