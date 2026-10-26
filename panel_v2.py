import time
import threading
import json
import os
import smtplib
import matris_motoru
import math
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText

import gspread
from google.oauth2.service_account import Credentials
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pytz
import requests
import logging
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components

try:
    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
except Exception:
    add_script_run_ctx = None
    get_script_run_ctx = None


class _ScriptRunCtxFiltresi(logging.Filter):
    def filter(self, record):
        return "missing ScriptRunContext" not in record.getMessage()


for _logger_adi in (
    "streamlit.runtime.scriptrunner_utils.script_run_context",
    "streamlit.runtime.scriptrunner.script_run_context",
):
    logging.getLogger(_logger_adi).addFilter(_ScriptRunCtxFiltresi())

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(
    page_title="Pro Kripto Canlı Akış ve Paneli",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- OTOMATİK YENİLEME (120 SANİYE) ---
st_autorefresh(interval=120000, key="kripto_panel_otomatik_yenileme")

# --- TABLET YATAY: masaüstü %100 düzeniyle göster (dar ekranda sütunlar sıkışmasın) ---
try:
    components.html("""<script>
(function () {
  function uygula(doc) {
    try {
      var m = doc.querySelector('meta[name=viewport]');
      if (!m) { m = doc.createElement('meta'); m.name = 'viewport'; doc.head.appendChild(m); }
      var w = window.screen.width, h = window.screen.height;
      var yatay = window.matchMedia('(orientation: landscape)').matches;
      var dokunmatik = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
      if (dokunmatik && yatay && Math.min(w, h) >= 600) { m.setAttribute('content', 'width=1366'); }
      else { m.setAttribute('content', 'width=device-width, initial-scale=1'); }
    } catch (e) {}
  }
  function hepsi() {
    var pencere = window;
    for (var i = 0; i < 4; i++) {
      try { uygula(pencere.document); } catch (e) {}
      if (pencere.parent === pencere) break;
      pencere = pencere.parent;
    }
  }
  hepsi();
  window.addEventListener('orientationchange', function () { setTimeout(hepsi, 300); });
  window.addEventListener('resize', function () { setTimeout(hepsi, 300); });
})();
</script>""", height=0)
except Exception:
    pass

# --- PREMIUM DARK TRADING TERMINAL TASARIMI ---
st.markdown(
    """
<style>
:root { --bg:#080d18; --panel:#101827; --panel2:#151f31; --border:#253247; --text:#e8eef8; --muted:#91a0b8; --green:#20d6a1; --red:#ff647c; --blue:#5b8cff; }
html, body, [class*="css"], .stApp { font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background:var(--bg) !important; color:var(--text) !important; }
[data-testid="stHeader"] { background:rgba(8,13,24,.88) !important; }
[data-testid="stMain"] { background:radial-gradient(ellipse at 15% 0%, rgba(48,86,160,.14), transparent 42%), var(--bg) !important; }
.block-container { max-width: 1600px; padding-top:1.4rem; padding-bottom:3rem; }
[data-testid="stVerticalBlockBorderWrapper"] { background:transparent; }
[data-testid="stMetric"], .metric-container { background:linear-gradient(145deg,#141f31,#0f1726) !important; border:1px solid var(--border) !important; border-radius:16px !important; padding:17px 19px !important; box-shadow:0 8px 28px rgba(0,0,0,.16); }
.metric-container { min-height:104px; container-type:inline-size; }
.metric-container p { color:var(--muted) !important; font-size:12px !important; letter-spacing:.35px; }
.metric-container h1 { font-size:25px !important; font-weight:750 !important; }
h1 { color:#f4f7ff !important; font-size:clamp(1.7rem,2.3vw,2.45rem) !important; font-weight:800 !important; letter-spacing:-.7px; }
h2,h3,h4 { color:#e8eef8 !important; font-weight:700 !important; letter-spacing:-.25px; }
p, label, [data-testid="stMarkdownContainer"] { color:var(--text); }
small, .muted { color:var(--muted) !important; }
hr { border-color:var(--border) !important; margin:1.4rem 0 !important; }
[data-testid="stTabs"] [data-baseweb="tab-list"] { gap:8px; border-bottom:1px solid var(--border); }
[data-testid="stTabs"] button[role="tab"] { background:#111b2b; border:1px solid var(--border); border-radius:10px 10px 0 0; color:var(--muted); padding:10px 16px; }
[data-testid="stTabs"] button[aria-selected="true"] { background:#1a2b45; color:#fff; border-color:#4269a9; }
.stButton > button, div.stFormSubmitButton > button, [data-testid="stDownloadButton"] button { background:linear-gradient(135deg,#3977f6,#5b8cff) !important; color:white !important; border:1px solid #4f83f5 !important; border-radius:10px !important; font-weight:700 !important; min-height:42px; transition:all .18s ease; }
.stButton > button:hover, div.stFormSubmitButton > button:hover { filter:brightness(1.12); border-color:#91b2ff !important; transform:translateY(-1px); }
[data-baseweb="input"] > div, [data-baseweb="select"] > div, [data-testid="stNumberInput"] input, [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea { background:#0d1523 !important; color:var(--text) !important; border-color:#2a3951 !important; border-radius:9px !important; }
[data-testid="stDataFrame"], [data-testid="stTable"] { border:1px solid var(--border); border-radius:12px; overflow:hidden; }
[data-testid="stExpander"] { background:#101827; border:1px solid var(--border); border-radius:12px; }
[data-testid="stAlert"] { border-radius:12px; }
.table-container { width:100%; max-width:100%; overflow-x:auto; -webkit-overflow-scrolling:touch; margin:10px 0 22px; border:1px solid var(--border); border-radius:13px; }
[data-testid="stHorizontalBlock"] { align-items:stretch; }
[data-testid="stPlotlyChart"] { min-width:0; background:transparent !important; border:none !important; border-radius:0px !important; padding:0px !important; box-shadow:none !important; }
@media (min-width: 1200px) { .block-container { max-width:100%; padding-left:1.5rem; padding-right:1.5rem; } }
.custom-table { width:100%; border-collapse:separate; border-spacing:0; background:#0e1726; }
.custom-table th { background:#19263a; text-align:center; padding:10px 5px; border-bottom:1px solid #30415b; color:#aebdd2 !important; font-weight:700; font-size:11px; line-height:1.35; white-space:nowrap; }
.custom-table td { background:#101a2a; text-align:center; padding:9px 5px; border-bottom:1px solid #202e43; font-weight:600; vertical-align:middle; color:#e4ebf7 !important; white-space:nowrap; font-size:11px; }
.custom-table tr:hover td { background:#17243a; }
.custom-table td img { width:22px; height:22px; object-fit:contain; vertical-align:middle; }
.kar-hucre { background-color: #00FF00 !important; color: #000000 !important; font-weight: bold; padding: 4px; border-radius: 4px; }
.zarar-hucre { background-color: rgb(255, 75, 0) !important; color: #000000 !important; font-weight: bold; padding: 4px; border-radius: 4px; }
[data-testid="stSidebar"] { background:#0b1220 !important; border-right:1px solid var(--border); }
[data-testid="stCaptionContainer"] { color:var(--muted) !important; }
@media (max-width: 768px) { .block-container { padding:1rem .7rem 2rem; } .metric-container { padding:12px !important; } .metric-container h1 { font-size:20px !important; } }
.custom-table td, .custom-table th { font-variant-numeric:tabular-nums; }
.custom-table th { background:#141f31; color:#8fa0ba !important; font-weight:600; letter-spacing:.2px; }
.custom-table td { background:#0f1828; }
.st-key-poz_kartlari [data-testid="stHorizontalBlock"] { gap:.6rem; }
.st-key-poz_kartlari [data-testid="stCheckbox"] label p { font-size:12px; color:#91a0b8; }
.pos-card { background:linear-gradient(145deg,#141f31,#0f1726); border:1px solid var(--border); border-radius:14px; padding:12px 12px 10px; font-variant-numeric:tabular-nums; margin-bottom:8px; }
.pos-head { display:flex; justify-content:space-between; align-items:flex-start; gap:6px; }
.pos-left { display:flex; align-items:center; gap:7px; min-width:0; }
.pos-logo { width:22px; height:22px; object-fit:contain; flex:none; }
.pos-name { font-size:13px; font-weight:800; color:#e8eef8; white-space:nowrap; }
.pos-sub { display:flex; align-items:center; gap:5px; margin-top:2px; }
.pos-id { color:var(--muted); font-size:10px; }
.pill { padding:1px 8px; border-radius:999px; font-size:10px; font-weight:700; border:1px solid; }
.pill-long { color:#00FF00; border-color:rgba(0,255,0,.45); background:rgba(0,255,0,.08); }
.pill-short { color:rgb(255,75,0); border-color:rgba(255,75,0,.5); background:rgba(255,75,0,.10); }
.pos-kz { font-size:17px; font-weight:800; text-align:right; line-height:1.1; white-space:nowrap; }
.pos-kz small { display:block; font-size:10px; font-weight:600; opacity:.8; }
.range-wrap { margin:14px 0 8px; }
.range-bar { position:relative; height:7px; border-radius:6px; background:linear-gradient(90deg,rgba(255,75,0,.60),rgba(145,160,184,.22) 50%,rgba(0,255,0,.50)); }
.range-tick { position:absolute; top:-4px; width:2px; height:15px; background:#91a0b8; border-radius:2px; transform:translateX(-1px); }
.range-dot { position:absolute; top:-5px; width:17px; height:17px; border-radius:50%; background:#e8eef8; border:3px solid #5b8cff; transform:translateX(-8px); box-shadow:0 0 0 3px rgba(91,140,255,.18); }
.range-lbl { display:flex; justify-content:space-between; margin-top:11px; font-size:10px; font-weight:700; gap:4px; }
.range-dist { display:flex; justify-content:space-between; align-items:baseline; margin-top:3px; font-size:10px; color:var(--muted); gap:4px; }
.range-mid { color:#e8eef8; font-weight:800; font-size:11px; }
.pos-meta { display:flex; justify-content:space-between; gap:6px; flex-wrap:wrap; font-size:10px; color:var(--muted); margin-top:7px; }
.pos-meta b { color:#e8eef8; font-weight:700; }
.bar-bg { height:6px; border-radius:6px; background:#1b2a40; overflow:hidden; }
.bar-mini { height:4px; margin-top:5px; }
.bar-fill { height:100%; border-radius:6px; transition:width .4s; }
.pos-detay { margin-top:8px; font-size:10px; color:var(--muted); }
.pos-detay summary { cursor:pointer; color:#8fa0ba; }
.pos-detay-ic { padding-top:5px; line-height:1.6; }
.risk-card { background:linear-gradient(145deg,#141f31,#0f1726); border:1px solid var(--border); border-radius:16px; padding:14px 18px; margin:6px 0 14px; }
.risk-top { display:flex; justify-content:space-between; align-items:baseline; gap:8px; flex-wrap:wrap; margin-bottom:8px; }
.risk-title { font-size:13px; font-weight:700; color:#e8eef8; }
.risk-val { font-size:15px; font-weight:800; font-variant-numeric:tabular-nums; }
.risk-val small { font-weight:600; color:var(--muted); }
.risk-note { font-size:10px; color:var(--muted); margin-top:7px; }
.ozet-card { background:linear-gradient(145deg,#141f31,#0f1726); border:1px solid var(--border); border-radius:14px; padding:14px 16px; font-variant-numeric:tabular-nums; }
.ozet-satir { display:flex; justify-content:space-between; align-items:baseline; gap:8px; font-size:12px; color:var(--muted); padding:6px 0; border-bottom:1px solid #1d2a40; }
.ozet-satir:last-child { border-bottom:none; }
.ozet-alt { text-align:center; font-size:10px; color:var(--muted); margin-top:6px; }
.ozet-bos { text-align:center; color:var(--muted); font-size:12px; padding:8px 0 12px; }
.ozet-card .range-wrap { margin:6px 0 10px; padding-bottom:6px; border-bottom:1px solid #1d2a40; }
.ozet-satir b { font-size:13px; font-weight:800; white-space:nowrap; }
.mx-wrap { min-width:118px; font-variant-numeric:tabular-nums; }
.mx-puan { font-weight:800; font-size:13px; }
.mx-yon { font-size:11px; font-weight:700; }
.mx-bar { position:relative; height:6px; border-radius:6px; margin:8px 6px 5px; background:linear-gradient(90deg,rgba(255,75,0,.60),rgba(145,160,184,.22) 50%,rgba(0,255,0,.50)); }
.mx-dot { position:absolute; top:-4px; width:14px; height:14px; border-radius:50%; background:#e8eef8; border:3px solid #5b8cff; transform:translateX(-7px); box-shadow:0 0 0 2px rgba(91,140,255,.18); }
.mx-lbl { display:flex; justify-content:space-between; font-size:10px; font-weight:700; }
.st-key-btn_tum_kapat button { background:rgb(255,75,0) !important; color:#000 !important; font-weight:800 !important; border:none !important; }
.risk-line { font-size:13px; line-height:1.55; color:#e8eef8; margin:4px 0 8px; }
.st-key-grafik_total [data-testid="stPlotlyChart"] { border:1px solid var(--border) !important; border-radius:14px !important; background:linear-gradient(145deg,#141f31,#0f1726) !important; padding:6px 4px 0 !important; overflow:hidden; }
</style>
""",
    unsafe_allow_html=True,
)

# --- SABİTLER ---
GOOGLE_SHEET_DOSYA = "KriptoPortfoyVeritabani"
BASLANGIC_BAKIYE = 0.0   # kasa sıfırdan başlar; tutarı "Kasaya Para Ekle" ile siz girersiniz
KALDIRAC = 5

# --- Komisyon ve risk ayarları (Binance USDⓈ-M Futures, standart kullanıcı / VIP 0) ---
KOMISYON_TAKER = 0.0005         # %0,05: piyasa emriyle giriş ve stop çıkışı
KOMISYON_MAKER = 0.0002         # %0,02: limit emirle hedef (kâr al) çıkışı
ISLEM_BASINA_RISK_YUZDE = 1.0   # tek işlemin (komisyon dahil) stop riski: kasanın en fazla %1'i
TOPLAM_RISK_LIMIT_YUZDE = 3.0   # tüm açık işlemlerin toplam stop riski: kasanın en fazla %3'ü

def giris_komisyonu(miktar):
    return float(miktar) * KALDIRAC * KOMISYON_TAKER

def cikis_komisyonu(miktar, hedef_mi):
    """Hedef (limit emir) maker, stop ve manuel kapanış (piyasa emri) taker öder."""
    return float(miktar) * KALDIRAC * (KOMISYON_MAKER if hedef_mi else KOMISYON_TAKER)

def beklenen_ve_olasi(long_mi, miktar, giris, kar_al, stop):
    """Hedefe/stopa ulaşılırsa kalan K/Z. Giriş komisyonu açılışta kasadan düşüldüğü için sadece çıkış komisyonu dahil."""
    if long_mi:
        brut_kar = miktar * KALDIRAC * ((kar_al - giris) / giris)
        brut_stop = miktar * KALDIRAC * ((stop - giris) / giris)
    else:
        brut_kar = miktar * KALDIRAC * ((giris - kar_al) / giris)
        brut_stop = miktar * KALDIRAC * ((giris - stop) / giris)
    return brut_kar - cikis_komisyonu(miktar, True), brut_stop - cikis_komisyonu(miktar, False)

def canli_beklenen_olasi(row):
    """Açık işlem: hedef/stop değerlerini GÜNCEL kaldıraç ve komisyonla hesaplar. Kapalı işlem: kayıtlı değer."""
    try:
        if not durum_kapali_mi(row["Durum"]):
            giris = float(row["Giris_Fiyat"])
            if giris > 0:
                return beklenen_ve_olasi("Long" in str(row["Yon"]), float(row["Islem_Miktari"]), giris, float(row["Kar_Al"]), float(row["Stop"]))
    except Exception:
        pass
    return float(row["Beklenen_Kar"]), float(row["Olasi_Stop"])

def stop_riski(miktar, giris, stop):
    """Stop vurulursa olası toplam zarar (pozitif): fiyat zararı + giriş ve çıkış komisyonu."""
    if giris <= 0:
        return 0.0
    return float(miktar) * KALDIRAC * (abs(stop - giris) / giris + 2 * KOMISYON_TAKER)

def acik_pozisyonlar_riski(df, haric_coin=None):
    if df is None or df.empty or "Durum" not in df.columns:
        return 0.0
    acik = df[~durum_kapali_maskesi(df["Durum"])]
    toplam = 0.0
    for _, r in acik.iterrows():
        if haric_coin is not None and r["Coin"] == haric_coin:
            continue
        toplam += stop_riski(float(r["Islem_Miktari"]), float(r["Giris_Fiyat"]), float(r["Stop"]))
    return toplam

def risk_kapasitesi(toplam_kasa, df, coin, giris, stop):
    """Bu coin için izin verilen azami toplam teminat. Sınırlar: işlem başı risk ve toplam risk."""
    stop_oran = abs(stop - giris) / giris if giris > 0 else 0.0
    birim = KALDIRAC * (stop_oran + 2 * KOMISYON_TAKER)
    islem_limit = max(0.0, toplam_kasa) * ISLEM_BASINA_RISK_YUZDE / 100.0
    toplam_limit = max(0.0, toplam_kasa) * TOPLAM_RISK_LIMIT_YUZDE / 100.0
    diger = acik_pozisyonlar_riski(df, haric_coin=coin)
    kalan = max(0.0, toplam_limit - diger)
    azami = min(islem_limit, kalan) / birim if birim > 0 else 0.0
    return {"azami": azami, "islem_limit": islem_limit, "kalan_toplam_risk": kalan, "diger_risk": diger, "birim": birim}

# ====================== GÖRSEL BİLEŞENLER ======================
RENK_YESIL, RENK_KIRMIZI, RENK_SARI = "#00FF00", "rgb(255, 75, 0)", "#f5c451"

def _fmt_fiyat(v):
    return f"{v:,.4f}" if abs(v) < 10 else f"{v:,.2f}"

def _risk_rengi(oran):
    return RENK_YESIL if oran < 0.6 else (RENK_SARI if oran < 0.9 else RENK_KIRMIZI)

def risk_kar_ozeti_html(df, toplam_kasa, efektif_kasa, bos_bakiye, marjin, acik_kz):
    """Açık işlemlerin toplamı: stop ↔ hedef aralığında anlık K/Z konumu + kasa bilgileri (tek satır HTML)."""
    acik = pd.DataFrame()
    if df is not None and not df.empty and "Durum" in df.columns:
        acik = df[~durum_kapali_maskesi(df["Durum"])]
    hedef_toplam = sum(canli_beklenen_olasi(r)[0] for _, r in acik.iterrows()) if not acik.empty else 0.0
    stop_toplam = sum(canli_beklenen_olasi(r)[1] for _, r in acik.iterrows()) if not acik.empty else 0.0

    def satir(etiket, deger, renkli="#e8eef8"):
        return f'<div class="ozet-satir"><span>{etiket}</span><b style="color:{renkli}">{deger}</b></div>'

    aralik = hedef_toplam - stop_toplam
    if acik.empty or aralik <= 0:
        bar = '<div class="ozet-bos">Açık işlem yok</div>'
    else:
        t_anlik = min(1.0, max(0.0, (acik_kz - stop_toplam) / aralik))
        t_sifir = min(1.0, max(0.0, (0.0 - stop_toplam) / aralik))
        stopa, hedefe = acik_kz - stop_toplam, hedef_toplam - acik_kz
        oran = (hedef_toplam / abs(stop_toplam)) if stop_toplam < 0 else 0.0
        kz_renk = RENK_YESIL if acik_kz >= 0 else RENK_KIRMIZI
        bar = ('<div class="range-wrap"><div class="range-bar">'
               f'<div class="range-tick" style="left:{t_sifir*100:.1f}%"></div><div class="range-dot" style="left:{t_anlik*100:.1f}%"></div></div>'
               f'<div class="range-lbl"><span style="color:{RENK_KIRMIZI}">Stop {stop_toplam:+,.2f} $</span><span style="color:{RENK_YESIL}">Hedef {hedef_toplam:+,.2f} $</span></div>'
               f'<div class="range-dist"><span>Stopa {stopa:,.2f} $</span><span class="range-mid" style="color:{kz_renk}">{acik_kz:+,.2f} $</span><span>Hedefe {hedefe:,.2f} $</span></div>'
               f'<div class="ozet-alt">{len(acik)} açık işlem toplamı · risk/ödül 1 : {oran:.2f}</div></div>')

    return ('<div class="ozet-card">' + bar
            + satir("Anlık K/Z (net)", f"{acik_kz:+,.2f} $", RENK_YESIL if acik_kz >= 0 else RENK_KIRMIZI)
            + satir("Efektif kasa", f"{efektif_kasa:,.2f} $")
            + satir("Toplam kasa", f"{toplam_kasa:,.2f} $")
            + satir("Kullanılan teminat", f"{marjin:,.2f} $")
            + satir("Boş nakit", f"{bos_bakiye:,.2f} $")
            + '</div>')

# ====================== A4 PDF RAPORU ======================
_TR_YEDEK_TABLO = str.maketrans("ğüşöçıİĞÜŞÖÇ", "gusociIGUSOC")

def _rapor_sayi(v, d=2):
    try:
        t = f"{float(v):,.{d}f}"
    except Exception:
        return "-"
    return t.replace(",", "X").replace(".", ",").replace("X", ".")

def _rapor_tarih(s_):
    """'22.10.2026 15:00' -> '22.10.26 15:00' (tablo sütununa sığsın)."""
    t = str(s_).strip()
    return (t[:6] + t[8:16]) if len(t) >= 16 and t[2] == "." and t[5] == "." else t

def _rapor_fiyat(v):
    try:
        v = float(v)
    except Exception:
        return "-"
    return _rapor_sayi(v, 4 if abs(v) < 10 else 2)

def _rapor_fontlari_kaydet():
    """Türkçe karakterli TTF kaydeder. Bulunamazsa Helvetica + ASCII yedek (adlar, ğ→g gibi sadeleşir)."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    adaylar = [("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]
    try:
        import matplotlib
        taban = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
        adaylar.append((os.path.join(taban, "DejaVuSans.ttf"), os.path.join(taban, "DejaVuSans-Bold.ttf")))
    except Exception:
        pass
    adaylar.append(("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"))
    for normal, kalin in adaylar:
        if os.path.exists(normal) and os.path.exists(kalin):
            try:
                pdfmetrics.registerFont(TTFont("RaporFont", normal))
                pdfmetrics.registerFont(TTFont("RaporFont-Bold", kalin))
                return "RaporFont", "RaporFont-Bold", True
            except Exception:
                continue
    return "Helvetica", "Helvetica-Bold", False

def rapor_pdf_olustur(df_trade, df_kasa, bakiye, fiyatlar, zaman):
    """Döner: (pdf_bytes, None) ya da (None, hata_metni)."""
    try:
        import io
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, KeepInFrame
        from reportlab.graphics.shapes import Drawing, String, Rect, Wedge, Circle, Line
        from reportlab.graphics.charts.lineplots import LinePlot
    except ImportError:
        return None, "reportlab kurulu değil (requirements.txt dosyasına 'reportlab' ekleyin)."

    try:
        FONT, FONT_B, ttf_var = _rapor_fontlari_kaydet()
        T = (lambda x: str(x)) if ttf_var else (lambda x: str(x).translate(_TR_YEDEK_TABLO))

        toplam_kasa, efektif_kasa, bos_bakiye, marjin, acik_kz = [float(x) for x in bakiye]
        YESIL, KIRMIZI = colors.HexColor("#0a8f3c"), colors.HexColor("#d9480f")
        NEON_Y, NEON_T = colors.HexColor("#00FF00"), colors.HexColor("#ff4b00")
        LACIVERT, GRI, ACIK = colors.HexColor("#14213d"), colors.HexColor("#5f6b7a"), colors.HexColor("#eef2f7")

        # ---------- veri hazırlığı
        cols = ["Islem_ID", "Acilis_Zamani", "Coin", "Yon", "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Beklenen_Kar",
                "Olasi_Stop", "Durum", "Net_Kar_Zarar", "Kapanis_Zamani", "Kapanis_Fiyati"]
        dt = df_trade.copy() if df_trade is not None and not df_trade.empty else pd.DataFrame(columns=cols)
        if not dt.empty:
            kapali_m = durum_kapali_maskesi(dt["Durum"])
            kap, acik = dt[kapali_m].copy(), dt[~kapali_m].copy()
        else:
            kap, acik = dt.copy(), dt.copy()
        kap["Net_Kar_Zarar"] = pd.to_numeric(kap["Net_Kar_Zarar"], errors="coerce").fillna(0.0)
        kap["_kt"] = pd.to_datetime(kap["Kapanis_Zamani"], format="%d.%m.%Y %H:%M", errors="coerce")
        kap = kap.sort_values(["_kt", "Islem_ID"], na_position="last").reset_index(drop=True)

        dk = df_kasa.copy() if df_kasa is not None and not df_kasa.empty else pd.DataFrame(columns=["Islem_ID", "Zaman", "Islem_Turu", "Tutar", "Aciklama"])
        dk["Tutar"] = pd.to_numeric(dk["Tutar"], errors="coerce").fillna(0.0)
        dk["_z"] = pd.to_datetime(dk["Zaman"], format="%d.%m.%Y %H:%M", errors="coerce")
        dk = dk.sort_values("Islem_ID").reset_index(drop=True)
        tur_toplam = {t: float(dk.loc[dk["Islem_Turu"] == t, "Tutar"].sum()) for t in ("Para_Yatir", "Para_Cek", "Trade_Sonuc", "Komisyon")}
        net_para_girisi = tur_toplam["Para_Yatir"] + tur_toplam["Para_Cek"]
        anapara = BASLANGIC_BAKIYE + net_para_girisi
        getiri = ((efektif_kasa - anapara) / anapara * 100.0) if anapara > 0 else 0.0
        gerceklesen = float(kap["Net_Kar_Zarar"].sum())

        # ID aralığı, ilk açılış, ID başlangıç/sonu kasa
        idler = pd.to_numeric(dt["Islem_ID"], errors="coerce").dropna().astype(int) if not dt.empty else pd.Series([], dtype=int)
        id_min, id_max = (int(idler.min()), int(idler.max())) if len(idler) else (0, 0)
        acilislar = pd.to_datetime(dt["Acilis_Zamani"], format="%d.%m.%Y %H:%M", errors="coerce").dropna() if not dt.empty else pd.Series([], dtype="datetime64[ns]")
        ilk_acilis = acilislar.min() if len(acilislar) else None
        para_hareketi = dk[dk["Islem_Turu"].isin(["Para_Yatir", "Para_Cek"])]
        if ilk_acilis is not None:
            para_hareketi = para_hareketi[(para_hareketi["_z"] <= ilk_acilis) | para_hareketi["_z"].isna()]
        id_baslangic_kasa = float(BASLANGIC_BAKIYE + para_hareketi["Tutar"].sum())
        id_sonu_kasa = toplam_kasa

        net = kap["Net_Kar_Zarar"]
        n_kap = len(kap)
        kaz, kay = net[net > 0], net[net < 0]
        isabet = (len(kaz) / n_kap * 100.0) if n_kap else 0.0
        pf = (kaz.sum() / abs(kay.sum())) if len(kay) and kay.sum() != 0 else None

        # ---------- stiller
        st_ba = ParagraphStyle("ba", fontName=FONT_B, fontSize=18, textColor=LACIVERT, leading=22)
        st_ust = ParagraphStyle("ust", fontName=FONT, fontSize=8, textColor=GRI, leading=11)
        st_h = ParagraphStyle("h", fontName=FONT_B, fontSize=11.5, textColor=colors.white, leading=14, backColor=LACIVERT,
                              borderPadding=(4, 6, 4, 6), spaceBefore=8, spaceAfter=6)
        st_pb = ParagraphStyle("pb", fontName=FONT_B, fontSize=12, textColor=LACIVERT, leading=15, spaceBefore=8, spaceAfter=3)
        st_n = ParagraphStyle("n", fontName=FONT, fontSize=8, textColor=colors.black, leading=10)

        def tablo_stili(baslik_renk=LACIVERT, fs=7, zebra=True):
            ts = [("FONTNAME", (0, 0), (-1, -1), FONT), ("FONTSIZE", (0, 0), (-1, -1), fs),
                  ("FONTNAME", (0, 0), (-1, 0), FONT_B), ("BACKGROUND", (0, 0), (-1, 0), baslik_renk),
                  ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                  ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
                  ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#d5dbe4"))]
            if zebra:
                ts.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ACIK]))
            return TableStyle(ts)

        def renkli(v):
            return YESIL if v > 0 else (KIRMIZI if v < 0 else colors.black)

        def hex_(c):
            return "#" + c.hexval().replace("0x", "")

        W = A4[0] - 24 * mm   # kullanılabilir genişlik

        def cizgi_grafik(noktalar, etiketler, baslik, renk, yukseklik=135):
            d = Drawing(W, yukseklik + 16)
            d.add(String(0, yukseklik + 4, T(baslik), fontName=FONT_B, fontSize=9, fillColor=LACIVERT))
            if len(noktalar) < 2:
                d.add(String(W / 2 - 50, yukseklik / 2, T("Yeterli veri yok"), fontName=FONT, fontSize=9, fillColor=GRI))
                return d
            lp = LinePlot()
            lp.x, lp.y, lp.width, lp.height = 44, 20, W - 54, yukseklik - 26
            lp.data = [[(i, float(v)) for i, v in enumerate(noktalar)]]
            lp.lines[0].strokeColor, lp.lines[0].strokeWidth = renk, 1.6
            n = len(noktalar)
            lp.xValueAxis.valueMin, lp.xValueAxis.valueMax = 0, n - 1
            lp.xValueAxis.valueSteps = sorted({int(round(i * (n - 1) / 5.0)) for i in range(6)})
            lp.xValueAxis.labelTextFormat = lambda v: T(etiketler[int(round(v))]) if 0 <= int(round(v)) < len(etiketler) else ""
            lp.xValueAxis.labels.fontName, lp.xValueAxis.labels.fontSize = FONT, 6.5
            lp.yValueAxis.labelTextFormat = lambda v: _rapor_sayi(v, 2)
            lp.yValueAxis.labels.fontName, lp.yValueAxis.labels.fontSize = FONT, 6.5
            lo, hi = min(noktalar), max(noktalar)
            pay = max((hi - lo) * 0.12, 0.5)
            lp.yValueAxis.valueMin, lp.yValueAxis.valueMax = lo - pay, hi + pay
            lp.yValueAxis.visibleGrid, lp.yValueAxis.gridStrokeColor = 1, colors.HexColor("#e1e6ee")
            d.add(lp)
            return d

        def halka(d, cx, cy, r_dis, r_ic, parcalar):
            """Halka grafik: parcalar = [(oran 0-1, renk)]. Tek dilim %100 ise iki yarım dilimle çizilir."""
            baslangic = 90.0
            for oran, renk in parcalar:
                if oran <= 0:
                    continue
                aci = 360.0 * oran
                bitis = baslangic - aci   # saat yönünde
                a1, a2 = (bitis, baslangic)
                if aci >= 359.9:
                    for (x1, x2) in ((a1, a1 + 180.0), (a1 + 180.0, a2)):
                        d.add(Wedge(cx, cy, r_dis, x1, x2, radius1=r_ic, fillColor=renk, strokeColor=None, strokeWidth=0))
                else:
                    d.add(Wedge(cx, cy, r_dis, a1, a2, radius1=r_ic, fillColor=renk, strokeColor=None, strokeWidth=0))
                baslangic = bitis

        def metrik_paneli(kdf):
            """Uygulamadaki koyu 'Strateji / Finansal Metrikler' paneli (halka grafik + iki sütun)."""
            h = 140
            d = Drawing(W, h)
            d.add(Rect(0, 0, W, h, rx=12, ry=12, fillColor=colors.HexColor("#070b14"), strokeColor=colors.HexColor("#1b2a40"), strokeWidth=0.8))
            if kdf is None or len(kdf) == 0:
                d.add(String(W / 2 - 60, h / 2, T("Kapanan işlem yok"), fontName=FONT, fontSize=10, fillColor=colors.HexColor("#91a0b8")))
                return d
            v = pd.to_numeric(kdf["Net_Kar_Zarar"], errors="coerce").fillna(0.0)
            karli, zararli = int((v >= 0).sum()), int((v < 0).sum())
            toplam = karli + zararli
            kazanc, kayip = float(v[v >= 0].sum()), float(abs(v[v < 0].sum()))
            net_fark = kazanc - kayip
            k_y, z_y = (karli / toplam * 100.0), (zararli / toplam * 100.0)
            parasal = (kazanc / (kazanc + kayip) * 100.0) if (kazanc + kayip) > 0 else 0.0
            cx, cy, r_dis, r_ic = 78, h / 2, 54, 30
            halka(d, cx, cy, r_dis, r_ic, [(karli / toplam, NEON_Y), (zararli / toplam, NEON_T)])
            import math as _m
            r_orta = (r_dis + r_ic) / 2.0
            baslangic_a = 90.0
            for oran_, yazi_, renk_ in ((karli / toplam, f"%{k_y:.1f}", colors.HexColor("#0b3d0b")), (zararli / toplam, f"%{z_y:.1f}", colors.white)):
                if oran_ <= 0:
                    continue
                orta_a = baslangic_a - 360.0 * oran_ / 2.0
                d.add(String(cx + r_orta * _m.cos(_m.radians(orta_a)), cy + r_orta * _m.sin(_m.radians(orta_a)) - 3, yazi_,
                             fontName=FONT_B, fontSize=8, fillColor=renk_, textAnchor="middle"))
                baslangic_a -= 360.0 * oran_
            x1, x2 = 160, W * 0.58
            ac_gri, beyaz = colors.HexColor("#91a0b8"), colors.HexColor("#e8eef8")
            d.add(String(x1, h - 22, T("Strateji Metrikleri"), fontName=FONT_B, fontSize=10, fillColor=beyaz))
            d.add(String(x1, h - 40, T("Toplam Kapanan"), fontName=FONT, fontSize=8, fillColor=ac_gri))
            d.add(String(x1, h - 57, f"{toplam} Adet", fontName=FONT_B, fontSize=14, fillColor=beyaz))
            d.add(Circle(x1 + 4, h - 76, 3.4, fillColor=NEON_Y, strokeColor=None))
            d.add(String(x1 + 12, h - 79, T(f"Kârlı: {karli} (%{k_y:.1f})"), fontName=FONT_B, fontSize=9, fillColor=NEON_Y))
            d.add(Circle(x1 + 4, h - 94, 3.4, fillColor=NEON_T, strokeColor=None))
            d.add(String(x1 + 12, h - 97, T(f"Zararlı: {zararli} (%{z_y:.1f})"), fontName=FONT_B, fontSize=9, fillColor=NEON_T))
            d.add(Line(x1, h - 108, x1 + (x2 - x1) - 24, h - 108, strokeColor=colors.HexColor("#25344d"), strokeWidth=0.6))
            d.add(String(x1, h - 124, T(f"Başarı Oranı: %{k_y:.1f}"), fontName=FONT_B, fontSize=9, fillColor=NEON_Y if k_y >= 50 else NEON_T))
            d.add(String(x2, h - 22, T("Finansal Metrikler"), fontName=FONT_B, fontSize=10, fillColor=beyaz))
            d.add(String(x2, h - 40, T("Net Fark"), fontName=FONT, fontSize=8, fillColor=ac_gri))
            d.add(String(x2, h - 57, T(f"{net_fark:+,.2f} $".replace(",", "X").replace(".", ",").replace("X", ".")), fontName=FONT_B, fontSize=14,
                         fillColor=NEON_Y if net_fark >= 0 else NEON_T))
            d.add(String(x2, h - 79, T(f"Toplam Kâr: {kazanc:+,.2f} $".replace(",", "X").replace(".", ",").replace("X", ".")), fontName=FONT_B, fontSize=9, fillColor=NEON_Y))
            d.add(String(x2, h - 97, T(f"Toplam Zarar: {-kayip:+,.2f} $".replace(",", "X").replace(".", ",").replace("X", ".")), fontName=FONT_B, fontSize=9, fillColor=NEON_T))
            d.add(Line(x2, h - 108, W - 18, h - 108, strokeColor=colors.HexColor("#25344d"), strokeWidth=0.6))
            d.add(String(x2, h - 124, T(f"Parasal Başarı Oranı: %{parasal:.1f}"), fontName=FONT_B, fontSize=9, fillColor=NEON_Y if parasal >= 50 else NEON_T))
            return d

        story = []
        story.append(Paragraph(T("Kripto Portföy Raporu"), st_ba))
        etiket = lambda x: f'<font name="{FONT_B}" color="#5f6b7a">{T(x)}</font>'
        ilk_str = ilk_acilis.strftime("%d.%m.%Y %H:%M") if ilk_acilis is not None else "-"
        sonu_renk = "#0a8f3c" if id_sonu_kasa >= id_baslangic_kasa else "#d9480f"
        story.append(Paragraph(f'{etiket("Başlangıç:")} <font name="{FONT_B}" color="#222222">{ilk_str} (TR)</font>  '
                               f'{etiket("Oluşturulma:")} <font name="{FONT_B}" color="#222222">{zaman.strftime("%d.%m.%Y %H:%M")} (TR)</font>', st_ust))
        story.append(Paragraph(f'{etiket("ID Başlangıç ve Bitiş :")} <font name="{FONT_B}" color="#222222">ID {id_min:02d}-{id_max:02d}</font>  '
                               f'{etiket("Toplam İşlem:")} <font name="{FONT_B}" color="#222222">{len(dt)}</font>  '
                               f'{etiket("Açık İşlem:")} <font name="{FONT_B}" color="#222222">{len(acik)}</font>  '
                               f'{etiket("Kapanan İşlem:")} <font name="{FONT_B}" color="#222222">{n_kap}</font>', st_ust))
        story.append(Paragraph(f'{T(f"Tüm tutarlar USDT · {KALDIRAC}x kaldıraç ·")} {etiket("Id Başlangıç Kasa :")} '
                               f'<font name="{FONT_B}" color="#222222">{_rapor_sayi(id_baslangic_kasa, 0 if abs(id_baslangic_kasa - round(id_baslangic_kasa)) < 0.005 else 2)} $</font>  '
                               f'{etiket("Id Sonu Kasa:")} <font name="{FONT_B}" color="{sonu_renk}">{_rapor_sayi(id_sonu_kasa, 0 if abs(id_sonu_kasa - round(id_sonu_kasa)) < 0.005 else 2)} $</font>', st_ust))
        story.append(Paragraph(T(f"Komisyon: giriş %{KOMISYON_TAKER*100:g}, hedef çıkışı %{KOMISYON_MAKER*100:g}, stop çıkışı %{KOMISYON_TAKER*100:g}"), st_ust))

        # ---------- 1) Kasa durumu
        story.append(Paragraph(T("1. Kasa Durumu"), st_h))
        def kpi(etiket_, deger, renk=colors.black):
            return [Paragraph(f'<font name="{FONT}" size="7" color="#5f6b7a">{T(etiket_)}</font>', st_n),
                    Paragraph(f'<font name="{FONT_B}" size="12" color="{hex_(renk)}">{T(deger)}</font>', st_n)]
        kz_r = lambda v: YESIL if v > 0 else (KIRMIZI if v < 0 else colors.black)
        ters = lambda txt: txt.replace(",", "X").replace(".", ",").replace("X", ".")
        hucreler = [
            kpi("Toplam kasa", f"{_rapor_sayi(toplam_kasa)} $"), kpi("Efektif kasa", f"{_rapor_sayi(efektif_kasa)} $"),
            kpi("Boş nakit", f"{_rapor_sayi(bos_bakiye)} $"), kpi("Kullanılan teminat", f"{_rapor_sayi(marjin)} $"),
            kpi("Anlık K/Z (net)", ters(f"{acik_kz:+,.2f} $"), kz_r(acik_kz)),
            kpi("Gerçekleşen net K/Z", ters(f"{gerceklesen:+,.2f} $"), kz_r(gerceklesen)),
            kpi("Anapara (başlangıç + net giriş)", f"{_rapor_sayi(anapara)} $"),
            kpi("Toplam getiri", ("-" if getiri < 0 else "") + f"%{_rapor_sayi(abs(getiri))}", kz_r(getiri)),
        ]
        grid = [[hucreler[i], hucreler[i + 1], hucreler[i + 2], hucreler[i + 3]] for i in (0, 4)]
        kt = Table(grid, colWidths=[W / 4.0] * 4)
        kt.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#c9d1dc")), ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dfe5ee")),
                                ("BACKGROUND", (0, 0), (-1, -1), ACIK), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
        story.append(kt)

        # ---------- Analiz
        story.append(Paragraph(T("Analiz"), st_h))
        en_iyi = kap.loc[net.idxmax()] if n_kap else None
        en_kotu = kap.loc[net.idxmin()] if n_kap else None
        long_m = kap["Yon"].astype(str).str.contains("Long") if n_kap else pd.Series([], dtype=bool)
        short_m = kap["Yon"].astype(str).str.contains("Short") if n_kap else pd.Series([], dtype=bool)
        long_n, short_n = int(long_m.sum()), int(short_m.sum())
        long_net, short_net = (float(net[long_m].sum()) if n_kap else 0.0), (float(net[short_m].sum()) if n_kap else 0.0)
        satirlar = [
            [T("Kapanan işlem"), str(n_kap), T("Açık işlem"), str(len(acik))],
            [T("Kazanan / Kaybeden"), f"{len(kaz)} / {len(kay)}", T("İsabet oranı"), f"%{_rapor_sayi(isabet, 1)}"],
            [T("Ortalama kâr"), _rapor_sayi(kaz.mean() if len(kaz) else 0) + " $", T("Ortalama zarar"), _rapor_sayi(kay.mean() if len(kay) else 0) + " $"],
            [T("Kâr faktörü"), (_rapor_sayi(pf) if pf is not None else "-"), T("İşlem başı beklenti"), _rapor_sayi(net.mean() if n_kap else 0) + " $"],
            [T("En iyi işlem"), (f"#{int(en_iyi['Islem_ID'])} {en_iyi['Coin']} {_rapor_sayi(en_iyi['Net_Kar_Zarar'])} $" if n_kap else "-"),
             T("En kötü işlem"), (f"#{int(en_kotu['Islem_ID'])} {en_kotu['Coin']} {_rapor_sayi(en_kotu['Net_Kar_Zarar'])} $" if n_kap else "-")],
            [T("Long (adet / net K/Z)"), f"{long_n} / {_rapor_sayi(long_net)} $", T("Short (adet / net K/Z)"), f"{short_n} / {_rapor_sayi(short_net)} $"],
        ]
        an_t = Table(satirlar, colWidths=[W * 0.22, W * 0.28, W * 0.22, W * 0.28])
        an_t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FONT), ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                                  ("FONTNAME", (0, 0), (0, -1), FONT_B), ("FONTNAME", (2, 0), (2, -1), FONT_B),
                                  ("TEXTCOLOR", (0, 0), (0, -1), GRI), ("TEXTCOLOR", (2, 0), (2, -1), GRI),
                                  ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, ACIK]), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                                  ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#c9d1dc"))]))
        story.append(an_t)

        if n_kap:
            cg = kap.groupby("Coin")["Net_Kar_Zarar"].agg(["count", lambda x: int((x > 0).sum()), lambda x: int((x <= 0).sum()), "sum", lambda x: (x > 0).mean() * 100.0])
            cg.columns = ["adet", "karli", "zararli", "net", "isabet"]
            cg = cg.sort_values("net", ascending=False)
            if len(cg) > 10:
                diger = cg.iloc[10:]
                cg = cg.iloc[:10]
                cg.loc[f"Diğer ({len(diger)})"] = [int(diger["adet"].sum()), int(diger["karli"].sum()), int(diger["zararli"].sum()),
                                                    float(diger["net"].sum()), float((diger["karli"].sum() / max(diger["adet"].sum(), 1)) * 100.0)]
            ct = Table([[T("Coin"), T("İşlem Sayısı"), T("Karlı Kapanan"), T("Zararlı Kapanan"), T("Net K/Z ($)"), T("İsabet")]] +
                       [[c, str(int(r["adet"])), str(int(r["karli"])), str(int(r["zararli"])), _rapor_sayi(r["net"]), f"%{_rapor_sayi(r['isabet'], 1)}"] for c, r in cg.iterrows()],
                       colWidths=[W * 0.16, W * 0.17, W * 0.17, W * 0.18, W * 0.18, W * 0.14], repeatRows=1)
            ct.setStyle(tablo_stili()); ct.setStyle(TableStyle([("ALIGN", (1, 0), (-1, -1), "CENTER")]))
            story.append(Spacer(1, 6)); story.append(ct)

        # ---------- Metrik panelleri (uygulamadaki koyu paneller)
        story.append(Paragraph(T(f"ID Başlangıç ve Bitiş : ID {id_min:02d}-{id_max:02d} Arası Metrikler"), st_pb))
        story.append(metrik_paneli(kap))
        story.append(Paragraph(T("Başlangıçtan Son İşleme Kapanan Metrikler"), st_pb))
        story.append(metrik_paneli(kap))


        def sayfa_alt(canvas, doc):
            canvas.saveState()
            canvas.setFont(FONT, 7)
            canvas.setFillColor(GRI)
            canvas.drawString(12 * mm, 8 * mm, T(f"Pro Kripto Paneli · {zaman.strftime('%d.%m.%Y %H:%M')}"))
            canvas.drawRightString(A4[0] - 12 * mm, 8 * mm, T(f"Sayfa {doc.page}"))
            canvas.restoreState()

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=14 * mm,
                                title=T("Kripto Portföy Raporu"), author="Pro Kripto Paneli")
        doc.build([KeepInFrame(W, A4[1] - 26 * mm - 4, story, mode="shrink")], onFirstPage=sayfa_alt, onLaterPages=sayfa_alt)
        return buf.getvalue(), None
    except Exception as e:
        import traceback
        return None, f"{type(e).__name__}: {e} | {traceback.format_exc().splitlines()[-3][:120]}"

def _secret_bul(anahtar):
    """Anahtarı sırayla ortam değişkeninde, secrets'ın en üstünde ve secrets bölümlerinin içinde arar.
    (TOML'da [bölüm] başlığından sonra yazılan anahtarlar o bölüme aittir.)"""
    deger = os.environ.get(anahtar, "").strip()
    if deger:
        return deger
    try:
        if anahtar in st.secrets:
            return str(st.secrets[anahtar]).strip()
        for ad in list(st.secrets.keys()):
            try:
                bolum = st.secrets[ad]
                if hasattr(bolum, "keys") and anahtar in bolum:
                    return str(bolum[anahtar]).strip()
            except Exception:
                continue
    except Exception:
        pass
    return ""

def _gmail_sifresi_bul():
    return _secret_bul("GMAIL_PASSWORD")

def rapor_maili_gonder(pdf_bytes, dosya_adi, bakiye, zaman):
    gonderici_mail = _secret_bul("GONDERICI_MAIL") or "erhanvancin@gmail.com"
    alici_mail = _secret_bul("ALICI_MAIL") or gonderici_mail
    sifre = _gmail_sifresi_bul().replace(" ", "")   # Google uygulama şifresini "abcd efgh ..." diye gösterir
    if not sifre:
        return False, "GMAIL_PASSWORD bulunamadı (Streamlit secrets'ın EN ÜSTÜNE, herhangi bir [bölüm] başlığından önce ekleyin)."
    toplam_kasa, efektif_kasa, bos_bakiye, marjin, acik_kz = [float(x) for x in bakiye]
    govde = (f"<h3>Kripto Portföy Raporu</h3><p>Oluşturulma: {zaman.strftime('%d.%m.%Y %H:%M')}</p>"
             f"<p><b>Toplam kasa:</b> {toplam_kasa:,.2f} $<br><b>Efektif kasa:</b> {efektif_kasa:,.2f} $<br>"
             f"<b>Anlık K/Z (net):</b> {acik_kz:+,.2f} $<br><b>Boş nakit:</b> {bos_bakiye:,.2f} $</p>"
             "<p>Rapor ekteki tek sayfalık A4 PDF dosyasındadır.</p>")
    msg = MIMEMultipart()
    msg["From"], msg["To"], msg["Subject"] = gonderici_mail, alici_mail, f"📄 Portföy Raporu - {zaman.strftime('%d.%m.%Y %H:%M')}"
    msg.attach(MIMEText(govde, "html", "utf-8"))
    ek = MIMEApplication(pdf_bytes, _subtype="pdf")
    ek.add_header("Content-Disposition", "attachment", filename=dosya_adi)
    msg.attach(ek)
    govde_metni = msg.as_string()

    hatalar = []
    for yontem, port in (("SSL", 465), ("STARTTLS", 587)):
        server = None
        try:
            if yontem == "SSL":
                server = smtplib.SMTP_SSL("smtp.gmail.com", port, timeout=30)
            else:
                server = smtplib.SMTP("smtp.gmail.com", port, timeout=30)
                server.ehlo()
                server.starttls()
                server.ehlo()
            server.login(gonderici_mail, sifre)
            server.sendmail(gonderici_mail, [alici_mail], govde_metni)
            return True, f"E-posta gönderildi ({yontem}/{port})."
        except smtplib.SMTPAuthenticationError:
            return False, ("Gmail girişi reddedildi (535). Normal hesap şifresi kabul edilmez: Google hesabında 2 adımlı doğrulamayı açıp "
                           "'Uygulama şifresi' oluşturun ve onu GMAIL_PASSWORD olarak girin.")
        except Exception as e:
            hatalar.append(f"{port}: {type(e).__name__}: {str(e)[:100]}")
        finally:
            if server is not None:
                try:
                    server.quit()
                except Exception:
                    pass
    return False, "Gmail'e bağlanılamadı (" + " | ".join(hatalar) + ")"

def rapor_telegram_gonder(pdf_bytes, dosya_adi, bakiye, zaman):
    """Mail gönderilemezse yedek kanal: PDF'i Telegram'a belge olarak yollar (secrets'ta TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID gerekir)."""
    token, chat_id = _secret_bul("TELEGRAM_BOT_TOKEN"), _secret_bul("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False, "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID secrets'ta yok"
    toplam_kasa, efektif_kasa, bos_bakiye, marjin, acik_kz = [float(x) for x in bakiye]
    aciklama = (f"📄 Portföy Raporu {zaman.strftime('%d.%m.%Y %H:%M')}\nToplam kasa: {toplam_kasa:,.2f} $ · Efektif: {efektif_kasa:,.2f} $ · "
                f"Anlık K/Z: {acik_kz:+,.2f} $")
    try:
        yanit = requests.post(f"https://api.telegram.org/bot{token}/sendDocument", data={"chat_id": chat_id, "caption": aciklama},
                              files={"document": (dosya_adi, pdf_bytes, "application/pdf")}, timeout=40)
        if yanit.status_code == 200 and yanit.json().get("ok"):
            return True, "Telegram'a gönderildi."
        return False, f"Telegram yanıtı: {yanit.status_code} {yanit.text[:100]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:100]}"

def matris_birlesik_html(nihai_puan, aktif_yon, y_yuzde, k_yuzde):
    """Matris puanı + teyit tek sütunda: yön adı (Long/Short, nötr bölgede de eğilimli yön) ve yönün rengiyle puan,
    altında Short|Long dengesini gösteren çubuk (nokta Long % konumunda)."""
    renk = RENK_YESIL if aktif_yon == "Long" else RENK_KIRMIZI
    t = max(0.0, min(100.0, float(y_yuzde)))
    return ('<div class="mx-wrap">'
            f'<div class="mx-puan" style="color:{renk}">{nihai_puan:.1f} / 100<span class="mx-yon"> ({aktif_yon})</span></div>'
            f'<div class="mx-bar"><div class="mx-dot" style="left:{t:.1f}%"></div></div>'
            f'<div class="mx-lbl"><span style="color:{RENK_KIRMIZI}">%{k_yuzde:.1f}</span><span style="color:{RENK_YESIL}">%{y_yuzde:.1f}</span></div></div>')

def pozisyon_karti_html(row, anl_f, logo_url, toplam_kasa):
    coin, yon = str(row["Coin"]), str(row["Yon"])
    long_mi = "Long" in yon
    giris, stop, hedef, miktar = float(row["Giris_Fiyat"]), float(row["Stop"]), float(row["Kar_Al"]), float(row["Islem_Miktari"])
    if giris <= 0 or anl_f is None:
        return ""
    fark = ((anl_f - giris) / giris) if long_mi else ((giris - anl_f) / giris)
    kz = miktar * KALDIRAC * fark - cikis_komisyonu(miktar, False)   # net: kapanışta ödenecek komisyon düşülmüş
    kz_yuzde = (kz / miktar * 100.0) if miktar > 0 else 0.0
    kz_renk = RENK_YESIL if kz >= 0 else RENK_KIRMIZI

    aralik = hedef - stop
    t_anlik = min(1.0, max(0.0, (anl_f - stop) / aralik)) if aralik else 0.5
    t_giris = min(1.0, max(0.0, (giris - stop) / aralik)) if aralik else 0.5
    stopa = abs(anl_f - stop) / anl_f * 100.0
    hedefe = abs(hedef - anl_f) / anl_f * 100.0

    islem_risk = stop_riski(miktar, giris, stop)
    islem_limit = max(0.0, float(toplam_kasa)) * ISLEM_BASINA_RISK_YUZDE / 100.0
    r_oran = (islem_risk / islem_limit) if islem_limit > 0 else 0.0
    r_renk = _risk_rengi(r_oran)

    pill = f'<span class="pill {"pill-long" if long_mi else "pill-short"}">{yon}</span>'
    logo = f'<img src="{logo_url}" class="pos-logo">' if logo_url else ""
    detay = (f'<details class="pos-detay"><summary>Detay</summary><div class="pos-detay-ic">'
             f'<div>Açılış: {row["Acilis_Zamani"]}</div><div>Matris: {row.get("Matris_Puan_RH", "-")}</div>'
             f'<div>Risk: <b style="color:{r_renk}">{islem_risk:,.2f} / {islem_limit:,.2f} $</b></div>'
             f'<div class="bar-bg bar-mini"><div class="bar-fill" style="width:{max(2.0, min(100.0, r_oran * 100.0)):.1f}%;background:{r_renk}"></div></div>'
             f'<div>Güncel kasa kaydı: {float(row["Guncel_Kasa"]):,.2f} $</div></div></details>')
    return ('<div class="pos-card">'
            f'<div class="pos-head"><div class="pos-left">{logo}<div><div class="pos-name">{coin}</div><div class="pos-sub">{pill}<span class="pos-id">#{int(row["Islem_ID"])}</span></div></div></div>'
            f'<div class="pos-kz" style="color:{kz_renk}">{kz:+,.2f} $<small>{kz_yuzde:+.1f}% net</small></div></div>'
            '<div class="range-wrap"><div class="range-bar">'
            f'<div class="range-tick" style="left:{t_giris*100:.1f}%"></div><div class="range-dot" style="left:{t_anlik*100:.1f}%"></div></div>'
            f'<div class="range-lbl"><span style="color:{RENK_KIRMIZI}">Stop {_fmt_fiyat(stop)}</span><span style="color:{RENK_YESIL}">Hedef {_fmt_fiyat(hedef)}</span></div>'
            f'<div class="range-dist"><span>Stopa %{stopa:.2f}</span><span class="range-mid">{_fmt_fiyat(anl_f)}</span><span>Hedefe %{hedefe:.2f}</span></div></div>'
            f'<div class="pos-meta"><span>Giriş <b>{_fmt_fiyat(giris)}</b></span><span>Teminat <b>{miktar:,.2f} $</b></span></div>'
            f'<div class="pos-meta"><span>Beklenen kâr <b style="color:{RENK_YESIL}">{canli_beklenen_olasi(row)[0]:+,.2f} $</b></span>'
            f'<span>Olası stop <b style="color:{RENK_KIRMIZI}">{canli_beklenen_olasi(row)[1]:+,.2f} $</b></span></div>'
            f'{detay}</div>')

_TR_ASCII = str.maketrans({
    "ı": "i", "İ": "i", "I": "i", "â": "a", "Â": "a", "î": "i", "Î": "i", "û": "u", "Û": "u",
    "ö": "o", "Ö": "o", "ü": "u", "Ü": "u", "ş": "s", "Ş": "s", "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g",
})


def durum_kapali_mi(durum):
    t = str(durum).translate(_TR_ASCII).lower()
    return any(k in t for k in ("kapandi", "kar", "zarar", "kismi"))


def durum_kapali_maskesi(seri):
    return seri.map(durum_kapali_mi).astype(bool)


TR_TZ = pytz.timezone("Europe/Istanbul")
HAFIZA_DOSYASI = "sinyal_hafizasi.json"
MAIL_LOG_DOSYASI = "mail_log.txt"
MAIL_PANELDEN_GONDER = False

def tr_zaman():
    return datetime.now(TR_TZ)

def hafta_sonu_mu():
    simdi = tr_zaman()
    haftanin_gunu = simdi.weekday()
    saat = simdi.hour
    if (haftanin_gunu == 4 and saat >= 23) or (haftanin_gunu in [5, 6]) or (haftanin_gunu == 0 and saat < 3):
        return True
    return False

def aktif_min_puan_esigi_getir():
    return 60.0 if hafta_sonu_mu() else 55.0

def hafizayi_oku():
    if os.path.exists(HAFIZA_DOSYASI):
        try:
            with open(HAFIZA_DOSYASI, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def hafizayi_kaydet(hafiza):
    try:
        with open(HAFIZA_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(hafiza, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Hafıza kayıt hatası: {e}")

coinler = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"]
logo_urls = {
    "BTC/USDT": "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/btc.png",
    "ETH/USDT": "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/eth.png",
    "BNB/USDT": "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/bnb.png",
    "SOL/USDT": "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/sol.png",
    "XRP/USDT": "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/xrp.png",
    "TOTAL": "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/usdt.png",
}
baz_fiyatlar = {
    "BTC/USDT": 83750.0,
    "ETH/USDT": 2511.0,
    "BNB/USDT": 745.0,
    "SOL/USDT": 107.6,
    "XRP/USDT": 1.373,
    "TOTAL": 2.77e12,
}

def mail_log_yaz(mesaj):
    try:
        zamanli_mesaj = f"[{tr_zaman().strftime('%d.%m.%Y %H:%M:%S')}] {mesaj}\n"
        with open(MAIL_LOG_DOSYASI, "a", encoding="utf-8") as f:
            f.write(zamanli_mesaj)
    except:
        pass

def gmail_bildirim_gonder(konu, icerik_html):
    if not MAIL_PANELDEN_GONDER:
        return False, "Panelden mail kapalı: mailleri GitHub (check_engine.py) gönderiyor."
    gonderici_mail = "erhanvancin@gmail.com"
    uygulama_sifresi = os.environ.get("GMAIL_PASSWORD", "").strip()
    alici_mail = "erhanvancin@gmail.com"
    
    if not uygulama_sifresi:
        hata = "GMAIL_PASSWORD tanımlı değil."
        return False, hata

    server = None
    try:
        msg = MIMEMultipart()
        msg["From"] = gonderici_mail
        msg["To"] = alici_mail
        msg["Subject"] = konu
        msg.attach(MIMEText(icerik_html, "html", "utf-8"))

        server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15)
        server.login(gonderici_mail, uygulama_sifresi)
        server.sendmail(gonderici_mail, [alici_mail], msg.as_string())
        return True, "E-posta başarıyla gönderildi."
    except Exception as e:
        return False, str(e)
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass

# --- BİNANCE API ENTEGRASYONU ---
@st.cache_data(ttl=30)
def fiyat_cek_binance(coin_symbol):
    if coin_symbol == "TOTAL":
        try:
            btc = fiyat_cek_binance("BTC/USDT")
            eth = fiyat_cek_binance("ETH/USDT")
            bnb = fiyat_cek_binance("BNB/USDT")
            sol = fiyat_cek_binance("SOL/USDT")
            xrp = fiyat_cek_binance("XRP/USDT")
            
            tahmini_total = (
                (btc * 19700000)
                + (eth * 120000000)
                + (bnb * 145000000)
                + (sol * 470000000)
                + (xrp * 5700000000)
            )
            if tahmini_total > 0:
                return float(tahmini_total)
        except:
            pass
        return baz_fiyatlar["TOTAL"]

    sym = coin_symbol.replace("/", "")
    endpoints = [
        f"https://data-api.binance.vision/api/v3/ticker/price?symbol={sym}",
        f"https://api.binance.com/api/v3/ticker/price?symbol={sym}",
    ]
    for ep in endpoints:
        try:
            r = requests.get(ep, timeout=3)
            if r.status_code == 200:
                val = float(r.json()["price"])
                if val > 0:
                    return val
        except:
            continue
    return baz_fiyatlar.get(coin_symbol, 100.0)

@st.cache_data(ttl=30)
def kline_cek_binance(coin_symbol, interval, limit):
    sym = coin_symbol.replace("/", "")
    endpoints = [
        f"https://data-api.binance.vision/api/v3/klines?symbol={sym}&interval={interval}&limit={limit}",
        f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={interval}&limit={limit}",
    ]
    for ep in endpoints:
        try:
            r = requests.get(ep, timeout=5)
            if r.status_code == 200:
                data = r.json()
                df = pd.DataFrame(
                    data,
                    columns=[
                        "timestamp", "Open", "High", "Low", "Close", "Volume",
                        "Close_Time", "QAV", "Num_Trades", "Taker_BBAV", "Taker_BQAV", "Ignore"
                    ],
                )
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.tz_convert(TR_TZ)
                for col in ["Open", "High", "Low", "Close"]:
                    df[col] = df[col].astype(float)
                return df[["timestamp", "Open", "High", "Low", "Close"]]
        except:
            continue
    return pd.DataFrame()

@st.cache_data(ttl=30)
def load_15min_market_data(coin_symbol: str):
    limit = 192
    if coin_symbol == "TOTAL":
        anlik_total = fiyat_cek_binance("TOTAL")
        df_btc = kline_cek_binance("BTC/USDT", "5m", limit)
        if not df_btc.empty:
            current_btc = float(df_btc["Close"].iloc[-1])
            if current_btc > 0:
                carpan = anlik_total / current_btc
                df_btc["Open"] = df_btc["Open"] * carpan
                df_btc["High"] = df_btc["High"] * carpan
                df_btc["Low"] = df_btc["Low"] * carpan
                df_btc["Close"] = df_btc["Close"] * carpan
        return df_btc

    if coin_symbol != "TOTAL":
        df = kline_cek_binance(coin_symbol, "5m", limit)
        if not df.empty:
            return df

    dates = pd.date_range(end=datetime.now(TR_TZ), periods=limit, freq="5min")
    base_p = baz_fiyatlar.get(coin_symbol, 2.77e12 if coin_symbol == "TOTAL" else 100.0)
    return pd.DataFrame({
        "timestamp": dates,
        "Open": [base_p] * limit,
        "High": [base_p] * limit,
        "Low": [base_p] * limit,
        "Close": [base_p] * limit,
    })

# --- LOGARİTMİK RİSK / HEDEF HESAPLAMA MİMARİSİ ---
def calculate_coin_metrics_by_score(matris_puani):
    hsonu = hafta_sonu_mu()
    min_esik = 60.0 if hsonu else 55.0

    if matris_puani < min_esik:
        return 0.70, 1.0, "Nötr"

    x_puanlar = np.array([55.0, 59.0, 63.0, 67.0, 71.0, 75.0])
    y_risk = np.array([0.70, 0.66, 0.62, 0.58, 0.54, 0.50])
    risk_katsayilar = np.polyfit(np.log(x_puanlar), y_risk, 1)

    y_hedef = np.array([0.70, 0.84, 1.00, 1.17, 1.35, 1.50])
    hedef_katsayilar = np.polyfit(np.log(x_puanlar), y_hedef, 1)

    puan = max(min_esik, min(100.0, matris_puani))

    stop_uzde = risk_katsayilar[0] * np.log(puan) + risk_katsayilar[1]
    hedef_uzde = hedef_katsayilar[0] * np.log(puan) + hedef_katsayilar[1]

    stop_uzde = max(0.40, min(0.70, stop_uzde))
    hedef_uzde = max(0.60, min(2.50, hedef_uzde))

    hedef_carpan = hedef_uzde / stop_uzde if stop_uzde > 0 else 1.5

    str_stop = f"{stop_uzde:.2f}".replace(".", ",")
    str_hedef = f"{hedef_uzde:.2f}".replace(".", ",")
    risk_hedef_metin = f"{str_stop} / {str_hedef}"

    return stop_uzde, hedef_carpan, risk_hedef_metin

# --- MATRİS (hesap matris_motoru.py içinde; GitHub motoru da aynı dosyayı kullanır) ---
def kurgusal_matris_hesapla(coin_symbol):
    anlik_fiyat = fiyat_cek_binance(coin_symbol)
    sembol_istek = coin_symbol if coin_symbol != "TOTAL" else "BTC/USDT"

    pencereler = [(etiket, kline_cek_binance(sembol_istek, aralik, mum_sayisi), agirlik)
                  for etiket, aralik, mum_sayisi, agirlik in matris_motoru.DILIMLER]
    sonuc = matris_motoru.matris_hesapla(pencereler)

    zaman_katkilari = {
        etiket: {"sl": k["sl"], "ss": k["ss"], "y_adet": k["y_adet"], "k_adet": k["k_adet"]}
        for etiket, k in sonuc["katkilar"].items()
    }
    nihai_long, nihai_short = sonuc["nihai_long"], sonuc["nihai_short"]
    min_esik_degeri = aktif_min_puan_esigi_getir()

    if nihai_long >= min_esik_degeri:
        nihai_puan = nihai_long
        aktif_yon = "Long"
    elif nihai_short >= min_esik_degeri:
        nihai_puan = nihai_short
        aktif_yon = "Short"
    else:
        nihai_puan = round(max(nihai_long, nihai_short), 2)
        aktif_yon = "Long" if nihai_long >= nihai_short else "Short"

    return anlik_fiyat, nihai_puan, aktif_yon, nihai_long, nihai_short, zaman_katkilari

# ====================== GOOGLE SHEETS GÜVENLİ BAĞLANTI MİMARİSİ ======================

# @st.cache_resource(ttl=3600) <-- Bu dekoratör token düşmelerinde 404 RefreshError'a sebep olduğu için kaldırıldı!
def _sayfa_nesnesi(sayfa_adi):
    """Hata verirse istisna fırlatır; Streamlit hatalı sonucu önbelleğe ALMAZ."""
    if "gcp_service_account" in st.secrets:
        sec_dict = dict(st.secrets["gcp_service_account"])
        sec_dict.pop("GMAIL_PASSWORD", None)   # [bölüm] içine düşmüş mail şifresi servis hesabı bilgisine karışmasın
        if "private_key" in sec_dict:
            sec_dict["private_key"] = sec_dict["private_key"].replace(r"\n", "\n")
        client = gspread.service_account_from_dict(sec_dict)
    else:
        client = gspread.service_account(filename="credentials.json")
    return client.open(GOOGLE_SHEET_DOSYA).worksheet(sayfa_adi)

_SON_SHEETS_HATASI = {"mesaj": ""}

def google_sheets_baglan(sayfa_adi):
    try:
        # Her çağırmada canlı kontrol sağlamak için cache mekanizması bypass edildi veya yenileniyor
        return _sayfa_nesnesi(sayfa_adi)
    except Exception as e:
        _SON_SHEETS_HATASI["mesaj"] = f"{type(e).__name__}: {str(e)[:160]}"
        print(f"Sheets bağlantı hatası ({sayfa_adi}): {_SON_SHEETS_HATASI['mesaj']}")
        # Bağlantı çöktüğünde Streamlit kaynak önbelleğini tamamen temizle
        try:
            st.cache_resource.clear()
            st.cache_data.clear()
        except:
            pass
        return None


@st.cache_data(ttl=15)
def islem_gecmisi_getir(sheet_guncelle=True):
    beklenen_kolonlar = [
        "Islem_ID", "Acilis_Zamani", "Coin", "Yon", "Zaman_Dilimi",
        "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Beklenen_Kar",
        "Matris_Puan_RH", "Olasi_Stop", "Durum", "Net_Kar_Zarar",
        "Guncel_Kasa", "Kapanis_Zamani", "Kapanis_Fiyati"
    ]
    sheet = google_sheets_baglan("KriptoPortfoyVeritabani")
    if sheet is None:
        return pd.DataFrame(columns=beklenen_kolonlar)
    try:
        ham_veriler = sheet.get_all_values()
    except Exception:
        return pd.DataFrame(columns=beklenen_kolonlar)

    if not ham_veriler or len(ham_veriler) == 0:
        if sheet_guncelle:
            try:
                sheet.append_row(beklenen_kolonlar)
            except:
                pass
        return pd.DataFrame(columns=beklenen_kolonlar)

    satirlar = ham_veriler[1:] if len(ham_veriler) > 1 else []
    duzeltilmis_satirlar = []
    for satir in satirlar:
        if len(satir) < len(beklenen_kolonlar):
            satir.extend([""] * (len(beklenen_kolonlar) - len(satir)))
        elif len(satir) > len(beklenen_kolonlar):
            satir = satir[: len(beklenen_kolonlar)]
        duzeltilmis_satirlar.append(satir)

    df = pd.DataFrame(duzeltilmis_satirlar, columns=beklenen_kolonlar)
    if not df.empty and "Islem_ID" in df.columns:
        df = df[
            df["Islem_ID"].notna()
            & (df["Islem_ID"] != "")
            & (df["Islem_ID"].astype(str) != "Islem_ID")
        ]
    df["Islem_ID"] = pd.to_numeric(df["Islem_ID"], errors="coerce").fillna(0).astype(int)
    df = df.drop_duplicates(subset=["Islem_ID"], keep="last").sort_values(by="Islem_ID").reset_index(drop=True)
    
    # Sağlamlaştırılmış Sayısal Kolon Dönüştürücü (Avrupa tipi 81.690,44 format desteği)
    sayisal_kolonlar = [
        "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Beklenen_Kar",
        "Olasi_Stop", "Net_Kar_Zarar", "Guncel_Kasa", "Kapanis_Fiyati"
    ]
    for col in sayisal_kolonlar:
        if col in df.columns:
            temiz_seri = (
                df[col]
                .astype(str)
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False)
                .str.strip()
            )
            df[col] = pd.to_numeric(temiz_seri, errors="coerce").fillna(0.0).astype(float)
    return df

def dataframe_guncelle_gsheets(df):
    """Başarılıysa True döner. Önce yeni veriyi yazar, sonra artan eski satırları siler.
    (Önce silip sonra yazmak, yazma yarıda kalırsa tabloyu boş bırakabilirdi.)"""
    sheet = google_sheets_baglan("KriptoPortfoyVeritabani")
    basarili = False
    if sheet is not None:
        try:
            df = df.copy()
            df["Islem_ID"] = df["Islem_ID"].astype(int)
            df = df.sort_values(by="Islem_ID").reset_index(drop=True)
            veri_listesi = [df.columns.tolist()] + df.values.tolist()
            eski_satir_sayisi = len(sheet.get_all_values())
            sheet.update(veri_listesi)
            if eski_satir_sayisi > len(veri_listesi):
                sheet.batch_clear([f"A{len(veri_listesi) + 1}:Z{eski_satir_sayisi}"])
            basarili = True
        except Exception as e:
            print(f"GSheets Güncelleme Hatası: {e}")
    st.cache_data.clear()
    return basarili

@st.cache_data(ttl=15)
def kasa_defteri_getir():
    kolonlar = ["Islem_ID", "Zaman", "Islem_Turu", "Tutar", "Aciklama"]
    sheet = google_sheets_baglan("KasaDefteri")
    if sheet is None:
        return pd.DataFrame(columns=kolonlar)
    try:
        ham = sheet.get_all_values()
    except:
        return pd.DataFrame(columns=kolonlar)

    if not ham or len(ham) == 0:
        try:
            sheet.append_row(kolonlar)
        except:
            pass
        return pd.DataFrame(columns=kolonlar)

    satirlar = ham[1:] if len(ham) > 1 else []
    duz_satirlar = []
    for s in satirlar:
        if len(s) < len(kolonlar):
            s.extend([""] * (len(kolonlar) - len(s)))
        elif len(s) > len(kolonlar):
            s = s[: len(kolonlar)]
        duz_satirlar.append(s)

    df = pd.DataFrame(duz_satirlar, columns=kolonlar)
    if not df.empty and "Islem_ID" in df.columns:
        df = df[
            df["Islem_ID"].notna()
            & (df["Islem_ID"] != "")
            & (df["Islem_ID"].astype(str) != "Islem_ID")
        ]
    df["Islem_ID"] = pd.to_numeric(df["Islem_ID"], errors="coerce").fillna(0).astype(int)
    
    temiz_tutar = (
        df["Tutar"]
        .astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip()
    )
    df["Tutar"] = pd.to_numeric(temiz_tutar, errors="coerce").fillna(0.0).astype(float)
    return df

def kasa_defteri_guncelle_gsheets(df):
    sheet = google_sheets_baglan("KasaDefteri")
    if sheet is not None:
        try:
            df["Islem_ID"] = df["Islem_ID"].astype(int)
            df = df.sort_values(by="Islem_ID").reset_index(drop=True)
            veri_listesi = [df.columns.tolist()] + df.values.tolist()
            sheet.clear()
            sheet.update(veri_listesi)
        except Exception as e:
            print(f"Kasa Defteri Güncelleme Hatası: {e}")
    st.cache_data.clear()

def _defter_id_oku(deger):
    try:
        return int(float(str(deger).replace(".", "").replace(",", ".")))
    except Exception:
        return None

_SON_DEFTER_HATASI = {"mesaj": ""}

def _deftere_satir_ekle(islem_turu, net_tutar, aciklama):
    """KasaDefteri'ne yalnızca satır EKLER (silip baştan yazmaz; motorla aynı anda yazsa bile satır kaybolmaz)."""
    _SON_DEFTER_HATASI["mesaj"] = ""
    for deneme in range(1, 4):
        sheet = google_sheets_baglan("KasaDefteri")
        if sheet is not None:
            try:
                ham = sheet.get_all_values()
                if not ham:
                    sheet.append_row(["Islem_ID", "Zaman", "Islem_Turu", "Tutar", "Aciklama"])
                    ham = [["Islem_ID"]]
                idler = [i for i in (_defter_id_oku(r[0]) for r in ham[1:] if r) if i is not None]
                yeni_id = (max(idler) if idler else 0) + 1
                sheet.append_row([yeni_id, tr_zaman().strftime("%d.%m.%Y %H:%M"), islem_turu, round(float(net_tutar), 4), aciklama])
                st.cache_data.clear()
                return True
            except Exception as e:
                _SON_DEFTER_HATASI["mesaj"] = f"{type(e).__name__}: {str(e)[:160]}"
                print(f"Kasa defteri kayıt hatası (deneme {deneme}/3): {_SON_DEFTER_HATASI['mesaj']}")
                try:
                    _sayfa_nesnesi.clear()      # bayat bağlantı olabilir: bir sonraki denemede yeniden bağlan
                except Exception:
                    pass
        else:
            _SON_DEFTER_HATASI["mesaj"] = _SON_SHEETS_HATASI["mesaj"] or "Google Sheets'e bağlanılamadı"
        if deneme < 3:
            time.sleep(2 * deneme)
    st.cache_data.clear()
    return False

def kasa_islem_ekle(islem_turu, tutar, aciklama):
    islem_carpan = 1.0 if islem_turu == "Para_Yatir" else -1.0
    net_tutar = float(tutar) * islem_carpan
    if _deftere_satir_ekle(islem_turu, net_tutar, aciklama):
        return True, f"Kasa işlemi başarılı: {islem_turu} -> {net_tutar:.2f} $"
    detay = _SON_DEFTER_HATASI["mesaj"] or "bilinmeyen hata"
    return False, f"⚠️ Kasa defterine yazılamadı! İşlem kaydedilmedi, lütfen tekrar deneyin. Ayrıntı: {detay}"

def kasa_islem_ekle_deftere(islem_turu, tutar, aciklama):
    return _deftere_satir_ekle(islem_turu, tutar, aciklama)

KAPANIS_ETIKETLERI = ("Hedef Kâr", "Otomatik Stop", "Trade K/Z")

def kapanis_defterde_var(islem_id):
    """Aynı işlemin tam kapanışı deftere daha önce yazıldı mı? (panel ve motor çift işlemesin)"""
    sheet = google_sheets_baglan("KasaDefteri")
    if sheet is None:
        return False
    try:
        for r in sheet.get_all_values()[1:]:
            if len(r) >= 5 and r[2] == "Trade_Sonuc":
                if any(str(r[4]).startswith(f"{e}: #{islem_id} ") for e in KAPANIS_ETIKETLERI):
                    return True
    except Exception as e:
        print(f"Kapanış kontrolü okunamadı: {e}")
    return False

def kapanis_deftere_yaz_tekil(islem_id, etiket, coin, tutar, sonuc_metin):
    if kapanis_defterde_var(islem_id):
        print(f"#{islem_id} kapanışı defterde zaten var, tekrar yazılmadı.")
        return True
    return kasa_islem_ekle_deftere("Trade_Sonuc", float(round(tutar, 2)), f"{etiket}: #{islem_id} {coin} ({sonuc_metin})")

def bakiye_durumunu_getir(ortak_fiyat_havuzu={}):
    df_trade = islem_gecmisi_getir(sheet_guncelle=False)
    df_kasa = kasa_defteri_getir()
    net_kasa_hareketleri = BASLANGIC_BAKIYE

    if not df_kasa.empty:
        net_kasa_hareketleri += pd.to_numeric(df_kasa["Tutar"], errors="coerce").fillna(0.0).sum()

    if not df_trade.empty:
        kap_trades = df_trade[durum_kapali_maskesi(df_trade["Durum"])]
        if not kap_trades.empty:
            trade_sonuc_defterde = 0.0
            if not df_kasa.empty and "Islem_Turu" in df_kasa.columns:
                ts_df = df_kasa[df_kasa["Islem_Turu"] == "Trade_Sonuc"]
                if not ts_df.empty:
                    trade_sonuc_defterde = pd.to_numeric(ts_df["Tutar"], errors="coerce").fillna(0.0).sum()
            gercek_trade_toplam = pd.to_numeric(kap_trades["Net_Kar_Zarar"], errors="coerce").fillna(0.0).sum()
            if gercek_trade_toplam != trade_sonuc_defterde:
                net_kasa_hareketleri += gercek_trade_toplam - trade_sonuc_defterde

    toplam_kasa = net_kasa_hareketleri
    acik_df = pd.DataFrame()
    if not df_trade.empty and "Durum" in df_trade.columns:
        kapali_mask = durum_kapali_maskesi(df_trade["Durum"])
        acik_df = df_trade[~kapali_mask]

    aktif_marjin_toplami = 0.0
    acik_kz_toplam = 0.0

    if not acik_df.empty:
        aktif_marjin_toplami = pd.to_numeric(acik_df["Islem_Miktari"], errors="coerce").fillna(0.0).sum()
        for _, rw in acik_df.iterrows():
            c_SYM = rw["Coin"]
            g_F = float(rw["Giris_Fiyat"])
            m_M = float(rw["Islem_Miktari"])
            y_Y = rw["Yon"]
            if not ortak_fiyat_havuzu:
                anl_F = fiyat_cek_binance(c_SYM)
            else:
                anl_F = ortak_fiyat_havuzu.get(c_SYM, baz_fiyatlar.get(c_SYM, 100.0))
            f_y = ((anl_F - g_F) / g_F) if "Long" in y_Y else ((g_F - anl_F) / g_F)
            acik_kz_toplam += m_M * KALDIRAC * f_y - cikis_komisyonu(m_M, False)

    efektif_kasa = toplam_kasa + acik_kz_toplam
    bos_bakiye = toplam_kasa - aktif_marjin_toplami
    return float(toplam_kasa), float(efektif_kasa), float(bos_bakiye), float(aktif_marjin_toplami), float(acik_kz_toplam)

def yeni_islem_ekle(coin, yon, giris_fiyat, islem_miktari, stop, kar_al, zaman_dilimi, matris_puan, risk_hedef_metin):
    df = islem_gecmisi_getir()
    toplam_kasa_risk, _, mevcut_bakiye, _, _ = bakiye_durumunu_getir()
    gereken_nakit = islem_miktari + giris_komisyonu(islem_miktari)
    if round(gereken_nakit, 2) > round(mevcut_bakiye, 2):
        return False, f"Bakiye yetersiz! Mevcut Bakiye: {mevcut_bakiye:.2f} $, Girilen: {islem_miktari:.2f} $ + giriş komisyonu {giris_komisyonu(islem_miktari):.2f} $"
    if islem_miktari <= 0:
        return False, "İşlem miktarı 0 $'dan büyük olmalıdır!"

    suan_tr = tr_zaman()
    suan_tr_str = suan_tr.strftime("%d.%m.%Y %H:%M")
    
    acik_islem_idx = None
    if not df.empty and "Durum" in df.columns:
        acik_mask = ~durum_kapali_maskesi(df["Durum"])
        acik_df = df[acik_mask]
        if not acik_df.empty and coin in acik_df["Coin"].values:
            acik_islem_idx = acik_df[acik_df["Coin"] == coin].index[0]

    if acik_islem_idx is not None:
        eski_giris = float(df.loc[acik_islem_idx, "Giris_Fiyat"])
        eski_miktar = float(df.loc[acik_islem_idx, "Islem_Miktari"])
        eski_yon = str(df.loc[acik_islem_idx, "Yon"])
        
        eski_zaman_str = str(df.loc[acik_islem_idx, "Acilis_Zamani"])

        gercek_zaman_str = eski_zaman_str
        try:
            df_market_filtre = load_15min_market_data(coin)
            if not df_market_filtre.empty and "timestamp" in df_market_filtre.columns and "Close" in df_market_filtre.columns:
                df_market_filtre["Fark"] = (df_market_filtre["Close"] - giris_fiyat).abs()
                en_yakin_satir = df_market_filtre.loc[df_market_filtre["Fark"].idxmin()]
                bulunan_zaman = en_yakin_satir["timestamp"]
                if isinstance(bulunan_zaman, pd.Timestamp):
                    gercek_zaman_str = bulunan_zaman.strftime("%d.%m.%Y %H:%M")
        except Exception as e:
            print(f"Binance zaman filtreleme hatası: {e}")

        try:
            eski_dt = datetime.strptime(eski_zaman_str.strip(), "%d.%m.%Y %H:%M")
            yeni_dt = datetime.strptime(gercek_zaman_str.strip(), "%d.%m.%Y %H:%M")
        except:
            eski_dt = suan_tr.replace(tzinfo=None)
            yeni_dt = suan_tr.replace(tzinfo=None)

        dakika_farki_yeni = (yeni_dt - eski_dt).total_seconds() / 60.0
        if dakika_farki_yeni < 0:
            dakika_farki_yeni = 0.0

        yeni_toplam_miktar = eski_miktar + islem_miktari
        agirlikli_dakika = ((0.0 * eski_miktar) + (dakika_farki_yeni * islem_miktari)) / yeni_toplam_miktar
        
        hesaplanan_yeni_dt = eski_dt + timedelta(minutes=agirlikli_dakika)
        yeni_acilis_zamani_str = hesaplanan_yeni_dt.strftime("%d.%m.%Y %H:%M")

        eski_matris_rh = str(df.loc[acik_islem_idx, "Matris_Puan_RH"])
        try:
            eski_puan = float(eski_matris_rh.split()[0].replace(",", "."))
        except:
            eski_puan = matris_puan

        yeni_agirlikli_ortalama = ((eski_miktar * eski_giris) + (islem_miktari * giris_fiyat)) / yeni_toplam_miktar
        yeni_agirlikli_puan = ((eski_miktar * eski_puan) + (islem_miktari * matris_puan)) / yeni_toplam_miktar

        stop_uzde_guncel, hedef_carpan_guncel, rh_guncel_metin = calculate_coin_metrics_by_score(yeni_agirlikli_puan)

        if "Long" in eski_yon:
            yeni_stop = yeni_agirlikli_ortalama * (1.0 - stop_uzde_guncel / 100.0)
            yeni_kar_al = yeni_agirlikli_ortalama * (1.0 + (stop_uzde_guncel * hedef_carpan_guncel) / 100.0)
        else:
            yeni_stop = yeni_agirlikli_ortalama * (1.0 + stop_uzde_guncel / 100.0)
            yeni_kar_al = yeni_agirlikli_ortalama * (1.0 - (stop_uzde_guncel * hedef_carpan_guncel) / 100.0)
        beklenen_kar, olasi_stop = beklenen_ve_olasi("Long" in eski_yon, yeni_toplam_miktar, yeni_agirlikli_ortalama, yeni_kar_al, yeni_stop)

        kap = risk_kapasitesi(toplam_kasa_risk, df, coin, yeni_agirlikli_ortalama, yeni_stop)
        if yeni_toplam_miktar > kap["azami"] + 0.005:
            eklenebilir = max(0.0, kap["azami"] - eski_miktar)
            return False, (f"⚠️ Risk sınırı aşılıyor! {coin} için azami toplam teminat {kap['azami']:.2f} $ "
                           f"(işlem başı risk %{ISLEM_BASINA_RISK_YUZDE:g} = {kap['islem_limit']:.2f} $, "
                           f"toplam risk payından kalan {kap['kalan_toplam_risk']:.2f} $). "
                           f"Şu an en fazla {eklenebilir:.2f} $ ekleyebilirsiniz.")

        basamak = 4 if yeni_agirlikli_ortalama < 10 else 2
        matris_rh_metin = f"{yeni_agirlikli_puan:.2f} ({rh_guncel_metin})"
        toplam_kasa, _, _, _, _ = bakiye_durumunu_getir()
        giris_kom = round(giris_komisyonu(islem_miktari), 4)

        df.at[acik_islem_idx, "Giris_Fiyat"] = round(yeni_agirlikli_ortalama, basamak)
        df.at[acik_islem_idx, "Islem_Miktari"] = round(yeni_toplam_miktar, 2)
        df.at[acik_islem_idx, "Stop"] = round(yeni_stop, basamak)
        df.at[acik_islem_idx, "Kar_Al"] = round(yeni_kar_al, basamak)
        df.at[acik_islem_idx, "Acilis_Zamani"] = yeni_acilis_zamani_str
        df.at[acik_islem_idx, "Beklenen_Kar"] = round(beklenen_kar, 2)
        df.at[acik_islem_idx, "Olasi_Stop"] = round(olasi_stop, 2)
        df.at[acik_islem_idx, "Matris_Puan_RH"] = matris_rh_metin
        df.at[acik_islem_idx, "Guncel_Kasa"] = round(toplam_kasa - giris_kom, 2)

        if not dataframe_guncelle_gsheets(df):
            return False, "⚠️ Ekleme Google Sheets'e yazılamadı! Pozisyon DEĞİŞMEDİ, lütfen tekrar deneyin."
        islem_no = int(df.at[acik_islem_idx, "Islem_ID"])
        kom_ok = kasa_islem_ekle_deftere("Komisyon", -giris_kom, f"Giriş Komisyonu: #{islem_no} {coin}")
        uyari = "" if kom_ok else " ⚠️ Giriş komisyonu deftere yazılamadı, KasaDefteri'ni kontrol edin."
        return True, f"🔄 {coin} pozisyonuna ekleme yapıldı! Binance Verisiyle Eşleşen Zaman ({yeni_acilis_zamani_str}) ve Maliyet Güncellendi. Giriş komisyonu: {giris_kom:.4f} $.{uyari}"
    else:
        min_esik_kontrol = aktif_min_puan_esigi_getir()
        if matris_puan < min_esik_kontrol or "Nötr" in yon or "Beklemede" in yon:
            return False, f"⚠️ Nötr veya Min. Eşik ({min_esik_kontrol}) altındaki yeni işlemler engellenmiştir!"

        yeni_id = 1 if df.empty else int(pd.to_numeric(df["Islem_ID"], errors="coerce").max() or 0) + 1

        beklenen_kar, olasi_stop = beklenen_ve_olasi("Long" in yon, islem_miktari, giris_fiyat, kar_al, stop)

        kap = risk_kapasitesi(toplam_kasa_risk, df, coin, giris_fiyat, stop)
        if islem_miktari > kap["azami"] + 0.005:
            return False, (f"⚠️ Risk sınırı aşılıyor! {coin} için azami teminat {kap['azami']:.2f} $ "
                           f"(işlem başı risk %{ISLEM_BASINA_RISK_YUZDE:g} = {kap['islem_limit']:.2f} $, "
                           f"toplam risk payından kalan {kap['kalan_toplam_risk']:.2f} $).")

        basamak = 4 if giris_fiyat < 10 else 2
        giris_kom = round(giris_komisyonu(islem_miktari), 4)
        matris_rh_metin = f"{matris_puan} ({risk_hedef_metin})"
        toplam_kasa, _, _, _, _ = bakiye_durumunu_getir()
        yeni_kayit = pd.DataFrame([{
            "Islem_ID": yeni_id,
            "Acilis_Zamani": suan_tr.strftime("%d.%m.%Y %H:%M"),
            "Coin": coin,
            "Yon": yon,
            "Zaman_Dilimi": zaman_dilimi,
            "Giris_Fiyat": round(giris_fiyat, basamak),
            "Islem_Miktari": round(islem_miktari, 2),
            "Stop": round(stop, basamak),
            "Kar_Al": round(kar_al, basamak),
            "Beklenen_Kar": round(beklenen_kar, 2),
            "Matris_Puan_RH": matris_rh_metin,
            "Olasi_Stop": round(olasi_stop, 2),
            "Durum": "Acik",
            "Net_Kar_Zarar": 0.0,
            "Guncel_Kasa": round(toplam_kasa - giris_kom, 2),
            "Kapanis_Zamani": "-",
            "Kapanis_Fiyati": 0.0,
        }])
        df = pd.concat([df, yeni_kayit], ignore_index=True).drop_duplicates(subset=["Islem_ID"], keep="last")
        if not dataframe_guncelle_gsheets(df):
            return False, "⚠️ İşlem Google Sheets'e yazılamadı! İşlem AÇILMADI, lütfen tekrar deneyin."
        kom_ok = kasa_islem_ekle_deftere("Komisyon", -giris_kom, f"Giriş Komisyonu: #{yeni_id} {coin}")
        uyari = "" if kom_ok else " ⚠️ Giriş komisyonu deftere yazılamadı, KasaDefteri'ni kontrol edin."
        return True, f"✅ {coin} emri başarıyla verildi! Giriş komisyonu: {giris_kom:.4f} $.{uyari}"

def _islem_acik_mi(durum):
    return not bool(durum_kapali_maskesi(pd.Series([durum])).iloc[0])

def manuel_islem_kapat(islem_id, anlik_kapatma_fiyati, kapatilacak_miktar=None):
    df = islem_gecmisi_getir()
    idx = df[df["Islem_ID"] == islem_id].index
    if idx.empty:
        return False, "İşlem bulunamadı!"
    row = df.loc[idx[0]]
    if not _islem_acik_mi(row["Durum"]):
        return False, "Bu işlem zaten kapalı!"
    try:
        giris_fiyat = float(row["Giris_Fiyat"])
        mevcut_miktar = float(row["Islem_Miktari"])
        suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")
        long_mi = "Long" in row["Yon"]
        fark_yuzde = ((anlik_kapatma_fiyati - giris_fiyat) / giris_fiyat) if long_mi else ((giris_fiyat - anlik_kapatma_fiyati) / giris_fiyat)

        if kapatilacak_miktar is not None and kapatilacak_miktar < mevcut_miktar:
            # Manuel kapanış piyasa emriyle yapılır: taker komisyonu çıkışta düşülür
            kismi_kar = kapatilacak_miktar * KALDIRAC * fark_yuzde - cikis_komisyonu(kapatilacak_miktar, False)

            yeni_id = int(pd.to_numeric(df["Islem_ID"], errors="coerce").max() or 0) + 1
            durum_metni = "Kısmi Kapandı (Zarar)" if kismi_kar < 0 else "Kısmi Kapandı (Kâr)"

            toplam_kasa, _, _, _, _ = bakiye_durumunu_getir()
            yeni_kapali_kayit = pd.DataFrame([{
                "Islem_ID": yeni_id,
                "Acilis_Zamani": row["Acilis_Zamani"],
                "Coin": row["Coin"],
                "Yon": row["Yon"],
                "Zaman_Dilimi": row["Zaman_Dilimi"],
                "Giris_Fiyat": giris_fiyat,
                "Islem_Miktari": round(kapatilacak_miktar, 2),
                "Stop": float(row["Stop"]),
                "Kar_Al": float(row["Kar_Al"]),
                "Beklenen_Kar": float(row["Beklenen_Kar"]),
                "Matris_Puan_RH": row["Matris_Puan_RH"],
                "Olasi_Stop": float(row["Olasi_Stop"]),
                "Durum": durum_metni,
                "Net_Kar_Zarar": float(round(kismi_kar, 2)),
                "Guncel_Kasa": float(round(toplam_kasa + kismi_kar, 2)),
                "Kapanis_Zamani": suan_tr,
                "Kapanis_Fiyati": float(round(anlik_kapatma_fiyati, 4)),
            }])

            kalan_miktar = mevcut_miktar - kapatilacak_miktar
            df.at[idx[0], "Islem_Miktari"] = round(kalan_miktar, 2)
            bek_kar_yeni, olasi_stop_yeni = beklenen_ve_olasi(long_mi, kalan_miktar, giris_fiyat, float(row["Kar_Al"]), float(row["Stop"]))
            df.at[idx[0], "Beklenen_Kar"] = round(bek_kar_yeni, 2)
            df.at[idx[0], "Olasi_Stop"] = round(olasi_stop_yeni, 2)

            df = pd.concat([df, yeni_kapali_kayit], ignore_index=True).sort_values(by="Islem_ID").reset_index(drop=True)
            if not dataframe_guncelle_gsheets(df):
                return False, "⚠️ Kısmi kapama Google Sheets'e yazılamadı! Pozisyon DEĞİŞMEDİ, lütfen tekrar deneyin."

            ok = kasa_islem_ekle_deftere(
                "Trade_Sonuc",
                float(round(kismi_kar, 2)),
                f"Kısmi K/Z: #{islem_id} {row['Coin']} ({kapatilacak_miktar}$ kapatıldı)",
            )
            uyari = "" if ok else " ⚠️ Kasa defterine yazılamadı, KasaDefteri'ni kontrol edin."
            return True, f"Kısmi kapama başarılı! Realize Edilen K/Z (komisyon dahil): {kismi_kar:,.2f} $.{uyari}"
        else:
            net_kar = mevcut_miktar * KALDIRAC * fark_yuzde - cikis_komisyonu(mevcut_miktar, False)

            durum_metni = "Kapandi (Zarar)" if net_kar < 0 else "Kapandi (Kar)"
            df.at[idx[0], "Durum"] = durum_metni
            df.at[idx[0], "Kapanis_Zamani"] = suan_tr
            df.at[idx[0], "Net_Kar_Zarar"] = float(round(net_kar, 2))
            df.at[idx[0], "Kapanis_Fiyati"] = float(round(anlik_kapatma_fiyati, 4))

            toplam_kasa, _, _, _, _ = bakiye_durumunu_getir()
            df.at[idx[0], "Guncel_Kasa"] = float(round(toplam_kasa + net_kar, 2))
            if not dataframe_guncelle_gsheets(df):
                return False, "⚠️ Kapanış Google Sheets'e yazılamadı! İşlem hâlâ AÇIK, lütfen tekrar deneyin."
            ok = kapanis_deftere_yaz_tekil(islem_id, "Trade K/Z", row["Coin"], net_kar, durum_metni)
            uyari = "" if ok else " ⚠️ Kasa defterine yazılamadı, KasaDefteri'ni kontrol edin."
            return True, f"İşlem tamamen kapatıldı. K/Z (komisyon dahil): {net_kar:.2f} $.{uyari}"
    except Exception as e:
        return False, f"Hata: {str(e)}"

def otomatik_stop_kar_kontrolu(df_arg, ortak_fiyat_havuzu=None):
    if df_arg is None or not isinstance(df_arg, pd.DataFrame) or df_arg.empty or "Durum" not in df_arg.columns:
        return

    # 1) Eldeki (eski olabilecek) tabloya göre hangi işlemler kapanmalı?
    adaylar = []  # (islem_id, hedefe_ulasti, kapanis_fiyati)
    for idx, row in df_arg.iterrows():
        if not _islem_acik_mi(row["Durum"]):
            continue
        islem_id = int(row["Islem_ID"])
        coin = row["Coin"]
        yon = row["Yon"]
        stop_f = float(row["Stop"])
        kar_al_f = float(row["Kar_Al"])
        if ortak_fiyat_havuzu is not None and coin in ortak_fiyat_havuzu:
            anl_f = ortak_fiyat_havuzu[coin]
        else:
            anl_f = fiyat_cek_binance(coin)

        if "Long" in yon:
            if anl_f <= stop_f:
                adaylar.append((islem_id, False, stop_f))
            elif anl_f >= kar_al_f:
                adaylar.append((islem_id, True, kar_al_f))
        elif "Short" in yon:
            if anl_f >= stop_f:
                adaylar.append((islem_id, False, stop_f))
            elif anl_f <= kar_al_f:
                adaylar.append((islem_id, True, kar_al_f))

    if not adaylar:
        return

    # 2) Yazmadan hemen önce tabloyu TAZE oku: motor aynı işlemi kapatmış ya da ekleme yapılmış olabilir.
    #    Eski tabloyu geri yazmak, bu değişiklikleri silerdi.
    st.cache_data.clear()
    df = islem_gecmisi_getir(sheet_guncelle=False).copy()
    if df is None or df.empty:
        return
    suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")
    toplam_kasa, _, _, _, _ = bakiye_durumunu_getir({} if ortak_fiyat_havuzu is None else ortak_fiyat_havuzu)
    kasa_ilerleyen = toplam_kasa
    yazilacaklar = []  # (islem_id, coin, hedefe_ulasti, net_kar)

    for islem_id, hedefe_ulasti, kapanis_fiyat_degeri in adaylar:
        eslesen = df.index[df["Islem_ID"] == islem_id]
        if len(eslesen) == 0:
            continue
        i = eslesen[0]
        if not _islem_acik_mi(df.at[i, "Durum"]):
            continue  # motor veya başka bir oturum zaten kapatmış
        giris_fiyat = float(df.at[i, "Giris_Fiyat"])
        miktar = float(df.at[i, "Islem_Miktari"])
        yon = df.at[i, "Yon"]
        coin = df.at[i, "Coin"]
        if giris_fiyat <= 0 or miktar <= 0:
            print(f"UYARI: #{islem_id} geçersiz değerler nedeniyle atlandı.")
            continue

        fark_yuzde = ((kapanis_fiyat_degeri - giris_fiyat) / giris_fiyat) if "Long" in yon else ((giris_fiyat - kapanis_fiyat_degeri) / giris_fiyat)
        # Giriş komisyonu açılışta düşüldü; çıkışta hedef=maker, stop=taker
        net_kar = miktar * KALDIRAC * fark_yuzde - cikis_komisyonu(miktar, hedefe_ulasti)
        kasa_ilerleyen += net_kar

        df.at[i, "Durum"] = "Kapandi (Kar)" if hedefe_ulasti else "Kapandi (Zarar)"
        df.at[i, "Kapanis_Zamani"] = suan_tr
        df.at[i, "Net_Kar_Zarar"] = float(round(net_kar, 2))
        df.at[i, "Kapanis_Fiyati"] = float(round(kapanis_fiyat_degeri, 4))
        df.at[i, "Guncel_Kasa"] = float(round(kasa_ilerleyen, 2))
        yazilacaklar.append((islem_id, coin, hedefe_ulasti, net_kar))

    if not yazilacaklar:
        return

    # 3) Önce tablo, sonra defter (tablo yazılamazsa defter de yazılmaz)
    if not dataframe_guncelle_gsheets(df):
        print("Otomatik kapanış tabloya yazılamadı; sonraki turda yeniden denenecek.")
        return
    for islem_id, coin, hedefe_ulasti, net_kar in yazilacaklar:
        etiket = "Hedef Kâr" if hedefe_ulasti else "Otomatik Stop"
        kapanis_deftere_yaz_tekil(islem_id, etiket, coin, net_kar, "Kar" if hedefe_ulasti else "Zarar")

def trend_asamasini_ve_ikon_belirle(puan, aktif_yon):
    hsonu = hafta_sonu_mu()
    min_esik = 60.0 if hsonu else 55.0

    if puan < min_esik:
        return "Nötr (Beklemede)", 1.0, False, False

    if not hsonu:
        if 55.0 <= puan < 58.75:
            return "⭐ 1. Aşama (Zayıf Trend)", 3.0, False, False
        elif 58.75 <= puan < 62.50:
            return "⭐⭐ 2. Aşama (Orta Trend)", 3.0, False, False
        elif 62.50 <= puan < 66.25:
            return "⭐⭐⭐ 3. Aşama (Güvenli Trend)", 3.0, False, False
        elif 66.25 <= puan < 70.00:
            return "🔥 4. Aşama (Güçlü Trend)", 3.0, False, False
        elif 70.00 <= puan < 73.75:
            return "🔥 🔥 5. Aşama (Çok Güçlü Trend)", 4.0, True, False
        else:
            return "🔥🔥🔥 6. Aşama (Boğa Vuruşu / Ayı Pençesi)", 5.0, False, True
    else:
        if 60.0 <= puan < 63.75:
            return "⭐ 1. Aşama (Zayıf Trend)", 3.0, False, False
        elif 63.75 <= puan < 67.50:
            return "⭐⭐ 2. Aşama (Orta Trend)", 3.0, False, False
        elif 67.50 <= puan < 71.25:
            return "⭐⭐⭐ 3. Aşama (Güvenli Trend)", 3.0, False, False
        elif 71.25 <= puan < 75.00:
            return "🔥 4. Aşama (Güçlü Trend)", 3.0, False, False
        elif 75.00 <= puan < 78.75:
            return "🔥 🔥 5. Aşama (Çok Güçlü Trend)", 4.0, True, False
        else:
            return "🔥🔥🔥 6. Aşama (Boğa Vuruşu / Ayı Pençesi)", 5.0, False, True

def sinyal_ve_trend_mail_kontrolu(sembol, nihai_puan, aktif_yon, trend_metni, coin_mi=True):
    if not MAIL_PANELDEN_GONDER:
        return
    hafiza = hafizayi_oku()
    if sembol not in hafiza:
        hafiza[sembol] = {"asama_5_tetiklendi": False, "asama_6_tetiklendi": False}

    hsonu = hafta_sonu_mu()
    asama_5_sart = False
    asama_6_sart = False

    if not hsonu:
        if 70.00 <= nihai_puan < 73.75:
            asama_5_sart = True
        elif nihai_puan >= 73.75:
            asama_6_sart = True
    else:
        if 75.00 <= nihai_puan < 78.75:
            asama_5_sart = True
        elif nihai_puan >= 78.75:
            asama_6_sart = True

    if asama_5_sart and not hafiza[sembol]["asama_5_tetiklendi"]:
        hafiza[sembol]["asama_5_tetiklendi"] = True
        hafizayi_kaydet(hafiza)
    elif not asama_5_sart and hafiza[sembol]["asama_5_tetiklendi"]:
        hafiza[sembol]["asama_5_tetiklendi"] = False
        hafizayi_kaydet(hafiza)

    if asama_6_sart and not hafiza[sembol]["asama_6_tetiklendi"]:
        hafiza[sembol]["asama_6_tetiklendi"] = True
        hafizayi_kaydet(hafiza)
    elif not asama_6_sart and hafiza[sembol]["asama_6_tetiklendi"]:
        hafiza[sembol]["asama_6_tetiklendi"] = False
        hafizayi_kaydet(hafiza)

def arka_plan_dinleyicisi(durdur_olayi):
    while not durdur_olayi.is_set():
        bekleme = 60
        try:
            tum_semboller = coinler + ["TOTAL"]
            anlik_fiyat_havuzu = {}
            for s in tum_semboller:
                anlik_fiyat_havuzu[s] = fiyat_cek_binance(s)
            for s in tum_semboller:
                if durdur_olayi.is_set():
                    return
                _, puan, yon, _, _, _ = kurgusal_matris_hesapla(s)
                trend_metni, _, _, _ = trend_asamasini_ve_ikon_belirle(puan, yon)
                sinyal_ve_trend_mail_kontrolu(s, puan, yon, trend_metni, coin_mi=(s != "TOTAL"))
            df_bg = islem_gecmisi_getir(sheet_guncelle=False)
            otomatik_stop_kar_kontrolu(df_bg, anlik_fiyat_havuzu)
        except Exception as e:
            print(f"Arka plan hata: {e}")
            bekleme = 10
        durdur_olayi.wait(bekleme)

@st.cache_resource
def botu_baslat_bir_kez():
    onceki_olay = getattr(threading, "_kripto_bot_durdur_olayi", None)
    if onceki_olay is not None:
        onceki_olay.set()

    yeni_olay = threading.Event()
    threading._kripto_bot_durdur_olayi = yeni_olay

    thread = threading.Thread(
        target=arka_plan_dinleyicisi,
        args=(yeni_olay,),
        name="arka_plan_dinleyicisi",
        daemon=True,
    )
    if add_script_run_ctx is not None and get_script_run_ctx is not None:
        ctx = get_script_run_ctx()
        if ctx is not None:
            add_script_run_ctx(thread, ctx)
    thread.start()
    return thread

arka_plan_thread = botu_baslat_bir_kez()

st.title("Piyasa Genel Bakış")
min_esik_bilgi = aktif_min_puan_esigi_getir()
mod_bilgi_metni = "Hafta Sonu / Sığ Piyasa Modu (Min Eşik: 60)" if min_esik_bilgi == 60.0 else "Hafta İçi Normal Mod (Min Eşik: 55)"
st.caption(f"Oransal Matris Omurgası + EMA, RSI Mıknatısı & Fib Katkıları | ⚙️ **{mod_bilgi_metni}**")

if "kasa_islem_acik" not in st.session_state:
    st.session_state["kasa_islem_acik"] = False
if "kasa_islem_turu" not in st.session_state:
    st.session_state["kasa_islem_turu"] = "Para Yatır"
if "sadece_aktifleri_goster" not in st.session_state:
    st.session_state["sadece_aktifleri_goster"] = True
if "kapama_paneli_acik" not in st.session_state:
    st.session_state["kapama_paneli_acik"] = False
if "islem_emri_kilit_acik" not in st.session_state:
    st.session_state["islem_emri_kilit_acik"] = False

tum_takip_edilenler = coinler + ["TOTAL"]
islenen_ham_veriler = []
ortak_fiyat_havuzu = {}

for sembol in tum_takip_edilenler:
    matris_sonuc = kurgusal_matris_hesapla(sembol)
    if matris_sonuc is None:
        matris_sonuc = (fiyat_cek_binance(sembol), 0.0, "Long", 0.0, 0.0, {})
    anlik_fiyat, nihai_puan, aktif_yon, l_puan, s_puan, zaman_katkilari = matris_sonuc
    if sembol == "TOTAL":
        anlik_fiyat = fiyat_cek_binance("TOTAL")
    ortak_fiyat_havuzu[sembol] = anlik_fiyat

    df_market = load_15min_market_data(sembol)
    if not df_market.empty and "Open" in df_market.columns and "Close" in df_market.columns:
        gunluk_oran = ((float(df_market.iloc[-1]["Close"]) - float(df_market.iloc[0]["Open"])) / float(df_market.iloc[0]["Open"])) * 100.0
    else:
        gunluk_oran = 0.0

    islenen_ham_veriler.append({
        "sembol": sembol, "anlik_fiyat": anlik_fiyat, "nihai_puan": nihai_puan,
        "aktif_yon": aktif_yon, "l_puan": l_puan, "s_puan": s_puan,
        "zaman_katkilari": zaman_katkilari, "gunluk_oran": gunluk_oran, "df_market": df_market,
    })

df_ana_kayit = islem_gecmisi_getir(sheet_guncelle=False)
otomatik_stop_kar_kontrolu(df_ana_kayit, ortak_fiyat_havuzu)

coin_ham_veriler = [d for d in islenen_ham_veriler if d["sembol"] != "TOTAL"]
total_ham_veri = [d for d in islenen_ham_veriler if d["sembol"] == "TOTAL"][0]

t_puan_val, t_l_puan, t_s_puan = total_ham_veri["nihai_puan"], total_ham_veri["l_puan"], total_ham_veri["s_puan"]
t_toplam_puan = t_l_puan + t_s_puan
t_yuzde = (t_l_puan / t_toplam_puan * 100.0) if t_toplam_puan > 0 else 50.0

total_puan_val = total_ham_veri["nihai_puan"]
total_yon_val = total_ham_veri["aktif_yon"]

gecici_islenen_liste = []
for data in coin_ham_veriler:
    sembol, nihai_puan, aktif_yon, l_puan, s_puan, anlik_fiyat = (
        data["sembol"], data["nihai_puan"], data["aktif_yon"],
        data["l_puan"], data["s_puan"], data["anlik_fiyat"]
    )
    gunluk_oran = data["gunluk_oran"]

    puan_toplam = l_puan + s_puan
    y_yuzde = (l_puan / puan_toplam * 100.0) if puan_toplam > 0 else 50.0
    k_yuzde = 100.0 - y_yuzde

    c_led = "🟢" if (nihai_puan >= min_esik_bilgi and aktif_yon == "Long") else ("🔴" if (nihai_puan >= min_esik_bilgi and aktif_yon == "Short") else "🟡")
    d_led = "🟢" if total_yon_val == "Long" else "🔴"

    yesil_led_sayisi = round((y_yuzde / 100.0) * 10.0)
    yesil_led_sayisi = max(0, min(10, yesil_led_sayisi))
    kirmizi_led_sayisi = 10 - yesil_led_sayisi

    detay_matris_html = ""  # artık birleşik sütunda (puan döngüsünde üretilir)

    is_notr = (nihai_puan < min_esik_bilgi)
    trend, ham_agirlik, asama_5, asama_6 = trend_asamasini_ve_ikon_belirle(nihai_puan, aktif_yon)

    if is_notr:
        aktif_yon_turu = "Nötr"
        yon_html = f'<div style="background-color: #6c757d; padding: 6px; border-radius: 6px; color: white; font-weight: bold; font-size: 12px;">{trend}</div>'
    else:
        aktif_yon_turu = aktif_yon
        renk_bg = "#00FF00" if aktif_yon == "Long" else "rgb(255, 75, 0)"
        yon_html = f'<div style="background-color: {renk_bg}; padding: 6px; border-radius: 6px; color: #000000; font-weight: bold; font-size: 12px;">{trend}</div>'

    sinyal_ve_trend_mail_kontrolu(sembol, nihai_puan, aktif_yon_turu, trend, coin_mi=True)

    stop_uzde, hedef_carpan, risk_hedef_metin = calculate_coin_metrics_by_score(nihai_puan)

    gecici_islenen_liste.append({
        "sembol": sembol, "nihai_puan": nihai_puan, "aktif_yon": aktif_yon,
        "aktif_yon_turu": aktif_yon_turu, "l_puan": l_puan, "s_puan": s_puan,
        "anlik_fiyat": anlik_fiyat, "gunluk_oran": gunluk_oran, "c_led": c_led,
        "d_led": d_led, "detay_matris_html": detay_matris_html, "yon_html": yon_html,
        "trend": trend, "is_notr": is_notr, "ham_agirlik": ham_agirlik,
        "stop_uzde": stop_uzde, "hedef_carpan": hedef_carpan, "risk_hedef_metin": risk_hedef_metin,
    })

toplam_aktif_agirlik = sum([item["ham_agirlik"] for item in gecici_islenen_liste if not item["is_notr"]])
islenen_veriler = []

for item in gecici_islenen_liste:
    sembol, nihai_puan, aktif_yon_turu, aktif_yon, anlik_fiyat, stop_uzde, hedef_carpan, is_notr, trend = (
        item["sembol"], item["nihai_puan"], item["aktif_yon_turu"], item["aktif_yon"],
        item["anlik_fiyat"], item["stop_uzde"], item["hedef_carpan"],
        item["is_notr"], item["trend"]
    )

    if toplam_aktif_agirlik > 0 and not is_notr:
        sepet_orani = round((item["ham_agirlik"] / toplam_aktif_agirlik) * 100.0, 1)
    else:
        sepet_orani = 0.0

    if aktif_yon_turu == "Long" or (is_notr and aktif_yon == "Long"):
        stop_fiyat, hedef_fiyat = anlik_fiyat * (1.0 - stop_uzde / 100.0), anlik_fiyat * (1.0 + (stop_uzde * hedef_carpan) / 100.0)
    else:
        stop_fiyat, hedef_fiyat = anlik_fiyat * (1.0 + stop_uzde / 100.0), anlik_fiyat * (1.0 - (stop_uzde * hedef_carpan) / 100.0)

    dom_html = f'<div style="text-align: center;"><div style="font-size: 16px; margin-bottom: 2px; letter-spacing: 4px;">{item["c_led"]}{item["d_led"]}</div><div style="font-size: 10px; font-weight: bold; color: #91a0b8;">C &nbsp;&nbsp; D</div></div>'

    puan_toplam_h = item["l_puan"] + item["s_puan"]
    y_yuzde_h = (item["l_puan"] / puan_toplam_h * 100.0) if puan_toplam_h > 0 else 50.0
    puan_html = matris_birlesik_html(nihai_puan, aktif_yon, y_yuzde_h, 100.0 - y_yuzde_h)

    basamak = 4 if anlik_fiyat < 10 else 2
    logo_html = f'<img src="{logo_urls.get(sembol, "")}" width="24" height="24">'

    islenen_veriler.append({
        "Sira_Anahtar": list(logo_urls.keys()).index(sembol),
        "Logo": logo_html, "Coin": sembol, "Fiyat": round(anlik_fiyat, basamak),
        "Yon": item["yon_html"], "Teyit_Sunumu": item["detay_matris_html"],
        "Dom_Sunumu": dom_html, "Matris_Puan_Sunumu": puan_html,
        "Gunluk_Oran": f"<span>{item['gunluk_oran']:+,.2f}%</span>",
        "Kar_Al": round(hedef_fiyat, basamak), "Stopla": round(stop_fiyat, basamak),
        "Skor": nihai_puan, "Sepet_Orani": sepet_orani, "Basamak": basamak,
        "Notr": is_notr, "Ham_Yon": trend, "Aktif_Yon": aktif_yon_turu,
        "Risk_Hedef_Metin": item['risk_hedef_metin'], "Ham_Agirlik": item["ham_agirlik"],
    })

islenen_veriler = sorted(islenen_veriler, key=lambda x: (1 if x["Notr"] else 0, -x["Ham_Agirlik"], -x["Skor"]))
toplam_kasa, efektif_kasa, mevcut_bakiye, aktif_yatirim_tutari, toplam_acik_kz = bakiye_durumunu_getir(ortak_fiyat_havuzu)

for v in islenen_veriler:
    v["Yatırım_Bedeli"] = f"{mevcut_bakiye * (v['Sepet_Orani'] / 100.0):,.2f} $"

col_ust1, col_ust2, col_ust3, col_ust4, col_ust5, col_ust6, col_kasa_buton = st.columns([1.6, 1.6, 1.6, 1.6, 1.6, 1.6, 1.6], gap="small")

df_metrik_trade = islem_gecmisi_getir(sheet_guncelle=False)
realize_kar = 0.0
if not df_metrik_trade.empty and "Durum" in df_metrik_trade.columns:
    kapananlar_mask = durum_kapali_maskesi(df_metrik_trade["Durum"])
    realize_kar = pd.to_numeric(df_metrik_trade[kapananlar_mask]["Net_Kar_Zarar"], errors="coerce").fillna(0.0).sum()

_df_kasa_anapara = kasa_defteri_getir()
anapara = float(BASLANGIC_BAKIYE)
if not _df_kasa_anapara.empty and "Islem_Turu" in _df_kasa_anapara.columns:
    _tutar_a = pd.to_numeric(_df_kasa_anapara["Tutar"], errors="coerce").fillna(0.0)
    anapara += float(_tutar_a[_df_kasa_anapara["Islem_Turu"].isin(["Para_Yatir", "Para_Cek"])].sum())

aktif_oran = (aktif_yatirim_tutari / toplam_kasa * 100) if toplam_kasa > 0 else 0.0
bostaki_oran = (mevcut_bakiye / toplam_kasa * 100) if toplam_kasa > 0 else 0.0
aktif_kar_oran = (toplam_acik_kz / aktif_yatirim_tutari * 100) if aktif_yatirim_tutari > 0 else 0.0
realize_kar_oran = (realize_kar / anapara * 100) if anapara > 0 else 0.0
ef_kasa_oran = (toplam_acik_kz / toplam_kasa * 100) if toplam_kasa > 0 else 0.0
toplam_kasa_oran = ((toplam_kasa - anapara) / anapara * 100) if anapara > 0 else 0.0

def format_yuzde(val, is_change=False):
    if is_change:
        return f"+%{val:.1f}" if val > 0 else f"-%{abs(val):.1f}" if val < 0 else "%0.0"
    return f"%{val:.1f}"

def metrik_kutusu(baslik, deger_metni, renk, yuzde_metni):
    """Üst özet kutusu. Tutar tek satırda kalır; yazı boyutu kutu genişliğine ve rakam sayısına göre küçülür
    (100.000 $ ve üzerinde de sığar). cqw desteklemeyen tarayıcılarda tahmini sabit boyut kullanılır."""
    n_deger, n_yuzde = len(deger_metni), len(yuzde_metni)
    yuzde_px = n_yuzde * 0.62 * 13.0 + 6.0
    sabit = max(8.0, min(22.0, (150.0 - yuzde_px) / (n_deger * 0.62)))
    return (f'<div class="metric-container"><div style="margin:0; font-size:13px; font-weight:bold; color:#91a0b8;">{baslik}</div>'
            f'<div style="display:flex; align-items:baseline; gap:6px; margin:5px 0 0 0; white-space:nowrap;">'
            f'<div style="color:{renk}; font-size:{sabit:.1f}px; font-size:clamp(8px, calc((100cqw - {yuzde_px:.0f}px) / {n_deger * 0.62:.2f}), 22px); font-weight:800;">{deger_metni}</div>'
            f'<div style="color:#ffffff; font-size:13px; font-weight:700;">{yuzde_metni}</div></div></div>')

aktif_renk = "#00FF00" if toplam_acik_kz >= 0 else "rgb(255, 75, 0)"
with col_ust1:
    st.markdown(metrik_kutusu("📊 Aktif Yatırım", f"{aktif_yatirim_tutari:,.2f} $", aktif_renk, format_yuzde(aktif_oran)), unsafe_allow_html=True)

with col_ust2:
    st.markdown(metrik_kutusu("🔥 Aktif Kâr", f"{toplam_acik_kz:+,.2f} $", aktif_renk, format_yuzde(aktif_kar_oran, True)), unsafe_allow_html=True)

with col_ust3:
    st.markdown(metrik_kutusu("🟢 Boştaki Nakit", f"{mevcut_bakiye:,.2f} $", "#e8eef8", format_yuzde(bostaki_oran)), unsafe_allow_html=True)

realize_kar_renk = "#00FF00" if realize_kar >= 0 else "rgb(255, 75, 0)"
with col_ust4:
    st.markdown(metrik_kutusu("⚡ Net Kâr (Realize)", f"{realize_kar:+,.2f} $", realize_kar_renk, format_yuzde(realize_kar_oran, True)), unsafe_allow_html=True)

efektif_renk = "#00FF00" if efektif_kasa >= toplam_kasa else "rgb(255, 75, 0)"
with col_ust5:
    st.markdown(metrik_kutusu("💎 Efektif Kasa", f"{efektif_kasa:,.2f} $", efektif_renk, format_yuzde(ef_kasa_oran, True)), unsafe_allow_html=True)

toplam_kasa_renk = "#00FF00" if toplam_kasa >= anapara else "rgb(255, 75, 0)"
with col_ust6:
    st.markdown(metrik_kutusu("💼 Toplam Kasa", f"{toplam_kasa:,.2f} $", toplam_kasa_renk, format_yuzde(toplam_kasa_oran, True)), unsafe_allow_html=True)

with col_kasa_buton:
    st.markdown(
        """<style>
        .st-key-ana_kasa_butonu { width: 100% !important; margin: 0 !important; padding: 0 !important; position: relative !important; top: -16px !important; }
        .st-key-ana_kasa_butonu [data-testid="stButton"] { width: 100% !important; margin: 0 !important; padding: 0 !important; }
        .st-key-ana_kasa_butonu button { box-sizing: border-box !important; display: flex !important; align-items: center !important; justify-content: center !important; width: 100% !important; height: 104px !important; min-height: 104px !important; padding: 12px 8px !important; margin: 0 !important; background: linear-gradient(135deg, #3977f6, #5b8cff) !important; color: #ffffff !important; border: 1px solid #4f83f5 !important; border-radius: 16px !important; font-size: 14px !important; font-weight: 800 !important; line-height: 1.35 !important; white-space: normal !important; text-align: center !important; box-shadow: 0 4px 12px rgba(57,119,246,.25) !important; transition: filter .18s ease, border-color .18s ease !important; }
        .st-key-ana_kasa_butonu button:hover { filter: brightness(1.08) !important; border-color: #91b2ff !important; transform: none !important; }
        </style>""",
        unsafe_allow_html=True,
    )
    if st.button("🏦 Kasa İşlemleri", width='stretch', key="ana_kasa_butonu"):
        st.session_state["kasa_islem_acik"] = not st.session_state.get("kasa_islem_acik", False)
        st.rerun()

if st.session_state.get("kasa_islem_acik", False):
    islem_yatir = st.session_state.get("kasa_islem_turu", "Para Yatır") == "Para Yatır"
    st.markdown(f"""<div style="background:linear-gradient(145deg,#121e30,#0e1726); border:1px solid #344765; border-left:4px solid #5b8cff; border-radius:14px; margin:16px 0 12px; padding: 15px;">""", unsafe_allow_html=True)
    col_header_sol, col_header_sag = st.columns([2.5, 1])
    with col_header_sol:
        baslik = "Kasaya Para Ekle" if islem_yatir else "Kasadan Para Çek"
        icon = "💰" if islem_yatir else "💸"
        st.markdown(f"""<div style="font-size:21px; font-weight:800; color:#f0f5ff; margin-bottom:4px;">{icon} {baslik}</div><div style="font-size:13px; color:#aab9d0;">Tutarı ve açıklamayı girin, ardından işlemi onaylayın.</div>""", unsafe_allow_html=True)
    with col_header_sag:
        h_btn_col1, h_btn_col2 = st.columns(2)
        with h_btn_col1:
            if st.button("💵 Ekle", width='stretch', key="btn_mod_ekle"):
                st.session_state["kasa_islem_turu"] = "Para Yatır"
                st.rerun()
        with h_btn_col2:
            if st.button("🏦 Çek", width='stretch', key="btn_mod_cek"):
                st.session_state["kasa_islem_turu"] = "Para Çek"
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    col_k1, col_k2, col_onay, col_kapat = st.columns([1.05, 2.2, 1, 1], gap="medium")
    with col_k1:
        kasa_tutar = st.number_input("Tutar ($)", min_value=1.0, value=100.0, step=10.0, key="k_tutar")
    with col_k2:
        kasa_aciklama = st.text_input("Açıklama", value="Ekstra sermaye" if islem_yatir else "Kasa çekimi", key="k_acik")
    with col_onay:
        st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
        if st.button("💾 Onayla", width='stretch', key="kasa_onayla"):
            basarili, mesaj = kasa_islem_ekle("Para_Yatir" if islem_yatir else "Para_Cek", kasa_tutar, kasa_aciklama)
            if basarili:
                st.success(mesaj)
                st.session_state["kasa_islem_acik"] = False
                time.sleep(1)
                st.rerun()
            else:
                st.error(mesaj)
    with col_kapat:
        st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
        if st.button("✖ Kapat", width='stretch', key="kasa_kapat"):
            st.session_state["kasa_islem_acik"] = False
            st.rerun()

st.markdown("---")

table_html = """<table class="custom-table"><thead class="custom-table-header"><tr><th>Logo</th><th>Coin<br>Adı</th><th>Güncel<br>Fiyat</th><th>Trend<br>Durumu</th><th>Piyasa &<br>Dominans</th><th>Matris<br>Puan & Teyit</th><th>Günlük<br>Değişim</th><th>Önerilen<br>Oran</th><th>Yatırım<br>Tutarı</th><th>Kar Al<br>Hedefi</th><th>Stop<br>Seviyesi</th><th>Risk / Hedef</th></tr></thead><tbody>"""
for v in islenen_veriler:
    fiyat_str = f"{v['Fiyat']:,.4f}&nbsp;$" if v["Basamak"] == 4 else f"{v['Fiyat']:,.2f}&nbsp;$"
    if v["Notr"]:
        kar_al_str, stopla_str, risk_hedef_gosterim = '<span style="color: #91a0b8;">Nötr</span>', '<span style="color: #91a0b8;">Nötr</span>', "Nötr"
    else:
        kar_al_str = f"{v['Kar_Al']:,.4f}&nbsp;$" if v["Basamak"] == 4 else f"{v['Kar_Al']:,.2f}&nbsp;$"
        stopla_str = f"{v['Stopla']:,.4f}&nbsp;$" if v["Basamak"] == 4 else f"{v['Stopla']:,.2f}&nbsp;$"
        risk_hedef_gosterim = v['Risk_Hedef_Metin']

    val_str = f"%{v['Sepet_Orani']:.1f}" if v['Sepet_Orani'] != int(v['Sepet_Orani']) else f"%{int(v['Sepet_Orani'])}"
    renk_yon = "#00FF00" if v['Aktif_Yon'] == "Long" else "rgb(255, 75, 0)"

    if v["Notr"]:
        oran_html = '<div style="background-color: rgba(255, 235, 59, 0.2); color: #e8eef8; padding: 5px; font-weight: bold;">%0<br>(Beklemede)</div>'
    else:
        oran_html = f'<div style="background-color: {renk_yon}; color: #000000; padding: 5px; font-weight: bold;">{val_str}<br>({v["Aktif_Yon"]})</div>'

    table_html += f"<tr><td>{v['Logo']}</td><td>{v['Coin']}</td><td style='font-weight: bold; color: #5b8cff; background-color: rgba(91, 140, 255, 0.08);'>{fiyat_str}</td><td>{v['Yon']}</td><td>{v['Dom_Sunumu']}</td><td style='background-color: rgba(0,0,0,0.02);'>{v['Matris_Puan_Sunumu']}</td><td>{v['Gunluk_Oran']}</td><td>{oran_html}</td><td>{v['Yatırım_Bedeli']}</td><td>{kar_al_str}</td><td>{stopla_str}</td><td style='font-weight: bold; color: #ff79c6;'>{risk_hedef_gosterim}</td></tr>"
table_html += "</tbody></table>"
st.markdown(f'<div class="table-container">{table_html}</div>', unsafe_allow_html=True)

col_sol_panel, col_orta_grafik, col_sag_endeks = st.columns([1.2, 2.5, 1.0])

with col_sol_panel:
    st.markdown("<h3>🚀 İşlem Emri Ver</h3>", unsafe_allow_html=True)
    df_gosterge = pd.DataFrame(islenen_veriler)
    df_gecmis_temp = islem_gecmisi_getir(sheet_guncelle=False)
    acik_coinler = []
    if not df_gecmis_temp.empty and "Durum" in df_gecmis_temp.columns:
        acik_mask = ~durum_kapali_maskesi(df_gecmis_temp["Durum"])
        acik_coinler = df_gecmis_temp[acik_mask]["Coin"].unique().tolist()

    if not df_gosterge.empty:
        df_islem_yapilabilir = df_gosterge[(~df_gosterge["Notr"] & (df_gosterge["Skor"] >= min_esik_bilgi)) | (df_gosterge["Coin"].isin(acik_coinler))]
    else:
        df_islem_yapilabilir = pd.DataFrame()

    coin_listesi = df_islem_yapilabilir["Coin"].tolist() if not df_islem_yapilabilir.empty else []
    secilen_coin = st.selectbox("İşlem Yapılacak Coin:", coin_listesi) if coin_listesi else None

    onerilen_oran_val, anlik_matris_puani, anlik_risk_hedef_metin, coin_verisii = 0.0, 0.0, "0,70 / 0,95", None
    if secilen_coin:
        coin_verisii = df_islem_yapilabilir[df_islem_yapilabilir["Coin"] == secilen_coin].iloc[0]
        onerilen_oran_val, anlik_matris_puani, anlik_risk_hedef_metin = float(coin_verisii["Sepet_Orani"]), float(coin_verisii["Skor"]), coin_verisii["Risk_Hedef_Metin"]

    acik_pozisyon_var = False
    if not df_gecmis_temp.empty and "Durum" in df_gecmis_temp.columns:
        acik_mask = ~durum_kapali_maskesi(df_gecmis_temp["Durum"])
        if secilen_coin and secilen_coin in df_gecmis_temp[acik_mask]["Coin"].values:
            acik_pozisyon_var = True

    onerilen_tutar_hesap = round(mevcut_bakiye * (onerilen_oran_val / 100.0), 2)

    # Risk bazlı üst sınır: işlem başı risk ve toplam risk (komisyon dahil)
    risk_mesaji, risk_eklenebilir = "", None
    if secilen_coin and coin_verisii is not None:
        try:
            _fiyat, _stop = float(coin_verisii["Fiyat"]), float(coin_verisii["Stopla"])
            _kap = risk_kapasitesi(toplam_kasa, df_gecmis_temp, secilen_coin, _fiyat, _stop)
            _mevcut_miktar = 0.0
            if acik_pozisyon_var:
                _acik_df = df_gecmis_temp[~durum_kapali_maskesi(df_gecmis_temp["Durum"])]
                _mevcut_miktar = float(_acik_df[_acik_df["Coin"] == secilen_coin]["Islem_Miktari"].iloc[0])
            risk_eklenebilir = max(0.0, _kap["azami"] - _mevcut_miktar)
            risk_mesaji = (f"🛡️ Risk sınırı: bu coinde azami toplam teminat {_kap['azami']:,.2f} $ "
                           f"(işlem başı risk %{ISLEM_BASINA_RISK_YUZDE:g} = {_kap['islem_limit']:,.2f} $, "
                           f"toplam risk payından kalan {_kap['kalan_toplam_risk']:,.2f} $), "
                           f"eklenebilir tutar {risk_eklenebilir:,.2f} $; komisyon: giriş %{KOMISYON_TAKER*100:g}, "
                           f"hedef çıkışı %{KOMISYON_MAKER*100:g}, stop çıkışı %{KOMISYON_TAKER*100:g}.")
            onerilen_tutar_hesap = round(min(onerilen_tutar_hesap, risk_eklenebilir), 2)
        except Exception as _e:
            print(f"Risk kapasitesi hesaplanamadı: {_e}")

    if acik_pozisyon_var:
        st.markdown("""<div style="background:linear-gradient(145deg,#1f2b3e,#162234); color:#e8eef8; border:1px solid #3b82f6; padding:12px; border-radius:10px; margin-bottom:12px; font-size:13px; line-height:1.8;"><div style="font-weight:750; color:#60a5fa; margin-bottom:4px;">🔄 Açık Pozisyona Ekleme Modu</div><div style="color:#dce6f5;">Bu coin için açık bir pozisyonunuz var. Girilen tutar ağırlıklı ortalama ile maliyete eklenecektir.</div></div>""", unsafe_allow_html=True)
    elif secilen_coin:
        st.markdown(f"""<div style="background:linear-gradient(145deg,#17263b,#111b2b); color:#e8eef8; border:1px solid #30415b; padding:12px; border-radius:10px; margin-bottom:12px; font-size:13px; line-height:1.8;"><div style="font-weight:750; color:#ffd166; margin-bottom:4px;">💡 Matris Önerisi (Oransal & Akışkan)</div><div style="color:#dce6f5;">Önerilen oran: <b style="color:#ffffff;">%{onerilen_oran_val:.1f}</b></div><div style="color:#dce6f5;">Önerilen tutar: <b style="color:#ffffff;">{onerilen_tutar_hesap:,.2f} $</b></div></div>""", unsafe_allow_html=True)

    if risk_mesaji:
        st.markdown(f'<div class="risk-line">{risk_mesaji.replace("$", "&#36;")}</div>', unsafe_allow_html=True)

    st.markdown('<div style="height: 5px;"></div>', unsafe_allow_html=True)

    if not st.session_state.get("islem_emri_kilit_acik", False):
        if st.button("🔓 İşlem Açma Kilidini Aç", width='stretch', key="btn_islem_kilidi_ac"):
            if coin_listesi:
                st.session_state["islem_emri_kilit_acik"] = True
                st.rerun()
            else:
                st.warning("Uygun işlem yapılacak coin bulunmuyor!")
    else:
        with st.form(key="manuel_islem_formu"):
            hesaplanan_tutar = min(100.0, float(mevcut_bakiye)) if acik_pozisyon_var else float(onerilen_tutar_hesap)
            if acik_pozisyon_var and risk_eklenebilir is not None:
                hesaplanan_tutar = min(hesaplanan_tutar, float(risk_eklenebilir))
            guvenli_tutar = max(0.0, float(hesaplanan_tutar))
            max_tutar = max(float(guvenli_tutar), float(mevcut_bakiye)) if mevcut_bakiye > 0 else 999999.0

            manuel_girilen_tutar = st.number_input("Tutar ($ Giriniz):", min_value=0.0, max_value=float(max_tutar), value=float(guvenli_tutar), step=10.0)
            st.markdown(f'<div style="font-size: 14px; font-weight: 800; color: #00FF00; padding: 5px 0 10px 0;">Boştaki Nakit: {mevcut_bakiye:,.2f} $</div>', unsafe_allow_html=True)
            
            col_islem_yap, col_kapat_kilit = st.columns(2)
            with col_islem_yap:
                submit_islem = st.form_submit_button("🔄 Ekleme Yap" if acik_pozisyon_var else "🚀 İşlemi Başlat", width='stretch')
            with col_kapat_kilit:
                kapat_kilit_tik = st.form_submit_button("🔒 Kilidi Kapat", width='stretch')
            if kapat_kilit_tik:
                st.session_state["islem_emri_kilit_acik"] = False
                st.rerun()

        if submit_islem:
            if not secilen_coin or coin_listesi == []:
                st.error("⚠️ Geçerli bir coin seçmelisiniz!")
            elif coin_verisii is not None:
                basari, mesaj = yeni_islem_ekle(secilen_coin, coin_verisii["Aktif_Yon"], coin_verisii["Fiyat"], manuel_girilen_tutar, coin_verisii["Stopla"], coin_verisii["Kar_Al"], "Oransal_Matris", anlik_matris_puani, anlik_risk_hedef_metin)
                if basari:
                    st.session_state["islem_emri_kilit_acik"] = False
                    st.success(mesaj)
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(mesaj)

with col_orta_grafik:
    st.markdown("<h3>🌐 Top 5 Coin (Oransal Omurga & Teknik Mıknatıs)</h3>", unsafe_allow_html=True)
    t_df_ham = total_ham_veri["df_market"]
    t_df = t_df_ham.tail(192).reset_index(drop=True)

    if not t_df.empty:
        delta = t_df["Close"].diff()
        rs = (delta.where(delta > 0, 0)).rolling(window=14).mean() / (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        t_df["RSI"] = (100 - (100 / (1 + rs))).fillna(50)

        min_f, max_f = float(t_df["Close"].min()), float(t_df["Close"].max())
        if max_f - min_f < (max_f * 0.0001):
            min_f, max_f = min_f * 0.999, max_f * 1.001

        fiyat_fark = max_f - min_f
        t_df["RSI_Norm"] = min_f + (t_df["RSI"] / 100.0) * fiyat_fark

        fib_levels = {
            -0.236: min_f - 0.236 * fiyat_fark,
            0.0: min_f, 0.236: min_f + 0.236 * fiyat_fark, 0.382: min_f + 0.382 * fiyat_fark,
            0.5: min_f + 0.5 * fiyat_fark, 0.618: min_f + 0.618 * fiyat_fark,
            0.786: min_f + 0.786 * fiyat_fark, 1.0: max_f,
            1.236: max_f + 0.236 * fiyat_fark,
        }

        min_zaman, max_zaman_grafik = t_df["timestamp"].min(), t_df["timestamp"].max() + pd.Timedelta(hours=1)
        alt_sinir, ust_sinir = min_f - (fiyat_fark * 0.28), max_f + (fiyat_fark * 0.28)

        fig_total = go.Figure()
        # Zemin: her fibonacci aralığı kendi düz rengiyle (degrade yok): altta bordo -> ortada sarı -> üstte koyu yeşil
        _seviyeler = sorted(fib_levels.keys())
        _bant_renkleri = [
            (96, 10, 36),    # -0.236 – 0      bordo
            (130, 30, 30),   # 0 – 0.236       koyu kırmızı
            (158, 72, 18),   # 0.236 – 0.382   turuncu-kahve
            (148, 110, 6),   # 0.382 – 0.5     koyu amber
            (192, 172, 14),  # 0.5 – 0.618     açık sarı
            (92, 128, 22),   # 0.618 – 0.786   sarı-yeşil
            (24, 104, 40),   # 0.786 – 1       yeşil
            (8, 70, 30),     # 1 – 1.236       koyu yeşil
        ]
        for _i in range(len(_seviyeler) - 1):
            _rgb = _bant_renkleri[min(_i, len(_bant_renkleri) - 1)]
            fig_total.add_hrect(y0=fib_levels[_seviyeler[_i]], y1=fib_levels[_seviyeler[_i + 1]],
                                fillcolor=f"rgb{_rgb}", opacity=1, line_width=0, layer="below")
        for oran, val in fib_levels.items():
            _ton = "255,235,59" if oran == 0.5 else ("0,255,0" if oran > 0.5 else "255,75,0")
            fig_total.add_hline(y=val, line_width=1.0, line_dash="dot", line_color=f"rgba({_ton},0.65)")
            # Etiket: kutu yok; yazı rengi seviyenin altındaki bandın rengi (aynı ton, koyu zeminde okunsun diye parlaklaştırılmış)
            _j = _seviyeler.index(oran)
            _cr = _bant_renkleri[max(0, min(_j - 1, len(_bant_renkleri) - 1))]
            _kat = 235.0 / max(_cr)
            _yazi = tuple(min(255, int(round(c * _kat))) for c in _cr)
            fig_total.add_annotation(x=1.0, xref="paper", y=val, yref="y", text=f"<b>{oran:g}</b>", showarrow=False,
                                     xanchor="left", xshift=8, font=dict(size=12, color=f"rgb{_yazi}"))

        MAVI_CIZGI, RSI_CIZGI = "rgb(0, 0, 175)", "rgb(255, 255, 0)"
        fig_total.add_trace(go.Scatter(
            x=t_df["timestamp"], y=t_df["Close"], mode="lines", name="Total Market",
            line=dict(color=MAVI_CIZGI, width=2.4, shape="spline", smoothing=0.6),
            hovertemplate="Total Market: %{y:,.2f}<extra></extra>"))
        fig_total.add_trace(go.Scatter(
            x=t_df["timestamp"], y=t_df["RSI_Norm"], mode="lines", name="RSI",
            line=dict(color=RSI_CIZGI, width=1.5, shape="spline", smoothing=0.6),
            customdata=t_df["RSI"], hovertemplate="RSI: %{customdata:.0f}<extra></extra>"))
        fig_total.add_trace(go.Scatter(
            x=[t_df["timestamp"].iloc[-1]], y=[t_df["Close"].iloc[-1]], mode="markers",
            marker=dict(size=9, color=MAVI_CIZGI, line=dict(color="#ffffff", width=2)), showlegend=False, hoverinfo="skip"))

        fig_total.update_layout(
            template="plotly_dark", margin=dict(t=28, b=32, l=8, r=86), height=340,
            xaxis=dict(range=[min_zaman, max_zaman_grafik], dtick=3600000, tickformat="%H:%M", tickangle=0,
                       tickfont=dict(size=12, color="#c3cfe2"), showgrid=True, gridcolor="rgba(255,255,255,0.16)", gridwidth=1,
                       zeroline=False, showline=False),
            yaxis=dict(showticklabels=False, range=[alt_sinir, ust_sinir], showgrid=False, zeroline=False),
            xaxis_rangeslider_visible=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            hovermode="x unified", hoverlabel=dict(bgcolor="#101827", bordercolor="#253247", font=dict(color="#e8eef8", size=12)),
            legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, font=dict(color="#aebdd2", size=11), bgcolor="rgba(0,0,0,0)"),
        )
        try:
            _grafik_kap = st.container(key="grafik_total")
        except TypeError:
            _grafik_kap = st.container()
        with _grafik_kap:
            st.plotly_chart(fig_total, width='stretch', config={"displayModeBar": False})

with col_sag_endeks:
    st.markdown("<h3>Top 5 Coin Endeksi</h3>", unsafe_allow_html=True)
    t_toplam_puan = t_l_puan + t_s_puan
    t_yuzde = (t_l_puan / t_toplam_puan * 100.0) if t_toplam_puan > 0 else 50.0
    t_yesil_led = max(0, min(10, round((t_yuzde / 100.0) * 10.0)))
    t_kirmizi_led = 10 - t_yesil_led

    st.markdown(f'<div style="text-align: center; line-height: 1.2; margin-bottom: 6px;"><div style="font-size: 14px; margin-bottom: 2px; letter-spacing: 1px;">{"🟢" * t_yesil_led}{"🔴" * t_kirmizi_led}</div><div style="font-size: 10px; font-weight: 600;"><span style="color: #00FF00; display: inline-block; width: 8px; height: 8px; background-color: #00FF00; border-radius: 50%; margin-right: 2px;"></span>%{t_yuzde:.1f} | <span style="color: rgb(255, 75, 0); display: inline-block; width: 8px; height: 8px; background-color: rgb(255, 75, 0); border-radius: 50%; margin-left: 2px; margin-right: 2px;"></span>%{100.0 - t_yuzde:.1f}</div></div>', unsafe_allow_html=True)

    t_zaman_kat = total_ham_veri["zaman_katkilari"]
    boxes_listesi = []
    for etk, veri in t_zaman_kat.items():
        sl, ss = veri["sl"], veri["ss"]
        y_ad, k_ad = veri["y_adet"], veri["k_adet"]
        kazanan_renk = "#00FF00" if sl >= ss else "rgb(255, 75, 0)"
        boxes_listesi.append(f'<div style="background-color: {kazanan_renk}; color: #000000; padding: 6px; border-radius: 6px; text-align: center; font-weight: bold; font-size: 11px; margin-bottom: 5px; line-height: 1.3;">{etk}<br>L: {sl:.2f}p | S: {ss:.2f}p</div>')
    boxes_birlestirilmis = "".join(boxes_listesi)

    st.markdown(f'<div class="metric-container" style="text-align: center; padding: 10px !important;"><div style="font-size: 12px; font-weight: bold; margin-bottom: 6px;">Top 5 Ortalama Değeri: <span style="color: #5b8cff;">${total_ham_veri["anlik_fiyat"] / 1e12:.2f}T</span><br>Puan: <span style="color: {"#00FF00" if total_ham_veri["aktif_yon"] == "Long" else ("rgb(255, 75, 0)" if total_ham_veri["aktif_yon"] == "Short" else "#ffc107")};">{total_ham_veri["nihai_puan"]:.1f} / 100 ({total_ham_veri["aktif_yon"]})</span></div>{boxes_birlestirilmis}</div>', unsafe_allow_html=True)

st.markdown("---")

df_gecmis = islem_gecmisi_getir(sheet_guncelle=False)
acik_islem_listesi = df_gecmis[~durum_kapali_maskesi(df_gecmis["Durum"])]["Islem_ID"].tolist() if not df_gecmis.empty and "Durum" in df_gecmis.columns else []

col_sol_analiz, col_orta_durum, col_sag_sonlandir = st.columns([2.5, 1, 1], gap="medium")

with col_sol_analiz:
    st.markdown("<h3>📊 Kapanan İşlemler & Para Akışı Analizi</h3>", unsafe_allow_html=True)
    kapananlar_df = pd.DataFrame() if df_gecmis.empty or "Durum" not in df_gecmis.columns else df_gecmis[durum_kapali_maskesi(df_gecmis["Durum"])]

    if not kapananlar_df.empty:
        karli_sayisi, zararli_sayisi = 0, 0
        toplam_kazanc_dolar, toplam_kayip_dolar = 0.0, 0.0
        for _, r in kapananlar_df.iterrows():
            val = float(pd.to_numeric(r["Net_Kar_Zarar"], errors="coerce") or 0.0)
            if val >= 0:
                karli_sayisi += 1
                toplam_kazanc_dolar += val
            else:
                zararli_sayisi += 1
                toplam_kayip_dolar += abs(val)

        toplam_kapanan = len(kapananlar_df)
        net_fark_dolar = toplam_kazanc_dolar - toplam_kayip_dolar
        kar_yuzde = (karli_sayisi / toplam_kapanan * 100.0) if toplam_kapanan > 0 else 0.0
        zarar_yuzde = (zararli_sayisi / toplam_kapanan * 100.0) if toplam_kapanan > 0 else 0.0

        sub_p1, sub_p2, sub_p3 = st.columns([1.35, 1.35, 1.35], gap="medium")
        with sub_p1:
            fig = px.pie(
                pd.DataFrame({"Durum": ["Kârlı", "Zararlı"], "Adet": [karli_sayisi, zararli_sayisi]}),
                names="Durum", values="Adet", hole=0.50, color="Durum",
                color_discrete_map={"Kârlı": "#00FF00", "Zararlı": "rgb(255, 75, 0)"}
            )
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#e8eef8", size=13), margin=dict(t=10, b=10, l=10, r=10), height=210, showlegend=False)
            fig.update_traces(textfont_size=13, textinfo="percent", marker=dict(line=dict(width=0)))
            st.plotly_chart(fig, width='stretch', config={"responsive": True, "displayModeBar": False})

        with sub_p2:
            st.markdown(f"""<div style="font-size: 15px; font-weight: bold; color: #e8eef8; margin-bottom: 4px;">📈 Strateji Metrikleri</div><p style="margin: 4px 0px 0px 0px; font-size: 13px; color: #91a0b8;">Toplam Kapanan</p><p style="margin: 0px; font-size: 18px; font-weight: bold; color: #e8eef8;">{toplam_kapanan} Adet</p><p style="margin: 8px 0px 0px 0px; font-size: 14px; color: #00FF00; font-weight: bold;">🟢 Kârlı: {karli_sayisi} (%{kar_yuzde:.1f})</p><p style="margin: 5px 0px 0px 0px; font-size: 14px; color: rgb(255, 75, 0); font-weight: bold;">🔴 Zararlı: {zararli_sayisi} (%{zarar_yuzde:.1f})</p><p style="margin: 10px 0px 0px 0px; padding-top: 6px; border-top: 1px solid #30415b; font-size: 14px; font-weight: bold; color: {'#00FF00' if kar_yuzde >= 50 else 'rgb(255, 75, 0)'};">🎯 Başarı Oranı: %{kar_yuzde:.1f}</p>""", unsafe_allow_html=True)

        with sub_p3:
            net_renk = "#00FF00" if net_fark_dolar >= 0 else "rgb(255, 75, 0)"
            toplam_hareket_dolar = toplam_kazanc_dolar + toplam_kayip_dolar
            parasal_basari_yuzde = (toplam_kazanc_dolar / toplam_hareket_dolar * 100.0) if toplam_hareket_dolar > 0 else 0.0
            parasal_renk = "#00FF00" if parasal_basari_yuzde >= 50 else "rgb(255, 75, 0)"
            st.markdown(f"""<div style="font-size: 15px; font-weight: bold; color: #e8eef8; margin-bottom: 4px;">💰 Finansal Metrikler</div><p style="margin: 4px 0px 0px 0px; font-size: 13px; color: #91a0b8;">Net Fark</p><p style="margin: 0px; font-size: 18px; font-weight: bold; color: {net_renk};">{net_fark_dolar:+,.2f} $</p><p style="margin: 8px 0px 0px 0px; font-size: 14px; color: #00FF00; font-weight: bold;">Toplam Kâr: +{toplam_kazanc_dolar:,.2f} $</p><p style="margin: 5px 0px 0px 0px; font-size: 14px; color: rgb(255, 75, 0); font-weight: bold;">Toplam Zarar: -{toplam_kayip_dolar:,.2f} $</p><p style="margin: 10px 0px 0px 0px; padding-top: 6px; border-top: 1px solid #30415b; font-size: 14px; font-weight: bold; color: {parasal_renk};">💵 Parasal Başarı Oranı: %{parasal_basari_yuzde:.1f}</p>""", unsafe_allow_html=True)
    else:
        st.info("ℹ️ Henüz kapanmış işlem bulunmuyor.")

def _ac_kapat_toggle(anahtar):
    st.session_state[anahtar] = not st.session_state.get(anahtar, False)

def _rapor_cb():
    """Tüm işlemler + kasa + para akışı + analiz içeren A4 PDF raporu üretip e-posta ile gönderir."""
    try:
        st.cache_data.clear()
        df_t = islem_gecmisi_getir()
        df_k = kasa_defteri_getir()
        bak = bakiye_durumunu_getir(ortak_fiyat_havuzu)
        fiyatlar = {c: ortak_fiyat_havuzu.get(c, baz_fiyatlar.get(c, 0.0)) for c in (df_t["Coin"].unique() if df_t is not None and not df_t.empty else [])}
        pdf_b, hata = rapor_pdf_olustur(df_t, df_k, bak, fiyatlar, tr_zaman())
        if pdf_b is None:
            st.session_state["kart_kapat_mesaj"] = (False, f"Rapor oluşturulamadı: {hata}")
            return
        dosya_adi = f"portfoy_raporu_{tr_zaman().strftime('%Y%m%d_%H%M')}.pdf"
        ok_m, msg_m = rapor_maili_gonder(pdf_b, dosya_adi, bak, tr_zaman())
        if ok_m:
            st.session_state.pop("rapor_pdf", None)
            st.session_state["kart_kapat_mesaj"] = (True, f"Rapor e-posta ile gönderildi ({dosya_adi}, {len(pdf_b) / 1024:.0f} KB).")
        else:
            ok_t, msg_t = rapor_telegram_gonder(pdf_b, dosya_adi, bak, tr_zaman())
            if ok_t:
                st.session_state.pop("rapor_pdf", None)
                st.session_state["kart_kapat_mesaj"] = (True, f"Mail gönderilemedi ({msg_m}) ama rapor Telegram'a gönderildi ({dosya_adi}).")
            else:
                st.session_state["rapor_pdf"] = (pdf_b, dosya_adi)
                st.session_state["kart_kapat_mesaj"] = (False, f"Rapor oluşturuldu ama gönderilemedi. Mail: {msg_m} | Telegram: {msg_t}. Raporu aşağıdan indirebilirsiniz.")
    except Exception as e:
        st.session_state["kart_kapat_mesaj"] = (False, f"Rapor hatası: {e}")

def _tum_kapat_cb():
    """Kriz anı: onay işaretliyse tüm açık işlemleri güncel fiyattan tamamen kapatır."""
    try:
        if not st.session_state.get("tum_kapat_acik", False):
            return
        st.cache_data.clear()
        df_t = islem_gecmisi_getir()
        acik_t = df_t[~durum_kapali_maskesi(df_t["Durum"])] if df_t is not None and not df_t.empty else pd.DataFrame()
        if acik_t.empty:
            st.session_state["kart_kapat_mesaj"] = (True, "Kapatılacak açık işlem yok.")
            st.session_state["tum_kapat_acik"] = False
            return
        basarili, hatalar = 0, []
        for _, r in acik_t.iterrows():
            coin_t = r["Coin"]
            try:
                fiyat_t = fiyat_cek_binance(coin_t) or ortak_fiyat_havuzu.get(coin_t, baz_fiyatlar.get(coin_t, 100.0))
            except Exception:
                fiyat_t = ortak_fiyat_havuzu.get(coin_t, baz_fiyatlar.get(coin_t, 100.0))
            ok_t, msg_t = manuel_islem_kapat(int(r["Islem_ID"]), fiyat_t, kapatilacak_miktar=None)
            if ok_t:
                basarili += 1
            else:
                hatalar.append(f"#{int(r['Islem_ID'])} {coin_t}: {msg_t}")
        metin = f"{basarili}/{len(acik_t)} işlem kapatıldı."
        if hatalar:
            metin += " Kapatılamayanlar: " + " | ".join(hatalar)
        st.session_state["kart_kapat_mesaj"] = (not hatalar, metin)
        st.session_state["tum_kapat_acik"] = False
    except Exception as e:
        st.session_state["kart_kapat_mesaj"] = (False, f"Toplu kapatma hatası: {e}")

with col_orta_durum:
    st.markdown("<h3>👁️ İşlem Sunumu</h3>", unsafe_allow_html=True)
    st.markdown('<div style="height: 8px;"></div>', unsafe_allow_html=True)
    if st.button("Aktif İşlemler", width='stretch'):
        st.session_state["sadece_aktifleri_goster"] = True
        st.rerun()
    if st.button("Tüm İşlemler", width='stretch'):
        st.session_state["sadece_aktifleri_goster"] = False
        st.rerun()
    st.caption("Görünüm: Aktif işlemler" if st.session_state["sadece_aktifleri_goster"] else "Görünüm: Tüm işlemler")
    st.button("Aktif İşlemleri Sonlandır", key="btn_tum_ac", width="stretch", on_click=_ac_kapat_toggle, args=("tum_kapat_acik",))
    if st.session_state.get("tum_kapat_acik", False):
        st.button("🛑 TÜM İŞLEMLERİ KAPAT", key="btn_tum_kapat", width="stretch", on_click=_tum_kapat_cb)
    st.button("Tüm İşlemleri Raporla", key="btn_rapor", width="stretch", on_click=_rapor_cb)
    if "rapor_pdf" in st.session_state:
        _pdf_b, _pdf_ad = st.session_state["rapor_pdf"]
        st.download_button("📄 Raporu indir (mail gönderilemedi)", data=_pdf_b, file_name=_pdf_ad, mime="application/pdf", width="stretch")

with col_sag_sonlandir:
    st.markdown("<h3>🛡️ Risk & Kâr Özeti</h3>", unsafe_allow_html=True)
    st.markdown(risk_kar_ozeti_html(df_gecmis, toplam_kasa, efektif_kasa, mevcut_bakiye, aktif_yatirim_tutari, toplam_acik_kz), unsafe_allow_html=True)

st.markdown("---")

if "kart_kapat_mesaj" in st.session_state:
    _ok_m, _msg_m = st.session_state.pop("kart_kapat_mesaj")
    (st.success if _ok_m else st.error)(_msg_m)

df_gecmisile_goster = islem_gecmisi_getir(sheet_guncelle=False)
df_gosterilecek = pd.DataFrame()
if not df_gecmisile_goster.empty:
    df_gosterilecek = df_gecmisile_goster[~durum_kapali_maskesi(df_gecmisile_goster["Durum"])] if st.session_state["sadece_aktifleri_goster"] else df_gecmisile_goster.copy()

anlik_fiyat_sozluk, anlik_kz_sozluk, hedef_kar_sozluk, olasi_stop_sozluk = {}, {}, {}, {}
if not df_gecmisile_goster.empty:
    for _, row in df_gecmisile_goster.iterrows():
        islem_id, coin, giris_fiyat, miktar, kar_al_f, stop_f, yon = (
            row["Islem_ID"], row["Coin"], float(row["Giris_Fiyat"]),
            float(row["Islem_Miktari"]), float(row["Kar_Al"]), float(row["Stop"]), row["Yon"]
        )
        anl_f = ortak_fiyat_havuzu.get(coin, baz_fiyatlar.get(coin, 100.0))
        anlik_fiyat_sozluk[islem_id] = anl_f
        hedef_kar_sozluk[islem_id], olasi_stop_sozluk[islem_id] = canli_beklenen_olasi(row)

        if not ("kapandi" in str(row["Durum"]).lower() or "kar" in str(row["Durum"]).lower() or "zarar" in str(row["Durum"]).lower() or "kısmi" in str(row["Durum"]).lower()):
            anlik_kz_sozluk[islem_id] = round(miktar * KALDIRAC * (((anl_f - giris_fiyat) / giris_fiyat) if "Long" in yon else ((giris_fiyat - anl_f) / giris_fiyat)) - cikis_komisyonu(miktar, False), 2)
        else:
            anlik_kz_sozluk[islem_id] = float(row["Net_Kar_Zarar"])

# ---- Açık pozisyon kartları (yalnızca "Aktif İşlemler" görünümünde) ----
def _kart_kapat_cb(islem_id, coin, miktar):
    """Kapatma butonu: açılan alan açıksa tamamını ya da girilen tutarı kapatır.
    Callback içinde çalıştığı için işlem sonrası alan ve tutar güvenle sıfırlanır."""
    onay_k, tutar_k = f"kart_ac_{islem_id}", f"kismi_tutar_{islem_id}"
    try:
        if not st.session_state.get(onay_k, False):
            return
        girilen = float(st.session_state.get(tutar_k, miktar))
        if girilen <= 0:
            st.session_state["kart_kapat_mesaj"] = (False, "Kapatılacak tutar 0'dan büyük olmalıdır!")
            return
        hedef_miktar = None if girilen >= float(miktar) - 0.005 else girilen
        try:
            fiyat_k = fiyat_cek_binance(coin) or ortak_fiyat_havuzu.get(coin, baz_fiyatlar.get(coin, 100.0))
        except Exception:
            fiyat_k = ortak_fiyat_havuzu.get(coin, baz_fiyatlar.get(coin, 100.0))
        ok_k, msg_k = manuel_islem_kapat(int(islem_id), fiyat_k, kapatilacak_miktar=hedef_miktar)
        st.session_state["kart_kapat_mesaj"] = (ok_k, msg_k)
        if ok_k:
            st.session_state[onay_k] = False
            if tutar_k in st.session_state:
                del st.session_state[tutar_k]
    except Exception as e:
        st.session_state["kart_kapat_mesaj"] = (False, f"Kapatma hatası: {e}")

if st.session_state["sadece_aktifleri_goster"]:
    st.markdown("<h3>🧭 Açık Pozisyonlar</h3>", unsafe_allow_html=True)
    _df_acik_kart = df_gecmisile_goster[~durum_kapali_maskesi(df_gecmisile_goster["Durum"])] if not df_gecmisile_goster.empty else pd.DataFrame()
    if _df_acik_kart.empty:
        st.info("Şu an açık pozisyon yok.")
    else:
        try:
            _kart_alani = st.container(key="poz_kartlari")
        except TypeError:
            _kart_alani = st.container()
        with _kart_alani:
            _satirlar = [_df_acik_kart.iloc[i:i + 5] for i in range(0, len(_df_acik_kart), 5)]
            for _grup in _satirlar:
                _kolonlar = st.columns(5)
                for _k, (_, _r) in zip(_kolonlar, _grup.iterrows()):
                    with _k:
                        _id = int(_r["Islem_ID"])
                        st.markdown(pozisyon_karti_html(_r, anlik_fiyat_sozluk.get(_r["Islem_ID"]), logo_urls.get(_r["Coin"], ""), toplam_kasa), unsafe_allow_html=True)
                        _miktar = float(_r["Islem_Miktari"])
                        st.button(f"{_id} ID İşlemini Sonlandır", key=f"btn_kart_ac_{_id}", width="stretch",
                                  on_click=_ac_kapat_toggle, args=(f"kart_ac_{_id}",))
                        if st.session_state.get(f"kart_ac_{_id}", False):
                            _etiket = "🛑 İşlemi Kapat"
                            _tutar = st.number_input("Kapatılacak tutar ($) — tamamı için bırakın", min_value=0.01, max_value=_miktar,
                                                     value=_miktar, step=10.0, key=f"kismi_tutar_{_id}")
                            if _tutar < _miktar - 0.005:
                                _etiket = f"✂️ Kısmi Kapat ({_tutar:,.2f} $)"
                            st.button(_etiket, key=f"btn_kart_kapat_{_id}", width="stretch",
                                      on_click=_kart_kapat_cb, args=(_id, _r["Coin"], _miktar))
else:
    st.markdown("<h3>📋 Tüm İşlemler</h3>", unsafe_allow_html=True)

# HTML Portföy Tablosu (Zaman Dilimi sütunu başlık ve satırlardan kaldırıldı, E-Tablo sıralaması korunuyor)
portfoy_html = """<table class="custom-table"><thead class="custom-table-header"><tr><th>ID</th><th>Açılış</th><th>Logo</th><th>Coin</th><th>Yön</th><th>Giriş</th><th>Anlık</th><th>Kapanış</th><th>Matris Puanı</th><th>Yatırım</th><th>Hedef</th><th>Stop</th><th>Beklenen Kâr</th><th>Olası Stop</th><th>Durum</th><th>Anlık K/Z</th><th>Kapanış Zamanı</th><th>Güncel Kasa</th></tr></thead><tbody>"""

if not df_gosterilecek.empty:
    df_gecmis_copy = df_gosterilecek.copy()
    df_gecmis_copy["Anlik_Fiyat_Deger"] = df_gecmis_copy["Islem_ID"].map(anlik_fiyat_sozluk)
    df_gecmis_copy["Canli_Beklenen_Kar"] = df_gecmis_copy["Islem_ID"].map(hedef_kar_sozluk)
    df_gecmis_copy["Canli_Olasi_Stop"] = df_gecmis_copy["Islem_ID"].map(olasi_stop_sozluk)
    df_gecmis_copy["Anlik_KZ_Deger"] = df_gecmis_copy["Islem_ID"].map(anlik_kz_sozluk)

    for _, row in df_gecmis_copy.iterrows():
        logo_h = f'<img src="{logo_urls.get(row["Coin"], "")}" width="24" height="24">'
        yon_h = f'<div style="background-color: {"#00FF00" if "Long" in row["Yon"] else "rgb(255, 75, 0)"}; padding: 6px; border-radius: 6px; color: #000000; font-weight: bold;">{row["Yon"]}</div>'
        anlik_fiyat_h = f'<div style="background-color: {"#00FF00" if float(row["Anlik_Fiyat_Deger"] or 0) > float(row["Giris_Fiyat"]) else "rgb(255, 75, 0)"}; color: #000000; padding: 5px; font-weight: bold;">{float(row["Anlik_Fiyat_Deger"] or 0):,.{4 if row["Coin"] == "XRP/USDT" else 2}f}&nbsp;$</div>'

        if not ("kapandi" in str(row["Durum"]).lower() or "kar" in str(row["Durum"]).lower() or "zarar" in str(row["Durum"]).lower() or "kısmi" in str(row["Durum"]).lower()):
            kapanis_fiyat_h, durum_h = '<div style="padding: 5px; color: #91a0b8;">-</div>', '<div style="background-color: #5b8cff; color: white; padding: 4px; border-radius: 4px; font-weight: bold;">Aktif</div>'
        else:
            is_kar = float(row["Net_Kar_Zarar"]) >= 0
            sinif = "kar-hucre" if is_kar else "zarar-hucre"
            kapanis_fiyat_h = f'<div class="{sinif}">{float(row.get("Kapanis_Fiyati", 0.0) or row["Giris_Fiyat"]):,.{4 if row["Coin"] == "XRP/USDT" else 2}f}&nbsp;$</div>'
            durum_h = f'<div class="{sinif}">{row["Durum"]}</div>'

        kz_h = f'<div style="background-color: {"#00FF00" if float(row["Anlik_KZ_Deger"] or 0) >= 0 else "rgb(255, 75, 0)"}; color: #000000; padding: 5px; font-weight: bold; white-space: nowrap;">{float(row["Anlik_KZ_Deger"] or 0):+,.2f}&nbsp;$</div>'

        matris_puan_rh_metin = str(row.get('Matris_Puan_RH', '55.0 (Nötr)'))
        islem_miktari_val = float(row['Islem_Miktari'])
        basamak_degeri = 4 if row['Coin'] == 'XRP/USDT' else 2
        kar_al_formatli = f"{float(row['Kar_Al']):,.{basamak_degeri}f}&nbsp;$"
        stop_formatli = f"{float(row['Stop']):,.{basamak_degeri}f}&nbsp;$"
        canli_beklenen_kar_val = float(row['Canli_Beklenen_Kar'])
        canli_olasi_stop_val = float(row['Canli_Olasi_Stop'])
        guncel_kasa_val = float(row['Guncel_Kasa'])
        giris_fiyat_val = float(row['Giris_Fiyat'])

        portfoy_html += f"<tr><td>{row['Islem_ID']}</td><td>{row['Acilis_Zamani']}</td><td>{logo_h}</td><td>{row['Coin']}</td><td>{yon_h}</td><td>{giris_fiyat_val:,.{basamak_degeri}f}&nbsp;$</td><td>{anlik_fiyat_h}</td><td>{kapanis_fiyat_h}</td><td style='font-weight: bold; color: #91a0b8;'>{matris_puan_rh_metin}</td><td>{islem_miktari_val:,.2f}&nbsp;$</td><td>{kar_al_formatli}</td><td>{stop_formatli}</td><td>{canli_beklenen_kar_val:,.2f}&nbsp;$</td><td>{canli_olasi_stop_val:,.2f}&nbsp;$</td><td>{durum_h}</td><td>{kz_h}</td><td>{row['Kapanis_Zamani']}</td><td>{guncel_kasa_val:,.2f}&nbsp;$</td></tr>"
else:
    portfoy_html += "<tr><td colspan='18' style='text-align: center; color: #91a0b8; padding: 20px;'>Kayıtlı işlem bulunmuyor.</td></tr>"

portfoy_html += "</tbody></table>"
if not st.session_state["sadece_aktifleri_goster"]:
    st.markdown(f'<div class="table-container">{portfoy_html}</div>', unsafe_allow_html=True)
