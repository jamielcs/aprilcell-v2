from flask import Blueprint, render_template, request, redirect, url_for, flash
from extensions import db
from app.models import (Account, Product, ProviderApp, Sale, ServiceSale,
                        StockMovement, now_jkt)
from app.utils import login_required, parse_amount, parse_date, audit, add_transaction
from app import shop

bp = Blueprint("products", __name__, url_prefix="/produk")


def _form_int(name, default=0):
    v = parse_amount(request.form.get(name))
    return default if v is None else v


def _fill_product(p):
    p.name = (request.form.get("name") or "").strip()
    p.kind = request.form.get("kind") or "produk"
    p.category = (request.form.get("category") or "").strip()
    p.nominal_label = (request.form.get("nominal_label") or "").strip()
    p.buy_price = _form_int("buy_price")
    p.price_ecer = _form_int("price_ecer")
    p.price_grosir1 = _form_int("price_grosir1")
    p.price_grosir2 = _form_int("price_grosir2")
    app_id = request.form.get("provider_app_id")
    p.provider_app_id = int(app_id) if app_id else None
    p.use_stock = bool(request.form.get("use_stock"))
    p.stock_min = _form_int("stock_min")
    p.note = (request.form.get("note") or "").strip()


@bp.route("/")
@login_required
def index():
    q = (request.args.get("q") or "").strip()
    kind = request.args.get("kind") or ""
    query = Product.query
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%") | Product.category.ilike(f"%{q}%"))
    if kind in ("produk", "jasa"):
        query = query.filter_by(kind=kind)
    items = query.order_by(Product.is_active.desc(), Product.kind, Product.category, Product.name).all()
    apps = ProviderApp.query.filter_by(is_active=True).order_by(ProviderApp.name).all()
    accounts = Account.query.filter_by(is_active=True).order_by(Account.id).all()
    return render_template("products/index.html", items=items, apps=apps,
                           accounts=accounts, q=q, kind=kind)


@bp.route("/create", methods=["POST"])
@login_required
def create():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Nama produk/jasa wajib diisi.", "danger")
        return redirect(url_for("products.index"))
    p = Product()
    _fill_product(p)
    db.session.add(p)
    db.session.flush()
    if p.use_stock:
        awal = _form_int("stock_awal")
        if awal > 0:
            shop.add_stock_movement(p, "awal", awal, date=now_jkt(),
                                    description="Stok awal")
    audit("create_product", f"{p.kind}: {p.display_name}")
    db.session.commit()
    flash("Produk/jasa ditambahkan ke master.", "success")
    return redirect(url_for("products.index"))


@bp.route("/<int:pid>/edit", methods=["POST"])
@login_required
def edit(pid):
    p = Product.query.get_or_404(pid)
    if not (request.form.get("name") or "").strip():
        flash("Nama wajib diisi.", "danger")
        return redirect(url_for("products.index"))
    _fill_product(p)
    audit("edit_product", f"#{p.id} {p.display_name}")
    db.session.commit()
    flash("Master diperbarui.", "success")
    return redirect(url_for("products.index"))


@bp.route("/<int:pid>/toggle", methods=["POST"])
@login_required
def toggle(pid):
    p = Product.query.get_or_404(pid)
    p.is_active = not p.is_active
    audit("toggle_product", f"#{p.id} aktif={p.is_active}")
    db.session.commit()
    flash("Status produk diperbarui.", "success")
    return redirect(url_for("products.index"))


@bp.route("/<int:pid>/delete", methods=["POST"])
@login_required
def delete(pid):
    p = Product.query.get_or_404(pid)
    used = (Sale.query.filter_by(product_id=pid).count()
            + ServiceSale.query.filter_by(product_id=pid).count()
            + StockMovement.query.filter_by(product_id=pid).count())
    if used:
        flash("Sudah pernah dipakai transaksi — tidak bisa dihapus, nonaktifkan saja.", "warning")
    else:
        db.session.delete(p)
        audit("delete_product", f"#{pid}")
        db.session.commit()
        flash("Produk/jasa dihapus dari master.", "success")
    return redirect(url_for("products.index"))


@bp.route("/<int:pid>/kulakan", methods=["POST"])
@login_required
def kulakan(pid):
    """Tambah stok (kulakan). Opsional: bayar dari rekening."""
    p = Product.query.get_or_404(pid)
    qty = _form_int("qty")
    unit_cost = _form_int("unit_cost", int(p.buy_price or 0))
    if qty <= 0:
        flash("Jumlah kulakan harus lebih dari 0.", "danger")
        return redirect(url_for("products.index"))
    total = qty * unit_cost
    acc = None
    tx = None
    acc_id = request.form.get("account_id")
    if acc_id and total > 0:
        acc = Account.query.get(int(acc_id))
        if acc is not None:
            tx = add_transaction(acc, "kulakan", -total,
                                 description=f"Kulakan {p.display_name} x{qty}",
                                 date=parse_date(request.form.get("date"), now_jkt()),
                                 reference_type="stock", reference_id=None)
    mv = shop.add_stock_movement(
        p, "kulakan", qty, unit_cost=unit_cost, total_cost=total,
        account=acc, tx=tx, date=parse_date(request.form.get("date"), now_jkt()),
        description=f"Kulakan x{qty}" + (f" dari {acc.name}" if acc else ""))
    if tx is not None:
        tx.reference_id = mv.id
    if unit_cost > 0:
        p.buy_price = unit_cost  # harga beli master mengikuti kulakan terakhir
    audit("kulakan", f"{p.display_name} +{qty} total {total}")
    db.session.commit()
    flash(f"Stok {p.display_name} bertambah {qty}. Stok sekarang {p.stock_qty}.", "success")
    return redirect(url_for("products.index"))


@bp.route("/<int:pid>/stok-koreksi", methods=["POST"])
@login_required
def stok_koreksi(pid):
    p = Product.query.get_or_404(pid)
    target = parse_amount(request.form.get("target"))
    reason = (request.form.get("reason") or "").strip()
    if target is None or target < 0:
        flash("Stok target tidak valid.", "danger")
    elif not reason:
        flash("Alasan koreksi stok wajib diisi.", "danger")
    else:
        delta = int(target) - int(p.stock_qty or 0)
        if delta == 0:
            flash("Stok sudah sama, tidak ada perubahan.", "info")
        else:
            shop.add_stock_movement(p, "koreksi", delta, date=now_jkt(),
                                    description=f"Koreksi stok: {reason}")
            audit("stok_koreksi", f"{p.display_name} delta {delta}: {reason}")
            db.session.commit()
            flash("Stok dikoreksi.", "success")
    return redirect(url_for("products.index"))


@bp.route("/<int:pid>/stok")
@login_required
def stok(pid):
    p = Product.query.get_or_404(pid)
    moves = (StockMovement.query.filter_by(product_id=pid)
             .order_by(StockMovement.date.desc(), StockMovement.id.desc()).all())
    return render_template("products/stok.html", p=p, moves=moves)
