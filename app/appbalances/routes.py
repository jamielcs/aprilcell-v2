from datetime import timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import func
from extensions import db
from app.models import Account, AppMutation, ProviderApp, now_jkt
from app.utils import login_required, parse_amount, parse_date, audit
from app import shop

bp = Blueprint("appbalances", __name__, url_prefix="/saldo-aplikasi")


def _month_range(now):
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        nxt = start.replace(year=start.year + 1, month=1)
    else:
        nxt = start.replace(month=start.month + 1)
    return start, nxt - timedelta(seconds=1)


@bp.route("/")
@login_required
def index():
    apps = ProviderApp.query.order_by(ProviderApp.is_active.desc(), ProviderApp.name).all()
    accounts = Account.query.filter_by(is_active=True).order_by(Account.id).all()
    now = now_jkt()
    start, end = _month_range(now)
    rekap = {}
    for a in apps:
        dep = db.session.query(func.coalesce(func.sum(AppMutation.signed_amount), 0)).filter(
            AppMutation.app_id == a.id, AppMutation.kind == "deposit",
            AppMutation.status == "active",
            AppMutation.date >= start, AppMutation.date <= end).scalar()
        pakai = db.session.query(func.coalesce(func.sum(AppMutation.signed_amount), 0)).filter(
            AppMutation.app_id == a.id, AppMutation.kind == "terpakai",
            AppMutation.status == "active",
            AppMutation.date >= start, AppMutation.date <= end).scalar()
        rekap[a.id] = {"deposit": int(dep or 0), "terpakai": abs(int(pakai or 0))}
    total = sum(int(a.balance or 0) for a in apps if a.is_active)
    return render_template("appbalances/index.html", apps=apps, accounts=accounts,
                           rekap=rekap, total=total,
                           low_default=shop.get_setting("low_balance_default"))


@bp.route("/create", methods=["POST"])
@login_required
def create():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Nama aplikasi wajib diisi.", "danger")
        return redirect(url_for("appbalances.index"))
    if ProviderApp.query.filter_by(name=name).first():
        flash("Aplikasi dengan nama itu sudah ada.", "danger")
        return redirect(url_for("appbalances.index"))
    min_bal = parse_amount(request.form.get("min_balance"))
    if min_bal is None:
        min_bal = parse_amount(shop.get_setting("low_balance_default")) or 50000
    a = ProviderApp(name=name, serves=(request.form.get("serves") or "").strip(),
                    min_balance=int(min_bal), balance=0)
    db.session.add(a)
    db.session.flush()
    awal = parse_amount(request.form.get("saldo_awal")) or 0
    if awal > 0:
        shop.add_app_mutation(a, "saldo_awal", int(awal),
                              description="Saldo awal aplikasi",
                              date=parse_date(request.form.get("date"), now_jkt()))
    audit("create_provider_app", name)
    db.session.commit()
    flash("Aplikasi provider ditambahkan.", "success")
    return redirect(url_for("appbalances.index"))


@bp.route("/<int:aid>/edit", methods=["POST"])
@login_required
def edit(aid):
    a = ProviderApp.query.get_or_404(aid)
    name = (request.form.get("name") or "").strip()
    if name:
        a.name = name
    a.serves = (request.form.get("serves") or "").strip()
    min_bal = parse_amount(request.form.get("min_balance"))
    if min_bal is not None:
        a.min_balance = int(min_bal)
    audit("edit_provider_app", f"#{a.id} {a.name}")
    db.session.commit()
    flash("Aplikasi diperbarui.", "success")
    return redirect(url_for("appbalances.index"))


@bp.route("/<int:aid>/toggle", methods=["POST"])
@login_required
def toggle(aid):
    a = ProviderApp.query.get_or_404(aid)
    a.is_active = not a.is_active
    db.session.commit()
    flash("Status aplikasi diperbarui.", "success")
    return redirect(url_for("appbalances.index"))


@bp.route("/<int:aid>/deposit", methods=["POST"])
@login_required
def deposit(aid):
    a = ProviderApp.query.get_or_404(aid)
    amount = parse_amount(request.form.get("amount"))
    mode = request.form.get("mode") or "nyambung"
    if amount is None or amount <= 0:
        flash("Nominal deposit harus lebih dari 0.", "danger")
        return redirect(url_for("appbalances.index"))
    source = None
    if mode == "nyambung":
        acc_id = request.form.get("source_account_id")
        source = Account.query.get(int(acc_id)) if acc_id else None
        if source is None:
            flash("Mode nyambung wajib pilih rekening sumber.", "danger")
            return redirect(url_for("appbalances.index"))
        if int(source.balance or 0) < amount:
            flash(f"Saldo {source.name} tidak cukup untuk deposit itu.", "danger")
            return redirect(url_for("appbalances.index"))
    shop.deposit(a, amount, mode, source,
                 parse_date(request.form.get("date"), now_jkt()),
                 note=(request.form.get("note") or "").strip())
    db.session.commit()
    flash(f"Saldo {a.name} bertambah. Saldo sekarang Rp {a.balance:,}.".replace(",", "."), "success")
    return redirect(url_for("appbalances.detail", aid=aid))


@bp.route("/<int:aid>/koreksi", methods=["POST"])
@login_required
def koreksi(aid):
    a = ProviderApp.query.get_or_404(aid)
    target = parse_amount(request.form.get("target"))
    reason = (request.form.get("reason") or "").strip()
    if target is None or target < 0:
        flash("Saldo target tidak valid.", "danger")
    elif not reason:
        flash("Alasan koreksi wajib diisi.", "danger")
    else:
        delta = int(target) - int(a.balance or 0)
        if delta == 0:
            flash("Saldo sudah sama, tidak ada perubahan.", "info")
        else:
            shop.add_app_mutation(a, "koreksi", delta,
                                  description=f"Koreksi saldo: {reason}",
                                  date=now_jkt())
            audit("koreksi_saldo_aplikasi", f"{a.name} delta {delta}: {reason}")
            db.session.commit()
            flash("Saldo aplikasi dikoreksi.", "success")
    return redirect(url_for("appbalances.detail", aid=aid))


@bp.route("/<int:aid>")
@login_required
def detail(aid):
    a = ProviderApp.query.get_or_404(aid)
    kind = request.args.get("kind") or ""
    q = AppMutation.query.filter_by(app_id=aid)
    if kind:
        q = q.filter_by(kind=kind)
    muts = q.order_by(AppMutation.date.desc(), AppMutation.id.desc()).limit(300).all()
    saldo_asli = parse_amount(request.args.get("saldo_asli"))
    selisih = None
    if saldo_asli is not None:
        selisih = int(a.balance or 0) - int(saldo_asli)
    accounts = Account.query.filter_by(is_active=True).order_by(Account.id).all()
    return render_template("appbalances/detail.html", a=a, muts=muts, kind=kind,
                           saldo_asli=saldo_asli, selisih=selisih, accounts=accounts)


@bp.route("/mutasi/<int:mid>/cancel", methods=["POST"])
@login_required
def cancel_mutation(mid):
    mut = AppMutation.query.get_or_404(mid)
    if mut.status == "cancelled":
        flash("Mutasi sudah dibatalkan.", "warning")
    elif mut.kind == "terpakai":
        flash("Mutasi 'terpakai' berasal dari penjualan — batalkan dari menu Jual Produk.", "warning")
    elif mut.kind == "deposit":
        shop.reverse_deposit(mut)
        audit("cancel_deposit", f"mutasi#{mut.id}")
        db.session.commit()
        flash("Deposit dibatalkan dan saldo dikembalikan.", "success")
    else:
        if mut.source_tx_id:
            from app.models import Transaction
            tx = Transaction.query.get(mut.source_tx_id)
            if tx is not None and tx.status == "active":
                from app.utils import cancel_transaction
                cancel_transaction(tx, "Pembatalan mutasi aplikasi")
        shop.cancel_app_mutation(mut, "Dibatalkan manual")
        audit("cancel_mutation", f"mutasi#{mut.id}")
        db.session.commit()
        flash("Mutasi dibatalkan via pembalikan.", "success")
    return redirect(request.referrer or url_for("appbalances.index"))
