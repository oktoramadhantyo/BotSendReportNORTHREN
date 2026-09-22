# Bot Laporan Northren

Bot Telegram yang menerima laporan tiket dari user, memilah otomatis per wilayah
(Jakarta Utara / Jakarta Barat) berdasarkan kode STO, lalu mengirimkan hasilnya
ke grup Telegram tujuan masing-masing.

## Cara Kerja

1. User mengirim teks laporan (hasil copy-paste dari report). Setiap pesan teks
   dianggap satu laporan penuh. Foto screenshot bersifat opsional (dikirim juga
   sebagai lampiran).
2. Bot membaca baris per baris, mendeteksi wilayah dari kode STO di setiap tiket.
3. Laporan di-render ulang menjadi tabel yang rapi, lalu dikirim ke grup JAKBAR
   dan/atau grup JAKUT sesuai wilayah tiket.
4. User mendapat notifikasi hasil:
   ```
   ✅ Selesai dikirim ke wilayah JAKBAR! (5 tiket)
   🚀 Berhasil: 1 grup.
   ❌ Gagal: 0 grup.
   ```

Daftar STO:
- **JAKUT (Jakarta Utara):** CIL, MRD, KLG, KTX, KTZ, MKR, PDM, STR, TPR
- **JAKBAR (Jakarta Barat):** CKG, TGA, KPK, JIA, KSB, PLM, KDY, MRY, SLP, SMI, DTG, SDM

## Perintah

| Perintah | Fungsi |
|---|---|
| `/start` `/help` | Instruksi penggunaan |
| `/setbot` | Tautkan grup ini sebagai grup tujuan JAKBAR/JAKUT (pilih via tombol) |
| `/grup` | Lihat grup tujuan yang terdaftar |
| `/hapusgrup JAKBAR` `/hapusgrup JAKUT` | Lepaskan tautan grup tujuan |

## Instalasi Lokal

1. Install Python 3.10+.
2. Buat bot di https://t.me/BotFather lalu isi token di file `.env`
   (salin dari `.env.example`).
3. Install dependensi:
   ```bash
   pip install -r requirements.txt
   ```
4. Jalankan:
   ```bash
   python bot.py
   ```
5. Siapkan grup tujuan:
   - Buat grup `JAKBAR` dan `JAKUT`.
   - Invite bot ke kedua grup dan jadikan admin.
   - Di grup JAKBAR: `/setbot` → pilih Jakarta Barat.
   - Di grup JAKUT: `/setbot` → pilih Jakarta Utara.
6. Kirim laporan dari private chat bot untuk mencoba.

## Deploy ke Render

1. Push kode ke repository GitHub (semua branch `main`).
2. Di dashboard Render: New → Blueprint, pilih repository tersebut.
3. Render membaca `render.yaml`. Isi environment variable
   `TELEGRAM_BOT_TOKEN` (nilai sama dengan token di `.env`) melalui dashboard
   Render sebagai secret value.
4. Deploy selesai — bot berjalan sebagai worker dengan long polling.

## Catatan

- `.env` dan `groups.json` tidak di-commit ke git.
- `groups.json` dibuat otomatis untuk menyimpan tautan grup tujuan.
- Laporan dikirim dari chat mana pun; jika dikirim dari grup tujuan sendiri
  (grup yang sudah di-set lewat `/setbot`), pesan tersebut diabaikan agar tidak
  terjadi pengiriman ganda.