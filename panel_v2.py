import time
import threading
import json
import os
import smtplib
import matris_motoru
import kasa_motoru
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

# --- TELEFON ALGILAMA (tarayıcı kimliğinden; tablet masaüstü düzenini kullanır) ---
def _mobil_mi():
    try:
        ua = str(st.context.headers.get("User-Agent", "")).lower()
        return any(k in ua for k in ("mobile", "android", "iphone", "ipod"))
    except Exception:
        return False

IS_MOBIL = _mobil_mi()

# --- OTOMATİK YENİLEME (60 SANİYE) ---
# İşlem emri kilidi açıkken (kullanıcı işlem yaparken) otomatik yenileme durdurulur.
if not st.session_state.get("islem_emri_kilit_acik", False):
    st_autorefresh(interval=60000, key="kripto_panel_otomatik_yenileme")
    
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
.pos-logo { width:26px; height:26px; object-fit:contain; flex:none; }
.pos-name { font-size:17px; font-weight:800; color:#e8eef8; white-space:nowrap; }
.pos-sub { display:flex; align-items:center; gap:5px; margin-top:2px; }
.pos-id { color:var(--muted); font-size:13px; }
.pill { padding:1px 8px; border-radius:999px; font-size:13px; font-weight:700; border:1px solid; }
.pill-long { color:#00FF00; border-color:rgba(0,255,0,.45); background:rgba(0,255,0,.08); }
.pill-short { color:rgb(255,75,0); border-color:rgba(255,75,0,.5); background:rgba(255,75,0,.10); }
.pos-kz { font-size:23px; font-weight:800; text-align:right; line-height:1.1; white-space:nowrap; }
.pos-kz small { display:block; font-size:13px; font-weight:600; opacity:.8; }
.range-wrap { margin:14px 0 8px; }
.range-bar { position:relative; height:7px; border-radius:6px; background:linear-gradient(90deg,rgba(255,75,0,.60),rgba(145,160,184,.22) 50%,rgba(0,255,0,.50)); }
.range-tick { position:absolute; top:-4px; width:2px; height:15px; background:#91a0b8; border-radius:2px; transform:translateX(-1px); }
.range-dot { position:absolute; top:-5px; width:17px; height:17px; border-radius:50%; background:#e8eef8; border:3px solid #5b8cff; transform:translateX(-8px); box-shadow:0 0 0 3px rgba(91,140,255,.18); }
.range-lbl { display:flex; justify-content:space-between; margin-top:11px; font-size:14px; font-weight:700; gap:4px; }
.range-dist { display:flex; justify-content:space-between; align-items:baseline; margin-top:3px; font-size:14px; color:var(--muted); gap:4px; }
.range-mid { color:#e8eef8; font-weight:800; font-size:16px; }
.pos-meta { display:flex; justify-content:space-between; gap:6px; flex-wrap:wrap; font-size:14px; color:var(--muted); margin-top:8px; }
.pos-meta b { color:#e8eef8; font-weight:700; }
.bar-bg { height:6px; border-radius:6px; background:#1b2a40; overflow:hidden; }
.bar-mini { height:4px; margin-top:5px; }
.bar-fill { height:100%; border-radius:6px; transition:width .4s; }
.pos-detay { margin-top:8px; font-size:14px; color:var(--muted); }
.pos-detay summary { cursor:pointer; color:#8fa0ba; }
.pos-detay-ic { padding-top:5px; line-height:1.6; }
.risk-card { background:linear-gradient(145deg,#141f31,#0f1726); border:1px solid var(--border); border-radius:16px; padding:14px 18px; margin:6px 0 14px; }
.risk-top { display:flex; justify-content:space-between; align-items:baseline; gap:8px; flex-wrap:wrap; margin-bottom:8px; }
.risk-title { font-size:13px; font-weight:700; color:#e8eef8; }
.risk-val { font-size:15px; font-weight:800; font-variant-numeric:tabular-nums; }
.risk-val small { font-weight:600; color:var(--muted); }
.risk-note { font-size:10px; color:var(--muted); margin-top:7px; }
.ozet-card { background:linear-gradient(145deg,#141f31,#0f1726); border:1px solid var(--border); border-radius:14px; padding:14px 16px; font-variant-numeric:tabular-nums; }
.ozet-satir { display:flex; justify-content:space-between; align-items:baseline; gap:8px; font-size:15px; color:var(--muted); padding:8px 0; border-bottom:1px solid #1d2a40; }
.ozet-satir:last-child { border-bottom:none; }
.ozet-alt { text-align:center; font-size:13px; color:var(--muted); margin-top:6px; }
.ozet-bos { text-align:center; color:var(--muted); font-size:14px; padding:8px 0 12px; }
.ozet-card .range-wrap { margin:6px 0 10px; padding-bottom:6px; border-bottom:1px solid #1d2a40; }
.ozet-satir b { font-size:17px; font-weight:800; white-space:nowrap; }
.ozet-card .range-lbl, .ozet-card .range-dist { font-size:13px; }
.ozet-card .range-mid { font-size:17px; }
.mx-wrap { min-width:118px; font-variant-numeric:tabular-nums; }
.mx-puan { font-weight:800; font-size:16px; }
.mx-yon { font-size:13px; font-weight:700; }
.mx-bar { position:relative; height:6px; border-radius:6px; margin:8px 6px 5px; background:linear-gradient(90deg,rgba(255,75,0,.60),rgba(145,160,184,.22) 50%,rgba(0,255,0,.50)); }
.mx-dot { position:absolute; top:-4px; width:14px; height:14px; border-radius:50%; background:#e8eef8; border:3px solid #5b8cff; transform:translateX(-7px); box-shadow:0 0 0 2px rgba(91,140,255,.18); }
.mx-lbl { display:flex; justify-content:space-between; font-size:13px; font-weight:700; }
.st-key-btn_tum_kapat button { background:rgb(255,75,0) !important; color:#000 !important; font-weight:800 !important; border:none !important; }
.risk-line { font-size:13px; line-height:1.55; color:#e8eef8; margin:4px 0 8px; }
.st-key-grafik_total [data-testid="stPlotlyChart"] { border:1px solid var(--border) !important; border-radius:14px !important; background:linear-gradient(145deg,#141f31,#0f1726) !important; padding:6px 4px 0 !important; overflow:hidden !important; box-sizing:content-box !important; }
.st-key-grafik_total [data-testid="stPlotlyChart"] > div, .st-key-grafik_total .js-plotly-plot, .st-key-grafik_total .plot-container { overflow:hidden !important; }
</style>
""",
    unsafe_allow_html=True,
)

# --- SABİTLER ---
GOOGLE_SHEET_DOSYA = "KriptoPortfoyVeritabani"
BASLANGIC_BAKIYE = 0.0   # kasa sıfırdan başlar; ilk sermaye eklemesiyle belirlenir
KALDIRAC = 5

# --- Komisyon ve risk ayarları (Binance USDⓈ-M Futures, standart kullanıcı / VIP 0) ---
KOMISYON_TAKER = 0.0005         # %0,05: piyasa emriyle giriş ve stop çıkışı
KOMISYON_MAKER = 0.0002         # %0,02: limit emirle hedef (kâr al) çıkışı
ISLEM_BASINA_RISK_YUZDE = 1.0   # tek işlemin (komisyon dahil) stop riski: kasanın en fazla %1'i
TOPLAM_RISK_LIMIT_YUZDE = 3.0   # tüm açık işlemlerin toplam stop riski: kasanın en fazla %3'ü
MAKS_POZISYON_ORANI = 1.0       # TEMİNAT TAVANI: tek pozisyonun büyüklüğü (teminat × kaldıraç) en fazla toplam kasanın bu katı.
                                # Stop dar olduğu için risk formülü büyük teminata izin verir; hızlı harekette stop kayarsa
                                # kaybı sınırlamak için bu tavan her zaman uygulanır ("risk sınırını aş" onayı bunu aşmaz).

KALDIRAC_MAX = 10   # seçilebilecek en yüksek kaldıraç

def satir_kaldiraci(row):
    """Bir işlem satırının kaldıracı (Kaldirac kolonu). Kayıt yoksa/geçersizse varsayılan KALDIRAC."""
    try:
        v = float(row.get("Kaldirac", 0) or 0)
    except Exception:
        v = 0.0
    return v if v >= 1 else float(KALDIRAC)

def giris_komisyonu(miktar, kaldirac=None):
    k = float(kaldirac) if kaldirac else float(KALDIRAC)
    return float(miktar) * k * KOMISYON_TAKER

def cikis_komisyonu(miktar, hedef_mi, kaldirac=None):
    """Hedef (limit emir) maker, stop ve manuel kapanış (piyasa emri) taker öder."""
    k = float(kaldirac) if kaldirac else float(KALDIRAC)
    return float(miktar) * k * (KOMISYON_MAKER if hedef_mi else KOMISYON_TAKER)

def giris_komisyon_toplami(df_kasa, id_araligi=None):
    """Kasa defterindeki tüm 'Giriş Komisyonu' kayıtlarının toplamı (pozitif sayı).
    Net K/Z'ler işlem satırında yalnızca çıkış komisyonunu içerir; giriş komisyonu deftere ayrıca yazılır."""
    try:
        if df_kasa is None or df_kasa.empty or "Islem_Turu" not in df_kasa.columns:
            return 0.0
        m = (df_kasa["Islem_Turu"] == "Komisyon") & df_kasa["Aciklama"].astype(str).str.contains("Giriş Komisyonu", regex=False)
        if id_araligi:
            _idler = pd.to_numeric(df_kasa["Aciklama"].astype(str).str.extract(r"#(\d+)")[0], errors="coerce")
            m = m & (_idler >= int(id_araligi[0])) & (_idler <= int(id_araligi[1]))
        return float(pd.to_numeric(df_kasa.loc[m, "Tutar"], errors="coerce").fillna(0.0).abs().sum())
    except Exception:
        return 0.0

def beklenen_ve_olasi(long_mi, miktar, giris, kar_al, stop, kaldirac=None):
    """Hedefe/stopa ulaşılırsa kalan K/Z (işlemin kaldıracıyla)."""
    kaldirac = float(kaldirac) if kaldirac else float(KALDIRAC)
    if long_mi:
        brut_kar = miktar * kaldirac * ((kar_al - giris) / giris)
        brut_stop = miktar * kaldirac * ((stop - giris) / giris)
    else:
        brut_kar = miktar * kaldirac * ((giris - kar_al) / giris)
        brut_stop = miktar * kaldirac * ((giris - stop) / giris)
    return brut_kar - cikis_komisyonu(miktar, True, kaldirac), brut_stop - cikis_komisyonu(miktar, False, kaldirac)

def canli_beklenen_olasi(row):
    """Açık işlem: hedef/stop değerlerini GÜNCEL kaldıraç ve komisyonla hesaplar."""
    try:
        if not durum_kapali_mi(row["Durum"]):
            giris = float(row["Giris_Fiyat"])
            if giris > 0:
                return beklenen_ve_olasi("Long" in str(row["Yon"]), float(row["Islem_Miktari"]), giris, float(row["Kar_Al"]), float(row["Stop"]), satir_kaldiraci(row))
    except Exception:
        pass
    return float(row["Beklenen_Kar"]), float(row["Olasi_Stop"])

def stop_riski(miktar, giris, stop, kaldirac=None):
    """Stop vurulursa olası toplam zarar (pozitif): fiyat zararı + giriş ve çıkış komisyonu."""
    kaldirac = float(kaldirac) if kaldirac else float(KALDIRAC)
    if giris <= 0:
        return 0.0
    return float(miktar) * kaldirac * (abs(stop - giris) / giris + 2 * KOMISYON_TAKER)

def acik_pozisyonlar_riski(df, haric_coin=None, haric_yon=None):
    if df is None or df.empty or "Durum" not in df.columns:
        return 0.0
    acik = df[~durum_kapali_maskesi(df["Durum"])]
    toplam = 0.0
    for _, r in acik.iterrows():
        if haric_coin is not None and r["Coin"] == haric_coin and (haric_yon is None or haric_yon in str(r["Yon"])):
            continue
        toplam += stop_riski(float(r["Islem_Miktari"]), float(r["Giris_Fiyat"]), float(r["Stop"]), satir_kaldiraci(r))
    return toplam

def risk_kapasitesi(toplam_kasa, df, coin, giris, stop, kaldirac=None, yon=None):
    """Bu coin için izin verilen azami toplam teminat."""
    stop_oran = abs(stop - giris) / giris if giris > 0 else 0.0
    birim = (float(kaldirac) if kaldirac else float(KALDIRAC)) * (stop_oran + 2 * KOMISYON_TAKER)
    islem_limit = max(0.0, toplam_kasa) * ISLEM_BASINA_RISK_YUZDE / 100.0
    toplam_limit = max(0.0, toplam_kasa) * TOPLAM_RISK_LIMIT_YUZDE / 100.0
    diger = acik_pozisyonlar_riski(df, haric_coin=coin, haric_yon=("Long" if yon and "Long" in str(yon) else ("Short" if yon else None)))
    kalan = max(0.0, toplam_limit - diger)
    azami = min(islem_limit, kalan) / birim if birim > 0 else 0.0
    lev_ = float(kaldirac) if kaldirac else float(KALDIRAC)
    tavan = max(0.0, toplam_kasa) * float(MAKS_POZISYON_ORANI) / lev_
    return {"azami": azami, "tavan": tavan, "islem_limit": islem_limit, "kalan_toplam_risk": kalan, "diger_risk": diger, "birim": birim}

# ====================== GÖRSEL BİLEŞENLER ======================
RENK_YESIL, RENK_KIRMIZI, RENK_SARI = "#00FF00", "rgb(255, 75, 0)", "#f5c451"

def _fmt_fiyat(v):
    return f"{v:,.4f}" if abs(v) < 10 else f"{v:,.2f}"

def _risk_rengi(oran):
    return RENK_YESIL if oran < 0.6 else (RENK_SARI if oran < 0.9 else RENK_KIRMIZI)

def risk_kar_ozeti_html(df, toplam_kasa, efektif_kasa, bos_bakiye, marjin, acik_kz):
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
    t = str(s_).strip()
    return (t[:6] + t[8:16]) if len(t) >= 16 and t[2] == "." and t[5] == "." else t

def _rapor_fiyat(v):
    try:
        v = float(v)
    except Exception:
        return "-"
    return _rapor_sayi(v, 4 if abs(v) < 10 else 2)

def _rapor_fontlari_kaydet():
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

def rapor_pdf_olustur(df_trade, df_kasa, bakiye, fiyatlar, zaman, id_araligi=None):
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
        return None, "reportlab kurulu değil."

    try:
        FONT, FONT_B, ttf_var = _rapor_fontlari_kaydet()
        T = (lambda x: str(x)) if ttf_var else (lambda x: str(x).translate(_TR_YEDEK_TABLO))

        toplam_kasa, efektif_kasa, bos_bakiye, marjin, acik_kz = [float(x) for x in bakiye]
        YESIL, KIRMIZI = colors.HexColor("#0a8f3c"), colors.HexColor("#d9480f")
        NEON_Y, NEON_T = colors.HexColor("#00FF00"), colors.HexColor("#ff4b00")
        LACIVERT, GRI, ACIK = colors.HexColor("#14213d"), colors.HexColor("#5f6b7a"), colors.HexColor("#eef2f7")

        cols = ["Islem_ID", "Acilis_Zamani", "Coin", "Yon", "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Beklenen_Kar",
                "Olasi_Stop", "Durum", "Net_Kar_Zarar", "Kapanis_Zamani", "Kapanis_Fiyati"]
        dt = df_trade.copy() if df_trade is not None and not df_trade.empty else pd.DataFrame(columns=cols)
        if id_araligi and not dt.empty:   # Dönem raporu: yalnızca seçilen ID aralığı
            _idn = pd.to_numeric(dt["Islem_ID"], errors="coerce").fillna(0).astype(int)
            dt = dt[(_idn >= int(id_araligi[0])) & (_idn <= int(id_araligi[1]))].copy()
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
        
        toplam_yatirilan = float(dk.loc[dk["Islem_Turu"].isin(["EKLE", "Para_Yatir"]), "Tutar"].sum())
        toplam_cekilen = float(dk.loc[dk["Islem_Turu"].isin(["CEK", "Para_Cek"]), "Tutar"].sum())
        net_para_girisi = toplam_yatirilan - toplam_cekilen
        anapara = BASLANGIC_BAKIYE + net_para_girisi
        getiri = ((efektif_kasa - anapara) / anapara * 100.0) if anapara > 0 else 0.0
        giris_kom_top = giris_komisyon_toplami(dk, id_araligi)
        gerceklesen_brut = float(kap["Net_Kar_Zarar"].sum())   # çıkış komisyonu düşülmüş
        gerceklesen = gerceklesen_brut - giris_kom_top          # giriş komisyonları da düşülmüş (net)

        idler = pd.to_numeric(dt["Islem_ID"], errors="coerce").dropna().astype(int) if not dt.empty else pd.Series([], dtype=int)
        id_min, id_max = (int(idler.min()), int(idler.max())) if len(idler) else (0, 0)
        acilislar = pd.to_datetime(dt["Acilis_Zamani"], format="%d.%m.%Y %H:%M", errors="coerce").dropna() if not dt.empty else pd.Series([], dtype="datetime64[ns]")
        ilk_acilis = acilislar.min() if len(acilislar) else None
        
        id_baslangic_kasa = float(BASLANGIC_BAKIYE)
        id_sonu_kasa = toplam_kasa
        if id_araligi and not dt.empty:
            # Dönem: kasa değerlerini defter hareketlerinden, dönemin başlangıç/bitiş anına göre hesapla
            def _isaretli(r_):
                _t = str(r_["Islem_Turu"]).lower()
                if any(k_ in _t for k_ in ["yatir", "satim", "gelir", "ekle"]):
                    return r_["Tutar"]
                if any(k_ in _t for k_ in ["cek", "alim", "gider", "komisyon", "zarar"]):
                    return -abs(r_["Tutar"])
                return r_["Tutar"]
            _dk_i = dk.copy()
            _dk_i["_i"] = _dk_i.apply(_isaretli, axis=1)
            if ilk_acilis is not None:
                id_baslangic_kasa = float(_dk_i.loc[_dk_i["_z"] < ilk_acilis, "_i"].sum())
            _son_kapanis = pd.to_datetime(kap["Kapanis_Zamani"], format="%d.%m.%Y %H:%M", errors="coerce").max() if not kap.empty else None
            if len(acik) == 0 and _son_kapanis is not None and pd.notna(_son_kapanis):
                id_sonu_kasa = float(_dk_i.loc[_dk_i["_z"] <= _son_kapanis, "_i"].sum())

        net = kap["Net_Kar_Zarar"]
        n_kap = len(kap)
        kaz, kay = net[net > 0], net[net < 0]
        isabet = (len(kaz) / n_kap * 100.0) if n_kap else 0.0
        pf = (kaz.sum() / abs(kay.sum())) if len(kay) and kay.sum() != 0 else None

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

        W = A4[0] - 24 * mm

        def halka(d, cx, cy, r_dis, r_ic, parcalar):
            baslangic = 90.0
            for oran, renk in parcalar:
                if oran <= 0:
                    continue
                aci = 360.0 * oran
                bitis = baslangic - aci
                a1, a2 = (bitis, baslangic)
                if aci >= 359.9:
                    for (x1, x2) in ((a1, a1 + 180.0), (a1 + 180.0, a2)):
                        d.add(Wedge(cx, cy, r_dis, x1, x2, radius1=r_ic, fillColor=renk, strokeColor=None, strokeWidth=0))
                else:
                    d.add(Wedge(cx, cy, r_dis, a1, a2, radius1=r_ic, fillColor=renk, strokeColor=None, strokeWidth=0))
                baslangic = bitis

        def metrik_paneli(kdf):
            """Panelle aynı düzen: solda Finansal (kâr/zarar $) donutu + metinleri, sağda Strateji (kârlı/zararlı adet) donutu + metinleri."""
            import math as _m
            from reportlab.pdfbase.pdfmetrics import stringWidth as _sw
            h = 165
            d = Drawing(W, h)
            d.add(Rect(0, 0, W, h, rx=12, ry=12, fillColor=colors.HexColor("#070b14"), strokeColor=colors.HexColor("#1b2a40"), strokeWidth=0.8))
            ac_gri, beyaz = colors.HexColor("#91a0b8"), colors.HexColor("#e8eef8")
            if kdf is None or len(kdf) == 0:
                d.add(String(W / 2 - 60, h / 2, T("Kapanan işlem yok"), fontName=FONT, fontSize=10, fillColor=ac_gri))
                return d
            v = pd.to_numeric(kdf["Net_Kar_Zarar"], errors="coerce").fillna(0.0)
            karli, zararli = int((v >= 0).sum()), int((v < 0).sum())
            toplam = karli + zararli
            kazanc, kayip = float(v[v >= 0].sum()), float(abs(v[v < 0].sum()))
            net_fark = kazanc - kayip - giris_kom_top
            k_y, z_y = (karli / toplam * 100.0), (zararli / toplam * 100.0)
            hareket = kazanc + kayip
            parasal = (kazanc / hareket * 100.0) if hareket > 0 else 0.0
            sayi = lambda x, isaretli=True: (f"{x:+,.2f}" if isaretli else f"{x:,.2f}").replace(",", "X").replace(".", ",").replace("X", ".")
            r_dis, r_ic, cy = 40, 18, h / 2 - 2
            r_orta = (r_dis + r_ic) / 2.0
            yarim = W / 2.0

            def donut(cx, oran_k, etiket_k, etiket_z):
                """oran_k: yeşil (kâr) dilim oranı 0..1. Veri yoksa gri halka."""
                if oran_k is None:
                    halka(d, cx, cy, r_dis, r_ic, [(1.0, colors.HexColor("#25344d"))])
                    return
                oran_z = 1.0 - oran_k
                halka(d, cx, cy, r_dis, r_ic, [(oran_k, NEON_Y), (oran_z, NEON_T)])
                baslangic_a = 90.0
                for oran_, yazi_, renk_ in ((oran_k, etiket_k, colors.HexColor("#0b3d0b")), (oran_z, etiket_z, colors.white)):
                    if oran_ <= 0.06:      # çok ince dilimde yazı sığmaz
                        baslangic_a -= 360.0 * oran_
                        continue
                    orta_a = baslangic_a - 360.0 * oran_ / 2.0
                    d.add(String(cx + r_orta * _m.cos(_m.radians(orta_a)), cy + r_orta * _m.sin(_m.radians(orta_a)) - 2.5, yazi_,
                                 fontName=FONT_B, fontSize=6.5, fillColor=renk_, textAnchor="middle"))
                    baslangic_a -= 360.0 * oran_

            def uygun_fs(x, sag_kenar, kalemler, fs=11.5):
                """Etiket + değer en uzun satırda bile yarım panele sığacak yazı boyutu."""
                bosluk, kullanilabilir = 4.0, sag_kenar - x - 12
                en_uzun = max(_sw(T(e), FONT, fs) + bosluk + _sw(T(dg), FONT_B, fs) for e, dg, _ in kalemler)
                return fs if en_uzun <= kullanilabilir else max(6.5, fs * kullanilabilir / en_uzun)

            def satirlar(x, baslik, kalemler, fs):
                d.add(String(x, h - 24, T(baslik), fontName=FONT_B, fontSize=13, fillColor=beyaz))
                y = h - 50
                for etiket_, deger_, renk_ in kalemler:
                    d.add(String(x, y, T(etiket_), fontName=FONT, fontSize=fs, fillColor=ac_gri))
                    d.add(String(x + _sw(T(etiket_), FONT, fs) + 4.0, y, T(deger_), fontName=FONT_B, fontSize=fs, fillColor=renk_))
                    y -= 21

            d.add(Line(yarim, 14, yarim, h - 14, strokeColor=colors.HexColor("#25344d"), strokeWidth=0.6))
            renk_p = NEON_Y if parasal >= 50 else NEON_T
            renk_b = NEON_Y if k_y >= 50 else NEON_T

            # --- sol yarı: Finansal Metrikler ---
            fin_kalem = [
                ("Net Kâr:", sayi(net_fark) + " $", NEON_Y if net_fark >= 0 else NEON_T),
                ("Giriş Komisyonu:", "-" + sayi(giris_kom_top, False) + " $", NEON_T),
                ("Toplam Kâr:", sayi(kazanc) + " $", NEON_Y),
                ("Toplam Zarar:", (("-" + sayi(kayip, False)) if kayip > 0 else "0,00") + " $", NEON_T),
                ("Parasal Başarı:", f"%{parasal:.1f}", renk_p),
            ]
            str_kalem = [
                ("Toplam Kapanan:", f"{toplam} Adet", beyaz),
                ("Kârlı:", f"{karli} Adet (%{k_y:.1f})", NEON_Y),
                ("Zararlı:", f"{zararli} Adet (%{z_y:.1f})", NEON_T),
                ("Başarı Oranı:", f"%{k_y:.1f}", renk_b),
            ]
            # iki yarıda da aynı yazı boyutu (ikisine de sığan en büyük)
            fs_ortak = min(uygun_fs(104, yarim, fin_kalem), uygun_fs(yarim + 104, W, str_kalem))
            donut(52, (kazanc / hareket) if hareket > 0 else None, f"%{parasal:.1f}", f"%{100 - parasal:.1f}")
            satirlar(104, "Finansal Metrikler", fin_kalem, fs_ortak)
            # --- sağ yarı: Strateji Metrikleri ---
            donut(yarim + 52, karli / toplam, f"%{k_y:.1f}", f"%{z_y:.1f}")
            satirlar(yarim + 104, "Strateji Metrikleri", str_kalem, fs_ortak)
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
        story.append(Paragraph(T(f"Tüm tutarlar USDT · işlem bazlı kaldıraç (varsayılan {KALDIRAC}x) · ") + f'{etiket("Id Başlangıç Kasa :")} <font name="{FONT_B}" color="#222222">{_rapor_sayi(id_baslangic_kasa, 0 if abs(id_baslangic_kasa - round(id_baslangic_kasa)) < 0.005 else 2)} $</font>', st_ust))
        story.append(Paragraph(f'{etiket("Id Sonu Kasa :")} <font name="{FONT_B}" color="{sonu_renk}">{_rapor_sayi(id_sonu_kasa, 0 if abs(id_sonu_kasa - round(id_sonu_kasa)) < 0.005 else 2)} $</font>', st_ust))
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
            kpi("Anapara", f"{_rapor_sayi(anapara)} $"),
            kpi("Toplam getiri", ("-" if getiri < 0 else "") + f"%{_rapor_sayi(abs(getiri))}", kz_r(getiri)),
        ]
        grid = [[hucreler[i], hupers[i + 1] if False else hucreler[i+1], hucreler[i + 2], hucreler[i + 3]] for i in (0, 4)]
        kt = Table(grid, colWidths=[W / 4.0] * 4)
        kt.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#c9d1dc")), ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dfe5ee")),
                                ("BACKGROUND", (0, 0), (-1, -1), ACIK), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
        story.append(kt)

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
            [T("Toplam giriş komisyonu"), f"-{_rapor_sayi(giris_kom_top)} $", T("Net K/Z (giriş kom. dahil)"), f"{_rapor_sayi(gerceklesen)} $"],
        ]
        an_t = Table(satirlar, colWidths=[W * 0.22, W * 0.28, W * 0.22, W * 0.28])
        an_t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FONT), ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                                  ("FONTNAME", (0, 0), (0, -1), FONT_B), ("FONTNAME", (2, 0), (2, -1), FONT_B),
                                  ("TEXTCOLOR", (0, 0), (0, -1), GRI), ("TEXTCOLOR", (2, 0), (2, -1), GRI),
                                  ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, ACIK]), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                                  ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#c9d1dc"))]))
        story.append(an_t)

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
        return None, f"{type(e).__name__}: {e}"

def _secret_bul(anahtar):
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
    sifre = _gmail_sifresi_bul().replace(" ", "")
    if not sifre:
        return False, "GMAIL_PASSWORD bulunamadı."
    toplam_kasa, efektif_kasa, bos_bakiye, marjin, acik_kz = [float(x) for x in bakiye]
    govde = (f"<h3>Kripto Portföy Raporu</h3><p>Oluşturulma: {zaman.strftime('%d.%m.%Y %H:%M')}</p>"
             f"<p><b>Toplam kasa:</b> {toplam_kasa:,.2f} $<br><b>Efektif kasa:</b> {efektif_kasa:,.2f} $<br>"
             f"<b>Anlık K/Z (net):</b> {acik_kz:+,.2f} $<br><b>Boş nakit:</b> {bos_bakiye:,.2f} $</p>")
    msg = MIMEMultipart()
    msg["From"], msg["To"], msg["Subject"] = gonderici_mail, alici_mail, f"📄 Portföy Raporu - {zaman.strftime('%d.%m.%Y %H:%M')}"
    msg.attach(MIMEText(govde, "html", "utf-8"))
    ek = MIMEApplication(pdf_bytes, _subtype="pdf")
    ek.add_header("Content-Disposition", "attachment", filename=dosya_adi)
    msg.attach(ek)
    govde_metni = msg.as_string()

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30)
        server.login(gonderici_mail, sifre)
        server.sendmail(gonderici_mail, [alici_mail], govde_metni)
        server.quit()
        return True, "E-posta gönderildi."
    except Exception as e:
        return False, f"Gmail hatası: {e}"

def rapor_telegram_gonder(pdf_bytes, dosya_adi, bakiye, zaman):
    token, chat_id = _secret_bul("TELEGRAM_BOT_TOKEN"), _secret_bul("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False, "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID yok"
    toplam_kasa, efektif_kasa, bos_bakiye, marjin, acik_kz = [float(x) for x in bakiye]
    aciklama = f"📄 Portföy Raporu {zaman.strftime('%d.%m.%Y %H:%M')}\nToplam kasa: {toplam_kasa:,.2f} $"
    try:
        yanit = requests.post(f"https://api.telegram.org/bot{token}/sendDocument", data={"chat_id": chat_id, "caption": aciklama},
                              files={"document": (dosya_adi, pdf_bytes, "application/pdf")}, timeout=40)
        if yanit.status_code == 200 and yanit.json().get("ok"):
            return True, "Telegram'a gönderildi."
        return False, f"Telegram yanıtı: {yanit.status_code}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

def matris_birlesik_html(nihai_puan, aktif_yon, y_yuzde, k_yuzde):
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
    lev = satir_kaldiraci(row)
    kz = miktar * lev * fark - cikis_komisyonu(miktar, False, lev)
    kz_yuzde = (kz / miktar * 100.0) if miktar > 0 else 0.0
    kz_renk = RENK_YESIL if kz >= 0 else RENK_KIRMIZI

    aralik = hedef - stop
    t_anlik = min(1.0, max(0.0, (anl_f - stop) / aralik)) if aralik else 0.5
    t_giris = min(1.0, max(0.0, (giris - stop) / aralik)) if aralik else 0.5
    stopa = abs(anl_f - stop) / anl_f * 100.0
    hedefe = abs(hedef - anl_f) / anl_f * 100.0

    islem_risk = stop_riski(miktar, giris, stop, lev)
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
            f'<div class="pos-head"><div class="pos-left">{logo}<div><div class="pos-name">{coin}</div><div class="pos-sub">{pill}<span class="pos-id">#{int(row["Islem_ID"])}</span><span class="pos-id">{lev:g}x</span></div></div></div>'
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
    # Başlangıç eşiği hafta içi 50, hafta sonu (sığ piyasa) 55 olarak güncellendi.
    return 55.0 if hafta_sonu_mu() else 50.0

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

# --- BİNANCE API ENTEGRASYONU ---
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter

_HTTP = requests.Session()
_HTTP.mount("https://", HTTPAdapter(pool_connections=20, pool_maxsize=20))
_SON_ENDPOINT = {"i": 0}   # son başarılı endpoint önce denenir (yanıt vermeyen sunucuda beklemeyi önler)

def _binance_get_json(urls, timeout):
    i0 = _SON_ENDPOINT["i"] % len(urls)
    for u in urls[i0:] + urls[:i0]:
        try:
            r = _HTTP.get(u, timeout=timeout)
            if r.status_code == 200:
                _SON_ENDPOINT["i"] = urls.index(u)
                return r.json()
        except Exception:
            continue
    return None

@st.cache_data(ttl=30)
def fiyat_cek_binance(coin_symbol):
    if coin_symbol == "TOTAL":
        try:
            btc = fiyat_cek_binance("BTC/USDT")
            eth = fiyat_cek_binance("ETH/USDT")
            bnb = fiyat_cek_binance("BNB/USDT")
            sol = fiyat_cek_binance("SOL/USDT")
            xrp = fiyat_cek_binance("XRP/USDT")
            
            _fiyatlar_ = {"BTC/USDT": btc, "ETH/USDT": eth, "BNB/USDT": bnb, "SOL/USDT": sol, "XRP/USDT": xrp}
            tahmini_total = sum(_fiyatlar_[c_] * a_ for c_, a_ in matris_motoru.TOP5_ARZ.items())
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
    veri = _binance_get_json(endpoints, 3)
    try:
        if veri is not None:
            val = float(veri["price"])
            if val > 0:
                return val
    except Exception:
        pass
    return baz_fiyatlar.get(coin_symbol, 100.0)

@st.cache_data(ttl=60)
def kline_cek_binance(coin_symbol, interval, limit):
    sym = coin_symbol.replace("/", "")
    endpoints = [
        f"https://data-api.binance.vision/api/v3/klines?symbol={sym}&interval={interval}&limit={limit}",
        f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={interval}&limit={limit}",
    ]
    data = _binance_get_json(endpoints, 5)
    if data is not None:
        try:
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
        except Exception:
            pass
    return pd.DataFrame()

@st.cache_data(ttl=30)
def load_15min_market_data(coin_symbol: str):
    limit = 192
    if coin_symbol == "TOTAL":
        # BTC değil: 5 coinin piyasa değeri ağırlıklı endeksi (Σ arz × fiyat)
        df_t = matris_motoru.birlesik_endeks({c_: kline_cek_binance(c_, "5m", limit) for c_ in matris_motoru.TOP5_ARZ})
        return df_t if df_t is not None else pd.DataFrame()

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

import numpy as np

STOP_YUZDESI = 0.50   # fiyat yüzdesi (kaldıraçtan bağımsız); tüm puanlarda sabit
# (puan, hedef %) - 50 altı en alt satır, 75 üstü en üst satır değerini alır
HEDEF_TABLOSU = [(50.0, 0.45), (55.0, 0.50), (59.0, 0.60), (63.0, 0.65), (67.0, 0.75), (71.0, 0.80), (75.0, 0.85)]

def calculate_coin_metrics_by_score(matris_puani):
    """Matris puanına göre (stop %, hedef %, metin) döner. Stop sabit %0,50; hedef tablodan doğrusal ara değerlemeyle."""
    xs = [p_ for p_, _ in HEDEF_TABLOSU]
    ys = [h_ for _, h_ in HEDEF_TABLOSU]
    hedef_uzde = float(np.interp(float(matris_puani), xs, ys))
    stop_uzde = float(STOP_YUZDESI)
    str_stop = f"{stop_uzde:.2f}".replace(".", ",")
    str_hedef = f"{hedef_uzde:.2f}".replace(".", ",")
    return stop_uzde, hedef_uzde, f"{str_stop} / {str_hedef}"

def pozisyon_kar_zarar_hesapla(yon, giris_fiyati, guncel_fiyat, yatirim_miktari, kaldirac=1.0):
    """
    Long ve Short işlemler için doğru kaldıraçlı Kâr/Zarar (USD) hesaplaması.
    """
    if giris_fiyati <= 0:
        return 0.0

    # Yön bazlı fiyat değişim oranı
    if yon.strip().lower() in ["long", "alış"]:
        fiyat_farki_yuzde = (guncel_fiyat - giris_fiyati) / giris_fiyati
    else:  # Short / Satış
        fiyat_farki_yuzde = (giris_fiyati - guncel_fiyat) / giris_fiyati

    # PnL = Yatırım Miktarı * Fiyat Değişim Yüzdesi * Kaldıraç
    pnl_usd = yatirim_miktari * fiyat_farki_yuzde * kaldirac
    return round(pnl_usd, 2)

def _kline_limitleri():
    """Her mum aralığı için gereken en uzun pencere (5m grafik için en az 192). Kısa pencereler bundan kesilir."""
    lim = {"5m": 192}
    for _e, _aralik, _mum, _w in matris_motoru.DILIMLER:
        lim[_aralik] = max(lim.get(_aralik, 0), int(_mum) + int(matris_motoru.ISITMA_MUM))
    return lim

KLINE_LIMITLERI = _kline_limitleri()

def kline_pencere(sembol, aralik, mum):
    """Puanlanan 'mum' adedi + ısınma mumlarını döndürür (EMA/RSI/ATR oturması için). TOTAL: 5 coinlik endeks mumları."""
    limit = KLINE_LIMITLERI.get(aralik, mum + matris_motoru.ISITMA_MUM)
    if sembol == "TOTAL":
        df = matris_motoru.birlesik_endeks({c_: kline_cek_binance(c_, aralik, limit) for c_ in matris_motoru.TOP5_ARZ})
    else:
        df = kline_cek_binance(sembol, aralik, limit)
    return df.tail(mum + matris_motoru.ISITMA_MUM) if df is not None and not df.empty else df

def piyasa_verisini_paralel_isit(semboller):
    """Fiyat ve mum verilerini paralel çekip önbelleğe alır; sonraki sıralı hesaplar önbellekten gelir."""
    gorevler, goruldu = [], set()

    def ekle(f, *a):
        k = (f.__name__,) + a
        if k not in goruldu:
            goruldu.add(k)
            gorevler.append((f, a))

    for sembol_ in semboller:
        ekle(fiyat_cek_binance, sembol_)
        if sembol_ == "TOTAL":
            continue    # TOTAL, 5 coinin kendi mumlarından türetilir (coinler zaten listede)
        for _aralik, _limit in KLINE_LIMITLERI.items():
            ekle(kline_cek_binance, sembol_, _aralik, _limit)

    ctx_ = get_script_run_ctx() if get_script_run_ctx is not None else None

    def calistir(g):
        f, a = g
        try:
            if ctx_ is not None and add_script_run_ctx is not None:
                add_script_run_ctx(threading.current_thread(), ctx_)
            f(*a)
        except Exception as e:
            print(f"Ön yükleme hatası ({f.__name__} {a}): {e}")

    with ThreadPoolExecutor(max_workers=12) as havuz:
        list(havuz.map(calistir, gorevler))

@st.cache_data(ttl=60, show_spinner=False)
def _matris_puanlari(sembol_istek):
    """Mum verisinden matris puanlarını hesaplar (veri zaten 60 sn önbellekte olduğundan sonuç da öyle tutulur)."""
    pencereler = [(etiket, kline_pencere(sembol_istek, aralik, mum_sayisi), agirlik, mum_sayisi)
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
    return nihai_puan, aktif_yon, nihai_long, nihai_short, zaman_katkilari

def kurgusal_matris_hesapla(coin_symbol):
    anlik_fiyat = fiyat_cek_binance(coin_symbol)          # fiyat her zaman 30 sn'den taze
    nihai_puan, aktif_yon, nihai_long, nihai_short, zaman_katkilari = _matris_puanlari(coin_symbol)
    return anlik_fiyat, nihai_puan, aktif_yon, nihai_long, nihai_short, zaman_katkilari

def _servis_hesabi_sozlugu():
    sec = {k: (v.strip() if isinstance(v, str) else v) for k, v in dict(st.secrets["gcp_service_account"]).items()}
    sec.pop("GMAIL_PASSWORD", None)
    pk = str(sec.get("private_key", ""))
    pk = pk.replace("\\n", "\n")
    sec["private_key"] = pk.strip()
    sec["token_uri"] = "https://oauth2.googleapis.com/token"
    sec["auth_uri"] = "https://accounts.google.com/o/oauth2/auth"
    sec["universe_domain"] = "googleapis.com"
    return sec

def _hata_ozeti(e):
    return f"{type(e).__name__}: {str(e)[:160]}"

# Dün Kasa Motorunda kullandığımız kusursuz ID bağlantısına geçiyoruz
GOOGLE_SHEET_ID = "1likk2RqtqxPxj7nSNDroxT6GQGrQXJmfx-SoyHswgyo"

@st.cache_resource(ttl=3600)
def _sayfa_nesnesi(sayfa_adi):
    client = gspread.service_account_from_dict(_servis_hesabi_sozlugu())
    sh = client.open_by_key(GOOGLE_SHEET_ID)
    try:
        return sh.worksheet(sayfa_adi)
    except gspread.exceptions.WorksheetNotFound:
        # Eğer sekme (KriptoPortfoyVeritabani) henüz E-Tabloda yoksa, çökme; otomatik oluştur!
        return sh.add_worksheet(title=sayfa_adi, rows="1000", cols="20")

_SON_SHEETS_HATASI = {"mesaj": ""}

def google_sheets_baglan(sayfa_adi):
    try:
        return _sayfa_nesnesi(sayfa_adi)
    except Exception as e:
        _SON_SHEETS_HATASI["mesaj"] = _hata_ozeti(e)
        return None

@st.cache_data(ttl=15)
def islem_gecmisi_getir(sheet_guncelle=True):
    beklenen_kolonlar = [
        "Islem_ID", "Acilis_Zamani", "Coin", "Yon", "Zaman_Dilimi",
        "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Beklenen_Kar",
        "Matris_Puan_RH", "Olasi_Stop", "Durum", "Net_Kar_Zarar",
        "Guncel_Kasa", "Kapanis_Zamani", "Kapanis_Fiyati", "Kaldirac", "Seviye_Zamani"
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
    
    sayisal_kolonlar = [
        "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Beklenen_Kar",
        "Olasi_Stop", "Net_Kar_Zarar", "Guncel_Kasa", "Kapanis_Fiyati", "Kaldirac"
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
    # Eski kayıtlarda Kaldirac boştur: varsayılan kaldıraç atanır
    if "Kaldirac" in df.columns:
        df["Kaldirac"] = df["Kaldirac"].where(df["Kaldirac"] >= 1, float(KALDIRAC))
    return df

def dataframe_guncelle_gsheets(df):
    sheet = google_sheets_baglan("KriptoPortfoyVeritabani")
    basarili = False
    if sheet is not None:
        try:
            df = df.copy()
            df["Islem_ID"] = df["Islem_ID"].astype(int)
            df = df.sort_values(by="Islem_ID").reset_index(drop=True)
            veri_listesi = [df.columns.tolist()] + df.values.tolist()
            eski_satir_sayisi = len(sheet.get_all_values())
            
            try:
                sheet.update(values=veri_listesi, range_name="A1")
            except TypeError:
                sheet.update(veri_listesi)
                
            if eski_satir_sayisi > len(veri_listesi):
                sheet.batch_clear([f"A{len(veri_listesi) + 1}:Z{eski_satir_sayisi}"])
            basarili = True
        except Exception as e:
            st.error(f"GSheets Yazma Hatası: {e}")
    else:
        st.error(f"Bağlantı Hatası: {_SON_SHEETS_HATASI['mesaj']}")
        
    veri_onbellegini_temizle()
    return basarili


# =====================================================================
# YEREL KASA MOTORU ENTEGRASYONU (Google Sheets Kasa Defteri Yerine)
# =====================================================================

AYAR_SAYFASI = "Ayarlar"   # Google Sheets'te otomatik oluşturulur: Anahtar | Deger

@st.cache_data(ttl=300, show_spinner=False)
def ayar_oku(anahtar):
    """Kalıcı ayarı Google Sheets 'Ayarlar' sayfasından okur (yoksa None). Sayfa yenilense de değişmez."""
    sheet = google_sheets_baglan(AYAR_SAYFASI)
    if sheet is None:
        return None
    try:
        for r in sheet.get_all_values():
            if len(r) >= 2 and r[0] == anahtar:
                return r[1]
    except Exception as e:
        print(f"Ayar okunamadı ({anahtar}): {e}")
    return None

def ayar_yaz(anahtar, deger):
    sheet = google_sheets_baglan(AYAR_SAYFASI)
    if sheet is None:
        return False
    try:
        satirlar = sheet.get_all_values()
        if not satirlar:
            sheet.update(values=[["Anahtar", "Deger"]], range_name="A1")
            satirlar = [["Anahtar", "Deger"]]
        for i, r in enumerate(satirlar, start=1):
            if r and r[0] == anahtar:
                sheet.update_cell(i, 2, str(deger))
                break
        else:
            sheet.append_row([anahtar, str(deger)])
        ayar_oku.clear()
        return True
    except Exception as e:
        print(f"Ayar yazılamadı ({anahtar}): {e}")
        return False

def kaldirac_kaydet(deger):
    """Seçilen kaldıraç tüm coinler için geçerli strateji ayarıdır; sheet'e yazılır, yenilemede korunur."""
    deger = int(max(1, min(KALDIRAC_MAX, int(deger))))
    st.session_state["kaldirac_secim"] = deger
    st.session_state["kaldirac_mod"] = "3x" if deger == 3 else ("5x" if deger == 5 else "sec")
    ayar_yaz("kaldirac", deger)

def veri_onbellegini_temizle():
    """Yazma işleminden sonra yalnızca işlem/kasa verisini tazeler; Binance fiyat/mum önbelleği korunur."""
    for _f in (islem_gecmisi_getir, kasa_defteri_getir):
        try:
            _f.clear()
        except Exception:
            pass
    try:
        kasa_motoru._ham_satirlar.clear()
    except Exception:
        pass

@st.cache_data(ttl=15)
def kasa_defteri_getir():
    """Yerel kasa motorundan geçmiş hareketleri okur ve DataFrame döndürür."""
    gecmis = kasa_motoru.gecmis_getir()
    kolonlar = ["Islem_ID", "Zaman", "Islem_Turu", "Tutar", "Aciklama"]
    if not gecmis:
        return pd.DataFrame(columns=kolonlar)
    
    satirlar = []
    for idx, h in enumerate(gecmis, start=1):
        satirlar.append({
            "Islem_ID": idx,
            "Zaman": h.get("tarih", ""),
            "Islem_Turu": h.get("tur", ""),
            "Tutar": h.get("tutar", 0.0),
            "Aciklama": f"{h.get('aciklama', '')} (Kom: {h.get('komisyon', 0.0)}$)" if h.get('komisyon', 0.0) > 0 else h.get('aciklama', '')
        })
    return pd.DataFrame(satirlar)

def kasa_islem_ekle(islem_turu, tutar, aciklama):
    """Kasa işlemlerini doğrudan entegre Kasa Motoru üzerinden tek seferde yazar (Çifte kaydı engeller)."""
    try:
        basarili, mesaj = kasa_motoru.islem_ekle(islem_turu, tutar, aciklama)
        veri_onbellegini_temizle()
        return basarili, mesaj
    except Exception as e:
        return False, f"Kasa kayıt hatası: {str(e)}"
        
        # 2. Doğrudan panel_v2 Sheets bağlantısı ile E-Tabloya yazma
        sheet = google_sheets_baglan("KasaDefteri")
        if sheet is not None:
            ham = sheet.get_all_values()
            if not ham:
                sheet.append_row(["Islem_ID", "Zaman", "Islem_Turu", "Tutar", "Aciklama"])
                ham = [["Islem_ID"]]
            idler = []
            for r in ham[1:]:
                if r and len(r) > 0 and str(r[0]).replace('.', '', 1).isdigit():
                    idler.append(int(float(r[0])))
            yeni_id = (max(idler) if idler else 0) + 1
            sheet.append_row([yeni_id, tr_zaman().strftime("%d.%m.%Y %H:%M"), islem_turu, round(float(tutar), 2), aciklama])
            return True, "Kasa işlemi başarıyla kaydedildi ve e-tabloya işlendi."
        return True, "Yerel kayıt yapıldı fakat e-tabloya bağlanılamadı."
    except Exception as e:
        return False, f"Kasa kayıt hatası: {str(e)}"

def kasa_islem_ekle_deftere(islem_turu, tutar, aciklama):
    basari, _ = kasa_islem_ekle(islem_turu, tutar, aciklama)
    return basari

def kapanis_defterde_var(islem_id):
    gecmis = kasa_motoru.gecmis_getir()
    for h in gecmis:
        if h.get("tur") == "Trade_Sonuc":
            if f"#{islem_id} " in str(h.get("aciklama", "")):
                return True
    return False

def kapanis_deftere_yaz_tekil(islem_id, etiket, coin, tutar, sonuc_metin):
    if kapanis_defterde_var(islem_id):
        return True
    return kasa_islem_ekle_deftere("Trade_Sonuc", float(round(tutar, 2)), f"{etiket}: #{islem_id} {coin} ({sonuc_metin})")

def bakiye_durumunu_getir(ortak_fiyat_havuzu={}):
    # Tüm bakiye ve kasa hesaplamaları artık doğrudan kasa_motoru üzerinden yönetilir
    nakit_bakiye = kasa_motoru.bakiye_getir()
    df_trade = islem_gecmisi_getir(sheet_guncelle=False)
    
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
            lev_ = satir_kaldiraci(rw)
            acik_kz_toplam += m_M * lev_ * f_y - cikis_komisyonu(m_M, False, lev_)

    efektif_kasa = nakit_bakiye + acik_kz_toplam
    bos_bakiye = nakit_bakiye - aktif_marjin_toplami
    return float(nakit_bakiye), float(efektif_kasa), float(bos_bakiye), float(aktif_marjin_toplami), float(acik_kz_toplam)


# =====================================================================
# İŞLEM VE RAPORLAMA FONKSİYONLARI
# =====================================================================

def yeni_islem_ekle(coin, yon, giris_fiyat, islem_miktari, stop, kar_al, zaman_dilimi, matris_puan, risk_hedef_metin, esik_atla=False, kaldirac=None, risk_asimi=False):
    df = islem_gecmisi_getir()
    toplam_kasa_risk, _, mevcut_bakiye, _, _ = bakiye_durumunu_getir()
    # Kaldıraç: coinde açık pozisyon varsa onunki korunur, yoksa seçilen değer kullanılır (1..KALDIRAC_MAX)
    _lev = max(1.0, min(float(KALDIRAC_MAX), float(kaldirac) if kaldirac else float(KALDIRAC)))
    if not df.empty and "Durum" in df.columns:
        _acik_l = df[~durum_kapali_maskesi(df["Durum"])]
        _acik_c = _acik_l[(_acik_l["Coin"] == coin) & _acik_l["Yon"].astype(str).str.contains("Long" if "Long" in yon else "Short", regex=False)]
        if not _acik_c.empty:
            _lev = satir_kaldiraci(_acik_c.iloc[0])
    gereken_nakit = islem_miktari + giris_komisyonu(islem_miktari, _lev)
    if round(gereken_nakit, 2) > round(mevcut_bakiye, 2):
        return False, f"Bakiye yetersiz! Mevcut Bakiye: {mevcut_bakiye:.2f} $, Girilen: {islem_miktari:.2f} $ + giriş komisyonu {giris_komisyonu(islem_miktari, _lev):.2f} $"
    if islem_miktari <= 0:
        return False, "İşlem miktarı 0 $'dan büyük olmalıdır!"

    suan_tr = tr_zaman()
    suan_tr_str = suan_tr.strftime("%d.%m.%Y %H:%M")
    
    acik_islem_idx = None
    if not df.empty and "Durum" in df.columns:
        acik_mask = ~durum_kapali_maskesi(df["Durum"])
        acik_df = df[acik_mask]
        _ayni_yon = acik_df[(acik_df["Coin"] == coin) & acik_df["Yon"].astype(str).str.contains("Long" if "Long" in yon else "Short", regex=False)] if not acik_df.empty else acik_df
        if not _ayni_yon.empty:   # aynı coin + aynı yön: ekleme; zıt yön: ayrı yeni işlem
            acik_islem_idx = _ayni_yon.index[0]

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

        dakika_farki_yeni = max(0.0, (yeni_dt - eski_dt).total_seconds() / 60.0)
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
            yeni_kar_al = yeni_agirlikli_ortalama * (1.0 + hedef_carpan_guncel / 100.0)
        else:
            yeni_stop = yeni_agirlikli_ortalama * (1.0 + stop_uzde_guncel / 100.0)
            yeni_kar_al = yeni_agirlikli_ortalama * (1.0 - hedef_carpan_guncel / 100.0)
            
        beklenen_kar, olasi_stop = beklenen_ve_olasi("Long" in eski_yon, yeni_toplam_miktar, yeni_agirlikli_ortalama, yeni_kar_al, yeni_stop, _lev)

        kap = risk_kapasitesi(toplam_kasa_risk, df, coin, yeni_agirlikli_ortalama, yeni_stop, _lev, eski_yon)
        if yeni_toplam_miktar > kap["tavan"] + 0.005:   # teminat tavanı: her zaman geçerli
            return False, (f"⛔ Teminat tavanı aşılıyor! Bu pozisyon için en fazla {kap['tavan']:.2f} $ teminat konabilir "
                           f"(pozisyon büyüklüğü kasanın {MAKS_POZISYON_ORANI:g} katını geçemez). Mevcut {eski_miktar:.2f} $; "
                           f"en fazla {max(0.0, kap['tavan'] - eski_miktar):.2f} $ ekleyebilirsiniz.")
        _risk_asildi = yeni_toplam_miktar > kap["azami"] + 0.005
        if _risk_asildi and not risk_asimi:
            eklenebilir = max(0.0, kap["azami"] - eski_miktar)
            return False, f"⚠️ Risk sınırı aşılıyor! En fazla {eklenebilir:.2f} $ ekleyebilirsiniz. Bilerek aşmak için formdaki 'Risk sınırını aşarak ekle' kutusunu işaretleyin."

        basamak = 4 if yeni_agirlikli_ortalama < 10 else 2
        matris_rh_metin = f"{yeni_agirlikli_puan:.2f} ({rh_guncel_metin})"
        toplam_kasa, _, _, _, _ = bakiye_durumunu_getir()
        giris_kom = round(giris_komisyonu(islem_miktari, _lev), 4)

        df.at[acik_islem_idx, "Giris_Fiyat"] = round(yeni_agirlikli_ortalama, basamak)
        df.at[acik_islem_idx, "Islem_Miktari"] = round(yeni_toplam_miktar, 2)
        df.at[acik_islem_idx, "Stop"] = round(yeni_stop, basamak)
        df.at[acik_islem_idx, "Kar_Al"] = round(yeni_kar_al, basamak)
        df.at[acik_islem_idx, "Acilis_Zamani"] = yeni_acilis_zamani_str
        df.at[acik_islem_idx, "Seviye_Zamani"] = suan_tr_str   # yeni stop/hedef seviyelerinin geçerli olduğu an
        df.at[acik_islem_idx, "Beklenen_Kar"] = round(beklenen_kar, 2)
        df.at[acik_islem_idx, "Olasi_Stop"] = round(olasi_stop, 2)
        df.at[acik_islem_idx, "Matris_Puan_RH"] = matris_rh_metin
        df.at[acik_islem_idx, "Guncel_Kasa"] = round(toplam_kasa - giris_kom, 2)

        if not dataframe_guncelle_gsheets(df):
            return False, "⚠️ Ekleme Google Sheets'e yazılamadı!"
        islem_no = int(df.at[acik_islem_idx, "Islem_ID"])
        kasa_islem_ekle_deftere("Komisyon", -giris_kom, f"Giriş Komisyonu: #{islem_no} {coin}")
        return True, f"🔄 {coin} pozisyonuna ekleme yapıldı! Giriş komisyonu: {giris_kom:.4f} $." + (" ⚠️ Risk sınırı bilinçli olarak aşıldı." if _risk_asildi else "")
    else:
        min_esik_kontrol = aktif_min_puan_esigi_getir()
        if (matris_puan < min_esik_kontrol and not esik_atla) or "Nötr" in yon or "Beklemede" in yon:
            return False, f"⚠️ Nötr veya Min. Eşik ({min_esik_kontrol}) altındaki yeni işlemler engellenmiştir!"

        yeni_id = 1 if df.empty else int(pd.to_numeric(df["Islem_ID"], errors="coerce").max() or 0) + 1
        beklenen_kar, olasi_stop = beklenen_ve_olasi("Long" in yon, islem_miktari, giris_fiyat, kar_al, stop, _lev)

        kap = risk_kapasitesi(toplam_kasa_risk, df, coin, giris_fiyat, stop, _lev, yon)
        if islem_miktari > kap["tavan"] + 0.005:   # teminat tavanı: her zaman geçerli
            return False, (f"⛔ Teminat tavanı aşılıyor! Bu işlem için en fazla {kap['tavan']:.2f} $ teminat konabilir "
                           f"(pozisyon büyüklüğü kasanın {MAKS_POZISYON_ORANI:g} katını geçemez).")
        _risk_asildi = islem_miktari > kap["azami"] + 0.005
        if _risk_asildi and not risk_asimi:
            return False, f"⚠️ Risk sınırı aşılıyor! Azami teminat {kap['azami']:.2f} $. Bilerek aşmak için formdaki 'Risk sınırını aşarak işlem aç' kutusunu işaretleyin."

        basamak = 4 if giris_fiyat < 10 else 2
        giris_kom = round(giris_komisyonu(islem_miktari, _lev), 4)
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
            "Kaldirac": int(_lev) if float(_lev).is_integer() else float(_lev),
            "Seviye_Zamani": suan_tr.strftime("%d.%m.%Y %H:%M"),
        }])
        df = pd.concat([df, yeni_kayit], ignore_index=True).drop_duplicates(subset=["Islem_ID"], keep="last")
        if not dataframe_guncelle_gsheets(df):
            return False, "⚠️ İşlem Google Sheets'e yazılamadı!"
        kasa_islem_ekle_deftere("Komisyon", -giris_kom, f"Giriş Komisyonu: #{yeni_id} {coin}")
        return True, f"✅ {coin} emri {_lev:g}x kaldıraçla verildi! Giriş komisyonu: {giris_kom:.4f} $." + (" ⚠️ Risk sınırı bilinçli olarak aşıldı." if _risk_asildi else "")

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
        lev = satir_kaldiraci(row)
        fark_yuzde = ((anlik_kapatma_fiyati - giris_fiyat) / giris_fiyat) if long_mi else ((giris_fiyat - anlik_kapatma_fiyati) / giris_fiyat)

        if kapatilacak_miktar is not None and kapatilacak_miktar < mevcut_miktar:
            kismi_kar = kapatilacak_miktar * lev * fark_yuzde - cikis_komisyonu(kapatilacak_miktar, False, lev)
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
                "Kaldirac": lev,
                "Seviye_Zamani": "-",
            }])

            kalan_miktar = mevcut_miktar - kapatilacak_miktar
            df.at[idx[0], "Islem_Miktari"] = round(kalan_miktar, 2)
            bek_kar_yeni, olasi_stop_yeni = beklenen_ve_olasi(long_mi, kalan_miktar, giris_fiyat, float(row["Kar_Al"]), float(row["Stop"]), lev)
            df.at[idx[0], "Beklenen_Kar"] = round(bek_kar_yeni, 2)
            df.at[idx[0], "Olasi_Stop"] = round(olasi_stop_yeni, 2)

            df = pd.concat([df, yeni_kapali_kayit], ignore_index=True).sort_values(by="Islem_ID").reset_index(drop=True)
            if not dataframe_guncelle_gsheets(df):
                return False, "⚠️ Kısmi kapama Google Sheets'e yazılamadı!"
            kasa_islem_ekle_deftere("Trade_Sonuc", float(round(kismi_kar, 2)), f"Kısmi K/Z: #{islem_id} {row['Coin']}")
            return True, f"Kısmi kapama başarılı! Realize K/Z: {kismi_kar:,.2f} $."
        else:
            net_kar = mevcut_miktar * lev * fark_yuzde - cikis_komisyonu(mevcut_miktar, False, lev)
            durum_metni = "Kapandi (Zarar)" if net_kar < 0 else "Kapandi (Kar)"
            df.at[idx[0], "Durum"] = durum_metni
            df.at[idx[0], "Kapanis_Zamani"] = suan_tr
            df.at[idx[0], "Net_Kar_Zarar"] = float(round(net_kar, 2))
            df.at[idx[0], "Kapanis_Fiyati"] = float(round(anlik_kapatma_fiyati, 4))

            toplam_kasa, _, _, _, _ = bakiye_durumunu_getir()
            df.at[idx[0], "Guncel_Kasa"] = float(round(toplam_kasa + net_kar, 2))
            if not dataframe_guncelle_gsheets(df):
                return False, "⚠️ Kapanış Google Sheets'e yazılamadı!"
            kapanis_deftere_yaz_tekil(islem_id, "Trade K/Z", row["Coin"], net_kar, durum_metni)
            return True, f"İşlem tamamen kapatıldı. K/Z: {net_kar:.2f} $."
    except Exception as e:
        return False, f"Hata: {str(e)}"

def _dk_mumlar_taze(coin, limit):
    """Önbelleksiz 1 dakikalık mumlar (stop/hedef dokunuşu için taze veri gerekir). Sütunlar: timestamp(ms), High, Low, Close."""
    sym = coin.replace("/", "")
    veri = _binance_get_json([
        f"https://data-api.binance.vision/api/v3/klines?symbol={sym}&interval=1m&limit={limit}",
        f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1m&limit={limit}",
    ], 5)
    if not veri:
        return pd.DataFrame()
    try:
        df = pd.DataFrame(veri, columns=["timestamp", "Open", "High", "Low", "Close", "Volume", "Close_Time", "QAV", "Num_Trades", "Taker_BBAV", "Taker_BQAV", "Ignore"])
        for c_ in ("High", "Low", "Close"):
            df[c_] = df[c_].astype(float)
        df["timestamp"] = df["timestamp"].astype("int64")
        return df[["timestamp", "High", "Low", "Close"]]
    except Exception:
        return pd.DataFrame()

def _seviye_baslangic_ms(row, simdi_ms):
    """Stop/hedef seviyelerinin geçerli olduğu an (UTC ms): Seviye_Zamani varsa o; yoksa Acilis_Zamani ile
    'son 20 dakika' arasında geç olan (ağırlıklı ortalama açılış zamanı sonradan yenilenen seviyeleri kapsamasın)."""
    def _ms(metin):
        t = str(metin).strip()
        for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y %H:%M:%S"):
            try:
                return int(TR_TZ.localize(datetime.strptime(t, fmt)).timestamp() * 1000)
            except Exception:
                continue
        return None
    seviye = _ms(row.get("Seviye_Zamani", ""))
    if seviye:
        return seviye
    acilis = _ms(row.get("Acilis_Zamani", ""))
    sinir = simdi_ms - 20 * 60 * 1000
    return max(acilis, sinir) if acilis else sinir

def otomatik_stop_kar_kontrolu(df_arg, ortak_fiyat_havuzu=None):
    if df_arg is None or not isinstance(df_arg, pd.DataFrame) or df_arg.empty or "Durum" not in df_arg.columns:
        return

    adaylar = []
    simdi_ms = int(time.time() * 1000)
    dk_mumlar = {}   # coin -> (limit, df): 1 dakikalık mumlar, coin başına tek istek
    for idx, row in df_arg.iterrows():
        if not _islem_acik_mi(row["Durum"]):
            continue
        islem_id = int(row["Islem_ID"])
        coin = row["Coin"]
        yon = row["Yon"]
        stop_f = float(row["Stop"])
        kar_al_f = float(row["Kar_Al"])

        # Seviyelerin geçerli olduğu andan beri 1 dakikalık mumların High/Low'una bakılır:
        # kontroller arasında seviyeye değip geri dönen fiyat kaçmaz. Mum alınamazsa anlık fiyata düşülür.
        baslangic_ms = _seviye_baslangic_ms(row, simdi_ms)
        gerekli = int(min(1000, max(5, (simdi_ms - baslangic_ms) / 60000.0 + 3)))
        onbellek = dk_mumlar.get(coin)
        if onbellek is None or onbellek[0] < gerekli:
            dk_mumlar[coin] = (gerekli, _dk_mumlar_taze(coin, gerekli))
        dk_df = dk_mumlar[coin][1]

        if dk_df is not None and not dk_df.empty:
            sonuc_d = matris_motoru.dokunus_bul(dk_df, "Long" in yon, stop_f, kar_al_f, baslangic_ms)
            if sonuc_d is not None:
                hedefe_ = (sonuc_d[0] == "hedef")
                adaylar.append((islem_id, hedefe_, kar_al_f if hedefe_ else stop_f))
            continue

        anl_f = ortak_fiyat_havuzu.get(coin, fiyat_cek_binance(coin)) if ortak_fiyat_havuzu is not None else fiyat_cek_binance(coin)
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

    veri_onbellegini_temizle()
    df = islem_gecmisi_getir(sheet_guncelle=False).copy()
    if df is None or df.empty:
        return
    suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")
    toplam_kasa, _, _, _, _ = bakiye_durumunu_getir({} if ortak_fiyat_havuzu is None else ortak_fiyat_havuzu)
    kasa_ilerleyen = toplam_kasa
    yazilacaklar = []

    for islem_id, hedefe_ulasti, kapanis_fiyat_degeri in adaylar:
        eslesen = df.index[df["Islem_ID"] == islem_id]
        if len(eslesen) == 0:
            continue
        i = eslesen[0]
        if not _islem_acik_mi(df.at[i, "Durum"]):
            continue
        giris_fiyat = float(df.at[i, "Giris_Fiyat"])
        miktar = float(df.at[i, "Islem_Miktari"])
        yon = df.at[i, "Yon"]
        coin = df.at[i, "Coin"]

        fark_yuzde = ((kapanis_fiyat_degeri - giris_fiyat) / giris_fiyat) if "Long" in yon else ((giris_fiyat - kapanis_fiyat_degeri) / giris_fiyat)
        lev = satir_kaldiraci(df.loc[i])
        net_kar = miktar * lev * fark_yuzde - cikis_komisyonu(miktar, hedefe_ulasti, lev)
        kasa_ilerleyen += net_kar

        df.at[i, "Durum"] = "Kapandi (Kar)" if hedefe_ulasti else "Kapandi (Zarar)"
        df.at[i, "Kapanis_Zamani"] = suan_tr
        df.at[i, "Net_Kar_Zarar"] = float(round(net_kar, 2))
        df.at[i, "Kapanis_Fiyati"] = float(round(kapanis_fiyat_degeri, 4))
        df.at[i, "Guncel_Kasa"] = float(round(kasa_ilerleyen, 2))
        yazilacaklar.append((islem_id, coin, hedefe_ulasti, net_kar))

    if not yazilacaklar:
        return

    if not dataframe_guncelle_gsheets(df):
        return
    for islem_id, coin, hedefe_ulasti, net_kar in yazilacaklar:
        etiket = "Hedef Kâr" if hedefe_ulasti else "Otomatik Stop"
        kapanis_deftere_yaz_tekil(islem_id, etiket, coin, net_kar, "Kar" if hedefe_ulasti else "Zarar")

def trend_asamasini_ve_ikon_belirle(puan, aktif_yon):
    hsonu = hafta_sonu_mu()
    min_esik = 55.0 if hsonu else 50.0

    if puan < min_esik:
        return "Nötr (Beklemede)", 1.0, False, False

    # Hafta içi (Normal Mod - 50 Tabana Göre)
    if not hsonu:
        if 50.0 <= puan < 55.0:
            return "⭐ Zayıf Trend", 2.0, False, False
        elif 55.0 <= puan < 59.0:
            return "⭐⭐ Orta Trend", 3.0, False, False
        elif 59.0 <= puan < 63.0:
            return "⭐⭐⭐ Güvenli Trend", 3.0, False, False
        elif 63.0 <= puan < 67.0:
            return "🔥 Güçlü Trend", 4.0, False, False
        elif 67.0 <= puan < 71.0:
            return "🔥 🔥 Orta Güçlü Trend", 4.0, True, False
        elif 71.0 <= puan < 75.0:
            return "🔥 🔥 🔥 Çok Güçlü Trend", 5.0, False, True
        else:
            return "🔥🔥🔥🔥 Boğa / Ayı Vuruşu", 5.0, False, True
            
    # Hafta sonu (Sığ Piyasa Modu - Eşikler 5 puan yukarı ötelenir)
    else:
        if 55.0 <= puan < 60.0:
            return "⭐ Zayıf Trend", 2.0, False, False
        elif 60.0 <= puan < 64.0:
            return "⭐⭐ Orta Trend", 3.0, False, False
        elif 64.0 <= puan < 68.0:
            return "⭐⭐⭐ Güvenli Trend", 3.0, False, False
        elif 68.0 <= puan < 72.0:
            return "🔥 Güçlü Trend", 4.0, False, False
        elif 72.0 <= puan < 76.0:
            return "🔥 🔥 Orta Güçlü Trend", 4.0, True, False
        elif 76.0 <= puan < 80.0:
            return "🔥 🔥 🔥 Çok Güçlü Trend", 5.0, False, True
        else:
            return "🔥🔥🔥🔥 Boğa / Ayı Vuruşu", 5.0, False, True

def sinyal_ve_trend_mail_kontrolu(sembol, nihai_puan, aktif_yon, trend_metni, coin_mi=True):
    pass

def arka_plan_dinleyicisi(durdur_olayi):
    while not durdur_olayi.is_set():
        bekleme = 60
        try:
            tum_semboller = coinler + ["TOTAL"]
            anlik_fiyat_havuzu = {}
            for s in tum_semboller:
                anlik_fiyat_havuzu[s] = fiyat_cek_binance(s)
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

piyasa_verisini_paralel_isit(tum_takip_edilenler)
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

    is_notr = (nihai_puan < min_esik_bilgi)
    trend, ham_agirlik, _, _ = trend_asamasini_ve_ikon_belirle(nihai_puan, aktif_yon)

    if is_notr:
        aktif_yon_turu = "Nötr"
        yon_html = f'<div style="background-color: #6c757d; padding: 6px; border-radius: 6px; color: white; font-weight: bold; font-size: 12px;">{trend}</div>'
    else:
        aktif_yon_turu = aktif_yon
        renk_bg = "#00FF00" if aktif_yon == "Long" else "rgb(255, 75, 0)"
        yon_html = f'<div style="background-color: {renk_bg}; padding: 6px; border-radius: 6px; color: #000000; font-weight: bold; font-size: 12px;">{trend}</div>'

    stop_uzde, hedef_carpan, risk_hedef_metin = calculate_coin_metrics_by_score(nihai_puan)

    gecici_islenen_liste.append({
        "sembol": sembol, "nihai_puan": nihai_puan, "aktif_yon": aktif_yon,
        "aktif_yon_turu": aktif_yon_turu, "l_puan": l_puan, "s_puan": s_puan,
        "anlik_fiyat": anlik_fiyat, "gunluk_oran": gunluk_oran, "c_led": c_led,
        "d_led": d_led, "detay_matris_html": "", "yon_html": yon_html,
        "trend": trend, "is_notr": is_notr, "ham_agirlik": ham_agirlik,
        "stop_uzde": stop_uzde, "hedef_carpan": hedef_carpan, "risk_hedef_metin": risk_hedef_metin,
    })

toplam_aktif_agirlik = sum([item["ham_agirlik"] for item in gecici_islenen_liste if not item["is_notr"]])
islenen_veriler = []

for item in gecici_islenen_liste:
    sembol, nihai_puan, aktif_yon_turu, aktif_yon, anlik_fiyat, stop_uzde, hedef_carpan, is_notr = (
        item["sembol"], item["nihai_puan"], item["aktif_yon_turu"], item["aktif_yon"],
        item["anlik_fiyat"], item["stop_uzde"], item["hedef_carpan"], item["is_notr"]
    )

    if toplam_aktif_agirlik > 0 and not is_notr:
        sepet_orani = round((item["ham_agirlik"] / toplam_aktif_agirlik) * 100.0, 1)
    else:
        sepet_orani = 0.0

    if aktif_yon_turu == "Long" or (is_notr and aktif_yon == "Long"):
        stop_fiyat, hedef_fiyat = anlik_fiyat * (1.0 - stop_uzde / 100.0), anlik_fiyat * (1.0 + hedef_carpan / 100.0)
    else:
        stop_fiyat, hedef_fiyat = anlik_fiyat * (1.0 + stop_uzde / 100.0), anlik_fiyat * (1.0 - hedef_carpan / 100.0)
        
    dom_html = f'<div style="text-align: center;"><div style="font-size: 16px; margin-bottom: 2px; letter-spacing: 4px;">{item["c_led"]}{item["d_led"]}</div><div style="font-size: 10px; font-weight: bold; color: #91a0b8;">C &nbsp;&nbsp; D</div></div>'

    puan_toplam_h = item["l_puan"] + item["s_puan"]
    y_yuzde_h = (item["l_puan"] / puan_toplam_h * 100.0) if puan_toplam_h > 0 else 50.0
    puan_html = matris_birlesik_html(nihai_puan, aktif_yon, y_yuzde_h, 100.0 - y_yuzde_h)

    basamak = 4 if anlik_fiyat < 10 else 2
    logo_html = f'<img src="{logo_urls.get(sembol, "")}" width="24" height="24">'

    islenen_veriler.append({
        "Sira_Anahtar": list(logo_urls.keys()).index(sembol),
        "Logo": logo_html, "Coin": sembol, "Fiyat": round(anlik_fiyat, basamak),
        "Yon": item["yon_html"], "Teyit_Sunumu": "",
        "Dom_Sunumu": dom_html, "Matris_Puan_Sunumu": puan_html,
        "Gunluk_Oran": f"<span>{item['gunluk_oran']:+,.2f}%</span>",
        "Kar_Al": round(hedef_fiyat, basamak), "Stopla": round(stop_fiyat, basamak),
        "Skor": nihai_puan, "Sepet_Orani": sepet_orani, "Basamak": basamak,
        "Notr": is_notr, "Ham_Yon": item["trend"], "Aktif_Yon": aktif_yon_turu,
        "Risk_Hedef_Metin": item['risk_hedef_metin'], "Ham_Agirlik": item["ham_agirlik"],
        "L_Puan": float(item["l_puan"]), "S_Puan": float(item["s_puan"]),
    })

islenen_veriler = sorted(islenen_veriler, key=lambda x: (1 if x["Notr"] else 0, -x["Ham_Agirlik"], -x["Skor"]))
toplam_kasa, efektif_kasa, mevcut_bakiye, aktif_yatirim_tutari, toplam_acik_kz = bakiye_durumunu_getir(ortak_fiyat_havuzu)

for v in islenen_veriler:
    v["Yatırım_Bedeli"] = f"{mevcut_bakiye * (v['Sepet_Orani'] / 100.0):,.2f} $"

if "kaldirac_secim" not in st.session_state:
    try:
        _kayitli = int(float(ayar_oku("kaldirac")))
        if not (1 <= _kayitli <= KALDIRAC_MAX):
            raise ValueError
    except Exception:
        _kayitli = int(KALDIRAC)
    st.session_state["kaldirac_secim"] = _kayitli
    st.session_state["kaldirac_mod"] = "3x" if _kayitli == 3 else ("5x" if _kayitli == 5 else "sec")

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
    anapara += float(_tutar_a[_df_kasa_anapara["Islem_Turu"].isin(["EKLE", "Para_Yatir", "Para_Cek", "CEK"])].sum())

# Net Kâr (Realize): kapanan işlemlerin net K/Z'si (çıkış komisyonu düşülmüş) - ödenen TÜM giriş komisyonları
realize_kar -= giris_komisyon_toplami(_df_kasa_anapara)

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
    """3 satır: başlık / değer / yüzde."""
    n_deger = max(1, len(deger_metni))
    return (f'<div class="metric-container"><div style="margin:0; font-size:14px; font-weight:bold; color:#91a0b8;">{baslik}</div>'
            f'<div style="color:{renk}; margin:4px 0 0 0; white-space:nowrap; font-size:clamp(12px, calc(100cqw / {n_deger * 0.60:.2f}), 26px); font-weight:800; line-height:1.15;">{deger_metni}</div>'
            f'<div style="color:#ffffff; margin:2px 0 0 0; font-size:14px; font-weight:700;">{yuzde_metni}</div></div>')

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
    if st.button("Kasa\u00a0İşlemleri\u00a0& Kaldıraç\u00a0Belirleme", width='stretch', key="ana_kasa_butonu"):
        st.session_state["kasa_islem_acik"] = not st.session_state.get("kasa_islem_acik", False)
        st.rerun()

RENK_NAVY, RENK_BTN_SARI, RENK_BTN_YESIL, RENK_BTN_TURUNCU = "#252569", "#ead518", "#00FF00", "rgb(255, 75, 0)"   # yeşil/turuncu: sayfadaki kâr/zarar renkleri

if st.session_state.get("kasa_islem_acik", False):
    st.session_state.setdefault("kasa_islem_secim", "Kasaya Para Ekleme")
    st.session_state.setdefault("kaldirac_secim", int(KALDIRAC))
    st.session_state.setdefault("kaldirac_mod", "5x")
    _kasa_mod = st.session_state["kasa_islem_secim"]
    _ekle_mi = (_kasa_mod == "Kasaya Para Ekleme")
    _lev_mod = st.session_state["kaldirac_mod"]

    def _kasa_secim_yap(deger):
        st.session_state["kasa_islem_secim"] = deger

    def _kaldirac_sec(mod, deger=None):
        if deger is not None:
            kaldirac_kaydet(deger)               # 3x / 5x: sheet'e yazılır
        else:
            st.session_state["kaldirac_mod"] = mod   # "Kaldıraç Seç": sürgü açılır, değer değişmez
            st.session_state["kaldirac_slider"] = int(st.session_state["kaldirac_secim"])

    def _secili(kosul):
        return ("3px solid #ffffff", "1") if kosul else ("1px solid rgba(255,255,255,.25)", "1")

    _k_ekle, _o_ekle = _secili(_ekle_mi)
    _k_cek, _o_cek = _secili(not _ekle_mi)
    _k3, _o3 = _secili(_lev_mod == "3x")
    _k5, _o5 = _secili(_lev_mod == "5x")
    _ks, _os = _secili(_lev_mod == "sec")
    _sb_renk, _sb_yazi = (RENK_NAVY, "#ffffff") if _ekle_mi else (RENK_BTN_TURUNCU, "#000000")
    st.markdown(f"""<style>
.st-key-kasa_btn_ekle button {{ background:{RENK_NAVY} !important; border:{_k_ekle} !important; opacity:{_o_ekle}; min-height:46px; }}
.st-key-kasa_btn_ekle button p {{ color:#ffffff !important; font-weight:800 !important; }}
.st-key-kasa_btn_cek button {{ background:{RENK_BTN_TURUNCU} !important; border:{_k_cek} !important; opacity:{_o_cek}; min-height:46px; }}
.st-key-kasa_btn_onay button {{ background:{RENK_BTN_YESIL} !important; border:none !important; min-height:46px; }}
.st-key-kasa_btn_cek button p, .st-key-kasa_btn_onay button p {{ color:#000000 !important; font-weight:800 !important; }}
.st-key-kld_3 button {{ background:{RENK_BTN_YESIL} !important; border:{_k3} !important; opacity:{_o3}; min-height:46px; }}
.st-key-kld_5 button {{ background:{RENK_BTN_SARI} !important; border:{_k5} !important; opacity:{_o5}; min-height:46px; }}
.st-key-kld_sec button {{ background:{RENK_NAVY} !important; border:{_ks} !important; opacity:{_os}; min-height:46px; }}
.st-key-kld_3 button p, .st-key-kld_5 button p {{ color:#000000 !important; font-weight:800 !important; }}
.st-key-kld_sec button p {{ color:#ffffff !important; font-weight:800 !important; }}
div[class*="st-key-kasa_acik_sec"] [data-baseweb="select"] > div {{ background:{_sb_renk} !important; border:1px solid rgba(255,255,255,.35) !important; }}
div[class*="st-key-kasa_acik_sec"] [data-baseweb="select"] * {{ color:{_sb_yazi} !important; font-weight:700 !important; }}
div[class*="st-key-kasa_acik_sec"] [data-baseweb="select"] svg {{ fill:{_sb_yazi} !important; }}
div[data-testid="stHorizontalBlock"]:has(.st-key-kld_3) {{ align-items:stretch !important; }}
div[data-testid="stColumn"]:has(.st-key-kld_3) > div[data-testid="stVerticalBlock"], div[data-testid="column"]:has(.st-key-kld_3) > div[data-testid="stVerticalBlock"] {{ height:100%; }}
div[data-testid="stColumn"]:has(.st-key-kld_3) > div[data-testid="stVerticalBlock"] > *:last-child, div[data-testid="column"]:has(.st-key-kld_3) > div[data-testid="stVerticalBlock"] > *:last-child {{ margin-top:auto; }}
</style>""", unsafe_allow_html=True)

    col_kasa_sol, col_kasa_sag = st.columns([2.2, 1.3], gap="medium")
    with col_kasa_sol:
        _baslik = "💰 Kasaya Para Ekle" if _ekle_mi else "💸 Nakit Avans Çekimi"
        st.markdown(f"""<div style="font-size:21px; font-weight:800; color:#f0f5ff; margin:2px 0 2px;">{_baslik}</div><div style="font-size:13px; color:#aab9d0; margin-bottom:8px;">Tutarı girin, işlem türünü seçip onaylayın.</div>""", unsafe_allow_html=True)
        _kb1, _kb2, _kb3 = st.columns(3, gap="small")
        with _kb1:
            st.button("Kasaya Para Ekleme", key="kasa_btn_ekle", width='stretch', on_click=_kasa_secim_yap, args=("Kasaya Para Ekleme",))
        with _kb2:
            st.button("Nakit Avans Çekimi", key="kasa_btn_cek", width='stretch', on_click=_kasa_secim_yap, args=("Nakit Avans Çekimi",))
        with _kb3:
            _onay_basildi = st.button("Onayla", key="kasa_btn_onay", width='stretch')
        _ka, _kt = st.columns(2, gap="small")
        with _ka:
            _acik_sec = st.selectbox("Açıklama", ["Kasaya Para Ekleme", "Nakit Avans Çekimi"],
                                     index=0 if _ekle_mi else 1, key=f"kasa_acik_sec_{'e' if _ekle_mi else 'c'}")
        with _kt:
            kasa_tutar = st.number_input("Tutar ($)", min_value=1.0, value=100.0, step=10.0, key="k_tutar")
        if _acik_sec != _kasa_mod:
            st.session_state["kasa_islem_secim"] = _acik_sec
            st.rerun()
        if _onay_basildi:
            islem_turu_str = "Para_Yatir" if _ekle_mi else "Para_Cek"
            basarili, mesaj = kasa_motoru.islem_ekle(islem_turu_str, kasa_tutar, _acik_sec)
            veri_onbellegini_temizle()
            if basarili:
                st.success(mesaj)
                st.session_state["kasa_islem_acik"] = False
                time.sleep(1)
                st.rerun()
            else:
                st.error(mesaj)

    with col_kasa_sag:
        _lev_baslik = st.empty()
        if _lev_mod == "sec":
            st.session_state.setdefault("kaldirac_slider", int(st.session_state["kaldirac_secim"]))
            _sec_deger = st.slider(f"Kaldıraç (en fazla {KALDIRAC_MAX}x)", 1, KALDIRAC_MAX, key="kaldirac_slider")
            if int(_sec_deger) != int(st.session_state["kaldirac_secim"]):
                kaldirac_kaydet(_sec_deger)
                st.session_state["kaldirac_mod"] = "sec"
        _l1, _l2, _l3 = st.columns(3, gap="small")
        with _l1:
            st.button("3x Kaldıraç", key="kld_3", width='stretch', on_click=_kaldirac_sec, args=("3x", 3))
        with _l2:
            st.button("5x Kaldıraç", key="kld_5", width='stretch', on_click=_kaldirac_sec, args=("5x", 5))
        with _l3:
            st.button("Kaldıraç Seç", key="kld_sec", width='stretch', on_click=_kaldirac_sec, args=("sec",))
        _lev_baslik.markdown(f"""<div style="border:1px solid #344765; border-radius:14px; padding:12px 15px; margin-bottom:8px; background:linear-gradient(145deg,#121e30,#0e1726);"><div style="font-size:18px; font-weight:800; color:#f0f5ff;">⚙️ Kaldıraç Belirle</div><div style="font-size:15px; font-weight:700; color:#e8eef8; margin-top:6px;">Kaldıraç Seçimi: <span style="color:{RENK_BTN_SARI};">{int(st.session_state['kaldirac_secim'])}x Kaldıraçlı İşlem</span></div></div>""", unsafe_allow_html=True)

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

SUTUN_ORANLARI = [1.2, 2.5, 1.0]
col_sol_panel, col_orta_grafik, col_sag_endeks = st.columns(SUTUN_ORANLARI)

# Hacim sırası: BTC en üstte, SOL en altta
HACIM_SIRASI = ["BTC/USDT", "ETH/USDT", "XRP/USDT", "BNB/USDT", "SOL/USDT"]
RENK_LONG, RENK_SHORT = "#00FF00", "rgb(255, 75, 0)"

def _form_butonu(etiket):
    try:
        return st.form_submit_button(etiket, width='stretch')
    except TypeError:
        return st.form_submit_button(etiket, use_container_width=True)

def yon_secimlerini_temizle():
    st.session_state["risk_asimi_sayac"] = st.session_state.get("risk_asimi_sayac", 0) + 1   # risk aşımı onay kutusu işaretsiz başlasın
    for _k in [k for k in st.session_state.keys() if str(k).startswith("islem_yonu_")]:
        st.session_state.pop(_k, None)

# Varsayılanlar (kilit kapalıyken alt yapı çizilmez, bu değişkenler modül sonunda kullanılır)
submit_islem, kapat_kilit_tik = False, False
manuel_girilen_tutar = 0.0
secilen_yon, onerilen_yon, yon_manuel_ters, esik_atla = None, None, False, False
islem_fiyat, islem_stop, islem_kar_al = 0.0, 0.0, 0.0
anlik_matris_puani, anlik_risk_hedef_metin, coin_verisii = 0.0, "0,70 / 0,95", None
islem_kaldiraci = float(KALDIRAC)
risk_asimi_onay = False
kilit_acik = st.session_state.get("islem_emri_kilit_acik", False)

df_gosterge = pd.DataFrame(islenen_veriler)
df_gecmis_temp = islem_gecmisi_getir(sheet_guncelle=False)
coin_listesi = [c for c in HACIM_SIRASI if (not df_gosterge.empty and c in df_gosterge["Coin"].values)]
if st.session_state.get("secili_coin") not in coin_listesi:
    st.session_state["secili_coin"] = coin_listesi[0] if coin_listesi else None
secilen_coin = st.session_state.get("secili_coin")

_sol_css = """<style>
div[data-testid="stHorizontalBlock"]:has(.st-key-islem_sol_kap) { align-items: stretch !important; }
div[data-testid="stColumn"]:has(.st-key-islem_sol_kap) > div[data-testid="stVerticalBlock"],
div[data-testid="column"]:has(.st-key-islem_sol_kap) > div[data-testid="stVerticalBlock"] { height: 100%; }
.st-key-islem_sol_kap { flex: 1 1 auto; }
.st-key-btn_islem_kilidi_ac { margin-top: auto; }

/* ================= TELEFON (<=640px: Streamlit sütunları alt alta dizer) ================= */
@media (max-width: 640px) {
  .block-container { padding: .8rem .6rem 2rem !important; }
  h3 { font-size: 1.15rem !important; }
  .st-key-grafik_total, .st-key-islem_sol_kap, .st-key-islem_sag_kap, .st-key-analiz_kart, .st-key-risk_kart_kap { min-height: 0 !important; }
  div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"], div[data-testid="column"] > div[data-testid="stVerticalBlock"] { height: auto !important; }
  .st-key-btn_islem_kilidi_ac, .st-key-btn_kilit_durum { margin-top: 0 !important; }
  .st-key-islem_sag_kap > *:last-child, .st-key-islem_sag_kap > *:last-child > div, .st-key-islem_sag_kap > *:last-child [data-testid="stMarkdownContainer"],
  .st-key-risk_kart_kap > *:last-child, .st-key-risk_kart_kap > *:last-child > div, .st-key-risk_kart_kap > *:last-child [data-testid="stMarkdownContainer"] { display: block !important; }
  /* üst bilgi satırı: 2'li ızgara, kasa butonu tam genişlik */
  div[data-testid="stHorizontalBlock"]:has(.st-key-ana_kasa_butonu) { flex-wrap: wrap !important; gap: 8px !important; }
  div[data-testid="stHorizontalBlock"]:has(.st-key-ana_kasa_butonu) > div[data-testid="stColumn"] { flex: 1 1 calc(50% - 8px) !important; min-width: calc(50% - 8px) !important; width: auto !important; }
  div[data-testid="stHorizontalBlock"]:has(.st-key-ana_kasa_butonu) > div[data-testid="stColumn"]:last-child { flex: 1 1 100% !important; min-width: 100% !important; }
  div[data-testid="stHorizontalBlock"]:has(.st-key-ana_kasa_butonu) .metric-container { height: auto !important; min-height: 92px; }
  .st-key-ana_kasa_butonu, .st-key-ana_kasa_butonu [data-testid="stButton"], .st-key-ana_kasa_butonu button { height: 84px !important; min-height: 84px !important; }
  /* düğme sıraları telefonda da yan yana kalsın */
  div[data-testid="stHorizontalBlock"]:has(.st-key-yon_long), div[data-testid="stHorizontalBlock"]:has(.st-key-yon_long_sec),
  div[data-testid="stHorizontalBlock"]:has(.st-key-kld_3):not(:has(.st-key-kasa_btn_ekle)),
  div[data-testid="stHorizontalBlock"]:has(.st-key-kasa_btn_ekle):not(:has(.st-key-kld_3)),
  .st-key-islem_form_kap div[data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 6px !important; }
  div[data-testid="stHorizontalBlock"]:has(.st-key-yon_long) > div[data-testid="stColumn"], div[data-testid="stHorizontalBlock"]:has(.st-key-yon_long_sec) > div[data-testid="stColumn"],
  div[data-testid="stHorizontalBlock"]:has(.st-key-kld_3):not(:has(.st-key-kasa_btn_ekle)) > div[data-testid="stColumn"],
  div[data-testid="stHorizontalBlock"]:has(.st-key-kasa_btn_ekle):not(:has(.st-key-kld_3)) > div[data-testid="stColumn"],
  .st-key-islem_form_kap div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] { flex: 1 1 0 !important; min-width: 0 !important; width: auto !important; }
  /* analiz altındaki 4 buton: 2x2, etiketler gizli */
  div[data-testid="stColumn"]:has(.grp-etiket) { display: none !important; }
  div[data-testid="stHorizontalBlock"]:has(.st-key-btn_sun_tum) { flex-wrap: wrap !important; gap: 8px !important; }
  div[data-testid="stHorizontalBlock"]:has(.st-key-btn_sun_tum) > div[data-testid="stColumn"] { flex: 1 1 calc(50% - 8px) !important; min-width: calc(50% - 8px) !important; }
  .st-key-islem_sol_kap button, .st-key-islem_sol_kap p { font-size: 15px !important; }
}
/* --- üst sağ buton: soldaki bilgi kutusuyla aynı yükseklik ve alt hiza --- */
.st-key-ana_kasa_butonu { width:100% !important; margin:0 !important; padding:0 !important; height:112px !important; }
.st-key-ana_kasa_butonu [data-testid="stButton"] { width:100% !important; height:112px !important; margin:0 !important; padding:0 !important; }
.st-key-ana_kasa_butonu button { box-sizing:border-box !important; display:flex !important; align-items:center !important; justify-content:center !important; width:100% !important; height:112px !important; min-height:112px !important; padding:6px 8px !important; margin:0 !important; background:#252569 !important; color:#ffffff !important; border:1px solid #3a3a9a !important; border-radius:16px !important; box-shadow:0 4px 12px rgba(37,37,105,.45) !important; }
.st-key-ana_kasa_butonu button [data-testid="stMarkdownContainer"] { width:100%; }
.st-key-ana_kasa_butonu button p { margin:0 auto !important; width:100% !important; max-width:12em; text-align:center !important; font-size:15px !important; font-weight:800 !important; line-height:1.25 !important; color:#ffffff !important; white-space:normal !important; }
.st-key-ana_kasa_butonu button p::before { content:"🏦"; display:block; font-size:26px; line-height:1.15; }
div[data-testid="stHorizontalBlock"]:has(.st-key-ana_kasa_butonu) .metric-container { height:112px; box-sizing:border-box; }
/* --- işlem kilidi açık durumu (devre dışı sarı buton, en altta) --- */
.st-key-btn_kilit_durum { margin-top:auto; }
.st-key-btn_kilit_durum button { background:#ead518 !important; border:none !important; opacity:1 !important; cursor:default !important; min-height:44px; }
.st-key-btn_kilit_durum button p { color:#000000 !important; font-weight:800 !important; }
/* --- Long / Short kutuları (seçili: beyaz çerçeve; seçilmeyen: soluk) --- */
div.st-key-yon_long button, div.st-key-yon_long_sec button { background:#00FF00 !important; min-height:64px; }
div.st-key-yon_short button, div.st-key-yon_short_sec button { background:rgb(255, 75, 0) !important; min-height:64px; }
div.st-key-yon_long button, div.st-key-yon_short button { border:3px solid transparent !important; opacity:.55; }
div.st-key-yon_long_sec button, div.st-key-yon_short_sec button { border:3px solid #ffffff !important; opacity:1; }
div[class*="st-key-yon_"] button p { color:#000000 !important; font-weight:800 !important; font-size:15px !important; }
.st-key-islem_form_kap [data-testid="stForm"] { border:none !important; padding:0 !important; }
.st-key-islem_form_kap div[data-testid="stColumn"]:nth-child(1) button { background:#252569 !important; border:1px solid #3a3a9a !important; min-height:46px; }
.st-key-islem_form_kap div[data-testid="stColumn"]:nth-child(1) button p { color:#ffffff !important; font-weight:800 !important; }
.st-key-islem_form_kap div[data-testid="stColumn"]:nth-child(2) button { background:#ead518 !important; border:1px solid #c9b800 !important; min-height:46px; }
.st-key-islem_form_kap div[data-testid="stColumn"]:nth-child(2) button p { color:#000000 !important; font-weight:800 !important; }
/* --- ana satır: üç blok aynı sabit yükseklikte (alt çizgileri aynı) --- */
.st-key-grafik_total, .st-key-islem_sol_kap, .st-key-islem_sag_kap { min-height: 380px; }
.st-key-grafik_total, .st-key-grafik_total * { scrollbar-width: none !important; }
.st-key-grafik_total ::-webkit-scrollbar { display: none !important; width: 0 !important; height: 0 !important; }
.st-key-grafik_total { overflow: hidden !important; }
/* --- sağ sütun: son kart sütunun altına kadar uzar --- */
div[data-testid="stColumn"]:has(.st-key-islem_sag_kap) > div[data-testid="stVerticalBlock"],
div[data-testid="column"]:has(.st-key-islem_sag_kap) > div[data-testid="stVerticalBlock"] { height: 100%; }
.st-key-islem_sag_kap { flex: 1 1 auto; }
.st-key-islem_sag_kap > *:last-child,
.st-key-islem_sag_kap > *:last-child > div,
.st-key-islem_sag_kap > *:last-child [data-testid="stMarkdownContainer"] { flex: 1 1 auto; display: flex; flex-direction: column; }
.st-key-islem_sag_kap > *:last-child .metric-container { flex: 1 1 auto; box-sizing: border-box; }
/* --- analiz kartı ve risk kartı: aynı alt çizgi --- */
div[data-testid="stHorizontalBlock"]:has(.st-key-analiz_kart) { align-items: stretch !important; }
div[data-testid="stColumn"]:has(.st-key-analiz_kart) > div[data-testid="stVerticalBlock"],
div[data-testid="column"]:has(.st-key-analiz_kart) > div[data-testid="stVerticalBlock"],
div[data-testid="stColumn"]:has(.st-key-risk_kart_kap) > div[data-testid="stVerticalBlock"],
div[data-testid="column"]:has(.st-key-risk_kart_kap) > div[data-testid="stVerticalBlock"] { height: 100%; }
.st-key-analiz_kart, .st-key-risk_kart_kap { flex: 1 1 auto; }
.st-key-risk_kart_kap > *:last-child,
.st-key-risk_kart_kap > *:last-child > div,
.st-key-risk_kart_kap > *:last-child [data-testid="stMarkdownContainer"] { flex: 1 1 auto; display: flex; flex-direction: column; }
.st-key-risk_kart_kap .ozet-card { flex: 1 1 auto; box-sizing: border-box; }
"""
for _c in coinler:
    _sym = _c.split("/")[0]
    _secili_mi = (_c == secilen_coin)
    _arka = ("linear-gradient(135deg,#3977f6,#5b8cff)" if _secili_mi else "linear-gradient(#111b2b,#111b2b)")
    _kenar = ("3px solid #ffd166" if _secili_mi else "1px solid #30415b")
    _renk = ("#ffffff" if _secili_mi else "#91a0b8")
    _golge = ("0 0 14px rgba(255,209,102,0.55)" if _secili_mi else "none")
    _sol_css += (
        f"div.st-key-coin_btn_{_sym} button {{ "
        f"background-color: transparent !important; "
        f"background-image: url('{logo_urls.get(_c, '')}'), {_arka} !important; "
        f"background-repeat: no-repeat, no-repeat !important; "
        f"background-position: 16px center, center !important; "
        f"background-size: 26px 26px, cover !important; "
        f"border: {_kenar} !important; color: {_renk} !important; box-shadow: {_golge} !important; "
        f"display: flex !important; align-items: center !important; justify-content: center !important; "
        f"padding: 0 56px !important; min-height: 48px !important; "
        f"opacity: {1.0 if _secili_mi else 0.85}; }}\n"
        f"div.st-key-coin_btn_{_sym} button p {{ width: 100% !important; text-align: center !important; margin: 0 !important; "
        f"font-weight: {800 if _secili_mi else 600} !important; color: {_renk} !important; }}\n"
    )
_sol_css += "</style>"
st.markdown(_sol_css, unsafe_allow_html=True)

with col_sol_panel:
    st.markdown("<h3>🚀 İşlem Emri Ver</h3>", unsafe_allow_html=True)
    kap = st.container(key="islem_sol_kap")
    with kap:
        # --- 5 coin butonu (logolu, hacim sırasıyla) ---
        for _c in coin_listesi:
            _sym = _c.split("/")[0]
            if st.button(("✔ " + _c) if _c == secilen_coin else _c, key=f"coin_btn_{_sym}", width='stretch'):
                if _c != secilen_coin:
                    st.session_state["secili_coin"] = _c
                    st.rerun()

        if not kilit_acik:
            if st.button("🔓 İşlem Açma Kilidini Aç", key="btn_islem_kilidi_ac", width='stretch'):
                if coin_listesi:
                    yon_secimlerini_temizle()
                    st.session_state["islem_emri_kilit_acik"] = True
                    st.rerun()
                else:
                    st.warning("Uygun işlem yapılacak coin bulunmuyor!")
        else:
            st.button("🔓 İşlem kilidi açık · işlem alanı aşağıda", key="btn_kilit_durum", width='stretch', disabled=True)

with col_orta_grafik:
    st.markdown("<h3>🌐 Top 5 Coin (Oransal Omurga & Teknik Mıknatıs)</h3>", unsafe_allow_html=True)
    t_df_ham = total_ham_veri["df_market"]
    t_df = t_df_ham.tail(192).reset_index(drop=True)

    if not t_df.empty:
        delta = t_df["Close"].diff()
        rs = (delta.where(delta > 0, 0)).rolling(window=14).mean() / (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        t_df["RSI"] = (100 - (100 / (1 + rs))).fillna(50)
        t_df = t_df.tail(96).reset_index(drop=True)   # 8 saat (5 dk × 96); RSI, ilk 96 mumla ısınmış olarak hesaplandı

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
        _seviyeler = sorted(fib_levels.keys())
        _bant_renkleri = [
            (96, 10, 36), (130, 30, 30), (158, 72, 18), (148, 110, 6),
            (192, 172, 14), (92, 128, 22), (24, 104, 40), (8, 70, 30)
        ]
        for _i in range(len(_seviyeler) - 1):
            _rgb = _bant_renkleri[min(_i, len(_bant_renkleri) - 1)]
            fig_total.add_hrect(y0=fib_levels[_seviyeler[_i]], y1=fib_levels[_seviyeler[_i + 1]],
                                fillcolor=f"rgb{_rgb}", opacity=1, line_width=0, layer="below")
        for oran, val in fib_levels.items():
            _ton = "255,235,59" if oran == 0.5 else ("0,255,0" if oran > 0.5 else "255,75,0")
            fig_total.add_hline(y=val, line_width=1.0, line_dash="dot", line_color=f"rgba({_ton},0.65)")
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
            template="plotly_dark", margin=dict(t=28, b=32, l=8, r=(56 if IS_MOBIL else 86)), height=(300 if IS_MOBIL else 372),
            xaxis=dict(fixedrange=True, range=[min_zaman, max_zaman_grafik], dtick=3600000, tickformat="%H:%M", tickangle=0,
                       tickfont=dict(size=12, color="#c3cfe2"), showgrid=True, gridcolor="rgba(255,255,255,0.16)", gridwidth=1,
                       zeroline=False, showline=False),
            yaxis=dict(showticklabels=False, range=[alt_sinir, ust_sinir], showgrid=False, zeroline=False, fixedrange=True),
            xaxis_rangeslider_visible=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            hovermode="x unified", hoverlabel=dict(bgcolor="#101827", bordercolor="#253247", font=dict(color="#e8eef8", size=12)),
            legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, font=dict(color="#aebdd2", size=11), bgcolor="rgba(0,0,0,0)"),
        )
        try:
            _grafik_kap = st.container(key="grafik_total")
        except TypeError:
            _grafik_kap = st.container()
        with _grafik_kap:
            st.plotly_chart(fig_total, width='stretch', config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False, "staticPlot": False})

with col_sag_endeks:
    st.markdown("<h3>Top 5 Coin Endeksi</h3>", unsafe_allow_html=True)
    try:
        _sag_kap = st.container(key="islem_sag_kap")
    except TypeError:
        _sag_kap = st.container()
    with _sag_kap:
        t_toplam_puan = t_l_puan + t_s_puan
        t_yuzde = (t_l_puan / t_toplam_puan * 100.0) if t_toplam_puan > 0 else 50.0

        # --- YENİ SLİDER / ÇUBUK GÖSTERİMİ ---
        t_k_yuzde = 100.0 - t_yuzde
        t_slider_html = matris_birlesik_html(t_puan_val, total_ham_veri["aktif_yon"], t_yuzde, t_k_yuzde)
        st.markdown(f'<div style="margin-bottom: 8px;">{t_slider_html}</div>', unsafe_allow_html=True)

        t_zaman_kat = total_ham_veri["zaman_katkilari"]
        boxes_listesi = []
        for etk, veri in t_zaman_kat.items():
            sl, ss = veri["sl"], veri["ss"]
            kazanan_renk = "#00FF00" if sl >= ss else "rgb(255, 75, 0)"
            boxes_listesi.append(f'<div style="background-color: {kazanan_renk}; color: #000000; padding: 6px; border-radius: 6px; text-align: center; font-weight: 800; font-size: 13px; margin-bottom: 6px; line-height: 1.3; white-space: nowrap;">{etk} · L: {sl:.2f}p | S: {ss:.2f}p</div>')
        boxes_birlestirilmis = "".join(boxes_listesi)

        st.markdown(f'<div class="metric-container" style="text-align: center; padding: 10px !important;"><div style="font-size: 15px; font-weight: bold; margin-bottom: 8px; line-height: 1.5;">Top 5 Ortalama Değeri: <span style="color: #5b8cff;">${total_ham_veri["anlik_fiyat"] / 1e12:.2f}T</span><br>Puan: <span style="color: {"#00FF00" if total_ham_veri["aktif_yon"] == "Long" else ("rgb(255, 75, 0)" if total_ham_veri["aktif_yon"] == "Short" else "#ffc107")};">{total_ham_veri["nihai_puan"]:.1f} / 100 ({total_ham_veri["aktif_yon"]})</span></div>{boxes_birlestirilmis}</div>', unsafe_allow_html=True)


# ================== KİLİT AÇIKKEN: ANA SATIRIN ALTINDA AÇILAN İŞLEM ALANI ==================
if kilit_acik:
    if IS_MOBIL:
        _acik_alan = kap          # telefonda işlem alanı coin butonlarının hemen altında açılır (grafiğin altına kaymaz)
    else:
        _s2_sol, _s2_orta, _s2_sag = st.columns(SUTUN_ORANLARI)
        _acik_alan = _s2_sol
    with _acik_alan:
        if secilen_coin:
            coin_verisii = df_gosterge[df_gosterge["Coin"] == secilen_coin].iloc[0]
            long_puani, short_puani = float(coin_verisii["L_Puan"]), float(coin_verisii["S_Puan"])
            onerilen_yon = coin_verisii["Aktif_Yon"] if coin_verisii["Aktif_Yon"] in ("Long", "Short") else ("Long" if long_puani >= short_puani else "Short")

            # --- Yön seçimi (renkli Long / Short kutuları): her zaman serbest ---
            _yon_key = f"islem_yonu_{secilen_coin}"
            st.session_state.setdefault(_yon_key, onerilen_yon)
            secilen_yon = st.session_state[_yon_key]
            yon_manuel_ters = (secilen_yon != onerilen_yon)

            # Aynı coinde AYNI yönde açık pozisyon varsa ekleme; zıt yönde varsa ayrı (hedge) yeni işlem açılır
            acik_pozisyon_var, _karsi_acik = False, False
            _acik_satir = pd.DataFrame()
            if not df_gecmis_temp.empty and "Durum" in df_gecmis_temp.columns:
                _acik_df_yon = df_gecmis_temp[~durum_kapali_maskesi(df_gecmis_temp["Durum"])]
                _acik_coin = _acik_df_yon[_acik_df_yon["Coin"] == secilen_coin]
                _ayni_maske = _acik_coin["Yon"].astype(str).str.contains(secilen_yon, regex=False)
                _acik_satir = _acik_coin[_ayni_maske]
                acik_pozisyon_var = not _acik_satir.empty
                _karsi_acik = (not _acik_coin.empty) and _acik_satir.empty

            islem_kaldiraci = float(st.session_state.get("kaldirac_secim", KALDIRAC))
            if acik_pozisyon_var:
                islem_kaldiraci = satir_kaldiraci(_acik_satir.iloc[0])

            _ls, _ss = (secilen_yon == "Long"), (secilen_yon == "Short")
            _kl, _ks = st.columns(2, gap="small")
            with _kl:
                if st.button(f"LONG • {long_puani:.1f}p" + (" ⭐" if onerilen_yon == "Long" else ""), key="yon_long_sec" if _ls else "yon_long", width='stretch'):
                    st.session_state[_yon_key] = "Long"
                    st.rerun()
            with _ks:
                if st.button(f"SHORT • {short_puani:.1f}p" + (" ⭐" if onerilen_yon == "Short" else ""), key="yon_short_sec" if _ss else "yon_short", width='stretch'):
                    st.session_state[_yon_key] = "Short"
                    st.rerun()
            _not = "⭐ matrisin önerdiği yön"
            if acik_pozisyon_var:
                _not += " · bu yönde açık pozisyon var: ekleme yapılır"
            elif _karsi_acik:
                _not += " · zıt yönde açık pozisyon var: ters yönde AYRI yeni işlem açılır"
            st.caption(_not)
            st.caption(f"⚙️ Kaldıraç: {islem_kaldiraci:g}x" + (" (açık pozisyonun kaldıracı)" if acik_pozisyon_var else " · 'Kasa İşlemleri & Kaldıraç Belirleme' bölümünden değiştirilir"))

            # --- Seçilen yöne göre puan / stop / hedef ---
            anlik_matris_puani = round(long_puani if secilen_yon == "Long" else short_puani, 2)
            # Ters yön seçilirse stop/hedef yüzdeleri (risk/ödül oranı) önerilen yönünkiyle aynı kalır
            _oran_puani = float(coin_verisii["Skor"]) if yon_manuel_ters else anlik_matris_puani
            _stop_u, _hedef_c, anlik_risk_hedef_metin = calculate_coin_metrics_by_score(_oran_puani)
            islem_fiyat = float(coin_verisii["Fiyat"])
            if secilen_yon == "Long":
                islem_stop, islem_kar_al = islem_fiyat * (1.0 - _stop_u / 100.0), islem_fiyat * (1.0 + _hedef_c / 100.0)
            else:
                islem_stop, islem_kar_al = islem_fiyat * (1.0 + _stop_u / 100.0), islem_fiyat * (1.0 - _hedef_c / 100.0)
            _bsm = int(coin_verisii["Basamak"])
            islem_stop, islem_kar_al = round(islem_stop, _bsm), round(islem_kar_al, _bsm)

            if secilen_yon == coin_verisii["Aktif_Yon"]:
                onerilen_oran_val = float(coin_verisii["Sepet_Orani"])
            else:
                _w = trend_asamasini_ve_ikon_belirle(anlik_matris_puani, secilen_yon)[1]
                _kendi_w = 0.0 if coin_verisii["Notr"] else float(coin_verisii["Ham_Agirlik"])
                onerilen_oran_val = round(_w / max(toplam_aktif_agirlik - _kendi_w + _w, 1e-9) * 100.0, 1)

            esik_atla = (not acik_pozisyon_var) and (anlik_matris_puani < min_esik_bilgi)
            if yon_manuel_ters or esik_atla:
                st.caption(f"⚠️ {secilen_yon} puanı {anlik_matris_puani:.2f} (minimum eşik {min_esik_bilgi:g}). "
                           f"Stop / hedef oranı: %{anlik_risk_hedef_metin}; bu işlem manuel olarak açılır.")

            onerilen_tutar_hesap = round(mevcut_bakiye * (onerilen_oran_val / 100.0), 2)

            risk_mesaji, risk_eklenebilir = "", None
            try:
                _kap = risk_kapasitesi(toplam_kasa, df_gecmis_temp, secilen_coin, islem_fiyat, islem_stop, islem_kaldiraci, secilen_yon)
                _mevcut_miktar = 0.0
                if acik_pozisyon_var:
                    _mevcut_miktar = float(_acik_satir["Islem_Miktari"].iloc[0])
                risk_eklenebilir = max(0.0, min(_kap["azami"], _kap["tavan"]) - _mevcut_miktar)
                risk_mesaji = (f"🧱 Teminat tavanı: {_kap['tavan']:,.2f} $ (pozisyon büyüklüğü ≤ kasanın {MAKS_POZISYON_ORANI:g} katı). "
                               f"🛡️ Risk sınırı: bu coinde azami toplam teminat {_kap['azami']:,.2f} $ "
                               f"(işlem başı risk %{ISLEM_BASINA_RISK_YUZDE:g} = {_kap['islem_limit']:,.2f} $, "
                               f"toplam risk payından kalan {_kap['kalan_toplam_risk']:,.2f} $), "
                               f"eklenebilir tutar {risk_eklenebilir:,.2f} $; komisyon: giriş %{KOMISYON_TAKER*100:g}, "
                               f"hedef çıkışı %{KOMISYON_MAKER*100:g}, stop çıkışı %{KOMISYON_TAKER*100:g}.")
                onerilen_tutar_hesap = round(min(onerilen_tutar_hesap, risk_eklenebilir), 2)
            except Exception as _e:
                print(f"Risk kapasitesi hesaplanamadı: {_e}")

            if acik_pozisyon_var:
                st.markdown("""<div style="background:linear-gradient(145deg,#1f2b3e,#162234); color:#e8eef8; border:1px solid #3b82f6; padding:12px; border-radius:10px; margin-bottom:12px; font-size:13px; line-height:1.8;"><div style="font-weight:750; color:#60a5fa; margin-bottom:4px;">🔄 Açık Pozisyona Ekleme Modu</div><div style="color:#dce6f5;">Bu coin için açık bir pozisyonunuz var. Girilen tutar ağırlıklı ortalama ile maliyete eklenecektir.</div></div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""<div style="background:linear-gradient(145deg,#17263b,#111b2b); color:#e8eef8; border:1px solid #30415b; padding:12px; border-radius:10px; margin-bottom:12px; font-size:13px; line-height:1.8;"><div style="font-weight:750; color:#ffd166; margin-bottom:4px;">💡 Matris Önerisi (Oransal & Akışkan)</div><div style="color:#dce6f5;">Önerilen yön: <b style="color:#ffffff;">{onerilen_yon}</b> &nbsp;|&nbsp; Long puanı: <b style="color:#ffffff;">{long_puani:.2f}</b> &nbsp;|&nbsp; Short puanı: <b style="color:#ffffff;">{short_puani:.2f}</b></div><div style="color:#dce6f5;">Seçilen yön: <b style="color:#ffffff;">{secilen_yon}</b> (puan {anlik_matris_puani:.2f}, stop / hedef %{anlik_risk_hedef_metin})</div><div style="color:#dce6f5;">Önerilen oran: <b style="color:#ffffff;">%{onerilen_oran_val:.1f}</b></div><div style="color:#dce6f5;">Önerilen tutar: <b style="color:#ffffff;">{onerilen_tutar_hesap:,.2f} $</b></div></div>""", unsafe_allow_html=True)

            if risk_mesaji:
                st.markdown(f'<div class="risk-line">{risk_mesaji.replace("$", "&#36;")}</div>', unsafe_allow_html=True)

            hesaplanan_tutar = min(100.0, float(mevcut_bakiye)) if acik_pozisyon_var else float(onerilen_tutar_hesap)
            guvenli_tutar = 0.0
            max_tutar = float(mevcut_bakiye) if mevcut_bakiye > 0 else 99999.0
            if acik_pozisyon_var and risk_eklenebilir is not None:
                hesaplanan_tutar = min(hesaplanan_tutar, float(risk_eklenebilir))
                guvenli_tutar = max(0.0, float(hesaplanan_tutar))
                max_tutar = max(float(guvenli_tutar), float(mevcut_bakiye)) if mevcut_bakiye > 0 else 99999.0

            try:
                _form_kap = st.container(key="islem_form_kap")
            except TypeError:
                _form_kap = st.container()
            with _form_kap:
                with st.form(key="islem_onay_formu", border=False):
                    manuel_girilen_tutar = st.number_input(
                        "Tutar ($ Giriniz):",
                        min_value=0.0,
                        max_value=float(max_tutar),
                        value=float(min(guvenli_tutar, max_tutar)),
                        step=10.0,
                        key="manuel_girilen_tutar_input",
                    )
                    risk_asimi_onay = st.checkbox(
                        "⚠️ Risk sınırını aşarak ekle (bilinçli onay)" if acik_pozisyon_var else "⚠️ Risk sınırını aşarak işlem aç (bilinçli onay)",
                        key=f"risk_asimi_{st.session_state.get('risk_asimi_sayac', 0)}",
                        help="İşaretlersen bu emir için işlem başı ve toplam risk sınırı uygulanmaz; yalnızca bakiye kontrolü sürer. Her emirden sonra kutu sıfırlanır.",
                    )
                    _fb1, _fb2 = st.columns(2, gap="small")
                    with _fb1:
                        submit_islem = _form_butonu("🔄 Ekleme Yap" if acik_pozisyon_var else "🚀 İşlemi Başlat")
                    with _fb2:
                        kapat_kilit_tik = _form_butonu("🔒 Kilidi Kapat")
        else:
            st.warning("Uygun işlem yapılacak coin bulunmuyor!")

# Buton kontrolleri formun DIŞINDADIR
if kapat_kilit_tik:
    yon_secimlerini_temizle()
    st.session_state["islem_emri_kilit_acik"] = False
    st.rerun()

if submit_islem:
    if not secilen_coin or coin_listesi == []:
        st.error("⚠️ Geçerli bir coin seçmelisiniz!")
    elif coin_verisii is not None:
        basari, mesaj = yeni_islem_ekle(
            secilen_coin,
            secilen_yon,
            islem_fiyat,
            manuel_girilen_tutar,
            islem_stop,
            islem_kar_al,
            "Oransal_Matris",
            anlik_matris_puani,
            anlik_risk_hedef_metin,
            esik_atla=esik_atla,
            kaldirac=islem_kaldiraci,
            risk_asimi=risk_asimi_onay
        )
        if basari:
            yon_secimlerini_temizle()
            st.session_state["islem_emri_kilit_acik"] = False
            st.success(mesaj)
            st.balloons()
            time.sleep(1)
            st.rerun()
        else:
            st.error(mesaj)

# Plotly'nin grafik alanına yeni boyutuyla oturması için pencere yeniden boyutlandırma sinyali (sütun dışında, hizayı bozmaz)
try:
  if not IS_MOBIL:
    components.html("""<script>
(function(){
  var P; try { P = window.parent; var d = P.document; } catch(e) { return; }
  function q(x){ return d.querySelector(x); }
  function fitUst(){
    var bt=q('.st-key-ana_kasa_butonu button'); if(!bt) return;
    var hb=bt.closest('[data-testid="stHorizontalBlock"]'); if(!hb) return;
    var mcs=hb.querySelectorAll('.metric-container'); if(!mcs.length) return;
    var mc=mcs[mcs.length-1]; bt.style.removeProperty('height');
    var dB=mc.getBoundingClientRect().bottom-bt.getBoundingClientRect().bottom;
    if(Math.abs(dB)>1) bt.style.setProperty('height',(bt.offsetHeight+dB)+'px','important');
  }
  function fitAnaliz(){
    var ak=q('.st-key-analiz_kart'), rk=q('.st-key-risk_kart_kap'); if(!ak||!rk) return;
    var oc=rk.querySelector('.ozet-card'); if(!oc) return;
    oc.style.minHeight=''; ak.style.minHeight='';
    var a=ak.getBoundingClientRect().bottom, r=oc.getBoundingClientRect().bottom, t=Math.max(a,r);
    if(t-r>1) oc.style.minHeight=(oc.offsetHeight+t-r)+'px';
    if(t-a>1) ak.style.minHeight=(ak.offsetHeight+t-a)+'px';
  }
  function fit(){
    if(P.innerWidth <= 900) return;   // dar ekranda hizalama kapalı
    fitUst(); fitAnaliz();
    var sol=q('.st-key-islem_sol_kap'), gr=q('.st-key-grafik_total'), sg=q('.st-key-islem_sag_kap');
    if(!sol||!gr||!sg) return;
    var kartlar = sg.querySelectorAll('.metric-container'), sgSon = kartlar.length ? kartlar[kartlar.length-1] : null;
    var pc = gr.querySelector('[data-testid="stPlotlyChart"]');
    sol.style.minHeight=''; if(sgSon) sgSon.style.minHeight='';
    function alt(e){ return e.getBoundingClientRect().bottom; }
    var grAlt = pc || gr;
    var sgAlt = sgSon || sg;
    var hedef = Math.max(alt(sol), alt(grAlt), alt(sgAlt));
    var dS=hedef-alt(sol), dG=hedef-alt(grAlt), dR=hedef-alt(sgAlt);
    if(dS>1) sol.style.minHeight=(sol.offsetHeight+dS)+'px';
    if(sgSon && dR>1) sgSon.style.minHeight=(sgSon.offsetHeight+dR)+'px';
    if(pc && dG>1){
      pc.style.setProperty('height',(pc.offsetHeight+dG)+'px','important');
      P.__fitBusy=true; setTimeout(function(){P.__fitBusy=false;},700);
      try{ P.dispatchEvent(new Event('resize')); }catch(e){}
    }
  }
  [300,900,1800,3200].forEach(function(t){ setTimeout(fit,t); });
  if(P.__fitH) P.removeEventListener('resize', P.__fitH);
  P.__fitH=function(){ if(P.__fitBusy) return; clearTimeout(P.__fitT); P.__fitT=setTimeout(fit,250); };
  P.addEventListener('resize', P.__fitH);
})();
</script>""", height=0)
except Exception:
    pass

st.markdown("---")

df_gecmis = islem_gecmisi_getir(sheet_guncelle=False)
acik_islem_listesi = df_gecmis[~durum_kapali_maskesi(df_gecmis["Durum"])]["Islem_ID"].tolist() if not df_gecmis.empty and "Durum" in df_gecmis.columns else []

# ---------------- geri çağrılar ----------------
def _ac_kapat_toggle(anahtar):
    st.session_state[anahtar] = not st.session_state.get(anahtar, False)

def _sunum_ayarla(sadece_aktif):
    st.session_state["sadece_aktifleri_goster"] = bool(sadece_aktif)

def _rapor_cb():
    """Tüm işlemler + kasa + para akışı + analiz içeren A4 PDF raporunu üretip doğrudan Telegram'a gönderir."""
    try:
        veri_onbellegini_temizle()
        df_t = islem_gecmisi_getir()
        df_k = kasa_defteri_getir()
        bak = bakiye_durumunu_getir(ortak_fiyat_havuzu)
        fiyatlar = {c: ortak_fiyat_havuzu.get(c, baz_fiyatlar.get(c, 0.0)) for c in (df_t["Coin"].unique() if df_t is not None and not df_t.empty else [])}
        pdf_b, hata = rapor_pdf_olustur(df_t, df_k, bak, fiyatlar, tr_zaman())
        if pdf_b is None:
            st.session_state["kart_kapat_mesaj"] = (False, f"Rapor oluşturulamadı: {hata}")
            return
        dosya_adi = f"portfoy_raporu_{tr_zaman().strftime('%Y%m%d_%H%M')}.pdf"
        
        ok_t, msg_t = rapor_telegram_gonder(pdf_b, dosya_adi, bak, tr_zaman())
        if ok_t:
            st.session_state.pop("rapor_pdf", None)
            st.session_state["kart_kapat_mesaj"] = (True, f"🚀 Rapor başarıyla Telegram'a gönderildi ({dosya_adi}).")
        else:
            st.session_state["rapor_pdf"] = (pdf_b, dosya_adi)
            st.session_state["kart_kapat_mesaj"] = (False, f"⚠️ Telegram gönderim hatası: {msg_t}. Raporu aşağıdan indirebilirsiniz.")
    except Exception as e:
        st.session_state["kart_kapat_mesaj"] = (False, f"Rapor hatası: {e}")

def _tum_kapat_cb():
    try:
        if not st.session_state.get("tum_kapat_acik", False):
            return
        veri_onbellegini_temizle()
        df_t = islem_gecmisi_getir()
        acik_t = df_t[~durum_kapali_maskesi(df_t["Durum"])] if df_t is not None and not df_t.empty else pd.DataFrame()
        if acik_t.empty:
            st.session_state["kart_kapat_mesaj"] = (True, "Kapatılacak açık işlem yok.")
            st.session_state["tum_kapat_acik"] = False
            return
        basarili = 0
        for _, r in acik_t.iterrows():
            coin_t = r["Coin"]
            fiyat_t = ortak_fiyat_havuzu.get(coin_t, fiyat_cek_binance(coin_t))
            ok_t, _ = manuel_islem_kapat(int(r["Islem_ID"]), fiyat_t, kapatilacak_miktar=None)
            if ok_t:
                basarili += 1
        st.session_state["kart_kapat_mesaj"] = (True, f"{basarili}/{len(acik_t)} işlem kapatıldı.")
        st.session_state["tum_kapat_acik"] = False
    except Exception as e:
        st.session_state["kart_kapat_mesaj"] = (False, f"Toplu kapatma hatası: {e}")

def _donem_rapor_cb():
    """Seçilen Başlangıç/Bitiş ID aralığı için PDF raporu üretip Telegram'a gönderir."""
    try:
        bas_id = int(st.session_state.get("donem_bas_id", 0))
        bit_id = int(st.session_state.get("donem_bit_id", 0))
        if bas_id <= 0 or bit_id < bas_id:
            st.session_state["kart_kapat_mesaj"] = (False, "Başlangıç ID, Bitiş ID'den büyük olamaz ve 0'dan büyük olmalı.")
            return
        veri_onbellegini_temizle()
        df_t = islem_gecmisi_getir()
        df_k = kasa_defteri_getir()
        if df_t is None or df_t.empty or not ((df_t["Islem_ID"] >= bas_id) & (df_t["Islem_ID"] <= bit_id)).any():
            st.session_state["kart_kapat_mesaj"] = (False, f"ID {bas_id}-{bit_id} aralığında işlem bulunamadı.")
            return
        bak = bakiye_durumunu_getir(ortak_fiyat_havuzu)
        fiyatlar = {c: ortak_fiyat_havuzu.get(c, baz_fiyatlar.get(c, 0.0)) for c in df_t["Coin"].unique()}
        pdf_b, hata = rapor_pdf_olustur(df_t, df_k, bak, fiyatlar, tr_zaman(), id_araligi=(bas_id, bit_id))
        if pdf_b is None:
            st.session_state["kart_kapat_mesaj"] = (False, f"Rapor oluşturulamadı: {hata}")
            return
        dosya_adi = f"donem_raporu_ID{bas_id}-{bit_id}_{tr_zaman().strftime('%Y%m%d_%H%M')}.pdf"
        ok_t, msg_t = rapor_telegram_gonder(pdf_b, dosya_adi, bak, tr_zaman())
        if ok_t:
            st.session_state.pop("rapor_pdf", None)
            st.session_state["donem_rapor_acik"] = False
            st.session_state["kart_kapat_mesaj"] = (True, f"🚀 Dönem raporu (ID {bas_id}-{bit_id}) Telegram'a gönderildi.")
        else:
            st.session_state["rapor_pdf"] = (pdf_b, dosya_adi)
            st.session_state["kart_kapat_mesaj"] = (False, f"⚠️ Telegram gönderim hatası: {msg_t}. Raporu aşağıdan indirebilirsiniz.")
    except Exception as e:
        st.session_state["kart_kapat_mesaj"] = (False, f"Dönem rapor hatası: {e}")

st.markdown(f"""<style>
.st-key-btn_sun_tum button, .st-key-btn_rapor button, .st-key-btn_tum_ac button {{ background:#252569 !important; border:1px solid #3a3a9a !important; min-height:44px; }}
.st-key-btn_sun_tum button p, .st-key-btn_rapor button p, .st-key-btn_tum_ac button p {{ color:#ffffff !important; font-weight:800 !important; }}
.st-key-btn_sun_aktif button, .st-key-btn_donem_ac button, .st-key-btn_donem_onay button {{ background:#ead518 !important; border:none !important; min-height:44px; }}
.st-key-btn_sun_aktif button p, .st-key-btn_donem_ac button p, .st-key-btn_donem_onay button p {{ color:#000000 !important; font-weight:800 !important; }}
.grp-etiket {{ display:flex; align-items:center; justify-content:flex-end; min-height:44px; font-size:15px; font-weight:800; color:#e8eef8; text-align:right; }}
</style>""", unsafe_allow_html=True)

col_sol_analiz, col_sag_sonlandir = st.columns([3.3, 1], gap="medium")
with col_sol_analiz:
    try:
        _analiz_kap = st.container(border=True, key="analiz_kart")
    except TypeError:
        _analiz_kap = st.container(border=True)
    with _analiz_kap:
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
            giris_kom_uygulama = giris_komisyon_toplami(_df_kasa_anapara)
            net_fark_dolar = toplam_kazanc_dolar - toplam_kayip_dolar - giris_kom_uygulama
            kar_yuzde = (karli_sayisi / toplam_kapanan * 100.0) if toplam_kapanan > 0 else 0.0
            zarar_yuzde = (zararli_sayisi / toplam_kapanan * 100.0) if toplam_kapanan > 0 else 0.0
            toplam_hareket_dolar = toplam_kazanc_dolar + toplam_kayip_dolar
            parasal_basari_yuzde = (toplam_kazanc_dolar / toplam_hareket_dolar * 100.0) if toplam_hareket_dolar > 0 else 0.0
            net_renk = RENK_YESIL if net_fark_dolar >= 0 else RENK_KIRMIZI
            parasal_renk = RENK_YESIL if parasal_basari_yuzde >= 50 else RENK_KIRMIZI
            basari_renk = RENK_YESIL if kar_yuzde >= 50 else RENK_KIRMIZI

            def _donut(etiketler, degerler):
                f_ = px.pie(pd.DataFrame({"Durum": etiketler, "Deger": degerler}), names="Durum", values="Deger", hole=0.55,
                            color="Durum", color_discrete_map={etiketler[0]: "#00FF00", etiketler[1]: "rgb(255, 75, 0)"})
                f_.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#e8eef8", size=13),
                                 margin=dict(t=6, b=6, l=6, r=6), height=(210 if IS_MOBIL else 270), showlegend=False)
                f_.update_traces(textfont_size=15, textinfo="percent", marker=dict(line=dict(width=0)), sort=False)
                return f_

            g_fin, g_str = st.columns(2, gap="medium")
            with g_fin:
                _d1, _t1 = st.columns([1, 1.15], gap="small")
                with _d1:
                    st.plotly_chart(_donut(["Toplam Kâr", "Toplam Zarar"], [max(toplam_kazanc_dolar, 0.0001), max(toplam_kayip_dolar, 0.0001)]),
                                    width='stretch', config={"responsive": True, "displayModeBar": False})
                with _t1:
                    st.markdown(f"""<div style="font-size:19px; font-weight:bold; color:#e8eef8; margin-bottom:8px;">💰 Finansal Metrikler</div><div style="font-size:16px; line-height:1.9; color:#cfd9ea;">• Net Kâr: <b style="color:{net_renk};">{net_fark_dolar:+,.2f} $</b><br>• Giriş Komisyonu: <b style="color:{RENK_KIRMIZI};">-{giris_kom_uygulama:,.2f} $</b><br>• Toplam Kâr: <b style="color:{RENK_YESIL};">+{toplam_kazanc_dolar:,.2f} $</b><br>• Toplam Zarar: <b style="color:{RENK_KIRMIZI};">-{toplam_kayip_dolar:,.2f} $</b><br>• Parasal Başarı Oranı: <b style="color:{parasal_renk};">%{parasal_basari_yuzde:.1f}</b></div>""", unsafe_allow_html=True)
            with g_str:
                _d2, _t2 = st.columns([1, 1.15], gap="small")
                with _d2:
                    st.plotly_chart(_donut(["Kârlı", "Zararlı"], [max(karli_sayisi, 0.0001), max(zararli_sayisi, 0.0001)]),
                                    width='stretch', config={"responsive": True, "displayModeBar": False})
                with _t2:
                    st.markdown(f"""<div style="font-size:19px; font-weight:bold; color:#e8eef8; margin-bottom:8px;">📈 Strateji Metrikleri</div><div style="font-size:16px; line-height:1.9; color:#cfd9ea;">• Toplam Kapanan Pozisyon: <b style="color:#e8eef8;">{toplam_kapanan} Adet</b><br>• Kârlı Pozisyonlar: <b style="color:{RENK_YESIL};">{karli_sayisi} Adet (%{kar_yuzde:.1f})</b><br>• Zararlı Pozisyonlar: <b style="color:{RENK_KIRMIZI};">{zararli_sayisi} Adet (%{zarar_yuzde:.1f})</b><br>• Başarı Oranı: <b style="color:{basari_renk};">%{kar_yuzde:.1f}</b></div>""", unsafe_allow_html=True)
        else:
            st.info("ℹ️ Henüz kapanmış işlem bulunmuyor.")

        # ---- buton sırası: İşlem Sunumu | Rapor Gönder ----
        _e1, _b1, _b2, _e2, _b3, _b4 = st.columns([0.9, 1, 1, 0.9, 1, 1], gap="small")
        with _e1:
            st.markdown('<div class="grp-etiket">İşlem Sunumu</div>', unsafe_allow_html=True)
        with _b1:
            st.button("Tüm İşlemler", key="btn_sun_tum", width='stretch', on_click=_sunum_ayarla, args=(False,))
        with _b2:
            st.button("Aktif İşlemler", key="btn_sun_aktif", width='stretch', on_click=_sunum_ayarla, args=(True,))
        with _e2:
            st.markdown('<div class="grp-etiket">Rapor Gönder</div>', unsafe_allow_html=True)
        with _b3:
            st.button("Tam Rapor", key="btn_rapor", width='stretch', on_click=_rapor_cb)
        with _b4:
            st.button("Dönem Rapor", key="btn_donem_ac", width='stretch', on_click=_ac_kapat_toggle, args=("donem_rapor_acik",))

        if st.session_state.get("donem_rapor_acik", False):
            _idler_t = df_gecmis["Islem_ID"].astype(int) if not df_gecmis.empty else pd.Series([1], dtype=int)
            st.session_state.setdefault("donem_bas_id", int(_idler_t.min()))
            st.session_state.setdefault("donem_bit_id", int(_idler_t.max()))
            _dc1, _dc2, _dc3 = st.columns([1, 1, 1.3], gap="small")
            with _dc1:
                st.number_input("Başlangıç ID", min_value=1, step=1, key="donem_bas_id")
            with _dc2:
                st.number_input("Bitiş ID", min_value=1, step=1, key="donem_bit_id")
            with _dc3:
                st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
                st.button("✅ Onayla ve Telegram'a Gönder", key="btn_donem_onay", width='stretch', on_click=_donem_rapor_cb)

        if "rapor_pdf" in st.session_state:
            _pdf_b, _pdf_ad = st.session_state["rapor_pdf"]
            st.download_button("📄 Raporu İndir", data=_pdf_b, file_name=_pdf_ad, mime="application/pdf", width="stretch")

with col_sag_sonlandir:
    st.markdown("<h3>🛡️ Risk & Kâr Özeti</h3>", unsafe_allow_html=True)
    try:
        _risk_kap = st.container(key="risk_kart_kap")
    except TypeError:
        _risk_kap = st.container()
    with _risk_kap:
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

        if not durum_kapali_mi(row["Durum"]):
            _lev_s = satir_kaldiraci(row)
            anlik_kz_sozluk[islem_id] = round(miktar * _lev_s * (((anl_f - giris_fiyat) / giris_fiyat) if "Long" in yon else ((giris_fiyat - anl_f) / giris_fiyat)) - cikis_komisyonu(miktar, False, _lev_s), 2)
        else:
            anlik_kz_sozluk[islem_id] = float(row["Net_Kar_Zarar"])

def _kart_kapat_cb(islem_id, coin, miktar):
    onay_k, tutar_k = f"kart_ac_{islem_id}", f"kismi_tutar_{islem_id}"
    try:
        if not st.session_state.get(onay_k, False):
            return
        girilen = float(st.session_state.get(tutar_k, miktar))
        if girilen <= 0:
            st.session_state["kart_kapat_mesaj"] = (False, "Tutar 0'dan büyük olmalı!")
            return
        hedef_miktar = None if girilen >= float(miktar) - 0.005 else girilen
        fiyat_k = ortak_fiyat_havuzu.get(coin, fiyat_cek_binance(coin))
        ok_k, msg_k = manuel_islem_kapat(int(islem_id), fiyat_k, kapatilacak_miktar=hedef_miktar)
        st.session_state["kart_kapat_mesaj"] = (ok_k, msg_k)
        if ok_k:
            st.session_state[onay_k] = False
    except Exception as e:
        st.session_state["kart_kapat_mesaj"] = (False, f"Kapatma hatası: {e}")

_hb1, _hb2, _hb3 = st.columns([1.3, 1.4, 3], gap="small")
with _hb1:
    st.markdown("<h3>🧭 Açık Pozisyonlar</h3>" if st.session_state["sadece_aktifleri_goster"] else "<h3>📋 Tüm İşlemler</h3>", unsafe_allow_html=True)
with _hb2:
    st.button("Aktif İşlemleri Sonlandır", key="btn_tum_ac", width="stretch", on_click=_ac_kapat_toggle, args=("tum_kapat_acik",))
with _hb3:
    if st.session_state.get("tum_kapat_acik", False):
        st.button("🛑 TÜM İŞLEMLERİ KAPAT", key="btn_tum_kapat", width="stretch", on_click=_tum_kapat_cb)

if st.session_state["sadece_aktifleri_goster"]:
    _df_acik_kart = df_gecmisile_goster[~durum_kapali_maskesi(df_gecmisile_goster["Durum"])] if not df_gecmisile_goster.empty else pd.DataFrame()
    if _df_acik_kart.empty:
        st.info("Şu an açık pozisyon yok.")
    else:
        try:
            _kart_alani = st.container(key="poz_kartlari")
        except TypeError:
            _kart_alani = st.container()
        with _kart_alani:
            _satirlar = [_df_acik_kart.iloc[i:i + 4] for i in range(0, len(_df_acik_kart), 4)]
            for _grup in _satirlar:
                _kolonlar = st.columns(4)
                for _k, (_, _r) in zip(_kolonlar, _grup.iterrows()):
                    with _k:
                        _id = int(_r["Islem_ID"])
                        st.markdown(pozisyon_karti_html(_r, anlik_fiyat_sozluk.get(_r["Islem_ID"]), logo_urls.get(_r["Coin"], ""), toplam_kasa), unsafe_allow_html=True)
                        _miktar = float(_r["Islem_Miktari"])
                        st.button(f"{_id} ID Sonlandır", key=f"btn_kart_ac_{_id}", width="stretch", on_click=_ac_kapat_toggle, args=(f"kart_ac_{_id}",))
                        if st.session_state.get(f"kart_ac_{_id}", False):
                            _tutar = st.number_input("Tutar ($)", min_value=0.01, max_value=_miktar, value=_miktar, step=10.0, key=f"kismi_tutar_{_id}")
                            st.button("🛑 İşlemi Kapat", key=f"btn_kart_kapat_{_id}", width="stretch", on_click=_kart_kapat_cb, args=(_id, _r["Coin"], _miktar))

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
        anlik_fiyat_h = f'<div style="background-color: {"#00FF00" if float(row["Anlik_Fiyat_Deger"] or 0) > float(row["Giris_Fiyat"]) else "rgb(255, 75, 0)"}; color: #000000; padding: 5px; font-weight: bold;">{float(row["Anlik_Fiyat_Deger"] or 0):,.2f}&nbsp;$</div>'

        if not durum_kapali_mi(row["Durum"]):
            kapanis_fiyat_h, durum_h = '<div style="padding: 5px; color: #91a0b8;">-</div>', '<div style="background-color: #5b8cff; color: white; padding: 4px; border-radius: 4px; font-weight: bold;">Aktif</div>'
        else:
            is_kar = float(row["Net_Kar_Zarar"]) >= 0
            sinif = "kar-hucre" if is_kar else "zarar-hucre"
            kapanis_fiyat_h = f'<div class="{sinif}">{float(row.get("Kapanis_Fiyati", 0.0) or row["Giris_Fiyat"]):,.2f}&nbsp;$</div>'
            durum_h = f'<div class="{sinif}">{row["Durum"]}</div>'

        kz_h = f'<div style="background-color: {"#00FF00" if float(row["Anlik_KZ_Deger"] or 0) >= 0 else "rgb(255, 75, 0)"}; color: #000000; padding: 5px; font-weight: bold;">{float(row["Anlik_KZ_Deger"] or 0):+,.2f}&nbsp;$</div>'

        portfoy_html += f"<tr><td>{row['Islem_ID']}</td><td>{row['Acilis_Zamani']}</td><td>{logo_h}</td><td>{row['Coin']}</td><td>{yon_h}</td><td>{float(row['Giris_Fiyat']):,.2f}&nbsp;$</td><td>{anlik_fiyat_h}</td><td>{kapanis_fiyat_h}</td><td>{row.get('Matris_Puan_RH', '-')}</td><td>{float(row['Islem_Miktari']):,.2f}&nbsp;$</td><td>{float(row['Kar_Al']):,.2f}&nbsp;$</td><td>{float(row['Stop']):,.2f}&nbsp;$</td><td>{float(row['Canli_Beklenen_Kar']):,.2f}&nbsp;$</td><td>{float(row['Canli_Olasi_Stop']):,.2f}&nbsp;$</td><td>{durum_h}</td><td>{kz_h}</td><td>{row['Kapanis_Zamani']}</td><td>{float(row['Guncel_Kasa']):,.2f}&nbsp;$</td></tr>"
else:
    portfoy_html += "<tr><td colspan='18' style='text-align: center; color: #91a0b8; padding: 20px;'>Kayıtlı işlem bulunmuyor.</td></tr>"

portfoy_html += "</tbody></table>"
if not st.session_state["sadece_aktifleri_goster"]:
    st.markdown(f'<div class="table-container">{portfoy_html}</div>', unsafe_allow_html=True)
