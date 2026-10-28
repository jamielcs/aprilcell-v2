# RINGKASAN FINAL — Konsep Rombak Total Catatan APRILcell v2

Disepakati tuntas: Kamis, 29 Oktober 2026 (±00:21 WIB). Status: **KONSEP SELESAI, BELUM DIBANGUN** — menunggu kata gas dari user.
Mockup tampilan: `mockup-aprilcell-v2.html` (data contoh).

## A. Fondasi
1. Aplikasi untuk usaha user: APRILcell, agen BRILink — jualan pulsa + aksesoris HP, jasa isi e-wallet & tarik tunai.
2. Produk dan jasa disatukan jadi 1 jenis data di master; pembedanya kolom Jenis.
3. Semua tempat uang punya catatan saldo akhir: rekening utama (11 rekening lama, termasuk Cash) + saldo aplikasi provider. Saldo akhir selalu hasil mutasi; tidak ada uang terhitung dobel; tidak ada saldo ngambang.
4. Semua tampilan WAJIB newbie friendly: bahasa konter sehari-hari, tanpa istilah akuntansi.

## B. Master "Produk & Jasa"
5. Struktur FLAT 1 tingkat (bukan bertingkat); tampilan boleh dikelompokkan per kategori/operator.
6. Kolom: Nama, Jenis (Produk/Jasa), Kategori/operator, Nominal/varian, Harga beli (modal), Harga ecer, Harga grosir level 1, Harga grosir level 2, Status aktif/nonaktif, Catatan (opsional), Tanggal dibuat (otomatis).
7. Di daftar master tampil hitungan otomatis untung per level = harga jual − modal.
8. Stok OPSIONAL per barang (Point 19): saklar "Pakai Stok" — ON hanya untuk barang fisik/aksesoris (stok tampil, berkurang otomatis saat penjualan, peringatan mau habis, catatan kulakan/tambah stok); OFF untuk pulsa & jasa (stok pulsa = saldo aplikasi itu sendiri).

## C. "Saldo Aplikasi" (provider) & Mutasi
9. Tabel baru terpisah dari master; kunci per APLIKASI pengisi (1 aplikasi bisa melayani banyak operator), bukan per operator.
10. Buku mutasi per aplikasi: tanggal & waktu, aplikasi, jenis mutasi, nominal, keterangan, saldo setelah mutasi. Saldo akhir = hasil hitungan mutasi.
11. Jenis mutasi: saldo awal, tambah saldo/deposit, terpakai penjualan, penyesuaian/koreksi (wajib alasan).
12. Dilengkapi: peringatan saldo menipis (batas minimum per aplikasi, indikator merah + banner di Dashboard), rekonsiliasi saldo catatan vs saldo asli aplikasi + selisihnya, rekap deposit vs terpakai per aplikasi per periode, dan setiap mutasi tersambung ke sumbernya (penjualan / rekening sumber).
13. Point 15 — Tambah saldo: NYAMBUNG sebagai aturan utama (deposit otomatis memotong rekening sumber) + tetap ada OPSI MANUAL per transaksi untuk pengecualian (saldo naik, rekening utama tidak disentuh); mutasi manual ditandai modenya.

## D. Penjualan Produk — menu "Jual Produk"
14. Form terpisah dari jasa (master tetap satu). Isi: pilih produk dari master, pilih level harga (ecer/grosir 1/grosir 2), jumlah, rekening tujuan, tanggal.
30. **Pola halaman pencatatan (KOREKSI user 2026-10-29 00:29, berlaku Jual Produk & Catat Jasa):** tambah/edit data lewat **MODAL** (popup), BUKAN form nempel di halaman; halaman isinya **satu kolom penuh berisi TABEL LENGKAP** — semua detail tiap transaksi kelihatan: tanggal & jam, produk/jasa, level harga, jumlah, harga, total, **pembeli bayar pakai apa** (tunai/transfer/QRIS/e-wallet), **masuk ke rekening apa**, saldo aplikasi mana yang terpotong / diteruskan dari saldo apa, untung/fee, dan tombol edit/hapus. (Untuk jasa kolomnya: nominal pokok, fee, total diterima, bayar pakai apa, masuk rekening apa, diteruskan dari saldo apa.)
15. Point 2 — Mutasi keluar WAJIB OTOMATIS: satu kali catat penjualan → saldo aplikasi produk itu berkurang sendiri senilai harga beli; mutasi tinggal tampil di buku mutasi, bukan input terpisah.
16. Point 16 — Uang hasil penjualan: rekening tujuan DIPILIH TIAP TRANSAKSI sesuai cara bayar pembeli (Cash tunai / transfer bank / e-wallet / QRIS — QRIS dicatat ke rekening tempat uangnya cair, atau rekening khusus "QRIS"), terisi default agar tetap cepat.

## E. Penjualan Jasa — menu "Catat Jasa"
17. Form terpisah. Isi: jenis jasa dari master, nominal pokok, fee admin, pelanggan bayar ke rekening mana, diteruskan dari saldo mana, tanggal.
18. Aturan jasa: nominal pokok = UANG LEWAT (bukan pendapatan, bukan keuntungan — masuk dari pelanggan lalu diteruskan). Keuntungan murni dari FEE ADMIN saja.
19. Fee diinput MANUAL tiap transaksi (bukan tarif tetap/bertingkat dari master).

## F. Menu "Keuntungan" (Point 17)
20. Menu terpisah + kartu ringkasan kecil "Untung Hari Ini" di Dashboard.
21. Isi: kartu angka besar total untung periode; tombol periode Hari Ini / Minggu Ini / Bulan Ini / Pilih Tanggal; dua kartu sumber (untung produk = jual − modal; untung jasa = fee) + batang perbandingan persen; grafik batang untung per hari 7 hari terakhir; daftar transaksi penyumbang untung dalam bahasa manusia (bisa diklik ke catatan sumbernya); Top 5 paling laris & paling menguntungkan.
22. Pokok jasa TIDAK tampil di menu ini. Untung produk dihitung & dikunci (snapshot) memakai harga beli saat transaksi terjadi — perubahan harga master belakangan tidak mengubah untung lama.

## G. Dashboard (Point 17 lanjutan)
23. Pola: SEMUA saldo tampil ringkas di Dashboard + halaman detail terpisah. Dashboard berisi: total saldo rekening + daftar ringkas rekening (termasuk Cash), saldo aplikasi provider ringkas + indikator menipis, kartu Untung Hari Ini, piutang/utang, uang belum diambil.

## H. Tanggal & CRUD
24. Semua catatan bertanggal: master = tanggal dibuat otomatis; penjualan/jasa/mutasi = tanggal + waktu otomatis. Tanggal transaksi BISA diganti manual untuk pencatatan telat (backdate) agar laporan harian tetap benar.
25. CRUD tetap penuh: master bebas tambah/edit/hapus/nonaktif. Catatan uang (penjualan/jasa) bisa diedit/dibatalkan lewat mekanisme aman — sistem otomatis membalik efek lama (saldo aplikasi, rekening tujuan, untung) lalu menerapkan yang baru; perubahan tercatat di riwayat/audit (fitur koreksi yang sudah ada di aplikasi sekarang).

## I. Menu & Tampilan
26. Total 17 item navigasi (12 lama + 5 baru):
    - Utama: Dashboard
    - Jualan — KHUSUS catat penjualan baru (aturan user 2026-10-29 00:25): Jual Produk, Catat Jasa. Master data TIDAK boleh ditaruh di grup/menu penjualan.
    - Kelola Toko (BARU, terpisah dari penjualan): Produk & Jasa (master), Saldo Aplikasi, Keuntungan
    - Keuangan: Rekening, Transaksi Saldo, Transfer Antar-Rekening, Utang dan Piutang, Pengeluaran Harian, Belum Diambil
    - Lainnya: Laporan Keuangan, Riwayat Transaksi, Backup dan Restore, Pengaturan, Logout
    Nama final (Point 18) bahasa aksi/pendek: "Jual Produk", "Catat Jasa", "Produk & Jasa", "Saldo Aplikasi", "Keuntungan".
27. Syarat tampilan (WAJIB dari user): responsive penuh (HP = navigasi bawah), ikon Font Awesome/SVG, gaya keren & modern, mode TERANG + GELAP (light/dark). Tanpa alert()/confirm() bawaan browser — dialog memakai modal modern.
29. Nama rekening BEBAS (user 2026-10-29 00:23): om sendiri yang menamai rekening/e-wallet-nya (cth: DANA Rudi, BRI Utama, Cash Laci, QRIS). Semua form tambah WAJIB punya placeholder contoh di tiap kolom (newbie friendly) — misal kolom nama rekening: "cth: DANA Rudi / BRI Utama / Cash Laci / QRIS".
28. Semua dialog konfirmasi/notifikasi memakai modal modern sesuai tema aplikasi (aturan UI lama tetap berlaku).

## Status
- Aplikasi v1 (tanpa rombakan ini) sudah jadi, ter-push ke repo jamielcs/catatan-keuangan dan ter-clone di PC user D:\Dev\catatan-keuangan — belum runtime-verified user di Windows.
- Konsep v2 ini: 19 point + syarat tampilan SELESAI diputus semua. Menunggu instruksi gas untuk dibangun.
