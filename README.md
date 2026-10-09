# oboardingmerchant — Pendaftaran Merchant QRIS (Deca / QASH for Business)

Formulir **pengumpulan data awal (lapis L1)** untuk calon merchant QRIS, plus backend kecil yang
meneruskan data ke **Base Sales** (`Merchant & Client`).

## Prinsip: tiga lapis data, satu data satu sumber

| Lapis | Kapan | Yang dikumpulkan | Ditaruh di |
|---|---|---|---|
| **L1 — pendaftaran** (repo ini) | sebelum punya akun | nama usaha, kategori, skala, jenis badan usaha, kontak penanggung jawab (nama/HP/email), wilayah & kota, alamat lokasi usaha, estimasi transaksi, layanan yang diminati, asal/partner | tabel `Merchant & Client`, `Status Merchant = Onboarding`, `Status KYC = Belum`, `Sumber Data = Form Aplikasi (L1)` |
| **L2 — KYC** (di platform, bukan di sini) | setelah akun For Business aktif | NIK, NPWP, tanggal lahir, alamat legal, **dokumen** (KTP/NPWP/NIB/buku rekening), selfie, screening, skor risiko | hasilnya saja: `Status KYC`, lalu `Sumber Data = KYC (L2)` |
| **L3 — aktivasi** | setelah merchant aktif | Merchant ID/NMID, MDR, rekening settlement, tanggal aktivasi | disalin dari QRIS Admin Panel, kunci = NMID |

**Aturan keras: form ini TIDAK meminta dokumen.** Tidak ada unggah berkas, tidak ada NIK/NPWP/selfie.
Itu semua milik L2 supaya merchant tidak mengisi dua kali dan tidak ada data identitas yang tertinggal di form publik.

## Isi repo
```
index.html        # form L1 (tanpa unggah berkas, tanpa field KYC)
api/server.py     # backend: terima submit -> validasi -> tulis ke Base Sales (mode dry-run / live)
deploy.sh         # skrip server: git pull -> sinkron ke folder yang disajikan -> restart API
README.md
```

## Backend

- Endpoint: `POST /api/apply` (JSON), `GET /health`
- Validasi: field wajib, format HP/email, persetujuan; `422` bila tidak lolos
- **Dedupe**: cari record dengan `No. HP` atau `Email` sama sebelum menulis → tidak ada entri ganda
- **Referensi**: `QRIS-L1-YYYYMMDD-XXXX` (disimpan di kolom `Referensi Aplikasi`)
- Mode:
  - `DRY_RUN=1` (**default**) — payload hanya dicatat ke log, **tidak menyentuh base**. Dipakai untuk uji ujung-ke-ujung tanpa kredensial.
  - `DRY_RUN=0` — menulis ke Base Sales; butuh berkas kredensial app (`BITABLE_CRED_FILE`), dibaca saat runtime. **Tidak ada kredensial di repo.**
- Variabel lingkungan: `PORT` (default 8091), `DRY_RUN`, `BITABLE_APP_TOKEN`, `BITABLE_TABLE_ID`, `BITABLE_CRED_FILE`, `LOG_FILE`, `COMPANY`

## Cara jalan di server (VPS riset product Deca)
```
~/apps/oboardingmerchant/
├── repo/         # clone repo ini (sasaran git pull)
├── current/      # yang disajikan nginx — ditimpa deploy.sh, jangan diedit manual
├── placeholder/  # konten sementara (kalau repo masih kosong)
├── deploy.sh     # dari repo ini
└── deploy.log
```
- Statis: container `onboarding-merchant` (nginx:alpine), port **8090**, mount `current/` read-only
- API: container `onboarding-api`, tidak perlu port publik — dipanggil lewat jalur `/api/`
- **Satu origin:** nginx di port yang sama meneruskan `/api/` ke container API (`nginx.conf`), jadi form memanggil `/api/apply`
  secara relatif — **cukup satu port yang di-forward**, tanpa CORS, aman dari blocked mixed-content.
  ```
  docker network create obm-net      # sekali saja
  # API (kode dari repo, ikut auto-pull)
  docker run -d --name onboarding-api --restart unless-stopped --network obm-net \
    -v ~/apps/oboardingmerchant/current/api:/srv:ro \
    -v obm-api-data:/data -e DRY_RUN=1 -e LOG_FILE=/data/apply.log \
    python:3.12-alpine python /srv/server.py
  # halaman + proxy
  docker run -d --name onboarding-merchant --restart unless-stopped --network obm-net \
    -p 8090:80 -v ~/apps/oboardingmerchant/current:/usr/share/nginx/html:ro \
    -v ~/apps/oboardingmerchant/nginx.conf:/etc/nginx/conf.d/default.conf:ro nginx:alpine
  ```
- Otomatisasi: cron tiap 5 menit menjalankan `deploy.sh` (pull → sinkron → restart API)
- **Alur update:** push ke repo ini → dalam ≤5 menit server menarik & menyajikan versi baru

## Yang belum ada
- Kredensial app untuk tulis ke Base Sales (mode `live`) — jalurnya lewat Administrator
- Rate-limit / captcha untuk form publik, dan penguncian CORS ke origin sendiri
- Integrasi L2 (KYC) dan L3 (salin dari QRIS Admin Panel)
- Notifikasi ke grup tim saat ada pendaftaran baru

## Konvensi
- Jangan menaruh rahasia/token/data pribadi (NIK/NPWP/KTP) di repo ini
- Perubahan lewat branch + pull request, bukan langsung ke `main`
