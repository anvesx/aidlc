// Clean Word Docs template. Keep style constants and helpers unchanged.
// Replace TITLE, SUBTITLE, and the content in the sections array.
const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, AlignmentType, ShadingType, LevelFormat
} = require('docx');

// ---- style constants (do not change) ----
const BRAND = "1F3B4D";   // headings and title only
const LIGHT = "EEF3F7";   // table header fill
const BLACK = "000000";   // all general text
const FONT = "Manrope";   // every run, normal weight
const TABLE_TOTAL = 10080; // full content width in DXA

// ---- helpers (do not change) ----
function h1(text) { return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 360, after: 160 }, children: [new TextRun({ text, color: BRAND, font: FONT })] }); }
function h2(text) { return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 280, after: 120 }, children: [new TextRun({ text, color: BRAND, font: FONT })] }); }
function p(text, opts = {}) { return new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text, color: BLACK, font: FONT, ...opts })] }); }
function bullet(text) { return new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 80 }, children: [new TextRun({ text, color: BLACK, font: FONT })] }); }

function cell(text, { bold = false, fill = null, width } = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: fill ? { type: ShadingType.CLEAR, fill } : undefined,
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({ children: [new TextRun({ text, bold, size: 20, color: BLACK, font: FONT })] })]
  });
}

function makeTable(headers, rows, widths) {
  return new Table({
    columnWidths: widths,
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    rows: [
      new TableRow({ tableHeader: true, children: headers.map((t, i) => cell(t, { bold: true, fill: LIGHT, width: widths[i] })) }),
      ...rows.map(r => new TableRow({ children: r.map((t, i) => cell(t, { width: widths[i] })) }))
    ]
  });
}

// ---- content (replace) ----
const TITLE = "Document Title";
const SUBTITLE = "Context | Scope | Month Year";

const exampleRows = [
  ["Item one", "Detail about item one"],
  ["Item two", "Detail about item two"]
];

const doc = new Document({
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 480, hanging: 240 } } } }]
    }]
  },
  styles: {
    default: {
      document: { run: { font: FONT, size: 22, color: BLACK } },
      heading1: { run: { size: 32, bold: true, font: FONT } },
      heading2: { run: { size: 26, bold: true, font: FONT } }
    }
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1080, bottom: 1080, left: 1080, right: 1080 } } },
    children: [
      new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: TITLE, bold: true, size: 48, color: BRAND, font: FONT })] }),
      new Paragraph({ spacing: { after: 300 }, children: [new TextRun({ text: SUBTITLE, size: 22, color: BLACK, font: FONT })] }),

      h1("1. First Section"),
      p("One short lead-in sentence describing the table below."),
      makeTable(["Item", "Detail"], exampleRows, [3000, 7080]),

      h1("2. Summary"),
      bullet("First key takeaway."),
      bullet("Second key takeaway.")
    ]
  }]
});

Packer.toBuffer(doc).then(b => { fs.writeFileSync("output.docx", b); console.log("done", b.length); });
