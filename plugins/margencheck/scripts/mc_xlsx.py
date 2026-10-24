"""Minimal XLSX reader/writer using only the Python standard library.

MargenCheck has to run wherever Claude runs (macOS system Python 3.9, Cowork sandbox, Windows),
so it cannot rely on openpyxl. The writer supports what the report needs: bold/coloured header,
number formats (EUR, %, integers), coloured verdict cells, wrapped text, column widths and a
frozen header row. The reader returns cell values of every sheet (for supplier price lists).
"""
import re
import zipfile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}
_COL_RE = re.compile(r"([A-Z]+)(\d+)")
_ILLEGAL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")


def col_letter(idx):
    s = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        s = chr(65 + rem) + s
    return s


def _col_index(ref):
    n = 0
    for ch in _COL_RE.match(ref).group(1):
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _text(el):
    return "".join(t.text or "" for t in el.iter("{%s}t" % NS["m"]))


def read_xlsx(path):
    """Return [(sheet_name, rows)]; rows are lists of str/float/None."""
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = [_text(si) for si in root.findall("m:si", NS)]
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {r.get("Id"): r.get("Target") for r in rels.findall("pr:Relationship", NS)}
        out = []
        for sh in wb.findall("m:sheets/m:sheet", NS):
            target = (targets.get(sh.get("{%s}id" % NS["r"]), "") or "").lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            if target in names:
                out.append((sh.get("name"), _read_sheet(z.read(target), shared)))
        return out


def _read_sheet(data, shared):
    root = ET.fromstring(data)
    rows = []
    for row in root.iter("{%s}row" % NS["m"]):
        rnum = row.get("r")
        if rnum is not None:
            while len(rows) < int(rnum) - 1:
                rows.append([])
        vals = []
        for c in row.findall("m:c", NS):
            ref = c.get("r")
            if ref:
                while len(vals) < _col_index(ref):
                    vals.append(None)
            t = c.get("t")
            v = c.find("m:v", NS)
            if t == "s" and v is not None:
                val = shared[int(v.text)]
            elif t == "inlineStr":
                el = c.find("m:is", NS)
                val = _text(el) if el is not None else ""
            elif t in ("str", "e"):
                val = v.text if v is not None else ""
            elif t == "b":
                val = (v.text == "1") if v is not None else None
            elif v is None or v.text is None:
                val = None
            else:
                try:
                    val = float(v.text)
                except ValueError:
                    val = v.text
            vals.append(val)
        rows.append(vals)
    return rows


# ---------------------------------------------------------------- writer
# style ids (cellXfs index)
S = {"text": 0, "head": 1, "eur": 2, "pct": 3, "int": 4, "dec": 5, "wrap": 6, "go": 7, "test": 8, "nein": 9,
     "title": 10, "bold": 11, "eur_bold": 12, "note": 13, "dec3": 14, "date": 15}


class Sheet(object):
    def __init__(self, name, widths=None, freeze=1):
        self.name = name
        self.rows = []
        self.widths = widths or []
        self.freeze = freeze

    def add(self, cells):
        """cells: list of values or (value, style) tuples."""
        self.rows.append(cells)

    def blank(self):
        self.rows.append([])


def _styles():
    numfmts = ('<numFmts count="4">'
               '<numFmt numFmtId="164" formatCode="#,##0.00\\ &quot;€&quot;"/>'
               '<numFmt numFmtId="165" formatCode="0.0%"/>'
               '<numFmt numFmtId="166" formatCode="0.000"/>'
               '<numFmt numFmtId="167" formatCode="dd.mm.yyyy"/>'
               '</numFmts>')
    fonts = ('<fonts count="5">'
             '<font><sz val="10"/><name val="Arial"/></font>'
             '<font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Arial"/></font>'
             '<font><b/><sz val="14"/><color rgb="FF1F3864"/><name val="Arial"/></font>'
             '<font><b/><sz val="10"/><name val="Arial"/></font>'
             '<font><i/><sz val="9"/><color rgb="FF595959"/><name val="Arial"/></font>'
             '</fonts>')
    fills = ('<fills count="6"><fill><patternFill patternType="none"/></fill>'
             '<fill><patternFill patternType="gray125"/></fill>'
             '<fill><patternFill patternType="solid"><fgColor rgb="FF1F3864"/></patternFill></fill>'
             '<fill><patternFill patternType="solid"><fgColor rgb="FFD6EBD8"/></patternFill></fill>'
             '<fill><patternFill patternType="solid"><fgColor rgb="FFFDF0D5"/></patternFill></fill>'
             '<fill><patternFill patternType="solid"><fgColor rgb="FFF8D7DA"/></patternFill></fill>'
             '</fills>')
    borders = ('<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border>'
               '<border><left style="thin"><color rgb="FFB7BFCB"/></left><right style="thin"><color rgb="FFB7BFCB"/></right>'
               '<top style="thin"><color rgb="FFB7BFCB"/></top><bottom style="thin"><color rgb="FFB7BFCB"/></bottom><diagonal/></border>'
               '</borders>')
    top = '<alignment vertical="top"/>'
    wrap = '<alignment vertical="top" wrapText="1"/>'
    xfs = [
        ('0', '0', '0', '0', top),            # text
        ('0', '1', '2', '1', wrap),           # head
        ('164', '0', '0', '0', top),          # eur
        ('165', '0', '0', '0', top),          # pct
        ('3', '0', '0', '0', top),            # int  (#,##0)
        ('4', '0', '0', '0', top),            # dec  (#,##0.00)
        ('0', '0', '0', '0', wrap),           # wrap
        ('0', '3', '3', '0', top),            # go
        ('0', '3', '4', '0', top),            # test
        ('0', '3', '5', '0', top),            # nein
        ('0', '2', '0', '0', top),            # title
        ('0', '3', '0', '0', top),            # bold
        ('164', '3', '0', '0', top),          # eur_bold
        ('0', '4', '0', '0', wrap),           # note
        ('166', '0', '0', '0', top),          # dec3
        ('167', '0', '0', '0', top),          # date
    ]
    cx = "".join('<xf numFmtId="%s" fontId="%s" fillId="%s" borderId="%s" xfId="0" applyNumberFormat="1" applyFont="1" '
                 'applyFill="1" applyBorder="1" applyAlignment="1">%s</xf>' % x for x in xfs)
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="%s">' % NS["m"]
            + numfmts + fonts + fills + borders
            + '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            + '<cellXfs count="%d">%s</cellXfs>' % (len(xfs), cx)
            + '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')


def _sheet_name(name):
    return re.sub(r"[\[\]:*?/\\]", "-", name)[:31]


def write_xlsx(path, sheets):
    """Write a list of Sheet objects."""
    sst, sst_index = [], {}

    def s_idx(text):
        text = _ILLEGAL.sub("", text)
        if text not in sst_index:
            sst_index[text] = len(sst)
            sst.append(text)
        return sst_index[text]

    xml_sheets = []
    for sh in sheets:
        parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                 '<worksheet xmlns="%s" xmlns:r="%s">' % (NS["m"], NS["r"])]
        if sh.freeze:
            parts.append('<sheetViews><sheetView workbookViewId="0"><pane ySplit="%d" topLeftCell="A%d" '
                         'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>' % (sh.freeze, sh.freeze + 1))
        if sh.widths:
            parts.append("<cols>" + "".join('<col min="%d" max="%d" width="%s" customWidth="1"/>' % (i + 1, i + 1, w)
                                            for i, w in enumerate(sh.widths)) + "</cols>")
        parts.append("<sheetData>")
        for r, row in enumerate(sh.rows):
            cells = []
            for c, cell in enumerate(row):
                val, style = (cell if isinstance(cell, tuple) else (cell, None))
                if val is None or val == "":
                    if style in ("head", "go", "test", "nein"):
                        cells.append('<c r="%s%d" s="%d"/>' % (col_letter(c), r + 1, S[style]))
                    continue
                ref = "%s%d" % (col_letter(c), r + 1)
                sid = S.get(style, 0) if style else (S["dec"] if isinstance(val, float) else 0)
                st = ' s="%d"' % sid
                if isinstance(val, bool):
                    cells.append('<c r="%s"%s t="s"><v>%d</v></c>' % (ref, st, s_idx("ja" if val else "nein")))
                elif isinstance(val, (int, float)):
                    cells.append('<c r="%s"%s><v>%s</v></c>' % (ref, st, repr(round(float(val), 6))))
                elif hasattr(val, "toordinal"):
                    serial = val.toordinal() - 693594  # 1899-12-30
                    cells.append('<c r="%s" s="%d"><v>%d</v></c>' % (ref, S["date"], serial))
                else:
                    cells.append('<c r="%s"%s t="s"><v>%d</v></c>' % (ref, st, s_idx(str(val))))
            parts.append('<row r="%d">%s</row>' % (r + 1, "".join(cells)))
        parts.append("</sheetData></worksheet>")
        xml_sheets.append("".join(parts))

    n = len(sheets)
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          + "".join('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % (i + 1) for i in range(n))
          + '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
          '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
          '</Types>')
    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="%s">'
                 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                 'Target="xl/workbook.xml"/></Relationships>' % NS["pr"])
    workbook = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="%s" xmlns:r="%s"><sheets>' % (NS["m"], NS["r"])
                + "".join('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (escape(_sheet_name(s.name), {'"': "&quot;"}), i + 1, i + 1)
                          for i, s in enumerate(sheets))
                + "</sheets></workbook>")
    wb_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="%s">' % NS["pr"]
               + "".join('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                         'Target="worksheets/sheet%d.xml"/>' % (i + 1, i + 1) for i in range(n))
               + '<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>' % (n + 1)
               + '<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>' % (n + 2)
               + "</Relationships>")
    sst_xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><sst xmlns="%s" count="%d" uniqueCount="%d">' % (NS["m"], len(sst), len(sst))
               + "".join('<si><t xml:space="preserve">%s</t></si>' % escape(s) for s in sst) + "</sst>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/styles.xml", _styles())
        z.writestr("xl/sharedStrings.xml", sst_xml)
        for i, x in enumerate(xml_sheets):
            z.writestr("xl/worksheets/sheet%d.xml" % (i + 1), x)
