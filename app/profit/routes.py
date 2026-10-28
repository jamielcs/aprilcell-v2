from datetime import timedelta, datetime
from flask import Blueprint, render_template, request
from app.models import Sale, ServiceSale, now_jkt
from app.utils import login_required
from app import shop

bp = Blueprint("profit", __name__, url_prefix="/keuntungan")


def _period():
    now = now_jkt()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    mode = request.args.get("periode") or "bulan"
    if mode == "hari":
        return today, today + timedelta(days=1) - timedelta(seconds=1), mode
    if mode == "minggu":
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=7) - timedelta(seconds=1), mode
    if mode == "custom":
        d1 = request.args.get("dari") or ""
        d2 = request.args.get("sampai") or ""
        try:
            start = datetime.strptime(d1, "%Y-%m-%d")
        except Exception:
            start = today.replace(day=1)
        try:
            end = datetime.strptime(d2, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
        except Exception:
            end = today + timedelta(days=1) - timedelta(seconds=1)
        return start, end, mode
    # bulan
    start = today.replace(day=1)
    if start.month == 12:
        nxt = start.replace(year=start.year + 1, month=1)
    else:
        nxt = start.replace(month=start.month + 1)
    return start, nxt - timedelta(seconds=1), "bulan"


@bp.route("/")
@login_required
def index():
    start, end, mode = _period()
    total, p_prod, p_jasa, n_tx = shop.profit_between(start, end)
    sales = Sale.query.filter(Sale.status == "active",
                              Sale.date >= start, Sale.date <= end).all()
    svcs = ServiceSale.query.filter(ServiceSale.status == "active",
                                    ServiceSale.date >= start, ServiceSale.date <= end).all()
    # daftar penyumbang untung (gabungan, terbaru dulu)
    contrib = []
    for s in sales:
        contrib.append({"date": s.date, "label": s.product.display_name,
                        "kind": "Produk", "amount": int(s.profit or 0),
                        "url": "/jual-produk/?tanggal=" + s.date.strftime("%Y-%m-%d")})
    for s in svcs:
        contrib.append({"date": s.date, "label": s.product.display_name + " — fee",
                        "kind": "Jasa", "amount": int(s.fee or 0),
                        "url": "/catat-jasa/?tanggal=" + s.date.strftime("%Y-%m-%d")})
    contrib.sort(key=lambda x: x["date"], reverse=True)
    # top 5 paling nguntungin
    agg = {}
    for c in contrib:
        agg[c["label"].replace(" — fee", "")] = agg.get(c["label"].replace(" — fee", ""), 0) + c["amount"]
    top5 = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)[:5]
    # grafik 7 hari terakhir
    now = now_jkt()
    labels, values = [], []
    for i in range(6, -1, -1):
        d0 = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        d1 = d0 + timedelta(days=1) - timedelta(seconds=1)
        t, _, _, _ = shop.profit_between(d0, d1)
        labels.append(d0.strftime("%a"))
        values.append(t)
    pct_prod = round(p_prod * 100 / total) if total > 0 else 0
    pct_jasa = 100 - pct_prod if total > 0 else 0
    return render_template("profit/index.html", total=total, p_prod=p_prod, p_jasa=p_jasa,
                           n_tx=n_tx, contrib=contrib[:30], top5=top5,
                           labels=labels, values=values, mode=mode,
                           dari=request.args.get("dari") or "", sampai=request.args.get("sampai") or "",
                           start=start, end=end, pct_prod=pct_prod, pct_jasa=pct_jasa,
                           n_prod=len(sales), n_jasa=len(svcs))
