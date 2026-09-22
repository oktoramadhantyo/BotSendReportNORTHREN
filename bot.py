import sys
import time

import requests

import config
import parser

API_BASE = config.API_BASE.format(token=config.TOKEN)

store = config.GroupStore()

PHOTO_BUF = {}
PHOTO_LIMIT = 2

START_TEXT = (
    "Selamat datang di Bot Laporan Northren (Jakarta Utara & Jakarta Barat).\n\n"
    "Cara kirim laporan:\n"
    "1. (Opsional) kirim foto screenshot laporan.\n"
    "2. Kirim teks laporan hasil copy-paste — setiap pesan teks = 1 laporan.\n"
    "3. Bot otomatis memilah tiket JAKUT/JAKBAR, mengirim ke grup tujuannya, "
    "lalu memberi notifikasi hasil.\n\n"
    "Pengaturan grup tujuan (dilakukan sekali):\n"
    "• Buka grup JAKBAR → ketik /setbot → pilih Jakarta Barat.\n"
    "• Buka grup JAKUT → ketik /setbot → pilih Jakarta Utara.\n\n"
    "Perintah lain:\n"
    "/setbot — tautkan grup ini sebagai tujuan JAKBAR/JAKUT\n"
    "/grup — lihat grup tujuan terdaftar\n"
    "/hapusgrup JAKBAR atau JAKUT — lepaskan tautan\n"
    "/help — bantuan ini"
)


def api(method, **kwargs):
    url = f"{API_BASE}/{method}"
    try:
        resp = requests.post(url, data=kwargs, timeout=60)
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(str(exc))
    if not data.get("ok"):
        raise RuntimeError(data.get("description", "Telegram API error"))
    return data.get("result")


def send_message(chat_id, text, parse_mode=None, reply_markup=None):
    kwargs = {"chat_id": chat_id, "text": text}
    if parse_mode:
        kwargs["parse_mode"] = parse_mode
    if reply_markup:
        kwargs["reply_markup"] = reply_markup
    api("sendMessage", **kwargs)


def get_me():
    return api("getMe")


def buffer_photo(chat_id, file_id):
    PHOTO_BUF.setdefault(chat_id, [])
    if file_id in PHOTO_BUF[chat_id]:
        return
    PHOTO_BUF[chat_id].append(file_id)
    if len(PHOTO_BUF[chat_id]) > PHOTO_LIMIT:
        PHOTO_BUF[chat_id] = PHOTO_BUF[chat_id][-PHOTO_LIMIT:]


def pop_photos(chat_id):
    return PHOTO_BUF.pop(chat_id, [])


def status_text():
    lines = ["📋 Status grup tujuan:"]
    for region in ("JAKUT", "JAKBAR"):
        target = store.get(region)
        label = config.LABEL_WILAYAH[region]
        lines.append(f"• {label}: {target if target else '❌ belum di-set'}")
    return "\n".join(lines)


def cmd_start(chat_id):
    send_message(chat_id, START_TEXT)


def cmd_setbot(chat_id, chat_type):
    if chat_type not in ("group", "supergroup"):
        send_message(
            chat_id,
            "⚠️ Perintah /setbot harus dijalankan dari dalam grup tujuan.\n"
            "Buka grup JAKBAR atau JAKUT, lalu ketik /setbot di sana.",
        )
        return
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🌆 Jakarta Utara (JAKUT)", "callback_data": "set:JAKUT"},
                {"text": "🌆 Jakarta Barat (JAKBAR)", "callback_data": "set:JAKBAR"},
            ]
        ]
    }
    send_message(chat_id, "Pilih wilayah untuk grup ini:\n\n" + status_text(), reply_markup=keyboard)


def cmd_grup(chat_id):
    send_message(chat_id, status_text())


def cmd_hapusgrup(chat_id, arg):
    region = arg.upper()
    if region not in ("JAKBAR", "JAKUT"):
        send_message(chat_id, "Gunakan: /hapusgrup JAKBAR atau /hapusgrup JAKUT")
        return
    store.clear(region)
    send_message(chat_id, f"✅ Tautan grup {config.LABEL_WILAYAH[region]} dilepaskan.\n\n{status_text()}")


def handle_callback(cb):
    data = cb.get("data", "")
    cb_id = cb.get("id")
    message = cb.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    chat_type = chat.get("type")

    if not data.startswith("set:"):
        api("answerCallbackQuery", callback_query_id=cb_id, text="Perintah tidak dikenal")
        return

    region = data.split(":", 1)[1]
    if region not in ("JAKUT", "JAKBAR"):
        api("answerCallbackQuery", callback_query_id=cb_id, text="Wilayah tidak dikenal")
        return

    if chat_type not in ("group", "supergroup"):
        api("answerCallbackQuery", callback_query_id=cb_id, text="Set dari dalam grup tujuan")
        return

    store.set(region, chat_id)
    api("answerCallbackQuery", callback_query_id=cb_id, text=f"{config.LABEL_WILAYAH[region]} tertaut")
    send_message(chat_id, f"✅ Grup ini kini tertaut sebagai {config.LABEL_WILAYAH[region]}.\n\n{status_text()}")


def process_report(chat_id, text, photos):
    result = parser.build_report(text)
    if not result.get("ok"):
        send_message(chat_id, result["reason"])
        return

    notes = []
    success = 0
    fail = 0
    for region in result["regions"]:
        target = store.get(region)
        if not target:
            fail += 1
            notes.append(f"⛔ {config.LABEL_WILAYAH[region]}: grup tujuan belum di-set (ketik /setbot di sana).")
            continue
        try:
            for file_id in photos:
                api("sendPhoto", chat_id=target, photo=file_id)
            for msg in result["regions"][region]["messages"]:
                api("sendMessage", chat_id=target, text=msg, parse_mode="HTML")
            success += 1
            count = result["regions"][region].get("count")
            detail = f" ({count} tiket)" if count else ""
            notes.append(f"✅ Selesai dikirim ke wilayah {region}!{detail}")
        except Exception as exc:
            fail += 1
            notes.append(f"❌ Gagal dikirim ke {config.LABEL_WILAYAH[region]}: {exc}")

    summary = "\n".join(notes)
    summary += f"\n\n🚀 Berhasil: {success} grup.\n❌ Gagal: {fail} grup."
    send_message(chat_id, summary)


def handle_message(msg):
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    chat_type = chat.get("type")
    text = msg.get("text") or ""
    caption = msg.get("caption") or ""

    photos = msg.get("photo") or []
    if photos:
        largest = max(photos, key=lambda p: p.get("file_size", 0) or 0)
        buffer_photo(chat_id, largest["file_id"])

    if text and text.startswith("/"):
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower().lstrip("/")
        arg = parts[1].strip() if len(parts) > 1 else ""
        if cmd in ("start", "help"):
            cmd_start(chat_id)
        elif cmd == "setbot":
            cmd_setbot(chat_id, chat_type)
        elif cmd == "grup":
            cmd_grup(chat_id)
        elif cmd == "hapusgrup":
            cmd_hapusgrup(chat_id, arg)
        return

    if photos and caption and not text:
        process_report(chat_id, caption, pop_photos(chat_id))
        return

    if text and not photos:
        if str(chat_id) in store.all_target_ids():
            return
        process_report(chat_id, text, pop_photos(chat_id))


def handle_update(update):
    if "message" in update:
        msg = update["message"]
        frm = (msg.get("from") or {}).get("id")
        me = getattr(handle_update, "_me_id", None)
        if me is not None and frm == me:
            return
        handle_message(msg)
    elif "callback_query" in update:
        handle_callback(update["callback_query"])


def run():
    if not config.TOKEN:
        print("TELEGRAM_BOT_TOKEN belum diisi di file .env", file=sys.stderr)
        sys.exit(1)
    try:
        me = get_me()
    except Exception as exc:
        print(f"Token tidak valid: {exc}", file=sys.stderr)
        sys.exit(1)
    handle_update._me_id = me["id"]
    print(f"Bot {me['username']} berjalan (polling)...")

    offset = None
    while True:
        try:
            kwargs = {"timeout": 50}
            if offset is not None:
                kwargs["offset"] = offset
            updates = api("getUpdates", **kwargs)
            for update in updates:
                offset = int(update["update_id"]) + 1
                handle_update(update)
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            time.sleep(2)
        time.sleep(0.5)


if __name__ == "__main__":
    run()