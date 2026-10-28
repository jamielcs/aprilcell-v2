import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from extensions import db
from app.models import User, ExpenseCategory, AuditLog, Person
from app.utils import login_required, audit
from app import shop

bp = Blueprint("settings", __name__, url_prefix="/settings")


@bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    user = User.query.get(session.get("user_id"))
    if request.method == "POST" and request.form.get("action") == "change_password":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if not user.check_password(current):
            flash("Password saat ini salah.", "danger")
        elif len(new) < 6:
            flash("Password baru minimal 6 karakter.", "danger")
        elif new != confirm:
            flash("Konfirmasi password baru tidak sama.", "danger")
        else:
            user.set_password(new)
            audit("change_password", f"User {user.username} ganti password")
            db.session.commit()
            flash("Password berhasil diubah.", "success")
            return redirect(url_for("settings.index"))
    categories = ExpenseCategory.query.order_by(ExpenseCategory.name).all()
    logs = AuditLog.query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(100).all()
    people = Person.query.order_by(Person.name).all()
    return render_template("settings/index.html", user=user, categories=categories, logs=logs, people=people,
                           low_balance_default=shop.get_setting("low_balance_default"),
                           low_warning=shop.get_setting("low_warning"),
                           auto_backup=shop.get_setting("auto_backup"))


@bp.route("/toko", methods=["POST"])
@login_required
def toko():
    shop.set_setting("shop_name", (request.form.get("shop_name") or "APRILcell").strip() or "APRILcell")
    shop.set_setting("shop_owner", (request.form.get("shop_owner") or "").strip())
    shop.set_setting("shop_phone", (request.form.get("shop_phone") or "").strip())
    shop.set_setting("shop_address", (request.form.get("shop_address") or "").strip())
    shop.set_setting("receipt_footer", (request.form.get("receipt_footer") or "").strip())
    f = request.files.get("logo")
    if f and f.filename:
        ext = os.path.splitext(f.filename)[1].lower()
        if ext in (".png", ".jpg", ".jpeg", ".webp", ".svg"):
            updir = os.path.join(current_app.static_folder, "uploads")
            os.makedirs(updir, exist_ok=True)
            fname = "logo" + ext
            f.save(os.path.join(updir, fname))
            shop.set_setting("logo_file", fname)
        else:
            flash("Format logo harus PNG/JPG/WebP/SVG.", "danger")
            return redirect(url_for("settings.index"))
    if request.form.get("hapus_logo"):
        shop.set_setting("logo_file", "")
    audit("update_toko", "Identitas toko diperbarui")
    db.session.commit()
    flash("Identitas toko disimpan.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/tampilan", methods=["POST"])
@login_required
def tampilan():
    theme = request.form.get("theme_default") or "light"
    if theme not in ("light", "dark", "system"):
        theme = "light"
    accent = (request.form.get("accent") or "#2563eb").strip()
    if not (accent.startswith("#") and len(accent) in (4, 7)):
        accent = "#2563eb"
    shop.set_setting("theme_default", theme)
    shop.set_setting("accent", accent)
    audit("update_tampilan", f"tema {theme} aksen {accent}")
    db.session.commit()
    flash("Pengaturan tampilan disimpan.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/usaha", methods=["POST"])
@login_required
def usaha():
    from app.utils import parse_amount
    low = parse_amount(request.form.get("low_balance_default"))
    if low is not None and low >= 0:
        shop.set_setting("low_balance_default", str(int(low)))
    shop.set_setting("low_warning", "1" if request.form.get("low_warning") else "0")
    shop.set_setting("auto_backup", "1" if request.form.get("auto_backup") else "0")
    audit("update_usaha", "Aturan usaha diperbarui")
    db.session.commit()
    flash("Aturan usaha disimpan.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/categories/create", methods=["POST"])
@login_required
def create_category():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Nama kategori wajib diisi.", "danger")
    elif ExpenseCategory.query.filter_by(name=name).first():
        flash("Kategori sudah ada.", "danger")
    else:
        db.session.add(ExpenseCategory(name=name))
        audit("create_category", name); db.session.commit()
        flash("Kategori ditambahkan.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/categories/<int:cid>/edit", methods=["POST"])
@login_required
def edit_category(cid):
    c = ExpenseCategory.query.get_or_404(cid)
    c.name = (request.form.get("name") or c.name).strip()
    db.session.commit(); flash("Kategori diperbarui.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/categories/<int:cid>/deactivate", methods=["POST"])
@login_required
def deactivate_category(cid):
    c = ExpenseCategory.query.get_or_404(cid)
    c.is_active = False
    audit("deactivate_category", c.name); db.session.commit()
    flash("Kategori dinonaktifkan.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/categories/<int:cid>/activate", methods=["POST"])
@login_required
def activate_category(cid):
    c = ExpenseCategory.query.get_or_404(cid)
    c.is_active = True; db.session.commit()
    flash("Kategori diaktifkan.", "success")
    return redirect(url_for("settings.index"))
