# oboardingmerchant — Aplikasi Onboarding Merchant DOB

Formulir pendaftaran calon merchant QRIS (Deca-For-Bisnis) — tahap **L1 (pengumpulan data ringan)**.
Data L1 sengaja tipis: identitas usaha, kontak, kategori, lokasi, estimasi transaksi.
Data berat (NIK/NPWP/dokumen/KYC) **tidak** diminta di sini — itu diambil sekali saat KYC setelah merchant
mendapat akun For Business (hindari entri ganda & kepatuhan APU-PPT tetap jalan).

## Isi
- `index.html` — formulir itu sendiri (HTML/JS mandiri, tanpa build step)
- `deploy.sh` — skrip di server: `git pull` -> sinkron ke folder yang disajikan nginx
- `.gitignore`

## Cara kerja di server (VPS riset product Deca)
```
~/apps/oboardingmerchant/
├── repo/         # clone repo ini (sasaran git pull)
├── current/      # yang disajikan nginx — ditimpa deploy.sh, jangan diedit manual
├── placeholder/  # konten sementara (kalau repo masih kosong)
├── deploy.sh     # diambil dari repo ini
└── deploy.log
```
- Container: `onboarding-merchant` (nginx:alpine), port **8090** → `-> /usr/share/nginx/html:ro`
- Otomatisasi: cron tiap 5 menit menjalankan `deploy.sh` (pull `--ff-only` → `rsync --delete` → log)
- **Alur update:** push ke repo ini → dalam ≤5 menit server otomatis menarik & menyajikan versi baru

## Status
- Frontend only. Belum ada backend; pengiriman ke Base Sales (Bitable) belum tersambung.
- Penyambungan ke base + validasi/dedupe menyusul setelah kredensial & jalur persetujuan selesai.

## Konvensi yang dipegang
- Jangan menaruh rahasia/token/data pribadi (NIK/NPWP/KTP) di repo ini
- Perubahan lewat branch + pull request, bukan langsung ke `main`
