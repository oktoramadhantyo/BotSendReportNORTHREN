import datetime
import html
import re

import config

ROW_RE = re.compile(
    r"^\s*(?:(?P<witel>JAKUT|JAKBAR)\s+)?"
    r"(?P<sto>[A-Z]{3})\s+"
    r"(?P<ti>INC\d+)\s+"
    r"(?P<inet>\d+|S)\s+"
    r"(?P<ctype>[A-Z][A-Z0-9_]*)\s+"
    r"(?P<tgl>\d{4}-\d{2}-\d{2})\s+(?P<jam>\d{1,2}:\d{2}:\d{2}(?:\.\d+)?)\s+"
    r"(?:(?P<layanan>[A-Z]+)\s+)?"
    r"(?P<durasi>.+?)\s*(?P<pic>@.*)?$"
)

KEYWORD_REJAK = re.compile(r"JAKBAR|JAKARTA\s+BARAT")
KEYWORD_REJUT = re.compile(r"JAKUT|JAKARTA\s+UTARA")

HAIJAR = [
    "JANUARI", "FEBRUARI", "MARET", "APRIL", "MEI", "JUNI",
    "JULI", "AGUSTUS", "SEPTEMBER", "OKTOBER", "NOVEMBER", "DESEMBER",
]
HARI = [
    "SENIN", "SELASA", "RABU", "KAMIS", "JUMAT", "SABTU", "MINGGU",
]

COLUMNS = ["STO", "NO TIKET", "INET GANGGUAN", "CUSTOMER TYPE", "REPORT DATE", "DURASI", "PIC"]


def detect_keywords(text):
    up = text.upper()
    regions = set()
    if KEYWORD_REJAK.search(up):
        regions.add("JAKBAR")
    if KEYWORD_REJUT.search(up):
        regions.add("JAKUT")
    return regions


def parse_rows(text):
    rows = []
    for line in text.splitlines():
        m = ROW_RE.match(line)
        if not m:
            continue
        sto = m.group("sto")
        region = config.STO_TO_REGION.get(sto)
        if region is None:
            witel = m.group("witel")
            region = witel if witel in ("JAKUT", "JAKBAR") else None
        if region is None:
            continue
        durasi = (m.group("durasi") or "").strip()
        pic = (m.group("pic") or "").strip()
        rows.append({
            "region": region,
            "sto": sto,
            "ti": m.group("ti"),
            "inet": m.group("inet"),
            "ctype": m.group("ctype"),
            "date": f"{m.group('tgl')} {re.sub(r'\\.0$', '', m.group('jam'))}",
            "durasi": durasi,
            "pic": pic,
        })
    return rows


def waktu_sekarang():
    now = datetime.datetime.now()
    hari = HARI[now.weekday()]
    bulan = HAIJAR[now.month - 1]
    return f"{hari}, {now.day} {bulan} {now.year} pukul {now.strftime('%H:%M')}"


def extract_context(text):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    title = next((ln for ln in lines if "REPORTING" in ln.upper()), "")
    tanggal = next(
        (ln for ln in lines if re.search(r"\d{1,2}:\d{2}|PUKUL|\b\d{1,2}\s+\w+(?:\s+\d{4})?", ln, re.I)),
        "",
    )
    return title, tanggal


def render_region(region, rows, context):
    title, tanggal = context[:2]
    nama = config.NAMA_WILAYAH[region]
    if "REPORTING" not in title.upper():
        title = f"REPORTING TIKET OPEN REGULER TTR 24 JAM {nama}"
    if not tanggal:
        tanggal = waktu_sekarang()
    if not re.search(r"\d{1,2}:\d{2}:?(\d{2})?", tanggal):
        tanggal = waktu_sekarang()

    header = [title, tanggal, f"Saldo Open {region} ({len(rows)} tiket)", ""]

    width = {col: len(col) for col in COLUMNS}
    data = []
    for r in rows:
        date_col = r["date"]
        cells = [r["sto"], r["ti"], r["inet"], r["ctype"], date_col, r["durasi"], r["pic"]]
        data.append(cells)
        for idx, col in enumerate(COLUMNS):
            width[col] = max(width[col], len(cells[idx]))

    sep = "-" * (sum(width.values()) + (len(COLUMNS) - 1) * 2)
    body = [sep]
    head_line = "  ".join(col.ljust(width[col]) for col in COLUMNS)
    body.append(head_line)
    body.append(sep)
    for cells in data:
        line = "  ".join(cells[idx].ljust(width[col]) for idx, col in enumerate(COLUMNS))
        body.append(line.rstrip())
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
    rows = parse_rows(text)
    grouped = {"JAKUT": [], "JAKBAR": []}
    for r in rows:
        grouped[r["region"]].append(r)

    regions_now = {reg for reg in grouped if grouped[reg]}
    has_rows = bool(rows)

    if not has_rows:
        keywords = detect_keywords(text)
        if len(keywords) == 1:
            region = list(keywords)[0]
            return {
                "ok": True,
                "regions": {
                    region: {"messages": chunk_lines(text), "count": None, "passthrough": True}
                },
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
                       "contoh: JAKBAR CKG INC52432227 ..."),
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