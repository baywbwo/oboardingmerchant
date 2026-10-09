#!/usr/bin/env python3
"""
Backend pendaftaran merchant QRIS — tahap L1 (form aplikasi ringan).

Tugasnya: menerima submit form L1 -> validasi -> (dry-run) catat payload / (live) tulis ke Base Sales
tabel `Merchant & Client`. Data KYC (NIK/NPWP/dokumen/selfie) SENGAJA tidak ada di sini — itu lapis L2.

Mode:
  DRY_RUN=1 (default) -> hanya menulis payload ke log; tidak menyentuh base sama sekali.
  DRY_RUN=0           -> menulis ke Bitable, butuh kredensial app (lihat BITABLE_CRED_FILE).

Jalankan:  PORT=8091 python3 server.py
"""
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8091"))
DRY_RUN = os.environ.get("DRY_RUN", "1") != "0"
LOG_FILE = os.environ.get("LOG_FILE", "/app/data/apply.log")
APP_TOKEN = os.environ.get("BITABLE_APP_TOKEN", "E8gFbq6pyaYzZAsuhdelwgSkgCg")
TABLE_ID = os.environ.get("BITABLE_TABLE_ID", "tblzKZ50116zadpW")
CRED_FILE = os.environ.get("BITABLE_CRED_FILE", "")
BASE_URL = os.environ.get("BITABLE_BASE_URL", "https://open.larksuite.com/open-apis/bitable/v1/apps")
COMPANY = os.environ.get("COMPANY", "DOB")
MAX_BODY = 64 * 1024

REQUIRED = ("nama_usaha", "kategori", "nama_pemilik", "hp", "email", "wilayah", "kota")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
HP_RE = re.compile(r"^(0|\+?62)\d{8,13}$")


def log(entry):
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:  # pragma: no cover
        print("gagal menulis log:", exc, file=sys.stderr)


def normalize(d):
    out = {}
    for k, v in (d or {}).items():
        if isinstance(v, str):
            v = v.strip()
        out[k] = v
    out["hp"] = re.sub(r"[\s-]", "", str(out.get("hp", "")))
    if out["hp"].startswith("62"):
        out["hp"] = "0" + out["hp"][2:]
    elif out["hp"].startswith("+62"):
        out["hp"] = "0" + out["hp"][3:]
    return out


def validate(d):
    errors = []
    for k in REQUIRED:
        if not d.get(k):
            errors.append("%s wajib diisi" % k)
    if d.get("hp") and not HP_RE.match(d["hp"]):
        errors.append("format no. HP tidak valid")
    if d.get("email") and not EMAIL_RE.match(d["email"]):
        errors.append("format email tidak valid")
    if d.get("estimasi"):
        try:
            d["estimasi"] = int(re.sub(r"[^\d]", "", str(d["estimasi"])) or 0)
        except ValueError:
            errors.append("estimasi transaksi harus angka")
    if not d.get("consent"):
        errors.append("persetujuan belum dicentang")
    return errors


def make_ref():
    return "QRIS-L1-%s-%04d" % (time.strftime("%Y%m%d"), random.randint(0, 9999))


def catatan(d):
    bits = ["Ref %s" % d["_ref"], "sumber: form aplikasi L1 (web)"]
    if d.get("layanan"):
        bits.append("layanan diminati: " + ", ".join(d["layanan"]
                    if isinstance(d["layanan"], list) else [str(d["layanan"])]))
    if d.get("jumlah_outlet"):
        bits.append("jumlah outlet: %s" % d["jumlah_outlet"])
    bits.append("NIK/NPWP/dokumen & selfie TIDAK dikumpulkan di tahap ini (menyusul di KYC/L2)")
    return " · ".join(bits)


def to_fields(d):
    """Peta L1 -> kolom tabel `Merchant & Client` (Base Sales)."""
    f = {
        "Nama Usaha / Brand": d.get("nama_usaha"),
        "Kategori Usaha": d.get("kategori"),
        "Nama Kontak": d.get("nama_pemilik"),
        "No. HP": d.get("hp"),
        "Email": d.get("email"),
        "Wilayah": d.get("wilayah"),
        "Kota / Kabupaten": d.get("kota"),
        "Status Merchant": "Onboarding",
        "Status KYC": "Belum",
        "Company": COMPANY,
        "Referensi Aplikasi": d["_ref"],
        "Sumber Data": "Form Aplikasi (L1)",
        "Catatan Klien": catatan(d),
    }
    for src, dst in (("skala", "Skala Usaha"), ("badan_usaha", "Jenis Badan Usaha"),
                     ("alamat", "Alamat Usaha"), ("sumber_lead", "Sumber Lead"),
                     ("partner", "Partner / Aggregator")):
        if d.get(src):
            f[dst] = d[src]
    if d.get("estimasi"):
        f["Estimasi Nilai Transaksi / Bulan"] = d["estimasi"]
    return {k: v for k, v in f.items() if v not in (None, "")}


def read_cred():
    if not CRED_FILE or not os.path.exists(CRED_FILE):
        raise RuntimeError("kredensial Bitable belum tersedia di server (BITABLE_CRED_FILE)")
    with open(CRED_FILE) as fh:
        c = json.load(fh)
    if "token" in c:
        return c["token"]
    raise RuntimeError("format kredensial tidak dikenal")


def bitable(path, method="GET", body=None, token=None):
    req = urllib.request.Request("%s/%s/%s" % (BASE_URL, APP_TOKEN, path),
                                data=json.dumps(body).encode() if body is not None else None,
                                method=method,
                                headers={"Authorization": "Bearer " + (token or read_cred()),
                                         "Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read())
        except Exception:
            return {"code": exc.code, "msg": "http error"}


def find_duplicate(token, d):
    """Cari record dengan No. HP atau Email sama -> supaya tidak ada entri ganda."""
    conditions = [{"field_name": "No. HP", "operator": "is", "value": [d["hp"]]},
                  {"field_name": "Email", "operator": "is", "value": [d["email"]]}]
    for cond in conditions:
        res = bitable("tables/%s/records/search" % TABLE_ID, "POST",
                      {"filter": {"conjunction": "or", "conditions": [cond]}, "page_size": 1}, token)
        items = (res.get("data") or {}).get("items") or []
        if items:
            return (items[0].get("fields") or {}).get("Referensi Aplikasi")
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = "aspro-onboarding/1.0"

    def _send(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        if self.path.split("?")[0] in ("/health", "/"):
            self._send(200, {"ok": True, "mode": "dry-run" if DRY_RUN else "live",
                             "app_token": APP_TOKEN, "table": TABLE_ID})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.split("?")[0] != "/api/apply":
            self._send(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY:
                self._send(413, {"error": "payload kosong/terlalu besar"})
                return
            raw = json.loads(self.rfile.read(length).decode() or "{}")
        except (ValueError, UnicodeDecodeError):
            self._send(400, {"error": "payload bukan JSON yang valid"})
            return

        d = normalize(raw)
        errors = validate(d)
        if errors:
            self._send(422, {"error": "data belum lengkap/valid", "errors": errors})
            return

        d["_ref"] = make_ref()
        fields = to_fields(d)
        entry = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "ref": d["_ref"],
                 "mode": "dry-run" if DRY_RUN else "live", "fields": fields}

        if DRY_RUN:
            log(entry)
            print("[dry-run] %s -> %s" % (d["_ref"], json.dumps(fields, ensure_ascii=False)), flush=True)
            self._send(200, {"ok": True, "ref": d["_ref"], "dry_run": True,
                             "message": "Terkirim (mode uji: belum masuk ke base)."})
            return

        try:
            token = read_cred()
            dup = find_duplicate(token, d)
            if dup:
                entry["duplicate_of"] = dup
                log(entry)
                self._send(200, {"ok": True, "ref": dup, "duplicate": True,
                                 "message": "Pendaftaran dengan kontak ini sudah ada."})
                return
            res = bitable("tables/%s/records" % TABLE_ID, "POST", {"fields": fields}, token)
            entry["bitable_code"] = res.get("code")
            log(entry)
            if res.get("code") != 0:
                self._send(502, {"error": "gagal menyimpan ke Base Sales", "detail": res.get("msg")})
                return
            self._send(200, {"ok": True, "ref": d["_ref"]})
        except Exception as exc:  # noqa: BLE001
            log(dict(entry, error=str(exc)))
            print("ERROR:", exc, file=sys.stderr, flush=True)
            self._send(500, {"error": "server pendaftaran bermasalah"})

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args), flush=True)


if __name__ == "__main__":
    print("onboarding L1 API di :%d | mode=%s | base=%s/%s" % (PORT, "dry-run" if DRY_RUN else "live", APP_TOKEN, TABLE_ID), flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
