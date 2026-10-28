# aprilcell-v2

**Catatan APRILcell v2** — rombak total dari `catatan-keuangan` (v1). Aplikasi catatan keuangan
konter pulsa & agen BRILink: master Produk & Jasa, Saldo Aplikasi provider + mutasi otomatis,
pencatatan Jual Produk & Catat Jasa, dan menu Keuntungan.

## Status

**KONSEP FINAL — BELUM DIBANGUN.** 19 point konsep disepakati tuntas pada 29 Oktober 2026.
Pembangunan menunggu instruksi eksplisit pemilik repo.

## Blueprint

- [Dokumen Konsep Final](docs/KONSEP-FINAL.md) — seluruh keputusan: master flat 1 tingkat,
  saldo aplikasi per aplikasi + buku mutasi, mutasi penjualan wajib otomatis, deposit nyambung
  (+opsi manual), fee jasa manual, pokok jasa = uang lewat, menu Keuntungan newbie friendly,
  Dashboard satu lirikan, tanggal + CRUD aman, 17 menu, syarat tampilan
  (responsive, Font Awesome, modern, light + dark).
- [Mockup Tampilan](docs/mockup-aprilcell-v2.html) — gambaran UI (data contoh): Dashboard,
  Jual Produk, Catat Jasa, Produk & Jasa, Saldo Aplikasi, Keuntungan. Buka file ini di browser.

## Menu (17)

- **Utama:** Dashboard
- **Jualan** (khusus catat penjualan baru): Jual Produk, Catat Jasa
- **Kelola Toko:** Produk & Jasa, Saldo Aplikasi, Keuntungan
- **Keuangan:** Rekening, Transaksi Saldo, Transfer Antar-Rekening, Utang dan Piutang,
  Pengeluaran Harian, Belum Diambil
- **Lainnya:** Laporan Keuangan, Riwayat Transaksi, Backup dan Restore, Pengaturan, Logout

## Rencana Stack

Mengikuti v1: Python + Flask + SQLite + SQLAlchemy, Bootstrap 5 + Chart.js lokal (offline),
Font Awesome lokal, jalan lokal di Windows via `install.bat` / `run.bat` (127.0.0.1:5000).
