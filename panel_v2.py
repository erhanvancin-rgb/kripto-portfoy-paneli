import json
import os
import smtplib
import threading
import time
import math
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
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
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(
    page_title="Pro Kripto Canlı Akış ve Paneli",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- OTOMATİK YENİLEME (120 SANİYE) ---
st_autorefresh(interval=120000, key="kripto_panel_otomatik_yenileme")

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
.metric-container { min-height:104px; }
.metric-container p { color:var(--muted) !important; font-size:12px !important; letter-spacing:.35px; }
.metric-container h1 { color:var(--text) !important; font-size:25px !important; font-weight:750 !important; }
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
</style>
""",
    unsafe_allow_html=True,
)

# --- SABİTLER ---
GOOGLE_SHEET_DOSYA = "KriptoPortfoyVeritabani"
ARSIV_KLASORU = "arsiv"
BASLANGIC_BAKIYE = 500.0
KALDIRAC = 3
TR_TZ = pytz.timezone("Europe/Istanbul")


def tr_zaman():
    return datetime.now(TR_TZ)


coinler = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"]
logo_urls = {
    "BTC/USDT": (
        "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/btc.png"
    ),
    "ETH/USDT": (
        "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/eth.png"
    ),
    "BNB/USDT": (
        "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/bnb.png"
    ),
    "SOL/USDT": (
        "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/sol.png"
    ),
    "XRP/USDT": (
        "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/xrp.png"
    ),
    "TOTAL": (
        "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/usdt.png"
    ),
}
baz_fiyatlar = {
    "BTC/USDT": 83750.0,
    "ETH/USDT": 2511.0,
    "BNB/USDT": 745.0,
    "SOL/USDT": 107.6,
    "XRP/USDT": 1.373,
    "TOTAL": 2.77e12,
}


def gmail_bildirim_gonder(konu, icerik_html):
    gonderici_mail = "erhanvancin@gmail.com"
    uygulama_sifresi = "jkef zgaf zwtg qyom"
    alici_mail = "erhanvancin@gmail.com"

    try:
        msg = MIMEMultipart()
        msg["From"] = gonderici_mail
        msg["To"] = alici_mail
        msg["Subject"] = konu
        msg.attach(MIMEText(icerik_html, "html"))

        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(gonderici_mail, uygulama_sifresi)
        server.sendmail(gonderici_mail, alici_mail, msg.as_string())
        server.quit()
        return True, "E-posta başarıyla gönderildi."
    except Exception as e:
        print(f"Mail Gönderim Hatası: {e}")
        return False, str(e)


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
                        "timestamp",
                        "Open",
                        "High",
                        "Low",
                        "Close",
                        "Volume",
                        "Close_Time",
                        "QAV",
                        "Num_Trades",
                        "Taker_BBAV",
                        "Taker_BQAV",
                        "Ignore",
                    ],
                )
                df["timestamp"] = (
                    pd.to_datetime(df["timestamp"], unit="ms", utc=True)
                    .dt.tz_convert(TR_TZ)
                )
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
    base_p = baz_fiyatlar.get(
        coin_symbol, 2.77e12 if coin_symbol == "TOTAL" else 100.0
    )
    return pd.DataFrame({
        "timestamp": dates,
        "Open": [base_p] * limit,
        "High": [base_p] * limit,
        "Low": [base_p] * limit,
        "Close": [base_p] * limit,
    })


def calculate_coin_metrics_by_score(matris_puani):
    if matris_puani < 54.0:
        stop_uzde = 1.0
        hedef_uzde = 1.5
        risk_hedef_metin = "Nötr"
    elif 54.0 <= matris_puani <= 60.0:
        oran = (matris_puani - 54.0) / (60.0 - 54.0)
        stop_uzde = 1.2 - (1.2 - 1.0) * oran
        hedef_uzde = 1.5 + (1.8 - 1.5) * oran
    elif 60.0 < matris_puani <= 65.0:
        oran = (matris_puani - 60.0) / (65.0 - 60.0)
        stop_uzde = 0.9 - (0.9 - 0.8) * oran
        hedef_uzde = 1.9 + (2.2 - 1.9) * oran
    elif 65.0 < matris_puani <= 75.0:
        oran = (matris_puani - 65.0) / (75.0 - 65.0)
        stop_uzde = 0.8 - (0.8 - 0.7) * oran
        hedef_uzde = 2.3 + (2.8 - 2.3) * oran
    else:
        p = min(matris_puani, 100.0)
        oran = (p - 75.0) / (100.0 - 75.0)
        stop_uzde = 0.7
        hedef_uzde = 3.0 + (4.0 - 3.0) * oran

    hedef_carpan = hedef_uzde / stop_uzde if stop_uzde > 0 else 1.8

    if matris_puani >= 54.0:
        str_stop = f"{stop_uzde:.2f}".rstrip("0").rstrip(".").replace(".", ",")
        str_hedef = f"{hedef_uzde:.2f}".rstrip("0").rstrip(".").replace(".", ",")
        risk_hedef_metin = f"{str_stop} / {str_hedef}"

    return stop_uzde, hedef_carpan, risk_hedef_metin


def rsi_momentum_fib_ve_ema_katkisi_hesapla_logaritmik(df, max_puan):
    if df.empty or len(df) < 20:
        return 0.0, 0.0

    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
    anlik_fiyat = float(df["Close"].iloc[-1])
    anlik_ema = float(df["EMA20"].iloc[-1])

    fark_yuzde = (abs(anlik_fiyat - anlik_ema) / anlik_ema) * 100.0
    ema_log_carpan = min(1.0, np.log1p(fark_yuzde) / np.log1p(1.5))
    max_ema_bonus = max_puan * 0.04

    ema_bonus_long = (
        max_ema_bonus * ema_log_carpan if anlik_fiyat > anlik_ema else 0.0
    )
    ema_bonus_short = (
        max_ema_bonus * ema_log_carpan if anlik_fiyat < anlik_ema else 0.0
    )

    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi_serisi = 100 - (100 / (1 + rs))
    rsi_anlik = (
        float(rsi_serisi.iloc[-1]) if not rsi_serisi.isna().all() else 50.0
    )

    fark_rsi = abs(rsi_anlik - 50.0)
    rsi_log_carpan = min(1.0, np.log1p(fark_rsi) / np.log1p(20.0))
    max_rsi_bonus = max_puan * 0.03

    rsi_bonus_long = max_rsi_bonus * rsi_log_carpan if rsi_anlik > 50 else 0.0
    rsi_bonus_short = max_rsi_bonus * rsi_log_carpan if rsi_anlik < 50 else 0.0

    max_f = float(df["High"].max())
    min_f = float(df["Low"].min())
    fiyat_fark = max_f - min_f

    fib_bonus_long, fib_bonus_short = 0.0, 0.0
    if fiyat_fark > 0:
        fib_050 = min_f + (fiyat_fark * 0.5)
        fib_618 = min_f + (fiyat_fark * 0.618)

        mesafe_050 = abs(anlik_fiyat - fib_050) / fiyat_fark
        mesafe_618 = abs(anlik_fiyat - fib_618) / fiyat_fark
        min_mesafe = min(mesafe_050, mesafe_618)

        if min_mesafe < 0.05:
            yaklasim = (0.05 - min_mesafe) / 0.05
            fib_log_carpan = np.log1p(yaklasim * 10) / np.log1p(10)
            max_fib_bonus = max_puan * 0.03

            if anlik_fiyat >= anlik_ema:
                fib_bonus_long = max_fib_bonus * fib_log_carpan
            else:
                fib_bonus_short = max_fib_bonus * fib_log_carpan

    long_bonus = ema_bonus_long + rsi_bonus_long + fib_bonus_long
    short_bonus = ema_bonus_short + rsi_bonus_short + fib_bonus_short
    return long_bonus, short_bonus


def kurgusal_matris_hesapla(coin_symbol):
    anlik_fiyat = fiyat_cek_binance(coin_symbol)
    sembol_istek = coin_symbol if coin_symbol != "TOTAL" else "BTC/USDT"

    df_16s = kline_cek_binance(sembol_istek, "15m", 64)
    df_8s = kline_cek_binance(sembol_istek, "5m", 96)
    df_4s = kline_cek_binance(sembol_istek, "5m", 48)
    df_2s = kline_cek_binance(sembol_istek, "1m", 120)
    df_1s = kline_cek_binance(sembol_istek, "1m", 60)

    y16 = (
        len(df_16s[df_16s["Close"] > df_16s["Open"]]) if not df_16s.empty else 32
    )
    k16 = (
        len(df_16s[df_16s["Close"] < df_16s["Open"]]) if not df_16s.empty else 32
    )

    y8 = len(df_8s[df_8s["Close"] > df_8s["Open"]]) if not df_8s.empty else 48
    k8 = len(df_8s[df_8s["Close"] < df_8s["Open"]]) if not df_8s.empty else 48

    y4 = len(df_4s[df_4s["Close"] > df_4s["Open"]]) if not df_4s.empty else 24
    k4 = len(df_4s[df_4s["Close"] < df_4s["Open"]]) if not df_4s.empty else 24

    y2 = len(df_2s[df_2s["Close"] > df_2s["Open"]]) if not df_2s.empty else 60
    k2 = len(df_2s[df_2s["Close"] < df_2s["Open"]]) if not df_2s.empty else 60

    y1 = len(df_1s[df_1s["Close"] > df_1s["Open"]]) if not df_1s.empty else 30
    k1 = len(df_1s[df_1s["Close"] < df_1s["Open"]]) if not df_1s.empty else 30

    dilimler = [
        (y16, k16, 64, 6.37, df_16s),
        (y8, k8, 96, 12.73, df_8s),
        (y4, k4, 48, 50.0, df_4s),
        (y2, k2, 120, 20.6, df_2s),
        (y1, k1, 60, 10.3, df_1s),
    ]

    toplam_long_puan = 0.0
    toplam_short_puan = 0.0
    zaman_katkilari = {}
    zaman_isimleri = ["16 S", "8 S", "4 S", "2 S", "1 S"]

    for idx, (y, k, toplam_led, max_puan, df_zaman) in enumerate(dilimler):
        if toplam_led > 0:
            sl = (y / toplam_led) * max_puan
            ss = (k / toplam_led) * max_puan
        else:
            sl, ss = max_puan / 2.0, max_puan / 2.0

        ek_lb, ek_sb = rsi_momentum_fib_ve_ema_katkisi_hesapla_logaritmik(
            df_zaman, max_puan
        )

        sl_gecici = sl + ek_lb
        ss_gecici = ss + ek_sb

        grup_toplam = sl_gecici + ss_gecici
        if grup_toplam > 0 and grup_toplam > max_puan:
            sl_yeni = (sl_gecici / grup_toplam) * max_puan
            ss_yeni = (ss_gecici / grup_toplam) * max_puan
        else:
            sl_yeni, ss_yeni = sl_gecici, ss_gecici

        toplam_long_puan += sl_yeni
        toplam_short_puan += ss_yeni

        zaman_katkilari[zaman_isimleri[idx]] = {
            "sl": round(sl_yeni, 2),
            "ss": round(ss_yeni, 2),
            "y_adet": y,
            "k_adet": k,
        }

    nihai_long = round(toplam_long_puan, 2)
    nihai_short = round(toplam_short_puan, 2)

    if nihai_long >= 54.0:
        nihai_puan = nihai_long
        aktif_yon = "Long"
    elif nihai_short >= 54.0:
        nihai_puan = nihai_short
        aktif_yon = "Short"
    else:
        nihai_puan = round(max(nihai_long, nihai_short), 2)
        aktif_yon = "Nötr"

    return (
        anlik_fiyat,
        nihai_puan,
        aktif_yon,
        nihai_long,
        nihai_short,
        zaman_katkilari,
    )


@st.cache_resource
def google_sheets_baglan(sayfa_adi):
    try:
        if "gcp_service_account" in st.secrets:
            sec_dict = dict(st.secrets["gcp_service_account"])
            if "private_key" in sec_dict:
                sec_dict["private_key"] = sec_dict["private_key"].replace(r"\n", "\n")
            client = gspread.service_account_from_dict(sec_dict)
        else:
            client = gspread.service_account(filename="credentials.json")
        return client.open(GOOGLE_SHEET_DOSYA).worksheet(sayfa_adi)
    except Exception:
        return None


@st.cache_data(ttl=15)
def islem_gecmisi_getir(sheet_guncelle=True):
    beklenen_kolonlar = [
        "Islem_ID",
        "Acilis_Zamani",
        "Coin",
        "Yon",
        "Zaman_Dilimi",
        "Giris_Fiyat",
        "Islem_Miktari",
        "Stop",
        "Kar_Al",
        "Beklenen_Kar",
        "Matris_Puan_RH",
        "Olasi_Stop",
        "Durum",
        "Net_Kar_Zarar",
        "Guncel_Kasa",
        "Kapanis_Zamani",
        "Kapanis_Fiyati",
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
        df["Islem_ID"] = (
            pd.to_numeric(df["Islem_ID"], errors="coerce").fillna(0).astype(int)
        )
        df = (
            df.drop_duplicates(subset=["Islem_ID"], keep="last")
            .sort_values(by="Islem_ID")
            .reset_index(drop=True)
        )
        sayisal_kolonlar = [
            "Giris_Fiyat",
            "Islem_Miktari",
            "Stop",
            "Kar_Al",
            "Beklenen_Kar",
            "Olasi_Stop",
            "Net_Kar_Zarar",
            "Guncel_Kasa",
            "Kapanis_Fiyati",
        ]
        for col in sayisal_kolonlar:
            if col in df.columns:
                df[col] = (
                    pd.to_numeric(
                        df[col].astype(str).str.replace(",", ".").str.strip(),
                        errors="coerce",
                    )
                    .fillna(0.0)
                    .astype(float)
                )
    return df


def dataframe_guncelle_gsheets(df):
    sheet = google_sheets_baglan("KriptoPortfoyVeritabani")
    if sheet is not None:
        try:
            sheet.clear()
            sheet.append_row(list(df.columns))
            for _, row in df.iterrows():
                sheet.append_row(list(row.values))
        except:
            pass
        st.cache_data.clear()


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
        df["Islem_ID"] = (
            pd.to_numeric(df["Islem_ID"], errors="coerce").fillna(0).astype(int)
        )
        df["Tutar"] = (
            pd.to_numeric(
                df["Tutar"].astype(str).str.replace(",", ".").str.strip(),
                errors="coerce",
            )
            .fillna(0.0)
            .astype(float)
        )
    return df


def kasa_defteri_guncelle_gsheets(df):
    sheet = google_sheets_baglan("KasaDefteri")
    if sheet is not None:
        try:
            sheet.clear()
            sheet.append_row(list(df.columns))
            for _, row in df.iterrows():
                sheet.append_row(list(row.values))
        except:
            pass
        st.cache_data.clear()


def kasa_islem_ekle(islem_turu, tutar, aciklama):
    df_kasa = kasa_defteri_getir()
    yeni_id = (
        1
        if df_kasa.empty
        else int(pd.to_numeric(df_kasa["Islem_ID"], errors="coerce").max() or 0)
        + 1
    )
    suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")

    islem_carpan = 1.0 if islem_turu == "Para_Yatir" else -1.0
    net_tutar = float(tutar) * islem_carpan

    yeni_kayit = pd.DataFrame([{
        "Islem_ID": yeni_id,
        "Zaman": suan_tr,
        "Islem_Turu": islem_turu,
        "Tutar": round(net_tutar, 2),
        "Aciklama": aciklama,
    }])
    df_kasa = pd.concat([df_kasa, yeni_kayit], ignore_index=True).drop_duplicates(
        subset=["Islem_ID"], keep="last"
    )
    kasa_defteri_guncelle_gsheets(df_kasa)
    return True, f"Kasa işlemi başarılı: {islem_turu} -> {net_tutar:.2f} $"


def kasa_islem_ekle_deftere(islem_turu, tutar, aciklama):
    df_kasa = kasa_defteri_getir()
    yeni_id = (
        1
        if df_kasa.empty
        else int(pd.to_numeric(df_kasa["Islem_ID"], errors="coerce").max() or 0)
        + 1
    )
    suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")
    yeni_kayit = pd.DataFrame([{
        "Islem_ID": yeni_id,
        "Zaman": suan_tr,
        "Islem_Turu": islem_turu,
        "Tutar": round(tutar, 2),
        "Aciklama": aciklama,
    }])
    df_kasa = pd.concat([df_kasa, yeni_kayit], ignore_index=True).drop_duplicates(
        subset=["Islem_ID"], keep="last"
    )
    kasa_defteri_guncelle_gsheets(df_kasa)


def elli_islem_arsiv_kontrol():
    try:
        df = islem_gecmisi_getir(sheet_guncelle=False)
        if df.empty:
            return
        toplam_islem = len(df)
        if toplam_islem >= 50:
            if not os.path.exists(ARSIV_KLASORU):
                os.makedirs(ARSIV_KLASORU)
            blok_sayisi = toplam_islem // 50
            for b in range(blok_sayisi):
                bas_i, bit_i = b * 50, (b + 1) * 50
                blok_df = df.iloc[bas_i:bit_i]
                yol = os.path.join(
                    ARSIV_KLASORU, f"islem_arsivi_{bas_i+1}_{bit_i}.csv"
                )
                if not os.path.exists(yol):
                    blok_df.to_csv(yol, sep=";", index=False)
    except:
        pass


def bakiye_durumunu_getir(ortak_fiyat_havuzu={}):
    df_trade = islem_gecmisi_getir(sheet_guncelle=False)
    df_kasa = kasa_defteri_getir()
    net_kasa_hareketleri = BASLANGIC_BAKIYE

    if not df_kasa.empty:
        net_kasa_hareketleri += (
            pd.to_numeric(df_kasa["Tutar"], errors="coerce").fillna(0.0).sum()
        )

    if not df_trade.empty:
        kap_trades = df_trade[
            df_trade["Durum"]
            .astype(str)
            .str.contains("Kapandi|Kar|Zarar|Kismi", case=False, na=False)
        ]
        if not kap_trades.empty:
            trade_sonuc_defterde = 0.0
            if not df_kasa.empty and "Islem_Turu" in df_kasa.columns:
                ts_df = df_kasa[df_kasa["Islem_Turu"] == "Trade_Sonuc"]
                if not ts_df.empty:
                    trade_sonuc_defterde = (
                        pd.to_numeric(ts_df["Tutar"], errors="coerce").fillna(0.0).sum()
                    )
            gercek_trade_toplam = (
                pd.to_numeric(kap_trades["Net_Kar_Zarar"], errors="coerce")
                .fillna(0.0)
                .sum()
            )
            if gercek_trade_toplam != trade_sonuc_defterde:
                net_kasa_hareketleri += gercek_trade_toplam - trade_sonuc_defterde

    toplam_kasa = net_kasa_hareketleri
    acik_df = pd.DataFrame()
    if not df_trade.empty and "Durum" in df_trade.columns:
        kapali_mask = (
            df_trade["Durum"]
            .astype(str)
            .str.contains("kapandi|kar|zarar", case=False, na=False)
        )
        acik_df = df_trade[~kapali_mask]

    aktif_marjin_toplami = 0.0
    acik_kz_toplam = 0.0

    if not acik_df.empty:
        aktif_marjin_toplami = (
            pd.to_numeric(acik_df["Islem_Miktari"], errors="coerce")
            .fillna(0.0)
            .sum()
        )
        for _, rw in acik_df.iterrows():
            c_SYM = rw["Coin"]
            g_F = float(rw["Giris_Fiyat"])
            m_M = float(rw["Islem_Miktari"])
            y_Y = rw["Yon"]
            if not ortak_fiyat_havuzu:
                anl_F = fiyat_cek_binance(c_SYM)
            else:
                anl_F = ortak_fiyat_havuzu.get(
                    c_SYM, baz_fiyatlar.get(c_SYM, 100.0)
                )
            f_y = (
                ((anl_F - g_F) / g_F) if "Long" in y_Y else ((g_F - anl_F) / g_F)
            )
            acik_kz_toplam += m_M * KALDIRAC * f_y

    efektif_kasa = toplam_kasa + acik_kz_toplam
    bos_bakiye = toplam_kasa - aktif_marjin_toplami
    return (
        float(toplam_kasa),
        float(efektif_kasa),
        float(bos_bakiye),
        float(aktif_marjin_toplami),
    )


def yeni_islem_ekle(
    coin,
    yon,
    giris_fiyat,
    islem_miktari,
    stop,
    kar_al,
    zaman_dilimi,
    matris_puan,
    risk_hedef_metin,
):
    df = islem_gecmisi_getir()

    _, _, mevcut_bakiye, _ = bakiye_durumunu_getir()
    if round(islem_miktari, 2) > round(mevcut_bakiye, 2):
        return (
            False,
            f"Bakiye yetersiz! Mevcut Bakiye: {mevcut_bakiye:.2f} $, Girilen:"
            f" {islem_miktari:.2f} $",
        )
    if islem_miktari <= 0:
        return False, "İşlem miktarı 0 $'dan büyük olmalıdır!"

    suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")

    acik_islem_idx = None
    if not df.empty and "Durum" in df.columns:
        acik_mask = ~df["Durum"].astype(str).str.contains(
            "kapandi|kar|zarar", case=False, na=False
        )
        acik_df = df[acik_mask]
        if not acik_df.empty and coin in acik_df["Coin"].values:
            acik_islem_idx = acik_df[acik_df["Coin"] == coin].index[0]

    if acik_islem_idx is not None:
        eski_giris = float(df.loc[acik_islem_idx, "Giris_Fiyat"])
        eski_miktar = float(df.loc[acik_islem_idx, "Islem_Miktari"])
        eski_yon = str(df.loc[acik_islem_idx, "Yon"])

        yeni_toplam_miktar = eski_miktar + islem_miktari
        yeni_agirlikli_ortalama = (
            (eski_miktar * eski_giris) + (islem_miktari * giris_fiyat)
        ) / yeni_toplam_miktar

        if eski_giris > 0:
            stop_oran = abs(stop - giris_fiyat) / giris_fiyat
            kar_al_oran = abs(kar_al - giris_fiyat) / giris_fiyat
        else:
            stop_oran, kar_al_oran = 0.01, 0.02

        if "Long" in eski_yon:
            yeni_stop = yeni_agirlikli_ortalama * (1.0 - stop_oran)
            yeni_kar_al = yeni_agirlikli_ortalama * (1.0 + kar_al_oran)
            beklenen_kar = (
                yeni_toplam_miktar
                * KALDIRAC
                * ((yeni_kar_al - yeni_agirlikli_ortalama) / yeni_agirlikli_ortalama)
            )
            olasi_stop = (
                yeni_toplam_miktar
                * KALDIRAC
                * ((yeni_stop - yeni_agirlikli_ortalama) / yeni_agirlikli_ortalama)
            )
        else:
            yeni_stop = yeni_agirlikli_ortalama * (1.0 + stop_oran)
            yeni_kar_al = yeni_agirlikli_ortalama * (1.0 - kar_al_oran)
            beklenen_kar = (
                yeni_toplam_miktar
                * KALDIRAC
                * ((yeni_agirlikli_ortalama - yeni_kar_al) / yeni_agirlikli_ortalama)
            )
            olasi_stop = (
                yeni_toplam_miktar
                * KALDIRAC
                * ((yeni_agirlikli_ortalama - yeni_stop) / yeni_agirlikli_ortalama)
            )

        basamak = 4 if yeni_agirlikli_ortalama < 10 else 2
        matris_rh_metin = f"{matris_puan} ({risk_hedef_metin})"
        toplam_kasa, _, _, _ = bakiye_durumunu_getir()

        df.at[acik_islem_idx, "Giris_Fiyat"] = round(
            yeni_agirlikli_ortalama, basamak
        )
        df.at[acik_islem_idx, "Islem_Miktari"] = round(yeni_toplam_miktar, 2)
        df.at[acik_islem_idx, "Stop"] = round(yeni_stop, basamak)
        df.at[acik_islem_idx, "Kar_Al"] = round(yeni_kar_al, basamak)
        df.at[acik_islem_idx, "Acilis_Zamani"] = suan_tr
        df.at[acik_islem_idx, "Beklenen_Kar"] = round(beklenen_kar, 2)
        df.at[acik_islem_idx, "Olasi_Stop"] = round(olasi_stop, 2)
        df.at[acik_islem_idx, "Matris_Puan_RH"] = matris_rh_metin
        df.at[acik_islem_idx, "Guncel_Kasa"] = round(toplam_kasa, 2)

        dataframe_guncelle_gsheets(df)
        elli_islem_arsiv_kontrol()
        return (
            True,
            f"🔄 {coin} pozisyonuna ekleme yapıldı! Yeni Ort. Maliyet:"
            f" {yeni_agirlikli_ortalama:,.{basamak}f} $",
        )

    else:
        if (
            matris_puan < 54.0
            or "Nötr" in yon
            or "Beklemede" in yon
            or "Ters Akıntı" in yon
        ):
            return (
                False,
                "⚠️ Nötr (Puan < 54.0) veya Ters Akıntı konumunda yeni işlem açılamaz!",
            )

        yeni_id = (
            1
            if df.empty
            else int(pd.to_numeric(df["Islem_ID"], errors="coerce").max() or 0) + 1
        )

        if "Long" in yon:
            beklenen_kar = islem_miktari * KALDIRAC * ((kar_al - giris_fiyat) / giris_fiyat)
            olasi_stop = islem_miktari * KALDIRAC * ((stop - giris_fiyat) / giris_fiyat)
        else:
            beklenen_kar = islem_miktari * KALDIRAC * ((giris_fiyat - kar_al) / giris_fiyat)
            olasi_stop = islem_miktari * KALDIRAC * ((giris_fiyat - stop) / giris_fiyat)

        basamak = 4 if giris_fiyat < 10 else 2
        matris_rh_metin = f"{matris_puan} ({risk_hedef_metin})"
        toplam_kasa, _, _, _ = bakiye_durumunu_getir()
        yeni_kayit = pd.DataFrame([{
            "Islem_ID": yeni_id,
            "Acilis_Zamani": suan_tr,
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
            "Guncel_Kasa": round(toplam_kasa, 2),
            "Kapanis_Zamani": "-",
            "Kapanis_Fiyati": 0.0,
        }])
        df = pd.concat([df, yeni_kayit], ignore_index=True).drop_duplicates(
            subset=["Islem_ID"], keep="last"
        )
        dataframe_guncelle_gsheets(df)
        elli_islem_arsiv_kontrol()
        return True, f"✅ {coin} emri başarıyla verildi!"


def manuel_islem_kapat(islem_id, anlik_kapatma_fiyati, kapatilacak_miktar=None):
    df = islem_gecmisi_getir()
    idx = df[df["Islem_ID"] == islem_id].index
    if idx.empty:
        return False, "İşlem bulunamadı!"
    row = df.loc[idx[0]]
    try:
        giris_fiyat = float(row["Giris_Fiyat"])
        mevcut_miktar = float(row["Islem_Miktari"])
        suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")

        if kapatilacak_miktar is not None and kapatilacak_miktar < mevcut_miktar:
            fark_yuzde = (
                ((anlik_kapatma_fiyati - giris_fiyat) / giris_fiyat)
                if "Long" in row["Yon"]
                else ((giris_fiyat - anlik_kapatma_fiyati) / giris_fiyat)
            )
            kismi_kar = kapatilacak_miktar * KALDIRAC * fark_yuzde
            
            yeni_id = int(pd.to_numeric(df["Islem_ID"], errors="coerce").max() or 0) + 1
            durum_metni = "Kısmi Kapandı (Zarar)" if kısmi_kar < 0 else "Kısmi Kapandı (Kâr)"
            
            toplam_kasa, _, _, _ = bakiye_durumunu_getir()
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
            
            if "Long" in row["Yon"]:
                bek_kar_yeni = kalan_miktar * KALDIRAC * ((float(row["Kar_Al"]) - giris_fiyat) / giris_fiyat)
                olasi_stop_yeni = kalan_miktar * KALDIRAC * ((float(row["Stop"]) - giris_fiyat) / giris_fiyat)
            else:
                bek_kar_yeni = kalan_miktar * KALDIRAC * ((giris_fiyat - float(row["Kar_Al"])) / giris_fiyat)
                olasi_stop_yeni = kalan_miktar * KALDIRAC * ((giris_fiyat - float(row["Stop"])) / giris_fiyat)
                
            df.at[idx[0], "Beklenen_Kar"] = round(bek_kar_yeni, 2)
            df.at[idx[0], "Olasi_Stop"] = round(olasi_stop_yeni, 2)
            
            df = pd.concat([df, yeni_kapali_kayit], ignore_index=True).sort_values(by="Islem_ID").reset_index(drop=True)
            dataframe_guncelle_gsheets(df)
            
            kasa_islem_ekle_deftere(
                "Trade_Sonuc",
                float(round(kismi_kar, 2)),
                f"Kısmi K/Z: #{islem_id} {row['Coin']} ({kapatilacak_miktar}$ kapatıldı)",
            )
            elli_islem_arsiv_kontrol()

            mail_icerik = (
                f"<h3>Kısmi İşlem Kapatıldı</h3>"
                f"<p><b>İşlem ID:</b> #{islem_id}</p>"
                f"<p><b>Coin:</b> {row['Coin']}</p>"
                f"<p><b>Yön:</b> {row['Yon']}</p>"
                f"<p><b>Kapatılan Miktar:</b> {kapatilacak_miktar:,.2f} $</p>"
                f"<p><b>Realize Edilen K/Z:</b> {kismi_kar:+,.2f} $</p>"
                f"<p><b>Güncel Kasa:</b> {toplam_kasa + kismi_kar:,.2f} $</p>"
            )
            gmail_bildirim_gonder(f"🔔 Kısmi Kapatma Raporu: #{islem_id} {row['Coin']}", mail_icerik)

            return True, f"Kısmi kapama başarılı! Realize Edilen K/Z: {kismi_kar:,.2f} $. Kalan Pozisyon: {kalan_miktar} $"

        else:
            fark_yuzde = (
                ((anlik_kapatma_fiyati - giris_fiyat) / giris_fiyat)
                if "Long" in row["Yon"]
                else ((giris_fiyat - anlik_kapatma_fiyati) / giris_fiyat)
            )
            net_kar = mevcut_miktar * KALDIRAC * fark_yuzde

            durum_metni = "Kapandi (Zarar)" if net_kar < 0 else "Kapandi (Kar)"
            df.at[idx[0], "Durum"] = durum_metni
            df.at[idx[0], "Kapanis_Zamani"] = suan_tr
            df.at[idx[0], "Net_Kar_Zarar"] = float(round(net_kar, 2))
            df.at[idx[0], "Kapanis_Fiyati"] = float(round(anlik_kapatma_fiyati, 4))

            toplam_kasa, _, _, _ = bakiye_durumunu_getir()
            df.at[idx[0], "Guncel_Kasa"] = float(round(toplam_kasa + net_kar, 2))
            dataframe_guncelle_gsheets(df)
            kasa_islem_ekle_deftere(
                "Trade_Sonuc",
                float(round(net_kar, 2)),
                f"Trade K/Z: #{islem_id} {row['Coin']} ({durum_metni})",
            )
            elli_islem_arsiv_kontrol()

            mail_icerik = (
                f"<h3>İşlem Tamamen Kapatıldı</h3>"
                f"<p><b>İşlem ID:</b> #{islem_id}</p>"
                f"<p><b>Coin:</b> {row['Coin']}</p>"
                f"<p><b>Yön:</b> {row['Yon']}</p>"
                f"<p><b>Durum:</b> {durum_metni}</p>"
                f"<p><b>Net Kâr/Zarar:</b> {net_kar:+,.2f} $</p>"
                f"<p><b>Güncel Kasa:</b> {toplam_kasa + net_kar:,.2f} $</p>"
            )
            gmail_bildirim_gonder(
                f"🔔 Kapatma Raporu: #{islem_id} {row['Coin']} ({durum_metni})",
                mail_icerik,
            )
            return True, f"İşlem tamamen kapatıldı. K/Z: {net_kar:.2f} $"

    except Exception as e:
        return False, f"Hata: {str(e)}"


def otomatik_stop_kar_kontrolu(ortak_fiyat_havuzu=None):
    df = islem_gecmisi_getir(sheet_guncelle=False)
    if df.empty or "Durum" not in df.columns:
        return

    degisiklik_oldu = False
    suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")

    for idx, row in df.iterrows():
        durum_str = str(row["Durum"]).lower()
        if not (
            "kapandi" in durum_str or "kar" in durum_str or "zarar" in durum_str
        ):
            islem_id = int(row["Islem_ID"])
            coin = row["Coin"]
            yon = row["Yon"]
            giris_fiyat = float(row["Giris_Fiyat"])
            stop_f = float(row["Stop"])
            kar_al_f = float(row["Kar_Al"])
            miktar = float(row["Islem_Miktari"])

            if ortak_fiyat_havuzu is not None and coin in ortak_fiyat_havuzu:
                anl_f = ortak_fiyat_havuzu[coin]
            else:
                anl_f = fiyat_cek_binance(coin)

            islem_kapatilacak = False
            hedefe_ulasti = False
            kapanis_fiyat_degeri = 0.0

            if "Long" in yon:
                if anl_f <= stop_f:
                    islem_kapatilacak, hedefe_ulasti, kapanis_fiyat_degeri = (
                        True,
                        False,
                        stop_f,
                    )
                elif anl_f >= kar_al_f:
                    islem_kapatilacak, hedefe_ulasti, kapanis_fiyat_degeri = (
                        True,
                        True,
                        kar_al_f,
                    )
            elif "Short" in yon:
                if anl_f >= stop_f:
                    islem_kapatilacak, hedefe_ulasti, kapanis_fiyat_degeri = (
                        True,
                        False,
                        stop_f,
                    )
                elif anl_f <= kar_al_f:
                    islem_kapatilacak, hedefe_ulasti, kapanis_fiyat_degeri = (
                        True,
                        True,
                        kar_al_f,
                    )

            if islem_kapatilacak:
                fark_yuzde = (
                    ((kapanis_fiyat_degeri - giris_fiyat) / giris_fiyat)
                    if "Long" in yon
                    else ((giris_fiyat - kapanis_fiyat_degeri) / giris_fiyat)
                )
                net_kar = miktar * KALDIRAC * fark_yuzde
                durum_metni = "Kapandi (Kar)" if hedefe_ulasti else "Kapandi (Zarar)"

                df.at[idx, "Durum"] = durum_metni
                df.at[idx, "Kapanis_Zamani"] = suan_tr
                df.at[idx, "Net_Kar_Zarar"] = float(round(net_kar, 2))
                df.at[idx, "Kapanis_Fiyati"] = float(round(kapanis_fiyat_degeri, 4))

                toplam_kasa, _, _, _ = bakiye_durumunu_getir(
                    {} if ortak_fiyat_havuzu is None else ortak_fiyat_havuzu
                )
                df.at[idx, "Guncel_Kasa"] = float(round(toplam_kasa + net_kar, 2))

                islem_turu_etiket = "Hedef Kâr" if hedefe_ulasti else "Otomatik Stop"
                kasa_islem_ekle_deftere(
                    "Trade_Sonuc",
                    float(round(net_kar, 2)),
                    f"{islem_turu_etiket}: #{islem_id} {coin} ({'Kar' if hedefe_ulasti else 'Zarar'})",
                )
                degisiklik_oldu = True

                mail_icerik = (
                    "<h3>İşlem Hedefe Ulaştı ve Otomatik Kapatıldı</h3><p><b>Kapanış"
                    f" Türü:</b> {islem_turu_etiket}</p><p><b>İşlem ID:</b>"
                    f" #{islem_id}</p><p><b>Coin:</b> {coin}</p><p><b>Yön:</b>"
                    f" {yon}</p><p><b>Net Kâr/Zarar:</b> {net_kar:+,.2f}"
                    f" $</p><p><b>Güncel Kasa:</b> {toplam_kasa + net_kar:,.2f} $</p>"
                )
                gmail_bildirim_gonder(
                    f"🔔 Otomatik İşlem Raporu: #{islem_id} {coin} ({'Kâr' if hedefe_ulasti else 'Zarar'})",
                    mail_icerik,
                )

    if degisiklik_oldu:
        dataframe_guncelle_gsheets(df)
        elli_islem_arsiv_kontrol()


def arka_plan_dinleyicisi():
    while True:
        try:
            tum_semboller = coinler + ["TOTAL"]
            for s in tum_semboller:
                _, p_val, a_yon, _, _, _ = kurgusal_matris_hesapla(s)
                if p_val >= 70.0:
                    pass
            otomatik_stop_kar_kontrolu(None)
        except Exception as e:
            print(f"Arka plan hata: {e}")
        time.sleep(60)


@st.cache_resource
def botu_baslat_bir_kez():
    t = threading.Thread(target=arka_plan_dinleyicisi, daemon=True)
    t.start()
    return t


arka_plan_thread = botu_baslat_bir_kez()

st.title("Piyasa Genel Bakış")
st.caption("Fibonacci ağırlıklı sinyal matrisi · Risk yönetimi · Portföy takibi")
elli_islem_arsiv_kontrol()

if "kasa_islem_acik" not in st.session_state:
    st.session_state["kasa_islem_acik"] = False
if "kasa_islem_turu" not in st.session_state:
    st.session_state["kasa_islem_turu"] = "Para Yatır"
if "sadece_aktifleri_goster" not in st.session_state:
    st.session_state["sadece_aktifleri_goster"] = False
if "gonderilen_mailler" not in st.session_state:
    st.session_state["gonderilen_mailler"] = set()
if "total_sermaye_alarm" not in st.session_state:
    st.session_state["total_sermaye_alarm"] = None
if "kapama_paneli_acik" not in st.session_state:
    st.session_state["kapama_paneli_acik"] = False

tum_takip_edilenler = coinler + ["TOTAL"]
islenen_ham_veriler = []
ortak_fiyat_havuzu = {}

for sembol in tum_takip_edilenler:
    anlik_fiyat, nihai_puan, aktif_yon, l_puan, s_puan, zaman_katkilari = (
        kurgusal_matris_hesapla(sembol)
    )
    if sembol == "TOTAL":
        anlik_fiyat = fiyat_cek_binance("TOTAL")
    ortak_fiyat_havuzu[sembol] = anlik_fiyat

    df_market = load_15min_market_data(sembol)
    if (
        not df_market.empty
        and "Open" in df_market.columns
        and "Close" in df_market.columns
    ):
        gunluk_oran = (
            (
                float(df_market.iloc[-1]["Close"])
                - float(df_market.iloc[0]["Open"])
            )
            / float(df_market.iloc[0]["Open"])
        ) * 100.0
    else:
        gunluk_oran = 0.0

    islenen_ham_veriler.append({
        "sembol": sembol,
        "anlik_fiyat": anlik_fiyat,
        "nihai_puan": nihai_puan,
        "aktif_yon": aktif_yon,
        "l_puan": l_puan,
        "s_puan": s_puan,
        "zaman_katkilari": zaman_katkilari,
        "gunluk_oran": gunluk_oran,
        "df_market": df_market,
    })

otomatik_stop_kar_kontrolu(ortak_fiyat_havuzu)

coin_ham_veriler = [d for d in islenen_ham_veriler if d["sembol"] != "TOTAL"]
total_ham_veri = [d for d in islenen_ham_veriler if d["sembol"] == "TOTAL"][0]

t_puan_val, t_l_puan, t_s_puan = (
    total_ham_veri["nihai_puan"],
    total_ham_veri["l_puan"],
    total_ham_veri["s_puan"],
)
t_toplam_puan = t_l_puan + t_s_puan
t_yuzde = (t_l_puan / t_toplam_puan * 100.0) if t_toplam_puan > 0 else 50.0

if t_puan_val >= 70.0:
    if total_ham_veri["aktif_yon"] == "Long":
        total_sermaye_durumu, t_alarm_renk = "Boğa Vuruşu", "#00FF00"
    else:
        total_sermaye_durumu, t_alarm_renk = "Ayı Pençesi", "rgb(255, 75, 0)"

    alarm_anahtar = f"total_mail_{datetime.now(TR_TZ).strftime('%Y%m%d_%H')}"
    if st.session_state.get("total_sermaye_alarm_zaman") != alarm_anahtar:
        st.session_state["total_sermaye_alarm_zaman"] = alarm_anahtar
        m_icerik = (
            "<h3>Piyasada Güçlü Sermaye Hareketi Tespit Edildi!</h3><p><b>Durum:</b>"
            f" <span style='color: {t_alarm_renk}; font-weight:"
            f" bold;'>{total_sermaye_durumu}</span></p><p><b>Matris Puanı:</b>"
            f" {t_puan_val:.1f} / 100 (Eşik: 70)</p><p><b>Long Oranı:</b>"
            f" %{t_yuzde:.1f}</p><p><b>Zaman:</b>"
            f" {tr_zaman().strftime('%d.%m.%Y %H:%M')}</p>"
        )
        gmail_bildirim_gonder(
            f"🚨 Top 5 Market Alarmı: {total_sermaye_durumu}!", m_icerik
        )

total_puan_val = total_ham_veri["nihai_puan"]
total_yon_val = total_ham_veri["aktif_yon"]

gecici_islenen_liste = []
for data in coin_ham_veriler:
    sembol, nihai_puan, aktif_yon, l_puan, s_puan, anlik_fiyat = (
        data["sembol"],
        data["nihai_puan"],
        data["aktif_yon"],
        data["l_puan"],
        data["s_puan"],
        data["anlik_fiyat"],
    )
    gunluk_oran = data["gunluk_oran"]

    puan_toplam = l_puan + s_puan
    y_yuzde = (l_puan / puan_toplam * 100.0) if puan_toplam > 0 else 50.0
    k_yuzde = 100.0 - y_yuzde

    c_led = (
        "🟢"
        if (nihai_puan >= 54.0 and aktif_yon == "Long")
        else ("🔴" if (nihai_puan >= 54.0 and aktif_yon == "Short") else "🟡")
    )
    d_led = "🟢" if total_yon_val == "Long" else "🔴"

    yesil_led_sayisi = round((y_yuzde / 100.0) * 10.0)
    yesil_led_sayisi = max(0, min(10, yesil_led_sayisi))
    kirmizi_led_sayisi = 10 - yesil_led_sayisi

    detay_matris_html = (
        '<div style="text-align: center; line-height: 1.2;"><div'
        ' style="font-size: 15px; margin-bottom: 2px; letter-spacing:'
        f' 1px;">{"🟢" * yesil_led_sayisi}{"🔴" * kirmizi_led_sayisi}</div><div'
        ' style="font-size: 11px; font-weight: 600;"><span style="color: #00FF00;'
        " display: inline-block; width: 10px; height: 10px; background-color:"
        ' #00FF00; border-radius: 50%; margin-right:'
        f' 2px;"></span>%{y_yuzde:.1f} | <span style="color: rgb(255, 75, 0);'
        " display: inline-block; width: 10px; height: 10px; background-color:"
        " rgb(255, 75, 0); border-radius: 50%; margin-left: 4px; margin-right:"
        f' 2px;"></span>%{k_yuzde:.1f}</div></div>'
    )

    c_yonu = (
        "Long"
        if (nihai_puan >= 54.0 and aktif_yon == "Long")
        else ("Short" if (nihai_puan >= 54.0 and aktif_yon == "Short") else "Nötr")
    )
    d_yonu = total_yon_val

    is_dip_tepkisi = (
        c_yonu == "Long" and gunluk_oran <= -2.0 and nihai_puan >= 58.0
    )
    is_tepe_donusu = (
        c_yonu == "Short" and gunluk_oran >= 2.0 and nihai_puan >= 58.0
    )

    def get_6_stage_stars(puan, kategori_tipi):
        if kategori_tipi == "Notr":
            if puan < 45.0:
                return "🥈"
            elif puan < 50.0:
                return "🥈🥈"
            else:
                return "🥈🥈🥈"
        elif kategori_tipi == "Ters_Akinti" or kategori_tipi == "Onayli":
            if puan < 56.66:
                return "🥈"
            elif puan < 59.33:
                return "🥈🥈"
            elif puan < 62.00:
                return "🥈🥈🥈"
            elif puan < 64.66:
                return "🥇🥈🥈"
            elif puan < 67.33:
                return "🥇🥇🥈"
            else:
                return "🥇🥇🥇"
        elif kategori_tipi == "Avci":
            if puan < 63.0:
                return "🥈"
            elif puan < 68.0:
                return "🥈🥈"
            elif puan < 73.0:
                return "🥈🥈🥈"
            elif puan < 78.0:
                return "🥇🥈🥈"
            elif puan < 84.0:
                return "🥇🥇🥈"
            else:
                return "🥇🥇🥇"
        elif kategori_tipi == "Guclu":
            if puan < 75.0:
                return "🥈"
            elif puan < 80.0:
                return "🥈🥈"
            elif puan < 86.0:
                return "🥈🥈🥈"
            elif puan < 92.0:
                return "🥇🥈🥈"
            elif puan < 97.0:
                return "🥇🥇🥈"
            else:
                return "🥇🥇🥇"
        return "🥈"

    if aktif_yon == "Nötr":
        yildizlar = get_6_stage_stars(nihai_puan, "Notr")
        trend = f"{yildizlar} Nötr (Beklemede)"
        aktif_yon_turu = "Nötr"
        yon_html = f'<div style="background-color: #6c757d; padding: 6px; border-radius: 6px; color: white; font-weight: bold; font-size: 12px;">{trend}</div>'
        ham_agirlik = 1.0
    elif is_dip_tepkisi:
        yildizlar = get_6_stage_stars(nihai_puan, "Avci")
        trend = f"{yildizlar} Dip / Tepe Avcısı 🎣"
        aktif_yon_turu = "Long"
        yon_html = f'<div style="background-color: #00FF00; padding: 6px; border-radius: 6px; color: #000000; font-weight: bold; font-size: 12px;">{trend}</div>'
        ham_agirlik = 4.0
    elif is_tepe_donusu:
        yildizlar = get_6_stage_stars(nihai_puan, "Avci")
        trend = f"{yildizlar} Dip / Tepe Avcısı 🎣"
        aktif_yon_turu = "Short"
        yon_html = f'<div style="background-color: rgb(255, 75, 0); padding: 6px; border-radius: 6px; color: #000000; font-weight: bold; font-size: 12px;">{trend}</div>'
        ham_agirlik = 4.0
    elif c_yonu != d_yonu and c_yonu != "Nötr":
        yildizlar = get_6_stage_stars(nihai_puan, "Ters_Akinti")
        trend = f"{yildizlar} Ters Akıntı"
        aktif_yon_turu = "Nötr"
        yon_html = f'<div style="background-color: #ffc107; padding: 6px; border-radius: 6px; color: #212529; font-weight: bold; font-size: 12px;">{trend}</div>'
        ham_agirlik = 2.0
    elif nihai_puan >= 70.0:
        yildizlar = get_6_stage_stars(nihai_puan, "Guclu")
        trend = f"{yildizlar} Güçlü Trend / Boğa-Ayı Vuruşu 🔥"
        aktif_yon_turu = aktif_yon
        renk_bg = "#00FF00" if aktif_yon == "Long" else "rgb(255, 75, 0)"
        yon_html = f'<div style="background-color: {renk_bg}; padding: 6px; border-radius: 6px; color: #000000; font-weight: bold; font-size: 12px;">{trend}</div>'
        ham_agirlik = 5.0
    else:
        yildizlar = get_6_stage_stars(nihai_puan, "Onayli")
        trend = f"{yildizlar} Onaylı Trend ({aktif_yon})"
        aktif_yon_turu = aktif_yon
        renk_bg = "#00FF00" if aktif_yon == "Long" else "rgb(255, 75, 0)"
        yon_html = f'<div style="background-color: {renk_bg}; padding: 6px; border-radius: 6px; color: #000000; font-weight: bold; font-size: 12px;">{trend}</div>'
        ham_agirlik = 3.0

    is_notr = (
        aktif_yon_turu == "Nötr" or "Ters Akıntı" in trend or aktif_yon == "Nötr"
    )

    stop_uzde, hedef_carpan, risk_hedef_metin = calculate_coin_metrics_by_score(
        nihai_puan
    )

    gecici_islenen_liste.append({
        "sembol": sembol,
        "nihai_puan": nihai_puan,
        "aktif_yon": aktif_yon,
        "aktif_yon_turu": aktif_yon_turu,
        "l_puan": l_puan,
        "s_puan": s_puan,
        "anlik_fiyat": anlik_fiyat,
        "gunluk_oran": gunluk_oran,
        "c_led": c_led,
        "d_led": d_led,
        "detay_matris_html": detay_matris_html,
        "yon_html": yon_html,
        "trend": trend,
        "is_notr": is_notr,
        "ham_agirlik": ham_agirlik,
        "stop_uzde": stop_uzde,
        "hedef_carpan": hedef_carpan,
        "risk_hedef_metin": risk_hedef_metin,
    })

toplam_aktif_agirlik = sum(
    [item["ham_agirlik"] for item in gecici_islenen_liste if not item["is_notr"]]
)
islenen_veriler = []

for item in gecici_islenen_liste:
    sembol = item["sembol"]
    nihai_puan = item["nihai_puan"]
    aktif_yon_turu = item["aktif_yon_turu"]
    anlik_fiyat = item["anlik_fiyat"]
    stop_uzde = item["stop_uzde"]
    hedef_carpan = item["hedef_carpan"]
    is_notr = item["is_notr"]
    trend = item["trend"]

    if toplam_aktif_agirlik > 0 and not is_notr:
        sepet_orani = round(
            (item["ham_agirlik"] / toplam_aktif_agirlik) * 100.0, 1
        )
    else:
        sepet_orani = 0.0

    if (
        "Güçlü Trend" in trend
        and not is_notr
        and sembol not in st.session_state["gonderilen_mailler"]
    ):
        st.session_state["gonderilen_mailler"].add(sembol)
        gmail_bildirim_gonder(
            f"🔥 Güçlü Trend Alarmı: {sembol} ({trend})",
            "<h3>Piyasada Güçlü Trend Sinyali Tespit Edildi!</h3><p><b>Coin:</b>"
            f" {sembol}</p><p><b>Durum:</b> {trend}</p><p><b>Matris Puanı:</b>"
            f" {nihai_puan:.1f} / 100</p><p><b>Güncel Fiyat:</b> {anlik_fiyat:,.2f}"
            f" $</p><p><b>Zaman:</b> {tr_zaman().strftime('%d.%m.%Y %H:%M')}</p>",
        )

    if aktif_yon_turu == "Long":
        stop_fiyat, hedef_fiyat = anlik_fiyat * (
            1.0 - stop_uzde / 100.0
        ), anlik_fiyat * (1.0 + (stop_uzde * hedef_carpan) / 100.0)
    elif aktif_yon_turu == "Short":
        stop_fiyat, hedef_fiyat = anlik_fiyat * (
            1.0 + stop_uzde / 100.0
        ), anlik_fiyat * (1.0 - (stop_uzde * hedef_carpan) / 100.0)
    else:
        stop_fiyat, hedef_fiyat = anlik_fiyat * (
            1.0 - stop_uzde / 100.0
        ), anlik_fiyat * (1.0 + (stop_uzde * hedef_carpan) / 100.0)

    dom_html = (
        '<div style="text-align: center;"><div style="font-size: 16px;'
        ' margin-bottom: 2px; letter-spacing:'
        f' 4px;">{item["c_led"]}{item["d_led"]}</div><div style="font-size: 10px;'
        ' font-weight: bold; color: #495057;">C &nbsp;&nbsp; D</div></div>'
    )

    if is_notr:
        puan_html = (
            '<div style="font-weight: bold; color:'
            f' #6c757d;">{nihai_puan:.1f} / 100<br><span style="font-size:'
            f' 10px;">({aktif_yon_turu})</span></div>'
        )
    else:
        puan_html = (
            '<div style="font-weight: bold; color:'
            f' {"#00FF00" if aktif_yon_turu == "Long" else "rgb(255, 75, 0)"};">{nihai_puan:.1f}'
            f' / 100<br><span style="font-size: 10px;">({aktif_yon_turu})</span></div>'
        )

    basamak = 4 if anlik_fiyat < 10 else 2
    logo_html = f'<img src="{logo_urls.get(sembol, "")}" width="24" height="24">'

    islenen_veriler.append({
        "Sira_Anahtar": list(logo_urls.keys()).index(sembol),
        "Logo": logo_html,
        "Coin": sembol,
        "Fiyat": round(anlik_fiyat, basamak),
        "Yon": item["yon_html"],
        "Teyit_Sunumu": item["detay_matris_html"],
        "Dom_Sunumu": dom_html,
        "Matris_Puan_Sunumu": puan_html,
        "Gunluk_Oran": f"<span>{item['gunluk_oran']:+,.2f}%</span>",
        "Kar_Al": round(hedef_fiyat, basamak),
        "Stopla": round(stop_fiyat, basamak),
        "Skor": nihai_puan,
        "Sepet_Orani": sepet_orani,
        "Basamak": basamak,
        "Notr": is_notr,
        "Ham_Yon": trend,
        "Aktif_Yon": aktif_yon_turu,
        "Risk_Hedef_Metin": item["risk_hedef_metin"],
        "Ham_Agirlik": item["ham_agirlik"],
    })

islenen_veriler = sorted(
    islenen_veriler, key=lambda x: (1 if x["Notr"] else 0, -x["Ham_Agirlik"], -x["Skor"])
)
toplam_kasa, efektif_kasa, mevcut_bakiye, aktif_yatirim_tutari = (
    bakiye_durumunu_getir(ortak_fiyat_havuzu)
)

for v in islenen_veriler:
    v["Yatırım_Bedeli"] = f"{mevcut_bakiye * (v['Sepet_Orani'] / 100.0):,.2f} $"

col_ust1, col_ust2, col_ust3, col_ust4, col_kasa_buton = st.columns(
    [2, 2, 2, 2, 1.55], gap="medium"
)

with col_ust1:
    st.markdown(
        f"""<div class="metric-container"><p style="margin:0; font-size:14px; font-weight:bold;">&#128202; Aktif Yatırım</p><h1 style="color:rgb(70,0,255); margin:5px 0 0 0; font-size:24px;">{aktif_yatirim_tutari:,.2f} $</h1></div>""",
        unsafe_allow_html=True,
    )

with col_ust2:
    st.markdown(
        f"""<div class="metric-container"><p style="margin:0; font-size:14px; font-weight:bold;">&#128994; Boştaki Nakit</p><h1 style="margin:5px 0 0 0; font-size:24px;">{mevcut_bakiye:,.2f} $</h1></div>""",
        unsafe_allow_html=True,
    )

with col_ust3:
    st.markdown(
        f"""<div class="metric-container"><p style="margin:0; font-size:14px; font-weight:bold;">&#128142; Efektif Kasa</p><h1 style="margin:5px 0 0 0; font-size:24px;">{efektif_kasa:,.2f} $</h1></div>""",
        unsafe_allow_html=True,
    )

with col_ust4:
    st.markdown(
        f"""<div class="metric-container"><p style="margin:0; font-size:14px; font-weight:bold;">&#128176; Toplam Kasa</p><h1 style="margin:5px 0 0 0; font-size:24px;">{toplam_kasa:,.2f} $</h1></div>""",
        unsafe_allow_html=True,
    )

with col_kasa_buton:
    st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
    if st.button(
        "💵 Kasaya Para Ekle", use_container_width=True, key="kasaya_para_ekle"
    ):
        st.session_state["kasa_islem_turu"] = "Para Yatır"
        st.session_state["kasa_islem_acik"] = True
        st.rerun()
    if st.button(
        "💸 Kasadan Para Çek", use_container_width=True, key="kasadan_para_cek"
    ):
        st.session_state["kasa_islem_turu"] = "Para Çek"
        st.session_state["kasa_islem_acik"] = True
        st.rerun()

if st.session_state["kasa_islem_acik"]:
    islem_yatir = (
        st.session_state.get("kasa_islem_turu", "Para Yatır") == "Para Yatır"
    )
    baslik = "Kasaya Para Ekle" if islem_yatir else "Kasadan Para Çek"
    st.markdown(
        f"""<div style="background:linear-gradient(145deg,#121e30,#0e1726); padding:18px 20px 10px; border:1px solid #344765; border-left:4px solid #5b8cff; border-radius:14px; margin:16px 0 12px;">
      <div style="font-size:21px; font-weight:800; color:#f0f5ff; margin-bottom:4px;">💰 {baslik}</div>
      <div style="font-size:13px; color:#aab9d0;">Tutarı ve açıklamayı girin, ardından işlemi onaylayın.</div>
    </div>""",
        unsafe_allow_html=True,
    )
    col_k1, col_k2, col_onay, col_kapat = st.columns(
        [1.05, 2.2, 1, 1], gap="medium"
    )
    with col_k1:
        kasa_tutar = st.number_input(
            "Tutar ($)", min_value=1.0, value=100.0, step=10.0, key="k_tutar"
        )
    with col_k2:
        kasa_aciklama = st.text_input(
            "Açıklama",
            value="Ekstra sermaye" if islem_yatir else "Kasa çekimi",
            key="k_acik",
        )
    with col_onay:
        st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
        if st.button("💾 Onayla", use_container_width=True, key="kasa_onayla"):
            basarili, mesaj = kasa_islem_ekle(
                "Para_Yatir" if islem_yatir else "Para_Cek",
                kasa_tutar,
                kasa_aciklama,
            )
            if basarili:
                st.success(mesaj)
                st.session_state["kasa_islem_acik"] = False
                time.sleep(1)
                st.rerun()
            else:
                st.error(mesaj)
    with col_kapat:
        st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
        if st.button("✖ Kapat", use_container_width=True, key="kasa_kapat"):
            st.session_state["kasa_islem_acik"] = False
            st.rerun()

st.markdown("---")

table_html = """
<table class="custom-table"><thead class="custom-table-header"><tr>
 <th>Logo</th><th>Coin<br>Adı</th><th>Güncel<br>Fiyat</th><th>Trend<br>Durumu</th>
 <th>Matris Teyit</th><th>Piyasa &<br>Dominans</th><th>Matris<br>Puanı</th><th>Günlük<br>Değişim</th><th>Önerilen<br>Oran</th>
 <th>Yatırım<br>Tutarı</th><th>Kar Al<br>Hedefi</th><th>Stop<br>Seviyesi</th><th>Risk / Hedef</th>
 </tr></thead><tbody>
"""
for v in islenen_veriler:
    fiyat_str = (
        f"{v['Fiyat']:,.4f}&nbsp;$"
        if v["Basamak"] == 4
        else f"{v['Fiyat']:,.2f}&nbsp;$"
    )
    kar_al_str = (
        f"{v['Kar_Al']:,.4f}&nbsp;$"
        if v["Basamak"] == 4
        else f"{v['Kar_Al']:,.2f}&nbsp;$"
    )
    stopla_str = (
        f"{v['Stopla']:,.4f}&nbsp;$"
        if v["Basamak"] == 4
        else f"{v['Stopla']:,.2f}&nbsp;$"
    )
    val_str = (
        f"%{v['Sepet_Orani']:.1f}"
        if v["Sepet_Orani"] != int(v["Sepet_Orani"])
        else f"%{int(v['Sepet_Orani'])}"
    )

    renk_yon = "#00FF00" if v["Aktif_Yon"] == "Long" else "rgb(255, 75, 0)"

    if v["Notr"]:
        oran_html = (
            '<div style="background-color: rgba(255, 235, 59, 0.3); padding: 5px;'
            ' font-weight: bold;">%0<br>(Beklemede)</div>'
        )
    else:
        oran_html = (
            f'<div style="background-color: {renk_yon}; color: #000000; padding:'
            f' 5px; font-weight: bold;">{val_str}<br>({v["Akt_Etiket"] if "Akt_Etiket" in v else v["Aktif_Yon"]})</div>'
        )

    table_html += (
        f"<tr><td>{v['Logo']}</td><td>{v['Coin']}</td><td style='font-weight:"
        " bold; color: rgb(70, 0, 255); background-color: rgba(70, 0, 255,"
        f" 0.05);'>{fiyat_str}</td><td>{v['Yon']}</td><td>{v['Teyit_Sunumu']}</td><td>{v['Dom_Sunumu']}</td><td"
        " style='background-color:"
        f" rgba(0,0,0,0.02);'>{v['Matris_Puan_Sunumu']}</td><td>{v['Gunluk_Oran']}</td><td>{oran_html}</td><td>{v['Yatırım_Bedeli']}</td><td>{kar_al_str}</td><td>{stopla_str}</td><td"
        " style='font-weight: bold; color:"
        f" #d63384;'>{v['Risk_Hedef_Metin']}</td></tr>"
    )
table_html += "</tbody></table>"
st.markdown(
    f'<div class="table-container">{table_html}</div>', unsafe_allow_html=True
)

col_sol_panel, col_orta_grafik, col_sag_endeks = st.columns([1.2, 2.5, 1.0])

with col_sol_panel:
    st.markdown("<h3>🚀 İşlem Emri Ver</h3>", unsafe_allow_html=True)
    df_gosterge = pd.DataFrame(islenen_veriler)
    coin_listesi = df_gosterge["Coin"].tolist() if not df_gosterge.empty else []

    secilen_coin = st.selectbox("Coin Seç:", coin_listesi) if coin_listesi else None
    if not coin_listesi:
        st.warning("Uygun coin yok.")

    onerilen_oran_val, anlik_matris_puani, anlik_risk_hedef_metin, coin_verisii = (
        0.0,
        0.0,
        "1,20 / 1,50",
        None,
    )
    if secilen_coin:
        coin_verisii = df_gosterge[df_gosterge["Coin"] == secilen_coin].iloc[0]
        (
            onerilen_oran_val,
            anlik_matris_puani,
            anlik_risk_hedef_metin,
        ) = (
            float(coin_verisii["Sepet_Orani"]),
            float(coin_verisii["Skor"]),
            coin_verisii["Risk_Hedef_Metin"],
        )

    df_gecmis_temp = islem_gecmisi_getir(sheet_guncelle=False)
    acik_pozisyon_var = False
    if not df_gecmis_temp.empty and "Durum" in df_gecmis_temp.columns:
        acik_mask = ~df_gecmis_temp["Durum"].astype(str).str.contains(
            "kapandi|kar|zarar", case=False, na=False
        )
        if secilen_coin in df_gecmis_temp[acik_mask]["Coin"].values:
            acik_pozisyon_var = True

    onerilen_tutar_hesap = round(mevcut_bakiye * (onerilen_oran_val / 100.0), 2)

    if acik_pozisyon_var:
        st.markdown(
            """
        <div style="background:linear-gradient(145deg,#1f2b3e,#162234); color:#e8eef8; border:1px solid #3b82f6; padding:12px; border-radius:10px; margin-bottom:12px; font-size:13px; line-height:1.8;">
            <div style="font-weight:750; color:#60a5fa; margin-bottom:4px;">🔄 Açık Pozisyona Ekleme Modu</div>
            <div style="color:#dce6f5;">Bu coin için açık bir pozisyonunuz var. Girilen tutar ağırlıklı ortalama ile maliyete eklenecektir.</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
        <div style="background:linear-gradient(145deg,#17263b,#111b2b); color:#e8eef8; border:1px solid #30415b; padding:12px; border-radius:10px; margin-bottom:12px; font-size:13px; line-height:1.8;">
            <div style="font-weight:750; color:#ffd166; margin-bottom:4px;">💡 Matris Önerisi</div>
            <div style="color:#dce6f5;">Önerilen oran: <b style="color:#ffffff;">%{onerilen_oran_val:.1f}</b></div>
            <div style="color:#dce6f5;">Önerilen tutar: <b style="color:#ffffff;">{onerilen_tutar_hesap:,.2f} $</b></div>
        </div>
    """,
            unsafe_allow_html=True,
        )

    with st.form(key="manuel_islem_formu"):
        MIN_ISLEM_TUTARI = 0.0
        if acik_pozisyon_var:
            hesaplanan_tutar = min(100.0, float(mevcut_bakiye))
        else:
            hesaplanan_tutar = float(onerilen_tutar_hesap)

        guvenli_tutar = max(float(MIN_ISLEM_TUTARI), float(hesaplanan_tutar))
        max_tutar = (
            max(float(guvenli_tutar), float(mevcut_bakiye))
            if mevcut_bakiye > 0
            else 999999.0
        )

        manuel_girilen_tutar = st.number_input(
            "Tutar ($ Giriniz):",
            min_value=float(MIN_ISLEM_TUTARI),
            max_value=float(max_tutar),
            value=float(guvenli_tutar),
            step=10.0,
        )
        st.markdown(
            f"🟢 **Boştaki Nakit:** `{mevcut_bakiye:,.2f} $`", unsafe_allow_html=True
        )
        submit_islem = st.form_submit_button(
            "🔄 Ekleme Yap" if acik_pozisyon_var else "🚀 İşlemi Başlat",
            use_container_width=True,
        )

        if submit_islem:
            if not secilen_coin or coin_listesi == []:
                st.error("⚠️ Geçerli bir coin seçmelisiniz!")
            elif coin_verisii is not None:
                basari, mesaj = yeni_islem_ekle(
                    secilen_coin,
                    coin_verisii["Aktif_Yon"],
                    coin_verisii["Fiyat"],
                    manuel_girilen_tutar,
                    coin_verisii["Stopla"],
                    coin_verisii["Kar_Al"],
                    "Matris Kurgusu",
                    anlik_matris_puani,
                    anlik_risk_hedef_metin,
                )
                if basari:
                    st.success(mesaj)
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(mesaj)

with col_orta_grafik:
    st.markdown(
        "<h3>🌐 Top 5 Coin (16 Saat 5m Fibonacci & RSI)</h3>",
        unsafe_allow_html=True,
    )
    t_df_ham = total_ham_veri["df_market"]
    t_df = t_df_ham.tail(192).reset_index(drop=True)

    if not t_df.empty:
        delta = t_df["Close"].diff()
        rs = (delta.where(delta > 0, 0)).rolling(window=14).mean() / (
            -delta.where(delta < 0, 0)
        ).rolling(window=14).mean()
        t_df["RSI"] = (100 - (100 / (1 + rs))).fillna(50)

        min_f = float(t_df["Close"].min())
        max_f = float(t_df["Close"].max())

        if max_f - min_f < (max_f * 0.0001):
            min_f = min_f * 0.999
            max_f = max_f * 1.001

        fiyat_fark = max_f - min_f
        t_df["RSI_Norm"] = min_f + (t_df["RSI"] / 100.0) * fiyat_fark

        fib_levels = {
            0.0: min_f,
            0.236: min_f + 0.236 * fiyat_fark,
            0.382: min_f + 0.382 * fiyat_fark,
            0.5: min_f + 0.5 * fiyat_fark,
            0.618: min_f + 0.618 * fiyat_fark,
            0.786: min_f + 0.786 * fiyat_fark,
            1.0: max_f,
        }

        min_zaman = t_df["timestamp"].min()
        max_zaman_grafik = t_df["timestamp"].max() + pd.Timedelta(hours=1)

        alt_sinir = min_f - (fiyat_fark * 0.05)
        ust_sinir = max_f + (fiyat_fark * 0.05)

        fig_total = make_subplots(specs=[[{"secondary_y": True}]])

        for b_alt, b_ust, renk in [
            (0.0, 0.236, "rgba(180, 20, 50, 0.35)"),
            (0.236, 0.382, "rgba(220, 90, 0, 0.32)"),
            (0.382, 0.5, "rgba(255, 200, 0, 0.35)"),
            (0.5, 0.618, "rgba(255, 200, 0, 0.35)"),
            (0.618, 0.786, "rgba(40, 180, 80, 0.32)"),
            (0.786, 1.0, "rgba(0, 200, 90, 0.38)"),
        ]:
            x_coords = (
                list(t_df["timestamp"])
                + [max_zaman_grafik, max_zaman_grafik]
                + list(t_df["timestamp"][::-1])
            )
            y_coords = (
                [fib_levels[b_ust]] * len(t_df)
                + [fib_levels[b_ust], fib_levels[b_alt]]
                + [fib_levels[b_alt]] * len(t_df)
            )

            fig_total.add_trace(
                go.Scatter(
                    x=x_coords,
                    y=y_coords,
                    fill="toself",
                    fillcolor=renk,
                    line=dict(color="rgba(255,255,255,0)"),
                    showlegend=False,
                    hoverinfo="skip",
                ),
                secondary_y=False,
            )

        fig_total.add_trace(
            go.Scatter(
                x=t_df["timestamp"],
                y=t_df["Close"],
                mode="lines",
                name="Total Market",
                line=dict(color="#5b8cff", width=2.5),
            ),
            secondary_y=False,
        )
        fig_total.add_trace(
            go.Scatter(
                x=t_df["timestamp"],
                y=t_df["RSI_Norm"],
                mode="lines",
                name="RSI (0-1)",
                line=dict(color="#FF9900", width=1.5, dash="solid"),
            ),
            secondary_y=False,
        )

        for oran, val in fib_levels.items():
            renk_cizgi = (
                "#CCCC00" if oran == 0.5 else ("#006400" if oran > 0.5 else "#800020")
            )
            fig_total.add_hline(
                y=val,
                line_dash="dash",
                line_color=renk_cizgi,
                line_width=1,
            )

        fig_total.update_layout(
            template="plotly_dark",
            margin=dict(t=15, b=25, l=10, r=0),
            height=340,
            xaxis=dict(
                range=[min_zaman, max_zaman_grafik],
                dtick=3600000,
                tickformat="%H:%M",
                tickangle=25,
                gridcolor="rgba(255,255,255,0.05)",
            ),
            yaxis=dict(
                showticklabels=False,
                range=[alt_sinir, ust_sinir],
                gridcolor="rgba(255,255,255,0.05)",
            ),
            xaxis_rangeslider_visible=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(color="#e8eef8"),
            ),
        )
        st.plotly_chart(fig_total, use_container_width=True)

with col_sag_endeks:
    st.markdown("<h3>Top 5 Coin Endeksi</h3>", unsafe_allow_html=True)
    t_toplam_puan = t_l_puan + t_s_puan
    t_yuzde = (t_l_puan / t_toplam_puan * 100.0) if t_toplam_puan > 0 else 50.0
    t_yesil_led = round((t_yuzde / 100.0) * 10.0)
    t_yesil_led = max(0, min(10, t_yesil_led))
    t_kirmizi_led = 10 - t_yesil_led

    st.markdown(
        '<div style="text-align: center; line-height: 1.2; margin-bottom:'
        ' 6px;"><div style="font-size: 14px; margin-bottom: 2px; letter-spacing:'
        f' 1px;">{"🟢" * t_yesil_led}{"🔴" * t_kirmizi_led}</div><div'
        ' style="font-size: 10px; font-weight: 600;"><span style="color: #00FF00;'
        " display: inline-block; width: 8px; height: 8px; background-color:"
        ' #00FF00; border-radius: 50%; margin-right:'
        f' 2px;"></span>%{t_yuzde:.1f} | <span style="color: rgb(255, 75, 0);'
        " display: inline-block; width: 8px; height: 8px; background-color:"
        " rgb(255, 75, 0); border-radius: 50%; margin-left: 2px; margin-right:"
        f' 2px;"></span>%{100.0 - t_yuzde:.1f}</div></div>',
        unsafe_allow_html=True,
    )

    t_zaman_kat = total_ham_veri["zaman_katkilari"]
    boxes_listesi = []
    for etk, veri in t_zaman_kat.items():
        sl, ss = veri["sl"], veri["ss"]
        y_ad, k_ad = veri["y_adet"], veri["k_adet"]
        kazanan_renk = "#00FF00" if sl >= ss else "rgb(255, 75, 0)"
        kutucuk_html = (
            f'<div style="background-color: {kazanan_renk}; color: #000000;'
            " padding: 6px; border-radius: 6px; text-align: center; font-weight:"
            " bold; font-size: 11px; margin-bottom: 5px; line-height:"
            f' 1.3;">{etk}<br>L: {sl:.2f}p ({y_ad}) | S: {ss:.2f}p ({k_ad})</div>'
        )
        boxes_listesi.append(kutucuk_html)
    boxes_birlestirilmis = "".join(boxes_listesi)

    st.markdown(
        '<div class="metric-container" style="text-align: center; padding: 10px'
        ' !important;"><div style="font-size: 12px; font-weight: bold;'
        " margin-bottom: 6px;\">Top 5 Ortalama Değeri: <span style=\"color:"
        f' rgb(70, 0, 255);">${total_ham_veri["anlik_fiyat"] / 1e12:.2f}T</span><br>Puan:'
        ' <span style="color:'
        f' {"#00FF00" if total_ham_veri["aktif_yon"] == "Long" else ("rgb(255, 75, 0)" if total_ham_veri["aktif_yon"] == "Short" else "#ffc107")};">{total_ham_veri["nihai_puan"]:.1f}'
        f' / 100 ({total_ham_veri["aktif_yon"]})</span></div>{boxes_birlestirilmis}</div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

df_gecmis = islem_gecmisi_getir(sheet_guncelle=False)
acik_islem_listesi = (
    df_gecmis[
        ~df_gecmis["Durum"]
        .astype(str)
        .str.contains("kapandi|kar|zarar", case=False, na=False)
    ]["Islem_ID"].tolist()
    if not df_gecmis.empty and "Durum" in df_gecmis.columns
    else []
)

col_sol_analiz, col_orta_durum, col_sag_sonlandir = st.columns(
    [2.5, 1, 1], gap="medium"
)

with col_sol_analiz:
    st.markdown(
        "<h3>📊 Kapanan İşlemler & Para Akışı Analizi</h3>",
        unsafe_allow_html=True,
    )
    kapananlar_df = (
        pd.DataFrame()
        if df_gecmis.empty or "Durum" not in df_gecmis.columns
        else df_gecmis[
            df_gecmis["Durum"]
            .astype(str)
            .str.contains("Kapandi|Kar|Zarar|Kismi", case=False, na=False)
        ]
    )

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
        kar_yuzde = (
            (karli_sayisi / toplam_kapanan * 100.0) if toplam_kapanan > 0 else 0.0
        )
        zarar_yuzde = (
            (zararli_sayisi / toplam_kapanan * 100.0) if toplam_kapanan > 0 else 0.0
        )

        sub_p1, sub_p2, sub_p3 = st.columns([1.35, 1.35, 1.35], gap="medium")
        with sub_p1:
            fig = px.pie(
                pd.DataFrame({
                    "Durum": ["Kârlı", "Zararlı"],
                    "Adet": [karli_sayisi, zararli_sayisi],
                }),
                names="Durum",
                values="Adet",
                hole=0.50,
                color="Durum",
                color_discrete_map={"Kârlı": "#00FF00", "Zararlı": "rgb(255, 75, 0)"},
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e8eef8", size=13),
                margin=dict(t=10, b=10, l=10, r=10),
                height=210,
                showlegend=False,
            )
            fig.update_traces(
                textfont_size=13, textinfo="percent", marker=dict(line=dict(width=0))
            )
            st.plotly_chart(
                fig,
                use_container_width=True,
                config={"responsive": True, "displayModeBar": False},
            )

        with sub_p2:
            st.markdown(
                f"""<div style="font-size: 15px; font-weight: bold; color: #e8eef8; margin-bottom: 4px;">📈 Strateji Metrikleri</div>
            <p style="margin: 4px 0px 0px 0px; font-size: 13px; color: #91a0b8;">Toplam Kapanan</p>
            <p style="margin: 0px; font-size: 18px; font-weight: bold; color: #e8eef8;">{toplam_kapanan} Adet</p>
            <p style="margin: 8px 0px 0px 0px; font-size: 14px; color: #00FF00; font-weight: bold;">🟢 Kârlı: {karli_sayisi} (%{kar_yuzde:.1f})</p>
            <p style="margin: 5px 0px 0px 0px; font-size: 14px; color: rgb(255, 75, 0); font-weight: bold;">🔴 Zararlı: {zararli_sayisi} (%{zarar_yuzde:.1f})</p>""",
                unsafe_allow_html=True,
            )

        with sub_p3:
            net_renk = "#00FF00" if net_fark_dolar >= 0 else "rgb(255, 75, 0)"
            st.markdown(
                f"""<div style="display: flex; flex-direction: column; justify-content: center; height: 100%; padding-top: 15px;">
                <div style="font-size: 14px; font-weight: bold; color: #00FF00; margin-bottom: 8px;">Toplam Kâr: +{toplam_kazanc_dolar:,.2f} $</div>
                <div style="font-size: 14px; font-weight: bold; color: rgb(255, 75, 0); margin-bottom: 8px;">Toplam Zarar: -{toplam_kayip_dolar:,.2f} $</div>
                <div style="font-size: 15px; font-weight: bold; color: {net_renk}; margin-top: 4px; border-top: 1px solid #30415b; padding-top: 8px;">Net Fark: {net_fark_dolar:+,.2f} $</div>
            </div>""",
                unsafe_allow_html=True,
            )
    else:
        st.info("ℹ️ Henüz kapanmış işlem bulunmuyor.")

with col_orta_durum:
    st.markdown("<h3>👁️ İşlem Sunumu</h3>", unsafe_allow_html=True)
    st.markdown('<div style="height: 40px;"></div>', unsafe_allow_html=True)
    if st.button("Aktif İşlemler", use_container_width=True):
        st.session_state["sadece_aktifleri_goster"] = True
        st.rerun()
    if st.button("Tüm İşlemler", use_container_width=True):
        st.session_state["sadece_aktifleri_goster"] = False
        st.rerun()

    if st.session_state["sadece_aktifleri_goster"]:
        st.info("ℹ️ Sadece Aktifler.")
    else:
        st.info("ℹ️ Tüm işlemler.")

# --- KESİN ÇÖZÜMLÜ FORM TABANLI İKİ YÖNLÜ SENKRONİZE KAPAMA PANELİ ---
with col_sag_sonlandir:
    st.markdown("<h3>🛑 İşlemi Kapat</h3>", unsafe_allow_html=True)
    st.markdown('<div style="height: 10px;"></div>', unsafe_allow_html=True)
    
    kapatilacak_id = st.selectbox(
        "ID Kodu:",
        acik_islem_listesi if acik_islem_listesi else [0],
        key="k_id_secim",
    )
    
    st.markdown('<div style="height: 5px;"></div>', unsafe_allow_html=True)
    
    if not st.session_state.get("kapama_paneli_acik", False):
        if st.button("Kapama Yap", use_container_width=True, key="kapama_paneli_ac_btn"):
            if acik_islem_listesi and kapatilacak_id in acik_islem_listesi:
                st.session_state["kapama_paneli_acik"] = True
                secilen_islem_satir = df_gecmis[df_gecmis["Islem_ID"] == kapatilacak_id]
                if not secilen_islem_satir.empty:
                    miktarr = float(secilen_islem_satir["Islem_Miktari"].iloc[0])
                    st.session_state["girilen_dolar_input"] = miktarr
                    st.session_state["girilen_yuzde_input"] = 100.0
                st.rerun()
            else:
                st.warning("Seçilen ID'ye ait açık işlem bulunmuyor!")
    else:
        secilen_islem_miktar = 100.0
        secilen_coin = "BTC/USDT"
        if acik_islem_listesi and kapatilacak_id in acik_islem_listesi:
            secilen_islem_satir = df_gecmis[df_gecmis["Islem_ID"] == kapatilacak_id]
            if not secilen_islem_satir.empty:
                secilen_islem_miktar = float(secilen_islem_satir["Islem_Miktari"].iloc[0])
                secilen_coin = str(secilen_islem_satir["Coin"].iloc[0])

        st.markdown(
            f"""<div style="background:linear-gradient(145deg,#17263b,#111b2b); color:#e8eef8; border:1px solid #30415b; padding:10px; border-radius:8px; margin-bottom:10px; font-size:12px;">
                <b>{secilen_coin}</b> (#{kapatilacak_id}) Pozisyonu:<br>
                Yatırım: <b style="color:#60a5fa;">{secilen_islem_miktar:,.2f} $</b>
            </div>""",
            unsafe_allow_html=True,
        )

        if "girilen_dolar_input" not in st.session_state:
            st.session_state["girilen_dolar_input"] = secilen_islem_miktar
        if "girilen_yuzde_input" not in st.session_state:
            st.session_state["girilen_yuzde_input"] = 100.0

        # Form kullanarak state döngü kilitlenmesini ve anlık senkronizasyon sorununu tamamen çözüyoruz
        with st.form(key="kapama_formu_senkron"):
            col_tutar_kutusu, col_oran_kutusu = st.columns(2)
            with col_tutar_kutusu:
                val_tutar = st.number_input(
                    "Tutar ($):",
                    min_value=0.0,
                    max_value=float(secilen_islem_miktar),
                    value=float(st.session_state["girilen_dolar_input"]),
                    step=10.0,
                )
            with col_oran_kutusu:
                val_oran = st.number_input(
                    "Oran (%):",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(st.session_state["girilen_yuzde_input"]),
                    step=5.0,
                )

            col_islem_yap, col_iptal = st.columns(2)
            with col_islem_yap:
                submit_kapat = st.form_submit_button("Emri Gerçekleştir", use_container_width=True)
            with col_iptal:
                submit_iptal = st.form_submit_button("İptal", use_container_width=True)

            if submit_iptal:
                st.session_state["kapama_paneli_acik"] = False
                st.rerun()

            if submit_kapat:
                # Kullanıcının hangi alanı değiştirdiğini akıllıca algılayıp hesaplıyoruz
                if val_tutar != st.session_state["girilen_dolar_input"]:
                    kapatilacak_net_tutar = val_tutar
                elif val_oran != st.session_state["girilen_yuzde_input"]:
                    kapatilacak_net_tutar = round((secilen_islem_miktar * val_oran) / 100.0, 2)
                else:
                    kapatilacak_net_tutar = val_tutar

                if kapatilacak_net_tutar <= 0:
                    st.error("Kapatılacak miktar 0'dan büyük olmalıdır!")
                else:
                    hedef_miktar = None if kapatilacak_net_tutar >= secilen_islem_miktar else kapatilacak_net_tutar
                    
                    b_durum, b_mesaj = manuel_islem_kapat(
                        kapatilacak_id,
                        ortak_fiyat_havuzu.get(
                            secilen_coin, baz_fiyatlar.get(secilen_coin, 100.0)
                        ),
                        kapatilacak_miktar=hedef_miktar
                    )
                    if b_durum:
                        st.session_state["kapama_paneli_acik"] = False
                        st.success(b_mesaj)
                        time.sleep(1.2)
                        st.rerun()
                    else:
                        st.error(b_mesaj)

st.markdown("---")

df_gecmisile_goster = islem_gecmisi_getir(sheet_guncelle=False)
df_gosterilecek = pd.DataFrame()
if not df_gecmisile_goster.empty:
    df_gosterilecek = (
        df_gecmisile_goster[
            ~df_gecmisile_goster["Durum"]
            .astype(str)
            .str.contains("kapandi|kar|zarar", case=False, na=False)
        ]
        if st.session_state["sadece_aktifleri_goster"]
        else df_gecmisile_goster.copy()
    )

anlik_fiyat_sozluk, anlik_kz_sozluk, hedef_kar_sozluk, olasi_stop_sozluk = (
    {},
    {},
    {},
    {},
)
if not df_gecmisile_goster.empty:
    for _, row in df_gecmisile_goster.iterrows():
        islem_id, coin, giris_fiyat, miktar, kar_al_f, stop_f, yon = (
            row["Islem_ID"],
            row["Coin"],
            float(row["Giris_Fiyat"]),
            float(row["Islem_Miktari"]),
            float(row["Kar_Al"]),
            float(row["Stop"]),
            row["Yon"],
        )
        anl_f = ortak_fiyat_havuzu.get(coin, baz_fiyatlar.get(coin, 100.0))
        anlik_fiyat_sozluk[islem_id] = anl_f

        if giris_fiyat > 0 and kar_al_f > 0 and stop_f > 0:
            hedef_kar_sozluk[islem_id] = round(
                miktar
                * KALDIRAC
                * (
                    ((kar_al_f - giris_fiyat) / giris_fiyat)
                    if "Long" in yon
                    else ((giris_fiyat - kar_al_f) / giris_fiyat)
                ),
                2,
            )
            olasi_stop_sozluk[islem_id] = round(
                miktar
                * KALDIRAC
                * (
                    ((stop_f - giris_fiyat) / giris_fiyat)
                    if "Long" in yon
                    else ((giris_fiyat - stop_f) / giris_fiyat)
                ),
                2,
            )
        else:
            hedef_kar_sozluk[islem_id], olasi_stop_sozluk[islem_id] = 0.0, 0.0

        if not (
            "kapandi" in str(row["Durum"]).lower()
            or "kar" in str(row["Durum"]).lower()
            or "zarar" in str(row["Durum"]).lower()
        ):
            anlik_kz_sozluk[islem_id] = round(
                miktar
                * KALDIRAC
                * (
                    ((anl_f - giris_fiyat) / giris_fiyat)
                    if "Long" in yon
                    else ((giris_fiyat - anl_f) / giris_fiyat)
                ),
                2,
            )
        else:
            anlik_kz_sozluk[islem_id] = float(row["Net_Kar_Zarar"])

portfoy_html = """
<table class="custom-table"><thead class="custom-table-header"><tr>
 <th>ID</th><th>Açılış</th><th>Logo</th><th>Coin</th><th>Yön</th><th>Giriş</th><th>Anlık</th><th>Kapanış</th>
 <th>Matris Puanı</th><th>Yatırım</th><th>Hedef</th><th>Stop</th><th>Beklenen Kâr</th><th>Olası Stop</th>
 <th>Durum</th><th>Anlık K/Z</th><th>Kapanış Zamanı</th><th>Güncel Kasa</th>
 </tr></thead><tbody>
"""

if not df_gosterilecek.empty:
    df_gecmis_copy = df_gosterilecek.copy()
    df_gecmis_copy["Anlik_Fiyat_Deger"] = df_gecmis_copy["Islem_ID"].map(
        anlik_fiyat_sozluk
    )
    df_gecmis_copy["Canli_Beklenen_Kar"] = df_gecmis_copy["Islem_ID"].map(
        hedef_kar_sozluk
    )
    df_gecmis_copy["Canli_Olasi_Stop"] = df_gecmis_copy["Islem_ID"].map(
        olasi_stop_sozluk
    )
    df_gecmis_copy["Anlik_KZ_Deger"] = df_gecmis_copy["Islem_ID"].map(
        anlik_kz_sozluk
    )

    for _, row in df_gecmis_copy.iterrows():
        logo_h = f'<img src="{logo_urls.get(row["Coin"], "")}" width="24" height="24">'
        yon_h = (
            '<div style="background-color:'
            f' {"#00FF00" if "Long" in row["Yon"] else "rgb(255, 75, 0)"}; padding:'
            ' 6px; border-radius: 6px; color: #000000; font-weight:'
            f' bold;">{row["Yon"]}</div>'
        )
        anlik_fiyat_h = (
            '<div style="background-color:'
            f' {"#00FF00" if float(row["Anlik_Fiyat_Deger"] or 0) > float(row["Giris_Fiyat"]) else "rgb(255, 75, 0)"};'
            " color: #000000; padding: 5px; font-weight:"
            f' bold;">{float(row["Anlik_Fiyat_Deger"] or 0):,.{4 if row["Coin"] == "XRP/USDT" else 2}f}&nbsp;$</div>'
        )

        if not (
            "kapandi" in str(row["Durum"]).lower()
            or "kar" in str(row["Durum"]).lower()
            or "zarar" in str(row["Durum"]).lower()
        ):
            kapanis_fiyat_h, durum_h = (
                '<div style="padding: 5px; color: #6c757d;">-</div>',
                '<div style="background-color: rgb(70, 0, 255); color: white;'
                ' padding: 4px; border-radius: 4px; font-weight: bold;">Aktif</div>',
            )
        else:
            is_kar = float(row["Net_Kar_Zarar"]) >= 0
            sinif = "kar-hucre" if is_kar else "zarar-hucre"
            kapanis_fiyat_h = (
                f'<div class="{sinif}">{float(row.get("Kapanis_Fiyati", 0.0) or row["Giris_Fiyat"]):,.{4 if row["Coin"] == "XRP/USDT" else 2}f}&nbsp;$</div>'
            )
            durum_h = (
                f'<div class="{sinif}">{row["Durum"]}</div>'
            )

        kz_h = (
            '<div style="background-color:'
            f' {"#00FF00" if float(row["Anlik_KZ_Deger"] or 0) >= 0 else "rgb(255, 75, 0)"};'
            " color: #000000; padding: 5px; font-weight: bold; white-space:"
            f' nowrap;">{float(row["Anlik_KZ_Deger"] or 0):+,.2f}&nbsp;$</div>'
        )

        matris_puan_rh_metin = str(row.get('Matris_Puan_RH', '50.0 (1,20 / 1,50)'))
        islem_miktari_val = float(row['Islem_Miktari'])

        portfoy_html += (
            f"<tr><td>{row['Islem_ID']}</td><td>{row['Acilis_Zamani']}</td><td>{logo_h}</td><td>{row['Coin']}</td><td>{yon_h}</td><td>{float(row['Giris_Fiyat']):,.{4 if row['Coin'] == 'XRP/USDT' else 2}f}&nbsp;$</td><td>{anlik_fiyat_h}</td><td>{kapanis_fiyat_h}</td><td"
            " style='font-weight: bold; color:"
            f" #495057;'>{matris_puan_rh_metin}</td><td>{islem_miktari_val:,.2f}&nbsp;$</td><td>{float(row['Kar_Al']):,.{4 if row['Coin'] == 'XRP/USDT' else 2}f}&nbsp;$</td><td>{float(row['Stop']):,.{4 if row['Coin'] == 'XRP/USDT' else 2}f}&nbsp;$</td><td>{float(row['Canli_Beklenen_Kar']):,.2f}&nbsp;$</td><td>{float(row['Canli_Olasi_Stop']):,.2f}&nbsp;$</td><td>{durum_h}</td><td>{kz_h}</td><td>{row['Kapanis_Zamani']}</td><td>{float(row['Guncel_Kasa']):,.2f}&nbsp;$</td></tr>"
        )
else:
    portfoy_html += (
        "<tr><td colspan='18' style='text-align: center; color: #6c757d; padding:"
        " 20px;'>Kayıtlı işlem bulunmuyor.</td></tr>"
    )

portfoy_html += "</tbody></table>"
st.markdown(
    f'<div class="table-container">{portfoy_html}</div>', unsafe_allow_html=True
)

st.markdown("---")
st.markdown(
    "<h3>📁 50'şerli İşlem Arşivleri (Analiz Klasörü)</h3>",
    unsafe_allow_html=True,
)
if os.path.exists(ARSIV_KLASORU):
    try:
        arsiv_dosyalari = sorted(os.listdir(ARSIV_KLASORU))
        if secilen_arsiv := (
            st.selectbox(
                "Geçmiş 50'li Blok Dönemini Seçin:",
                arsiv_dosyalari,
                key="arsiv_select_50",
            )
            if arsiv_dosyalari
            else None
        ):
            st.write(
                pd.read_csv(
                    os.path.join(ARSIV_KLASORU, secilen_arsiv), delimiter=";"
                ).to_html(escape=False, index=False),
                unsafe_allow_html=True,
            )
        elif not arsiv_dosyalari:
            st.info("Henüz 50 işleme ulaşılmadı.")
    except:
        st.info("Arşiv yüklenirken bilgi alınamadı.")
else:
    st.info("Arşiv klasörü henüz oluşturulmadı.")
