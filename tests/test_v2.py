"""Tes fitur v2 aprilcell-v2: master, saldo aplikasi, jual produk, jasa, keuntungan."""
import os, sys
from datetime import datetime
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import TestConfig


@pytest.fixture(scope="module")
def app_instance(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("data2") / "test2.db"
    from app import create_app
    application = create_app(TestConfig, {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file}"})
    yield application


@pytest.fixture(scope="module")
def client(app_instance):
    return app_instance.test_client()


def _acc(name):
    from app.models import Account
    return Account.query.filter_by(name=name).first()


def _today():
    return datetime.now().strftime("%Y-%m-%dT%H:%M")


def test_setup_dan_login(client):
    r = client.post("/setup", data={"username": "admin", "password": "rahasia123",
                                    "confirm_password": "rahasia123"}, follow_redirects=True)
    assert r.status_code == 200
    r = client.post("/login", data={"username": "admin", "password": "rahasia123"},
                    follow_redirects=True)
    assert r.status_code == 200
    assert "Untung Hari Ini".encode() in r.data


def test_buat_aplikasi_provider_saldo_awal(client):
    r = client.post("/saldo-aplikasi/create",
                    data={"name": "Aplikasi A", "serves": "XL, Telkomsel",
                          "min_balance": "50000", "saldo_awal": "500000", "date": _today()},
                    follow_redirects=True)
    assert r.status_code == 200
    with client.application.app_context():
        from app.models import ProviderApp, AppMutation
        a = ProviderApp.query.filter_by(name="Aplikasi A").first()
        assert a is not None and a.balance == 500000
        m = AppMutation.query.filter_by(app_id=a.id, kind="saldo_awal").first()
        assert m is not None and m.balance_after == 500000


def test_buat_master_produk_dan_jasa(client):
    with client.application.app_context():
        from app.models import ProviderApp
        app_id = ProviderApp.query.filter_by(name="Aplikasi A").first().id
    r = client.post("/produk/create",
                    data={"name": "Pulsa XL", "kind": "produk", "category": "XL",
                          "nominal_label": "10.000", "buy_price": "9800",
                          "price_ecer": "12000", "price_grosir1": "11500",
                          "price_grosir2": "11000", "provider_app_id": str(app_id)},
                    follow_redirects=True)
    assert r.status_code == 200
    r = client.post("/produk/create",
                    data={"name": "Isi E-Wallet", "kind": "jasa", "category": "DANA",
                          "nominal_label": "DANA"},
                    follow_redirects=True)
    assert r.status_code == 200
    r = client.post("/produk/create",
                    data={"name": "Kabel Data USB-C", "kind": "produk", "category": "Aksesoris",
                          "nominal_label": "1 meter", "buy_price": "17000",
                          "price_ecer": "25000", "use_stock": "1",
                          "stock_awal": "10", "stock_min": "3"},
                    follow_redirects=True)
    assert r.status_code == 200
    with client.application.app_context():
        from app.models import Product
        pulsa = Product.query.filter_by(name="Pulsa XL").first()
        assert pulsa.price_for("grosir1") == 11500
        kabel = Product.query.filter_by(name="Kabel Data USB-C").first()
        assert kabel.use_stock and kabel.stock_qty == 10


def test_saldo_awal_rekening(client):
    with client.application.app_context():
        bri, dana = _acc("BRI").id, _acc("DANA Rudi").id
    client.post(f"/accounts/{bri}/saldo-awal", data={"amount": "1000000"})
    client.post(f"/accounts/{dana}/saldo-awal", data={"amount": "500000"})
    with client.application.app_context():
        assert _acc("BRI").balance == 1000000
        assert _acc("DANA Rudi").balance == 500000


def test_deposit_nyambung_motong_rekening(client):
    with client.application.app_context():
        from app.models import ProviderApp
        aid = ProviderApp.query.filter_by(name="Aplikasi A").first().id
        bri = _acc("BRI").id
    r = client.post(f"/saldo-aplikasi/{aid}/deposit",
                    data={"amount": "200000", "mode": "nyambung",
                          "source_account_id": str(bri), "date": _today(), "note": "tes"},
                    follow_redirects=True)
    assert r.status_code == 200
    with client.application.app_context():
        from app.models import ProviderApp, AppMutation
        a = ProviderApp.query.get(aid)
        assert a.balance == 700000
        assert _acc("BRI").balance == 800000
        m = AppMutation.query.filter_by(app_id=aid, kind="deposit").order_by(AppMutation.id.desc()).first()
        assert m.mode == "nyambung" and m.balance_after == 700000


def test_deposit_manual_tidak_motong(client):
    with client.application.app_context():
        from app.models import ProviderApp
        aid = ProviderApp.query.filter_by(name="Aplikasi A").first().id
    client.post(f"/saldo-aplikasi/{aid}/deposit",
                data={"amount": "50000", "mode": "manual", "date": _today()})
    with client.application.app_context():
        from app.models import ProviderApp, AppMutation
        assert ProviderApp.query.get(aid).balance == 750000
        assert _acc("BRI").balance == 800000  # tidak berubah
        m = AppMutation.query.filter_by(app_id=aid, kind="deposit").order_by(AppMutation.id.desc()).first()
        assert m.mode == "manual"


def _pulsa_sale(client, qty="1"):
    with client.application.app_context():
        from app.models import Product
        pid = Product.query.filter_by(name="Pulsa XL").first().id
        cash = _acc("Cash").id
    return client.post("/jual-produk/create",
                       data={"product_id": str(pid), "price_level": "ecer", "qty": qty,
                             "payment_method": "tunai", "dest_account_id": str(cash),
                             "date": _today()}, follow_redirects=True)


def test_penjualan_pulsa_potong_saldo_aplikasi(client):
    r = _pulsa_sale(client)
    assert r.status_code == 200
    with client.application.app_context():
        from app.models import ProviderApp, Sale
        a = ProviderApp.query.filter_by(name="Aplikasi A").first()
        assert a.balance == 750000 - 9800
        assert _acc("Cash").balance == 12000
        s = Sale.query.order_by(Sale.id.desc()).first()
        assert s.profit == 2200 and s.total == 12000 and s.app_mutation_id is not None


def test_edit_penjualan_membetulkan_efek(client):
    with client.application.app_context():
        from app.models import Sale, Product
        sid = Sale.query.order_by(Sale.id.desc()).first().id
        pid = Product.query.filter_by(name="Pulsa XL").first().id
        cash = _acc("Cash").id
    r = client.post(f"/jual-produk/{sid}/edit",
                    data={"product_id": str(pid), "price_level": "ecer", "qty": "2",
                          "payment_method": "tunai", "dest_account_id": str(cash),
                          "date": _today()}, follow_redirects=True)
    assert r.status_code == 200
    with client.application.app_context():
        from app.models import ProviderApp, Sale
        a = ProviderApp.query.filter_by(name="Aplikasi A").first()
        assert a.balance == 750000 - 19600
        assert _acc("Cash").balance == 24000
        assert Sale.query.get(sid).profit == 4400


def test_batal_penjualan_membalik_efek(client):
    with client.application.app_context():
        from app.models import Sale
        sid = Sale.query.order_by(Sale.id.desc()).first().id
    client.post(f"/jual-produk/{sid}/cancel", data={})
    with client.application.app_context():
        from app.models import ProviderApp, Sale
        a = ProviderApp.query.filter_by(name="Aplikasi A").first()
        assert a.balance == 750000
        assert _acc("Cash").balance == 0
        assert Sale.query.get(sid).status == "cancelled"


def test_jasa_fee_saja_yang_untung(client):
    with client.application.app_context():
        from app.models import Product
        pid = Product.query.filter_by(name="Isi E-Wallet").first().id
        cash, dana = _acc("Cash").id, _acc("DANA Rudi").id
    r = client.post("/catat-jasa/create",
                    data={"product_id": str(pid), "principal": "100000", "fee": "2500",
                          "payment_method": "tunai", "dest_account_id": str(cash),
                          "source_account_id": str(dana), "date": _today()},
                    follow_redirects=True)
    assert r.status_code == 200
    with client.application.app_context():
        assert _acc("Cash").balance == 102500        # pokok + fee masuk
        assert _acc("DANA Rudi").balance == 400000   # pokok diteruskan
        from app.shop import profit_between
        from datetime import datetime as dt, timedelta
        d0 = dt.now().replace(hour=0, minute=0, second=0, microsecond=0)
        total, pp, pj, n = profit_between(d0, d0 + timedelta(days=1))
        assert pj == 2500 and pp == 0 and total == 2500  # pokok tidak dihitung


def test_batal_jasa_membalik(client):
    with client.application.app_context():
        from app.models import ServiceSale
        sid = ServiceSale.query.order_by(ServiceSale.id.desc()).first().id
    client.post(f"/catat-jasa/{sid}/cancel", data={})
    with client.application.app_context():
        assert _acc("Cash").balance == 0
        assert _acc("DANA Rudi").balance == 500000


def test_stok_terjual_dan_kulakan(client):
    with client.application.app_context():
        from app.models import Product
        pid = Product.query.filter_by(name="Kabel Data USB-C").first().id
        cash = _acc("Cash").id
    r = client.post("/jual-produk/create",
                    data={"product_id": str(pid), "price_level": "ecer", "qty": "2",
                          "payment_method": "qris", "dest_account_id": str(cash),
                          "date": _today()}, follow_redirects=True)
    assert r.status_code == 200
    with client.application.app_context():
        from app.models import Product
        assert Product.query.get(pid).stock_qty == 8
        assert _acc("Cash").balance == 50000
    # kulakan +5 bayar dari Cash @17000
    r = client.post(f"/produk/{pid}/kulakan",
                    data={"qty": "5", "unit_cost": "17000", "account_id": str(cash),
                          "date": datetime.now().strftime("%Y-%m-%d")},
                    follow_redirects=True)
    assert r.status_code == 200
    with client.application.app_context():
        from app.models import Product
        assert Product.query.get(pid).stock_qty == 13
        assert _acc("Cash").balance == 50000 - 85000
    # koreksi stok ke 12 dengan alasan
    client.post(f"/produk/{pid}/stok-koreksi", data={"target": "12", "reason": "hitung ulang"})
    with client.application.app_context():
        from app.models import Product
        assert Product.query.get(pid).stock_qty == 12


def test_jual_melebihi_stok_ditolak(client):
    with client.application.app_context():
        from app.models import Product
        pid = Product.query.filter_by(name="Kabel Data USB-C").first().id
        cash = _acc("Cash").id
    client.post("/jual-produk/create",
                data={"product_id": str(pid), "price_level": "ecer", "qty": "99",
                      "payment_method": "tunai", "dest_account_id": str(cash),
                      "date": _today()})
    with client.application.app_context():
        from app.models import Product, Sale
        assert Product.query.get(pid).stock_qty == 12
        assert Sale.query.filter_by(product_id=pid, status="active").count() == 1


def test_koreksi_saldo_aplikasi(client):
    with client.application.app_context():
        from app.models import ProviderApp
        aid = ProviderApp.query.filter_by(name="Aplikasi A").first().id
    # tanpa alasan -> tidak berubah
    client.post(f"/saldo-aplikasi/{aid}/koreksi", data={"target": "1", "reason": ""})
    with client.application.app_context():
        from app.models import ProviderApp
        assert ProviderApp.query.get(aid).balance == 750000
    client.post(f"/saldo-aplikasi/{aid}/koreksi",
                data={"target": "700000", "reason": "rekonsiliasi manual"})
    with client.application.app_context():
        from app.models import ProviderApp, AppMutation
        assert ProviderApp.query.get(aid).balance == 700000
        m = AppMutation.query.filter_by(app_id=aid, kind="koreksi").order_by(AppMutation.id.desc()).first()
        assert m.signed_amount == -50000 and m.balance_after == 700000


def test_halaman_baru_render(client):
    for path, marker in [("/produk/", "Produk &amp; Jasa"), ("/saldo-aplikasi/", "Saldo Aplikasi"),
                         ("/jual-produk/", "Jual Produk"), ("/catat-jasa/", "Catat Jasa"),
                         ("/keuntungan/", "Keuntungan"), ("/settings/", "Identitas Toko")]:
        r = client.get(path)
        assert r.status_code == 200, path
        assert marker.encode() in r.data, path
    r = client.get("/keuntungan/?periode=hari")
    assert r.status_code == 200
    assert "16.000".encode() in r.data  # untung kabel 2 x 8000


def test_pengaturan_toko_dan_tema(client):
    r = client.post("/settings/toko", data={"shop_name": "APRILcell Baru",
                                            "shop_owner": "Roichatul",
                                            "receipt_footer": "Makasih!"}, follow_redirects=True)
    assert r.status_code == 200
    r = client.post("/settings/tampilan", data={"theme_default": "dark", "accent": "#f97316"},
                    follow_redirects=True)
    assert r.status_code == 200
    r = client.get("/dashboard/")
    assert "APRILcell Baru".encode() in r.data
    assert b'data-bs-theme="dark"' in r.data
