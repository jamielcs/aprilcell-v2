"""Service layer v2: saldo aplikasi, stok, penjualan produk & jasa.

Prinsip (konsep final aprilcell-v2):
- Saldo aplikasi selalu hasil mutasi; penjualan memotong saldo aplikasi OTOMATIS.
- Deposit NYAMBUNG memotong rekening sumber; mode MANUAL tidak menyentuh rekening.
- Penjualan jasa: pokok = uang lewat (masuk lalu diteruskan), untung = fee saja.
- Edit/batal aman: efek lama DIBALIK (reversal) lalu efek baru diterapkan.
- Untung penjualan dikunci dari snapshot harga saat transaksi terjadi.
Semua fungsi di sini TIDAK commit — caller yang commit.
"""
from extensions import db
from app.models import (AppMutation, ProviderApp, Product, Sale, ServiceSale,
                        StockMovement, AppSetting, now_jkt)
from app.utils import add_transaction, cancel_transaction, audit

SHOP_DEFAULTS = {
    "shop_name": "APRILcell",
    "shop_owner": "",
    "shop_phone": "",
    "shop_address": "",
    "receipt_footer": "Terima kasih sudah berbelanja di APRILcell",
    "logo_file": "",
    "theme_default": "light",  # light / dark / system
    "accent": "#2563eb",
    "low_balance_default": "50000",
    "low_warning": "1",
    "auto_backup": "0",
}

PAYMENT_METHODS = [
    ("tunai", "Tunai"),
    ("transfer", "Transfer"),
    ("qris", "QRIS"),
    ("ewallet", "E-Wallet"),
]
PRICE_LEVELS = [("ecer", "Ecer"), ("grosir1", "Grosir 1"), ("grosir2", "Grosir 2")]


def get_setting(key, default=None):
    row = AppSetting.query.filter_by(key=key).first()
    if row is not None and row.value not in (None, ""):
        return row.value
    if default is not None:
        return default
    return SHOP_DEFAULTS.get(key, "")


def set_setting(key, value):
    row = AppSetting.query.filter_by(key=key).first()
    if row is None:
        row = AppSetting(key=key, value=str(value))
        db.session.add(row)
    else:
        row.value = str(value)
    return row


def shop_context():
    return {
        "shop_name": get_setting("shop_name"),
        "shop_owner": get_setting("shop_owner"),
        "shop_phone": get_setting("shop_phone"),
        "shop_address": get_setting("shop_address"),
        "receipt_footer": get_setting("receipt_footer"),
        "logo_file": get_setting("logo_file"),
        "theme_default": get_setting("theme_default"),
        "accent": get_setting("accent"),
    }


# ---------------- Saldo aplikasi ----------------

def add_app_mutation(app, kind, signed_amount, description="", date=None, mode="",
                     source_account_id=None, source_tx_id=None,
                     reference_type="", reference_id=None):
    mut = AppMutation(
        app_id=app.id, kind=kind,
        amount=abs(int(signed_amount)), signed_amount=int(signed_amount),
        balance_after=0, date=date or now_jkt(),
        description=description or "", mode=mode or "",
        source_account_id=source_account_id, source_tx_id=source_tx_id,
        reference_type=reference_type or "", reference_id=reference_id,
        status="active",
    )
    app.balance = int(app.balance or 0) + int(signed_amount)
    mut.balance_after = int(app.balance)
    db.session.add(mut)
    db.session.flush()
    return mut


def cancel_app_mutation(mut, reason=""):
    """Balik satu mutasi (reversal) dan kembalikan saldo aplikasi."""
    if mut.status == "cancelled":
        return None
    app = mut.app
    rev = AppMutation(
        app_id=mut.app_id, kind="koreksi",
        amount=mut.amount, signed_amount=-mut.signed_amount,
        balance_after=0, date=now_jkt(),
        description=f"Pembalikan: {mut.description} {reason}".strip(),
        mode=mut.mode or "",
        source_account_id=mut.source_account_id,
        reference_type=mut.reference_type or "", reference_id=mut.reference_id,
        status="active", is_reversal=True, reversal_of_id=mut.id,
    )
    app.balance = int(app.balance or 0) - int(mut.signed_amount)
    rev.balance_after = int(app.balance)
    mut.status = "cancelled"
    db.session.add(rev)
    db.session.flush()
    return rev


def deposit(app, amount, mode, source_account, date, note=""):
    """Tambah saldo aplikasi. mode nyambung: potong rekening sumber."""
    amount = int(amount)
    source_tx = None
    if mode == "nyambung" and source_account is not None:
        source_tx = add_transaction(
            source_account, "deposit_aplikasi", -amount,
            description=f"Deposit saldo {app.name}" + (f" — {note}" if note else ""),
            date=date, reference_type="app_deposit", reference_id=None)
    mut = add_app_mutation(
        app, "deposit", amount,
        description=(note or f"Tambah saldo {app.name}"),
        date=date, mode=mode,
        source_account_id=source_account.id if (mode == "nyambung" and source_account) else None,
        source_tx_id=source_tx.id if source_tx else None)
    if source_tx is not None:
        source_tx.reference_id = mut.id
    audit("deposit_aplikasi", f"{app.name} +{amount} mode {mode}")
    return mut


def reverse_deposit(mut):
    """Batalkan deposit: balik mutasi + balik potongan rekening (bila nyambung)."""
    if mut.source_tx_id:
        from app.models import Transaction
        tx = Transaction.query.get(mut.source_tx_id)
        if tx is not None and tx.status == "active":
            cancel_transaction(tx, "Pembatalan deposit aplikasi")
    cancel_app_mutation(mut, "Deposit dibatalkan")


# ---------------- Stok ----------------

def add_stock_movement(product, kind, qty_signed, unit_cost=None, total_cost=None,
                       account=None, tx=None, date=None, description="",
                       reference_type="", reference_id=None):
    mv = StockMovement(
        product_id=product.id, kind=kind, qty_signed=int(qty_signed),
        stock_after=0, unit_cost=unit_cost, total_cost=total_cost,
        account_id=account.id if account else None,
        tx_id=tx.id if tx else None,
        date=date or now_jkt(), description=description or "",
        reference_type=reference_type or "", reference_id=reference_id,
        status="active")
    product.stock_qty = int(product.stock_qty or 0) + int(qty_signed)
    mv.stock_after = int(product.stock_qty)
    db.session.add(mv)
    db.session.flush()
    return mv


def cancel_stock_movement(mv, reason=""):
    if mv.status == "cancelled":
        return None
    product = mv.product
    rev = StockMovement(
        product_id=mv.product_id, kind="koreksi", qty_signed=-mv.qty_signed,
        stock_after=0, unit_cost=mv.unit_cost, total_cost=mv.total_cost,
        account_id=mv.account_id, date=now_jkt(),
        description=f"Pembalikan stok: {mv.description} {reason}".strip(),
        reference_type=mv.reference_type or "", reference_id=mv.reference_id,
        status="active", is_reversal=True, reversal_of_id=mv.id)
    product.stock_qty = int(product.stock_qty or 0) - int(mv.qty_signed)
    rev.stock_after = int(product.stock_qty)
    mv.status = "cancelled"
    db.session.add(rev)
    db.session.flush()
    return rev


# ---------------- Penjualan produk ----------------

def apply_sale_effects(sale):
    """Terapkan efek penjualan: uang masuk rekening tujuan, saldo aplikasi
    terpotong otomatis (produk digital) ATAU stok berkurang (barang fisik)."""
    product = sale.product
    # uang masuk (harga jual x qty) ke rekening tujuan
    if sale.dest_account_id:
        from app.models import Account
        acc = Account.query.get(sale.dest_account_id)
        if acc is not None:
            tx = add_transaction(
                acc, "penjualan", int(sale.total),
                description=f"Jual {product.display_name} x{sale.qty}",
                date=sale.date, reference_type="sale", reference_id=sale.id)
            sale.dest_tx_id = tx.id
    # potong saldo aplikasi (produk yang terhubung aplikasi provider)
    if product.provider_app_id:
        app = ProviderApp.query.get(product.provider_app_id)
        if app is not None:
            mut = add_app_mutation(
                app, "terpakai", -int(sale.unit_buy) * int(sale.qty),
                description=f"Terpakai: {product.display_name} x{sale.qty}",
                date=sale.date, reference_type="sale", reference_id=sale.id)
            sale.app_mutation_id = mut.id
    # stok barang fisik
    if product.use_stock:
        mv = add_stock_movement(
            product, "terjual", -int(sale.qty), date=sale.date,
            description=f"Terjual: {product.display_name}",
            reference_type="sale", reference_id=sale.id)
        sale.stock_movement_id = mv.id
    db.session.flush()


def reverse_sale_effects(sale, reason="Penjualan dibatalkan"):
    """Balik semua efek penjualan (rekening, saldo aplikasi, stok)."""
    from app.models import Transaction
    if sale.dest_tx_id:
        tx = Transaction.query.get(sale.dest_tx_id)
        if tx is not None and tx.status == "active":
            cancel_transaction(tx, reason)
    if sale.app_mutation_id:
        mut = AppMutation.query.get(sale.app_mutation_id)
        if mut is not None and mut.status == "active":
            cancel_app_mutation(mut, reason)
    if sale.stock_movement_id:
        mv = StockMovement.query.get(sale.stock_movement_id)
        if mv is not None and mv.status == "active":
            cancel_stock_movement(mv, reason)
    db.session.flush()


# ---------------- Penjualan jasa ----------------

def apply_service_effects(svc):
    """Pokok+fee masuk ke rekening tujuan; pokok diteruskan dari saldo sumber.
    Yang jadi keuntungan hanya fee."""
    product = svc.product
    from app.models import Account
    if svc.dest_account_id:
        acc = Account.query.get(svc.dest_account_id)
        if acc is not None:
            tx = add_transaction(
                acc, "jasa_masuk", int(svc.total_received),
                description=f"Jasa {product.display_name}: pokok {svc.principal} + fee {svc.fee}",
                date=svc.date, reference_type="service", reference_id=svc.id)
            svc.dest_tx_id = tx.id
    if svc.source_account_id and int(svc.principal or 0) > 0:
        acc = Account.query.get(svc.source_account_id)
        if acc is not None:
            tx = add_transaction(
                acc, "jasa_keluar", -int(svc.principal),
                description=f"Diteruskan: {product.display_name} (uang lewat)",
                date=svc.date, reference_type="service", reference_id=svc.id)
            svc.source_tx_id = tx.id
    db.session.flush()


def reverse_service_effects(svc, reason="Jasa dibatalkan"):
    from app.models import Transaction
    for tx_id in (svc.dest_tx_id, svc.source_tx_id):
        if tx_id:
            tx = Transaction.query.get(tx_id)
            if tx is not None and tx.status == "active":
                cancel_transaction(tx, reason)
    db.session.flush()


# ---------------- Keuntungan ----------------

def profit_between(start, end):
    """(total, dari_produk, dari_jasa, jumlah_transaksi) untuk rentang tanggal."""
    sales = Sale.query.filter(Sale.status == "active",
                              Sale.date >= start, Sale.date <= end).all()
    svcs = ServiceSale.query.filter(ServiceSale.status == "active",
                                    ServiceSale.date >= start, ServiceSale.date <= end).all()
    p_prod = sum(int(s.profit or 0) for s in sales)
    p_jasa = sum(int(s.fee or 0) for s in svcs)
    return p_prod + p_jasa, p_prod, p_jasa, len(sales) + len(svcs)
