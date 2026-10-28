from datetime import timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from extensions import db
from app.models import Account, Product, Sale, now_jkt
from app.utils import login_required, parse_amount, parse_date, audit
from app import shop

bp = Blueprint("sales", __name__, url_prefix="/jual-produk")


def _day_range(dstr):
    now = now_jkt()
    if dstr:
        try:
            from datetime import datetime
            base = datetime.strptime(dstr, "%Y-%m-%d")
        except Exception:
            base = now.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        base = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return base, base + timedelta(days=1) - timedelta(seconds=1)


def _read_form():
    """Baca + validasi form penjualan. Return (data, error)."""
    product = Product.query.get(request.form.get("product_id", type=int) or 0)
    if product is None or product.kind != "produk":
        return None, "Produk wajib dipilih."
    level = request.form.get("price_level") or "ecer"
    if level not in ("ecer", "grosir1", "grosir2"):
        level = "ecer"
    unit_sell = product.price_for(level)
    if unit_sell <= 0:
        unit_sell = int(product.price_ecer or 0)
    if unit_sell <= 0:
        return None, f"Harga jual {product.display_name} belum diisi di master Produk & Jasa."
    qty = parse_amount(request.form.get("qty")) or 0
    if qty <= 0:
        return None, "Jumlah harus lebih dari 0."
    if product.use_stock and qty > int(product.stock_qty or 0):
        return None, f"Stok {product.display_name} tinggal {product.stock_qty} — tidak cukup."
    dest = Account.query.get(request.form.get("dest_account_id", type=int) or 0)
    if dest is None:
        return None, "Rekening tujuan (uang masuk ke) wajib dipilih."
    data = {
        "product": product, "level": level, "qty": int(qty),
        "unit_sell": int(unit_sell), "unit_buy": int(product.buy_price or 0),
        "dest": dest,
        "payment_method": request.form.get("payment_method") or "tunai",
        "date": parse_date(request.form.get("date"), now_jkt()),
        "note": (request.form.get("note") or "").strip(),
    }
    return data, None


@bp.route("/")
@login_required
def index():
    dstr = request.args.get("tanggal") or ""
    start, end = _day_range(dstr)
    items = (Sale.query.filter(Sale.date >= start, Sale.date <= end)
             .order_by(Sale.date.desc(), Sale.id.desc()).all())
    aktif = [s for s in items if s.status == "active"]
    total_jual = sum(int(s.total or 0) for s in aktif)
    total_untung = sum(int(s.profit or 0) for s in aktif)
    products = (Product.query.filter_by(kind="produk", is_active=True)
                .order_by(Product.category, Product.name).all())
    accounts = Account.query.filter_by(is_active=True).order_by(Account.id).all()
    return render_template("sales/index.html", items=items, products=products,
                           accounts=accounts, tanggal=dstr or start.strftime("%Y-%m-%d"),
                           total_jual=total_jual, total_untung=total_untung,
                           payment_methods=shop.PAYMENT_METHODS,
                           price_levels=shop.PRICE_LEVELS, now=now_jkt())


@bp.route("/create", methods=["POST"])
@login_required
def create():
    data, err = _read_form()
    if err:
        flash(err, "danger")
        return redirect(url_for("sales.index"))
    p = data["product"]
    sale = Sale(product_id=p.id, date=data["date"], price_level=data["level"],
                qty=data["qty"], unit_buy=data["unit_buy"], unit_sell=data["unit_sell"],
                total=data["unit_sell"] * data["qty"],
                profit=(data["unit_sell"] - data["unit_buy"]) * data["qty"],
                payment_method=data["payment_method"],
                dest_account_id=data["dest"].id, note=data["note"], status="active")
    db.session.add(sale)
    db.session.flush()
    shop.apply_sale_effects(sale)
    audit("create_sale", f"{p.display_name} x{sale.qty} total {sale.total} untung {sale.profit}")
    db.session.commit()
    extra = ""
    if p.provider_app_id:
        from app.models import ProviderApp
        app_ = ProviderApp.query.get(p.provider_app_id)
        if app_ is not None and int(app_.balance or 0) < 0:
            extra = f" Perhatian: saldo {app_.name} jadi minus — cek lagi saldo aplikasinya."
    flash(f"Penjualan tersimpan. Untung Rp {sale.profit:,}.".replace(",", ".") + extra,
          "warning" if extra else "success")
    return redirect(url_for("sales.index", tanggal=sale.date.strftime("%Y-%m-%d")))


@bp.route("/<int:sid>/edit", methods=["POST"])
@login_required
def edit(sid):
    sale = Sale.query.get_or_404(sid)
    if sale.status != "active":
        flash("Penjualan sudah dibatalkan, tidak bisa diedit.", "warning")
        return redirect(url_for("sales.index"))
    data, err = _read_form()
    if err:
        # stok produk lama sudah termasuk efek lama; validasi stok saat edit
        # memakai stok saat ini + qty lama produk yang sama
        prod = Product.query.get(request.form.get("product_id", type=int) or 0)
        if prod is not None and prod.id == sale.product_id and prod.use_stock and err.startswith("Stok"):
            data, err = None, None
            qty = parse_amount(request.form.get("qty")) or 0
            if qty <= int(prod.stock_qty or 0) + int(sale.qty or 0):
                level = request.form.get("price_level") or "ecer"
                unit_sell = prod.price_for(level) or int(prod.price_ecer or 0)
                dest = Account.query.get(request.form.get("dest_account_id", type=int) or 0)
                if dest is not None and unit_sell > 0 and qty > 0:
                    data = {"product": prod, "level": level, "qty": int(qty),
                            "unit_sell": int(unit_sell), "unit_buy": int(prod.buy_price or 0),
                            "dest": dest,
                            "payment_method": request.form.get("payment_method") or "tunai",
                            "date": parse_date(request.form.get("date"), now_jkt()),
                            "note": (request.form.get("note") or "").strip()}
                else:
                    err = "Data edit tidak valid."
            else:
                err = f"Stok {prod.display_name} tidak cukup."
        if err:
            flash(err, "danger")
            return redirect(url_for("sales.index"))
    shop.reverse_sale_effects(sale, "Penjualan diedit")
    p = data["product"]
    sale.product_id = p.id
    sale.date = data["date"]
    sale.price_level = data["level"]
    sale.qty = data["qty"]
    sale.unit_buy = data["unit_buy"]
    sale.unit_sell = data["unit_sell"]
    sale.total = data["unit_sell"] * data["qty"]
    sale.profit = (data["unit_sell"] - data["unit_buy"]) * data["qty"]
    sale.payment_method = data["payment_method"]
    sale.dest_account_id = data["dest"].id
    sale.note = data["note"]
    sale.dest_tx_id = None
    sale.app_mutation_id = None
    sale.stock_movement_id = None
    shop.apply_sale_effects(sale)
    audit("edit_sale", f"sale#{sale.id} total {sale.total}")
    db.session.commit()
    flash("Penjualan diperbarui — saldo & untung sudah dibenerin otomatis.", "success")
    return redirect(url_for("sales.index", tanggal=sale.date.strftime("%Y-%m-%d")))


@bp.route("/<int:sid>/cancel", methods=["POST"])
@login_required
def cancel(sid):
    sale = Sale.query.get_or_404(sid)
    if sale.status == "cancelled":
        flash("Penjualan sudah dibatalkan.", "warning")
    else:
        shop.reverse_sale_effects(sale, "Penjualan dibatalkan")
        sale.status = "cancelled"
        audit("cancel_sale", f"sale#{sale.id}")
        db.session.commit()
        flash("Penjualan dibatalkan — semua efeknya sudah dibalik.", "success")
    return redirect(url_for("sales.index", tanggal=sale.date.strftime("%Y-%m-%d")))
