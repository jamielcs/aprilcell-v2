from datetime import datetime, timezone, timedelta
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

JKT = timezone(timedelta(hours=7))


def now_jkt():
    return datetime.now(JKT).replace(tzinfo=None)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    failed_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=now_jkt)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class Account(db.Model):
    __tablename__ = "accounts"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    short_name = db.Column(db.String(50), nullable=False)
    account_type = db.Column(db.String(50), default="bank")
    balance = db.Column(db.Integer, default=0, nullable=False)  # rupiah int
    initial_balance = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=now_jkt)
    transactions = db.relationship("Transaction", backref="account", lazy=True)


class Transaction(db.Model):
    __tablename__ = "transactions"
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False, index=True)
    type = db.Column(db.String(40), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)  # abs
    signed_amount = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=now_jkt, index=True)
    description = db.Column(db.String(500), default="")
    notes = db.Column(db.Text, default="")
    category_id = db.Column(db.Integer, db.ForeignKey("expense_categories.id"), nullable=True, index=True)
    person_id = db.Column(db.Integer, db.ForeignKey("people.id"), nullable=True, index=True)
    transfer_id = db.Column(db.Integer, db.ForeignKey("transfers.id"), nullable=True, index=True)
    status = db.Column(db.String(20), default="active", index=True)  # active/cancelled
    affects_balance = db.Column(db.Boolean, default=True)
    is_reversal = db.Column(db.Boolean, default=False)
    reversal_of_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True)
    reference_type = db.Column(db.String(50), default="")
    reference_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=now_jkt)
    category = db.relationship("ExpenseCategory", lazy=True)
    person = db.relationship("Person", lazy=True)


class Transfer(db.Model):
    __tablename__ = "transfers"
    id = db.Column(db.Integer, primary_key=True)
    from_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False, index=True)
    to_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=now_jkt, index=True)
    description = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=now_jkt)
    from_account = db.relationship("Account", foreign_keys=[from_account_id])
    to_account = db.relationship("Account", foreign_keys=[to_account_id])


class Person(db.Model):
    __tablename__ = "people"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    contact = db.Column(db.String(120), default="")
    notes = db.Column(db.Text, default="")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=now_jkt)


class Debt(db.Model):
    __tablename__ = "debts"
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey("people.id"), nullable=False, index=True)
    direction = db.Column(db.String(20), nullable=False, index=True)  # piutang / utang
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=True)
    principal = db.Column(db.Integer, nullable=False)
    paid_amount = db.Column(db.Integer, default=0)
    date = db.Column(db.DateTime, default=now_jkt, index=True)
    description = db.Column(db.String(500), default="")
    status = db.Column(db.String(20), default="aktif")  # aktif / lunas
    created_at = db.Column(db.DateTime, default=now_jkt)
    person = db.relationship("Person", backref="debts")
    account = db.relationship("Account")

    @property
    def remaining(self):
        return self.principal - (self.paid_amount or 0)


class DebtPayment(db.Model):
    __tablename__ = "debt_payments"
    id = db.Column(db.Integer, primary_key=True)
    debt_id = db.Column(db.Integer, db.ForeignKey("debts.id"), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=True)
    amount = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=now_jkt, index=True)
    description = db.Column(db.String(500), default="")
    transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=now_jkt)
    debt = db.relationship("Debt", backref="payments")
    account = db.relationship("Account")


class ExpenseCategory(db.Model):
    __tablename__ = "expense_categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=now_jkt)


class Expense(db.Model):
    __tablename__ = "expenses"
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("expense_categories.id"), nullable=True, index=True)
    person_id = db.Column(db.Integer, db.ForeignKey("people.id"), nullable=True, index=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True)
    amount = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=now_jkt, index=True)
    description = db.Column(db.String(500), default="")
    notes = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="active")
    created_at = db.Column(db.DateTime, default=now_jkt)
    account = db.relationship("Account")
    category = db.relationship("ExpenseCategory")
    person = db.relationship("Person")


class UncollectedIncome(db.Model):
    __tablename__ = "uncollected_income"
    id = db.Column(db.Integer, primary_key=True)
    source_name = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    received_amount = db.Column(db.Integer, default=0)
    date = db.Column(db.DateTime, default=now_jkt, index=True)
    description = db.Column(db.String(500), default="")
    status = db.Column(db.String(30), default="belum_diambil")  # belum_diambil/diambil_sebagian/sudah_diambil
    created_at = db.Column(db.DateTime, default=now_jkt)

    @property
    def remaining(self):
        return self.amount - (self.received_amount or 0)

    def refresh_status(self):
        if self.remaining <= 0:
            self.status = "sudah_diambil"
        elif (self.received_amount or 0) > 0:
            self.status = "diambil_sebagian"
        else:
            self.status = "belum_diambil"


class UncollectedIncomePayment(db.Model):
    __tablename__ = "uncollected_income_payments"
    id = db.Column(db.Integer, primary_key=True)
    uncollected_id = db.Column(db.Integer, db.ForeignKey("uncollected_income.id"), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=now_jkt, index=True)
    description = db.Column(db.String(500), default="")
    transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=now_jkt)
    uncollected = db.relationship("UncollectedIncome", backref="payments")
    account = db.relationship("Account")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    details = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=now_jkt, index=True)
    user = db.relationship("User")


class AppSetting(db.Model):
    __tablename__ = "app_settings"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, default="")


# ================= v2: TOKO (master, saldo aplikasi, penjualan, jasa) =================

class ProviderApp(db.Model):
    """Aplikasi pengisi saldo provider (kunci saldo per APLIKASI, bukan per operator)."""
    __tablename__ = "provider_apps"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    serves = db.Column(db.String(300), default="")  # operator yang dilayani, teks bebas
    min_balance = db.Column(db.Integer, default=50000)  # batas peringatan menipis
    balance = db.Column(db.Integer, default=0, nullable=False)  # hasil mutasi
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=now_jkt)
    mutations = db.relationship("AppMutation", backref="app", lazy=True)

    @property
    def is_low(self):
        return int(self.balance or 0) < int(self.min_balance or 0)


class AppMutation(db.Model):
    """Buku mutasi saldo aplikasi: saldo_awal / deposit / terpakai / koreksi."""
    __tablename__ = "app_mutations"
    id = db.Column(db.Integer, primary_key=True)
    app_id = db.Column(db.Integer, db.ForeignKey("provider_apps.id"), nullable=False, index=True)
    kind = db.Column(db.String(30), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)  # abs
    signed_amount = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=now_jkt, index=True)
    description = db.Column(db.String(500), default="")
    mode = db.Column(db.String(20), default="")  # deposit: nyambung / manual
    source_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=True)
    source_tx_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True)
    reference_type = db.Column(db.String(50), default="")  # sale
    reference_id = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), default="active", index=True)
    is_reversal = db.Column(db.Boolean, default=False)
    reversal_of_id = db.Column(db.Integer, db.ForeignKey("app_mutations.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=now_jkt)
    source_account = db.relationship("Account")


class Product(db.Model):
    """Master Produk & Jasa — FLAT 1 tingkat."""
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    kind = db.Column(db.String(20), nullable=False, index=True)  # produk / jasa
    category = db.Column(db.String(100), default="")  # operator / kategori
    nominal_label = db.Column(db.String(100), default="")  # nominal / varian
    buy_price = db.Column(db.Integer, default=0)  # harga beli / modal
    price_ecer = db.Column(db.Integer, default=0)
    price_grosir1 = db.Column(db.Integer, default=0)
    price_grosir2 = db.Column(db.Integer, default=0)
    provider_app_id = db.Column(db.Integer, db.ForeignKey("provider_apps.id"), nullable=True)
    use_stock = db.Column(db.Boolean, default=False)  # saklar Pakai Stok (barang fisik)
    stock_qty = db.Column(db.Integer, default=0)
    stock_min = db.Column(db.Integer, default=0)  # peringatan stok mau habis
    is_active = db.Column(db.Boolean, default=True)
    note = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=now_jkt)
    provider_app = db.relationship("ProviderApp")

    def price_for(self, level):
        if level == "grosir1":
            return int(self.price_grosir1 or 0)
        if level == "grosir2":
            return int(self.price_grosir2 or 0)
        return int(self.price_ecer or 0)

    @property
    def display_name(self):
        return f"{self.name} {self.nominal_label}".strip()


class StockMovement(db.Model):
    __tablename__ = "stock_movements"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    kind = db.Column(db.String(30), nullable=False, index=True)  # awal / kulakan / terjual / koreksi
    qty_signed = db.Column(db.Integer, nullable=False)
    stock_after = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Integer, nullable=True)
    total_cost = db.Column(db.Integer, nullable=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=True)
    tx_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True)
    date = db.Column(db.DateTime, default=now_jkt, index=True)
    description = db.Column(db.String(500), default="")
    reference_type = db.Column(db.String(50), default="")
    reference_id = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), default="active", index=True)
    is_reversal = db.Column(db.Boolean, default=False)
    reversal_of_id = db.Column(db.Integer, db.ForeignKey("stock_movements.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=now_jkt)
    product = db.relationship("Product")
    account = db.relationship("Account")


class Sale(db.Model):
    """Penjualan produk. Untung dikunci (snapshot) saat transaksi terjadi."""
    __tablename__ = "sales"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    date = db.Column(db.DateTime, default=now_jkt, index=True)
    price_level = db.Column(db.String(20), default="ecer")  # ecer / grosir1 / grosir2
    qty = db.Column(db.Integer, default=1)
    unit_buy = db.Column(db.Integer, default=0)  # snapshot modal
    unit_sell = db.Column(db.Integer, default=0)  # snapshot harga jual
    total = db.Column(db.Integer, default=0)
    profit = db.Column(db.Integer, default=0)
    payment_method = db.Column(db.String(30), default="tunai")  # tunai/transfer/qris/ewallet
    dest_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=True)
    dest_tx_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True)
    app_mutation_id = db.Column(db.Integer, db.ForeignKey("app_mutations.id"), nullable=True)
    stock_movement_id = db.Column(db.Integer, db.ForeignKey("stock_movements.id"), nullable=True)
    status = db.Column(db.String(20), default="active", index=True)
    note = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=now_jkt)
    product = db.relationship("Product")
    dest_account = db.relationship("Account")
    app_mutation = db.relationship("AppMutation")


class ServiceSale(db.Model):
    """Penjualan jasa. Pokok = uang lewat; keuntungan = fee saja."""
    __tablename__ = "service_sales"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    date = db.Column(db.DateTime, default=now_jkt, index=True)
    principal = db.Column(db.Integer, default=0)  # nominal pokok (uang lewat)
    fee = db.Column(db.Integer, default=0)  # fee admin manual = keuntungan
    payment_method = db.Column(db.String(30), default="tunai")
    dest_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=True)
    source_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=True)
    dest_tx_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True)
    source_tx_id = db.Column(db.Integer, db.ForeignKey("transactions.id"), nullable=True)
    status = db.Column(db.String(20), default="active", index=True)
    note = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=now_jkt)
    product = db.relationship("Product")
    dest_account = db.relationship("Account", foreign_keys=[dest_account_id])
    source_account = db.relationship("Account", foreign_keys=[source_account_id])

    @property
    def total_received(self):
        return int(self.principal or 0) + int(self.fee or 0)
