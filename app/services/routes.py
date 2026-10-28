from datetime import timedelta, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from extensions import db
from app.models import Account, Product, ServiceSale, now_jkt
from app.utils import login_required, parse_amount, parse_date, audit
from app import shop

bp = Blueprint("services", __name__, url_prefix="/catat-jasa")


def _day_range(dstr):
    now = now_jkt()
    if dstr:
        try:
            base = datetime.strptime(dstr, "%Y-%m-%d")
        except Exception:
            base = now.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        base = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return base, base + timedelta(days=1) - timedelta(seconds=1)


def _read_form():
    product = Product.query.get(request.form.get("product_id", type=int) or 0)
    if product is None or product.kind != "jasa":
        return None, "Jenis jasa wajib dipilih."
    principal = parse_amount(request.form.get("principal"))
    fee = parse_amount(request.form.get("fee"))
    if principal is None or principal < 0:
        return None, "Nominal pokok tidak valid (boleh 0 untuk jasa tanpa pokok)."
    if fee is None or fee < 0:
        return None, "Fee admin tidak valid."
    if principal == 0 and fee == 0:
        return None, "Pokok dan fee tidak boleh sama-sama 0."
    dest = Account.query.get(request.form.get("dest_account_id", type=int) or 0)
    if dest is None:
        return None, "Rekening tujuan (uang masuk ke) wajib dipilih."
    source = None
    if principal > 0:
        source = Account.query.get(request.form.get("source_account_id", type=int) or 0)
        if source is None:
            return None, "Saldo sumber untuk meneruskan pokok wajib dipilih."
    data = {
        "product": product, "principal": int(principal), "fee": int(fee),
        "dest": dest, "source": source,
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
    items = (ServiceSale.query.filter(ServiceSale.date >= start, ServiceSale.date <= end)
             .order_by(ServiceSale.date.desc(), ServiceSale.id.desc()).all())
    aktif = [s for s in items if s.status == "active"]
    total_fee = sum(int(s.fee or 0) for s in aktif)
    total_pokok = sum(int(s.principal or 0) for s in aktif)
    products = (Product.query.filter_by(kind="jasa", is_active=True)
                .order_by(Product.category, Product.name).all())
    accounts = Account.query.filter_by(is_active=True).order_by(Account.id).all()
    return render_template("services/index.html", items=items, products=products,
                           accounts=accounts, tanggal=dstr or start.strftime("%Y-%m-%d"),
                           total_fee=total_fee, total_pokok=total_pokok,
                           payment_methods=shop.PAYMENT_METHODS, now=now_jkt())


@bp.route("/create", methods=["POST"])
@login_required
def create():
    data, err = _read_form()
    if err:
        flash(err, "danger")
        return redirect(url_for("services.index"))
    p = data["product"]
    svc = ServiceSale(product_id=p.id, date=data["date"],
                      principal=data["principal"], fee=data["fee"],
                      payment_method=data["payment_method"],
                      dest_account_id=data["dest"].id,
                      source_account_id=data["source"].id if data["source"] else None,
                      note=data["note"], status="active")
    db.session.add(svc)
    db.session.flush()
    shop.apply_service_effects(svc)
    audit("create_service", f"{p.display_name} pokok {svc.principal} fee {svc.fee}")
    db.session.commit()
    flash(f"Jasa tersimpan. Fee (untung) Rp {svc.fee:,}.".replace(",", "."), "success")
    return redirect(url_for("services.index", tanggal=svc.date.strftime("%Y-%m-%d")))


@bp.route("/<int:sid>/edit", methods=["POST"])
@login_required
def edit(sid):
    svc = ServiceSale.query.get_or_404(sid)
    if svc.status != "active":
        flash("Catatan jasa sudah dibatalkan, tidak bisa diedit.", "warning")
        return redirect(url_for("services.index"))
    data, err = _read_form()
    if err:
        flash(err, "danger")
        return redirect(url_for("services.index"))
    shop.reverse_service_effects(svc, "Jasa diedit")
    p = data["product"]
    svc.product_id = p.id
    svc.date = data["date"]
    svc.principal = data["principal"]
    svc.fee = data["fee"]
    svc.payment_method = data["payment_method"]
    svc.dest_account_id = data["dest"].id
    svc.source_account_id = data["source"].id if data["source"] else None
    svc.note = data["note"]
    svc.dest_tx_id = None
    svc.source_tx_id = None
    shop.apply_service_effects(svc)
    audit("edit_service", f"service#{svc.id} fee {svc.fee}")
    db.session.commit()
    flash("Catatan jasa diperbarui — saldo sudah dibenerin otomatis.", "success")
    return redirect(url_for("services.index", tanggal=svc.date.strftime("%Y-%m-%d")))


@bp.route("/<int:sid>/cancel", methods=["POST"])
@login_required
def cancel(sid):
    svc = ServiceSale.query.get_or_404(sid)
    if svc.status == "cancelled":
        flash("Catatan jasa sudah dibatalkan.", "warning")
    else:
        shop.reverse_service_effects(svc, "Jasa dibatalkan")
        svc.status = "cancelled"
        audit("cancel_service", f"service#{svc.id}")
        db.session.commit()
        flash("Catatan jasa dibatalkan — semua efeknya sudah dibalik.", "success")
    return redirect(url_for("services.index", tanggal=svc.date.strftime("%Y-%m-%d")))
