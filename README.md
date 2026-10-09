# ⚠️ STATUS: DIPENSIUNKAN — alur pindah ke Form Lark Base

Sejak 9 Okt 2026 pengumpulan data pengajuan merchant memakai **Form view di Base Sales**
(tabel `Pipeline Akuisisi`, view `📝 Form Pendaftaran Merchant`):
submit langsung masuk base secara **realtime**, tanpa backend, tanpa kredensial.

Kode di repo ini (form HTML + `api/server.py` + `deploy.sh`) **tidak lagi dijalankan** —
container `onboarding-merchant` & `onboarding-api` dihentikan dan cron auto-pull dicabut.
Disimpan sebagai referensi bila nanti dibutuhkan lagi (mis. form khusus dengan validasi lanjutan).

Perubahan model yang berlaku sekarang:
- Pengajuan **L1 masuk ke `Pipeline Akuisisi`** (Tahap Akuisisi = Prospek), bukan ke `Merchant & Client`
- `Merchant & Client` = master data, barisnya dibuat **setelah prospek menang/aktivasi** (close won)
- Data KYC (NIK/NPWP/dokumen/selfie) tetap lapis L2 — tidak dikumpulkan di form pengajuan

