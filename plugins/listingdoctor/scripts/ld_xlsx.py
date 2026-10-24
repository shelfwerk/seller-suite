"""Minimal XLSX reader/writer using only the Python standard library.

ListingDoctor must run on any machine that has Claude (macOS system Python 3.9, Cowork sandbox,
Windows), so it cannot rely on openpyxl being installed. This module reads the cell values of
every sheet and writes simple workbooks (shared strings, numbers, bold header row, frozen
header, column widths) that Excel, Numbers, LibreOffice and Amazon's bulk upload accept.
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


def _col_index(ref):
    letters = _COL_RE.match(ref).group(1)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _col_letter(idx):
    s = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        s = chr(65 + rem) + s
    return s


def _text(el):
    """Concatenate all <t> texts below an element (handles rich text runs)."""
    return "".join(t.text or "" for t in el.iter("{%s}t" % NS["m"]))


def read_xlsx(path):
    """Return a list of (sheet_name, rows); rows are lists of str/float/None."""
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
            rid = sh.get("{%s}id" % NS["r"])
            target = targets.get(rid, "")
            target = target.lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            if target not in names:
                continue
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
                idx = _col_index(ref)
                while len(vals) < idx:
                    vals.append(None)
            t = c.get("t")
            v = c.find("m:v", NS)
            if t == "s" and v is not None:
                val = shared[int(v.text)]
            elif t == "inlineStr":
                is_el = c.find("m:is", NS)
                val = _text(is_el) if is_el is not None else ""
            elif t in ("str", "e"):
                val = v.text if v is not None else ""
            elif t == "b":
                val = (v.text == "1") if v is not None else None
            else:
                if v is None or v.text is None:
                    val = None
                else:
                    try:
                        val = float(v.text)
                    except ValueError:
                        val = v.text
            vals.append(val)
        rows.append(vals)
    return rows


_ILLEGAL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")


def write_xlsx(path, sheets):
    """Write sheets = [(name, rows, opts)]; opts: {"widths": [..], "header": True}.

    Cell values: None -> empty, int/float -> number, everything else -> string.
    """
    sst, sst_index = [], {}

    def s_idx(text):
        text = _ILLEGAL.sub("", text)
        if text not in sst_index:
            sst_index[text] = len(sst)
            sst.append(text)
        return sst_index[text]

    sheet_xml = []
    for name, rows, opts in sheets:
        opts = opts or {}
        header = opts.get("header", True)
        parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                 '<worksheet xmlns="%s" xmlns:r="%s">' % (NS["m"], NS["r"])]
        if header and rows:
            parts.append('<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
                         'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>')
        widths = opts.get("widths")
        if widths:
            parts.append("<cols>")
            for i, w in enumerate(widths):
                parts.append('<col min="%d" max="%d" width="%s" customWidth="1"/>' % (i + 1, i + 1, w))
            parts.append("</cols>")
        parts.append("<sheetData>")
        for r, row in enumerate(rows):
            cells = []
            for c, val in enumerate(row):
                if val is None or val == "":
                    continue
                ref = "%s%d" % (_col_letter(c), r + 1)
                style = ' s="1"' if (header and r == 0) else ""
                if isinstance(val, bool):
                    cells.append('<c r="%s"%s t="str"><v>%s</v></c>' % (ref, style, "TRUE" if val else "FALSE"))
                elif isinstance(val, (int, float)):
                    cells.append('<c r="%s"%s><v>%s</v></c>' % (ref, style, repr(round(val, 6)) if isinstance(val, float) else val))
                else:
                    cells.append('<c r="%s"%s t="s"><v>%d</v></c>' % (ref, style, s_idx(str(val))))
            parts.append('<row r="%d">%s</row>' % (r + 1, "".join(cells)))
        parts.append("</sheetData></worksheet>")
        sheet_xml.append("".join(parts))

    n = len(sheets)
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + "".join('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % (i + 1) for i in range(n))
        + '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        "</Types>")
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="%s"><Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>' % NS["pr"])
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="%s" xmlns:r="%s"><sheets>' % (NS["m"], NS["r"])
        + "".join('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (escape(_sheet_name(name), {'"': "&quot;"}), i + 1, i + 1)
                  for i, (name, _, _) in enumerate(sheets))
        + "</sheets></workbook>")
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="%s">' % NS["pr"]
        + "".join('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                  'Target="worksheets/sheet%d.xml"/>' % (i + 1, i + 1) for i in range(n))
        + '<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>' % (n + 1)
        + '<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>' % (n + 2)
        + "</Relationships>")
    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="%s">'
        '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>" % NS["m"])
    sst_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="%s" count="%d" uniqueCount="%d">' % (NS["m"], len(sst), len(sst))
        + "".join('<si><t xml:space="preserve">%s</t></si>' % escape(s) for s in sst)
        + "</sst>")

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/styles.xml", styles)
        z.writestr("xl/sharedStrings.xml", sst_xml)
        for i, xml in enumerate(sheet_xml):
            z.writestr("xl/worksheets/sheet%d.xml" % (i + 1), xml)


def _sheet_name(name):
    """Excel sheet names: max 31 chars, none of []:*?/\\ ."""
    return re.sub(r"[\[\]:*?/\\]", "-", name)[:31]
