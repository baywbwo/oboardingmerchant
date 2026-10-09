#!/usr/bin/env bash
# Deploy otomatis: tarik perubahan dari GitHub -> sinkronkan ke folder yang disajikan nginx -> segarkan API.
# Dipasang oleh Aspro (asisten product) 9 Okt 2026. Aman & idempoten.
# Catatan: "remote masih kosong (belum ada commit)" BUKAN kegagalan -> pakai placeholder.
set -u
APP="$(cd "$(dirname "$0")" && pwd)"
LOG="$APP/deploy.log"
ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

if git -C "$APP/repo" ls-remote --exit-code --heads origin >/dev/null 2>&1; then
  if ! git -C "$APP/repo" pull --ff-only >> "$LOG" 2>&1; then
    echo "[$(ts)] PULL GAGAL (dicoba lagi tick berikutnya)" >> "$LOG"
    exit 0
  fi
  echo "[$(ts)] pull ok" >> "$LOG"
else
  echo "[$(ts)] remote masih kosong (belum ada commit) -> placeholder" >> "$LOG"
fi

if git -C "$APP/repo" rev-parse --verify HEAD >/dev/null 2>&1; then
  SRC="$APP/repo"; KET="isi repo"
else
  SRC="$APP/placeholder"; KET="placeholder"
fi
if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete --exclude=.git "$SRC/" "$APP/current/" >> "$LOG" 2>&1
else
  find "$APP/current" -mindepth 1 -delete
  (cd "$SRC" && tar --exclude=.git -cf - .) | (cd "$APP/current" && tar -xf -) >> "$LOG" 2>&1
fi
echo "[$(ts)] sinkron selesai dari $KET (berkas: $(find "$APP/current" -type f | wc -l))" >> "$LOG"

# pengaman: kalau sumber tidak punya index.html (mis. branch main masih berisi zip),
# sajikan placeholder supaya situs tidak jadi 403
if [ ! -f "$APP/current/index.html" ] && [ -f "$APP/placeholder/index.html" ]; then
  rsync -a --delete "$APP/placeholder/" "$APP/current/" >> "$LOG" 2>&1
  echo "[$(ts)] tidak ada index.html di sumber -> placeholder disajikan" >> "$LOG"
fi

# segarkan konfigurasi nginx kalau berubah, lalu wadah yang memakai kode repo
if [ -f "$APP/current/nginx.conf" ] && { [ ! -f "$APP/nginx.conf" ] || ! cmp -s "$APP/current/nginx.conf" "$APP/nginx.conf"; }; then
  cp -f "$APP/current/nginx.conf" "$APP/nginx.conf"
  echo "[$(ts)] konfigurasi nginx disegarkan" >> "$LOG"
  docker restart onboarding-merchant >/dev/null 2>&1 && echo "[$(ts)] onboarding-merchant di-restart" >> "$LOG"
fi

# segarkan API kalau wadahnya sudah ada (kode di-current/ di-mount read-only)
if docker ps -a --format '{{.Names}}' | grep -q '^onboarding-api$'; then
  docker restart onboarding-api >/dev/null 2>&1 && echo "[$(ts)] onboarding-api di-restart" >> "$LOG" \
    || echo "[$(ts)] GAGAL restart onboarding-api" >> "$LOG"
fi
