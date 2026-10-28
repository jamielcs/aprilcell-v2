# aprilcell-v2 — Catatan APRILcell v2

Aplikasi catatan keuangan konter pulsa & agen BRILink. **Rombak total dari v1** (`catatan-keuangan`)
mengikuti dokumen konsep final: [docs/KONSEP-FINAL.md](docs/KONSEP-FINAL.md) dan
[mockup tampilan](docs/mockup-aprilcell-v2.html).

Berjalan lokal di Windows lewat browser `http://127.0.0.1:5000`. Python + Flask + SQLite,
Bootstrap 5 + Chart.js + Font Awesome **lokal** (offline). Semua nominal integer rupiah.

## Cara Jalan

1. `install.bat` — sekali saja (bikin `.venv` + install dependensi).
2. `run.bat` — menjalankan aplikasi & membuka browser.
3. Kunjungan pertama: halaman **Setup** untuk membuat akun admin (setelah itu setup terkunci).

## Menu (17)

- **Utama:** Dashboard — semua saldo ringkas (rekening + aplikasi), Untung Hari Ini, peringatan saldo menipis
- **Jualan** (khusus catat penjualan baru, form lewat **modal**, halaman berisi **tabel lengkap**):
  - **Jual Produk** — saldo aplikasi terpotong otomatis / stok berkurang; untung dikunci saat transaksi
  - **Catat Jasa** — pokok = uang lewat (masuk lalu diteruskan), keuntungan = fee admin manual
- **Kelola Toko:**
  - **Produk & Jasa** — master FLAT 1 tingkat: modal + 3 harga (ecer/grosir 1/grosir 2), aplikasi pengisi, stok opsional + kulakan
  - **Saldo Aplikasi** — saldo per aplikasi provider + buku mutasi; deposit **nyambung** (potong rekening) atau **manual**; peringatan menipis; rekonsiliasi + koreksi beralasan
  - **Keuntungan** — periode hari/minggu/bulan/tanggal bebas, pisah untung produk vs fee jasa, grafik 7 hari, daftar penyumbang untung, top 5
- **Keuangan:** Rekening, Transaksi Saldo, Transfer Antar-Rekening, Buku Utang dan Piutang, Pengeluaran Harian, Uang Masuk Belum Diambil
- **Lainnya:** Laporan Keuangan, Riwayat Transaksi, Backup dan Restore, **Pengaturan** (identitas toko + upload logo, mode terang/gelap + warna aksen, aturan usaha, akun login), Logout

## Aturan uang (sesuai konsep)

- Setiap saldo adalah **hasil mutasi** — tidak ada saldo ngambang / terhitung dobel.
- Penjualan adalah pintu masuk tunggal mutasi keluar saldo aplikasi (otomatis).
- Edit/batal catatan uang selalu aman: sistem **membalik efek lama** lalu menerapkan yang baru; semua tercatat di audit.
- Semua catatan bertanggal; tanggal bisa diganti manual untuk catat telat (backdate).

## Struktur Kode

- `app.py` — entry point · `config.py` · `extensions.py`
- `app/models.py` — semua model · `app/utils.py` — ledger rekening + pembalikan
- `app/shop.py` — service layer toko: mutasi aplikasi, deposit, stok, efek penjualan/jasa, keuntungan
- Blueprint per menu di `app/<menu>/routes.py`, template di `app/templates/`
- Tes: `pytest` (41 tes — alur v1 + fitur v2)
