import datetime
import html
import re

import config

INC_RE = re.compile(r"^INC\d+$")
INET_RE = re.compile(r"^\d{4,}$")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
DUR_RE = re.compile(r"(?:^\d+:\d+|Jam|Hari|Menit)")
CTYPE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
TYPE_WORDS = {"INTERNET", "IPTV", "VOICE", "MANJA"}

KEYWORD_REJAK = re.compile(r"JAKBAR|JAKARTA\s+BARAT")
KEYWORD_REJUT = re.compile(r"JAKUT|JAKARTA\s+UTARA")

HAIJAR = [
    "JANUARI", "FEBRUARI", "MARET", "APRIL", "MEI", "JUNI",
    "JULI", "AGUSTUS", "SEPTEMBER", "OKTOBER", "NOVEMBER", "DESEMBER",
]
HARI = [
    "SENIN", "SELASA", "RABU", "KAMIS", "JUMAT", "SABTU", "MINGGU",
]

COLUMNS = ["STO", "NO TIKET", "CUSTOMER TYPE", "REPORT DATE", "TYPE TIKET", "DURASI", "PIC"]


def tokenize(line):
    cells = [c.strip() for c in re.split(r"[\t,;]", line.strip())]
    if len(cells) >= 2:
        return cells
    parts = re.split(r"\s{2,}", line.strip())
    return parts if len(parts) >= 2 else line.split()


def classify_cell(cell, fields):
    if not cell:
        return
    if cell in ("JAKUT", "JAKBAR"):
        if fields["witel"] is None:
            fields["witel"] = cell
    elif INC_RE.match(cell):
        if fields["ti"] is None:
            fields["ti"] = cell
    elif cell in config.STO_TO_REGION:
        if fields["sto"] is None:
            fields["sto"] = cell
    elif fields["inet"] is None and (cell == "S" or (INET_RE.match(cell) and fields["date"] is None)):
        fields["inet"] = cell
    elif fields["date"] is None and DATE_RE.search(cell):
        fields["date"] = cell
    elif fields["durasi"] is None and DUR_RE.search(cell):
        fields["durasi"] = cell
    elif cell.startswith("@"):
        fields["pic"] = (fields["pic"] + " " + cell).strip()
    elif cell in TYPE_WORDS and fields["type"] is None:
        fields["type"] = cell
    elif fields["ctype"] is None and CTYPE_RE.match(cell) and cell not in config.STO_TO_REGION:
        fields["ctype"] = cell


def parse_line(line):
    fields = {
        "witel": None, "sto": None, "ti": None, "inet": None,
        "ctype": None, "date": None, "durasi": None, "pic": "", "type": None,
    }
    for cell in tokenize(line):
        classify_cell(cell, fields)

    ti = fields["ti"]
    region = config.STO_TO_REGION.get(fields["sto"]) or fields["witel"]
    if not (ti and region):
        return None

    date = fields["date"] or "-"
    durasi = fields["durasi"] or "-"
    ctype = fields["ctype"] or "-"
    inet = fields["inet"] or "-"
    tipe = fields["type"] or "-"
    pic = fields["pic"] or "-"

    return {
        "region": region,
        "sto": fields["sto"] or "-",
        "ti": ti,
        "inet": inet,
        "ctype": ctype,
        "date": date,
        "durasi": durasi,
        "pic": pic,
        "type": tipe,
    }


def detect_keywords(text):
    up = text.upper()
    regions = set()
    if KEYWORD_REJAK.search(up):
        regions.add("JAKBAR")
    if KEYWORD_REJUT.search(up):
        regions.add("JAKUT")
    return regions


def waktu_sekarang():
    now = datetime.datetime.now()
    hari = HARI[now.weekday()]
    bulan = HAIJAR[now.month - 1]
    return f"{hari}, {now.day} {bulan} {now.year} pukul {now.strftime('%H:%M')}"


def extract_context(text):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    def clean_title(ln):
        if ln.count(",") > 1 or ln.count("\t") > 1:
            return False
        return len(ln.split()) <= 12

    title = next(
        (ln for ln in lines
         if ("REPORTING" in ln.upper() or "MONITORING" in ln.upper()) and clean_title(ln)),
        "",
    )
    tanggal = ""
    for ln in lines:
        if re.match(r"^\s*TANGGAL\s*\d", ln, re.I):
            tanggal = ln
            break
        if re.search(
            r"\b\d{1,2}\s+(?:Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus"
            r"|September|Oktober|November|Desember|January|February|March|May"
            r"|June|July|August|October|December)\w*\s*(?:,?\s+\d{2,4})?",
            ln,
            re.I,
        ):
            tanggal = ln
            break
    return title, tanggal


def render_region(region, rows, context):
    title, tanggal = context[:2]
    nama = config.NAMA_WILAYAH[region]
    if not title:
        title = f"REPORTING TIKET OPEN TTR 24 JAM {nama}"
    other = "JAKARTA BARAT" if region == "JAKUT" else "JAKARTA UTARA"
    if other in title.upper():
        title = f"REPORTING TIKET OPEN TTR 24 JAM {nama}"
    if not tanggal:
        tanggal = waktu_sekarang()

    header = [title, tanggal, f"Saldo Open {region} ({len(rows)} tiket)", ""]

    width = {col: len(col) for col in COLUMNS}
    data = []
    for r in rows:
        cells = [r["sto"], r["ti"], r["ctype"], r["date"], r["type"], r["durasi"], r["pic"]]
        data.append(cells)
        for idx, col in enumerate(COLUMNS):
            width[col] = max(width[col], len(cells[idx]))

    sep = "-" * (sum(width.values()) + (len(COLUMNS) - 1) * 2)
    body = [sep]
    body.append("  ".join(col.ljust(width[col]) for col in COLUMNS))
    body.append(sep)
    for cells in data:
        body.append("  ".join(cells[idx].ljust(width[col]) for idx, col in enumerate(COLUMNS)).rstrip())
    body.append(sep)

    return "\n".join(header) + "\n" + "\n".join(body)


def chunk_lines(text, limit=3900):
    lines = text.splitlines()
    chunks = []
    cur = ""
    for ln in lines:
        cand = ln if not cur else cur + "\n" + ln
        if len(cand) > limit and cur:
            chunks.append(cur)
            cur = ln
        else:
            cur = cand
    if cur:
        chunks.append(cur)

    messages = []
    for i, chunk in enumerate(chunks):
        prefix = "🔄 Lanjutan dari pesan sebelumnya" if i > 0 else ""
        body = (prefix + "\n" + chunk) if i > 0 else chunk
        messages.append("<pre>\n" + html.escape(body) + "\n</pre>")
    return messages


def build_report(text):
    rows = []
    for line in text.splitlines():
        row = parse_line(line)
        if row:
            rows.append(row)

    grouped = {"JAKUT": [], "JAKBAR": []}
    for r in rows:
        grouped[r["region"]].append(r)

    if not (grouped["JAKUT"] or grouped["JAKBAR"]):
        keywords = detect_keywords(text)
        if len(keywords) == 1:
            region = list(keywords)[0]
            return {
                "ok": True,
                "regions": {region: {"messages": chunk_lines(text), "count": None, "passthrough": True}},
            }
        if len(keywords) > 1:
            return {
                "ok": False,
                "reason": ("❌ Gagal mengirim.\n"
                           "Terdeteksi campuran JAKUT dan JAKBAR tanpa baris tiket yang valid. "
                           "Kirim satu laporan per wilayah."),
            }
        return {
            "ok": False,
            "reason": ("❌ Gagal mengirim.\n"
                       "Lokasi/tiket tidak terdeteksi. Pastikan laporan memuat baris tiket dengan kode STO, "
                       "contoh: INC53307774  CIL  HVC_GOLD  0 Jam 30 Menit"),
        }

    context = extract_context(text)
    out = {}
    for region in ("JAKUT", "JAKBAR"):
        if not grouped[region]:
            continue
        rendered = render_region(region, grouped[region], context)
        out[region] = {
            "messages": chunk_lines(rendered),
            "count": len(grouped[region]),
            "passthrough": False,
        }
    return {"ok": True, "regions": out}