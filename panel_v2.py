import time
import threading
import json
import os
import smtplib
import math
import sys
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
HAFIZA_DOSYASI = "sinyal_hafizasi.json"
MAIL_LOG_DOSYASI = "mail_log.txt"

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

# ==========================================
# 1. HİBRİT SİSTEM: PANEL İÇİ MAİL GÖNDERİCİ (Manuel Kapanışlar İçin)
# ==========================================
def manuel_kapanis_maili_gonder(coin, yon, miktar, net_kar, guncel_kasa):
    gonderici_mail = "erhanvancin@gmail.com"
    alici_mail = "erhanvancin@gmail.com"
    
    try:
        uygulama_sifresi = st.secrets.get("GMAIL_PASSWORD", os.environ.get("GMAIL_PASSWORD", ""))
    except:
        uygulama_sifresi = os.environ.get("GMAIL_PASSWORD", "")
        
    if not uygulama_sifresi:
        print("Mail şifresi bulunamadı, mail gönderilemiyor.")
        return False
        
    try:
        durum_metni = "Kar" if net_kar > 0 else "Zarar"
        konu = f"🛑 PANEL KAPANIŞI: {coin} ({durum_metni})"
        icerik_html = f"""
        <h3>İşlem Arayüzden Kapatıldı</h3>
        <p><b>Coin:</b> {coin}</p>
        <p><b>Yön:</b> {yon}</p>
        <p><b>Kapatılan Miktar:</b> {miktar:,.2f} $</p>
        <p><b>Net K/Z:</b> {net_kar:,.2f} $</p>
        <p><b>Güncel Kasa:</b> {guncel_kasa:,.2f} $</p>
        """
        
        msg = MIMEMultipart()
        msg["From"] = gonderici_mail
        msg["To"] = alici_mail
        msg["Subject"] = konu
        msg.attach(MIMEText(icerik_html, "html", "utf-8"))

        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(gonderici_mail, uygulama_sifresi)
        server.sendmail(gonderici_mail, [alici_mail], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Mail gönderme hatası: {e}")
        return False

# ==========================================
# 2. LOGARİTMİK RİSK VE HEDEF EĞRİSİ 
# ==========================================
def calculate_coin_metrics_by_score(matris_puani):
    hsonu = hafta_sonu_mu() if 'hafta_sonu_mu' in globals() else False
    min_esik = 60.0 if hsonu else 55.0

    if matris_puani < min_esik:
        return 0.70, 1.0, "Nötr"

    x_puanlar = np.array([55.0, 59.0, 63.0, 67.0, 71.0, 75.0])
    y_risk    = np.array([0.75, 0.70, 0.65, 0.60, 0.55, 0.50])
    y_hedef   = np.array([0.75, 0.91, 1.08, 1.27, 1.46, 1.50])

    puan = max(min_esik, min(75.0, matris_puani))

    stop_uzde = float(np.interp(puan, x_puanlar, y_risk))
    hedef_uzde = float(np.interp(puan, x_puanlar, y_hedef))

    hedef_carpan = hedef_uzde / stop_uzde if stop_uzde > 0 else 1.5

    str_stop = f"{stop_uzde:.2f}".replace(".", ",")
    str_hedef = f"{hedef_uzde:.2f}".replace(".", ",")
    risk_hedef_metin = f"{str_stop} / {str_hedef}"

    return stop_uzde, hedef_carpan, risk_hedef_metin

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
    sayisal_kolonlar = [
        "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Beklenen_Kar",
        "Olasi_Stop", "Net_Kar_Zarar", "Guncel_Kasa", "Kapanis_Fiyati"
    ]
    for col in sayisal_kolonlar:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", ".").str.strip(),
                errors="coerce",
            ).fillna(0.0).astype(float)
    return df

def dataframe_guncelle_gsheets(df):
    sheet = google_sheets_baglan("KriptoPortfoyVeritabani")
    if sheet is not None:
        try:
            df["Islem_ID"] = df["Islem_ID"].astype(int)
            df = df.sort_values(by="Islem_ID").reset_index(drop=True)
            veri_listesi = [df.columns.tolist()] + df.values.tolist()
            sheet.clear()
            sheet.update(veri_listesi)
        except Exception as e:
            print(f"GSheets Güncelleme Hatası: {e}")
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
    df["Islem_ID"] = pd.to_numeric(df["Islem_ID"], errors="coerce").fillna(0).astype(int)
    df["Tutar"] = pd.to_numeric(
        df["Tutar"].astype(str).str.replace(",", ".").str.strip(),
        errors="coerce",
    ).fillna(0.0).astype(float)
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

def kasa_islem_ekle(islem_turu, tutar, aciklama):
    df_kasa = kasa_defteri_getir()
    yeni_id = 1 if df_kasa.empty else int(pd.to_numeric(df_kasa["Islem_ID"], errors="coerce").max() or 0) + 1
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
    df_kasa = pd.concat([df_kasa, yeni_kayit], ignore_index=True).drop_duplicates(subset=["Islem_ID"], keep="last")
    kasa_defteri_guncelle_gsheets(df_kasa)
    return True, f"Kasa işlemi başarılı: {islem_turu} -> {net_tutar:.2f} $"

def kasa_islem_ekle_deftere(islem_turu, tutar, aciklama):
    df_kasa = kasa_defteri_getir()
    yeni_id = 1 if df_kasa.empty else int(pd.to_numeric(df_kasa["Islem_ID"], errors="coerce").max() or 0) + 1
    suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")
    yeni_kayit = pd.DataFrame([{
        "Islem_ID": yeni_id,
        "Zaman": suan_tr,
        "Islem_Turu": islem_turu,
        "Tutar": round(tutar, 2),
        "Aciklama": aciklama,
    }])
    df_kasa = pd.concat([df_kasa, yeni_kayit], ignore_index=True).drop_duplicates(subset=["Islem_ID"], keep="last")
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
                yol = os.path.join(ARSIV_KLASORU, f"islem_arsivi_{bas_i+1}_{bit_i}.csv")
                if not os.path.exists(yol):
                    blok_df.to_csv(yol, sep=";", index=False)
    except:
        pass

def bakiye_durumunu_getir(ortak_fiyat_havuzu={}):
    df_trade = islem_gecmisi_getir(sheet_guncelle=False)
    df_kasa = kasa_defteri_getir()
    net_kasa_hareketleri = BASLANGIC_BAKIYE

    if not df_kasa.empty:
        net_kasa_hareketleri += pd.to_numeric(df_kasa["Tutar"], errors="coerce").fillna(0.0).sum()

    if not df_trade.empty:
        kap_trades = df_trade[df_trade["Durum"].astype(str).str.contains("Kapandi|Kar|Zarar|Kismi", case=False, na=False)]
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
        kapali_mask = df_trade["Durum"].astype(str).str.contains("kapandi|kar|zarar|kısmi", case=False, na=False)
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
            
            anl_F = ortak_fiyat_havuzu.get(c_SYM, baz_fiyatlar.get(c_SYM, 100.0))
            f_y = ((anl_F - g_F) / g_F) if "Long" in y_Y else ((g_F - anl_F) / g_F)
            acik_kz_toplam += m_M * KALDIRAC * f_y

    efektif_kasa = toplam_kasa + acik_kz_toplam
    bos_bakiye = toplam_kasa - aktif_marjin_toplami
    return float(toplam_kasa), float(efektif_kasa), float(bos_bakiye), float(aktif_marjin_toplami), float(acik_kz_toplam)

# ==========================================
# 3. ZAMAN VE SERMAYE AĞIRLIKLI İŞLEM EKLEME (DCA)
# ==========================================
def yeni_islem_ekle(coin, yon, giris_fiyat, islem_miktari, stop, kar_al, zaman_dilimi, matris_puan, risk_hedef_metin):
    df = islem_gecmisi_getir()
    _, _, mevcut_bakiye, _, _ = bakiye_durumunu_getir()
    
    if round(islem_miktari, 2) > round(mevcut_bakiye, 2):
        return False, f"Bakiye yetersiz! Mevcut Bakiye: {mevcut_bakiye:.2f} $, Girilen: {islem_miktari:.2f} $"
    if islem_miktari <= 0:
        return False, "İşlem miktarı 0 $'dan büyük olmalıdır!"

    suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")
    acik_islem_idx = None
    
    if not df.empty and "Durum" in df.columns:
        acik_mask = ~df["Durum"].astype(str).str.contains("kapandi|kar|zarar|kısmi", case=False, na=False)
        acik_df = df[acik_mask]
        if not acik_df.empty and coin in acik_df["Coin"].values:
            acik_islem_idx = acik_df[acik_df["Coin"] == coin].index[0]

    if acik_islem_idx is not None:
        eski_giris = float(df.loc[acik_islem_idx, "Giris_Fiyat"])
        eski_miktar = float(df.loc[acik_islem_idx, "Islem_Miktari"])
        eski_yon = str(df.loc[acik_islem_idx, "Yon"])
        eski_zaman_str = str(df.loc[acik_islem_idx, "Acilis_Zamani"])

        eski_matris_rh = str(df.loc[acik_islem_idx, "Matris_Puan_RH"])
        try:
            eski_puan = float(eski_matris_rh.split()[0].replace(",", "."))
        except:
            eski_puan = matris_puan

        # -- ZAMAN VE SERMAYE AĞIRLIĞI HESAPLAMASI --
        try:
            eski_zaman_obj = datetime.strptime(eski_zaman_str, "%d.%m.%Y %H:%M").replace(tzinfo=TR_TZ)
            simdi_zaman_obj = tr_zaman()
            gecen_dakika = max(0.0, (simdi_zaman_obj - eski_zaman_obj).total_seconds() / 60.0)
        except:
            gecen_dakika = 0.0

        yeni_toplam_miktar = eski_miktar + islem_miktari

        if yeni_toplam_miktar > 0:
            agirlikli_dakika = ((eski_miktar * 0.0) + (islem_miktari * gecen_dakika)) / yeni_toplam_miktar
            yeni_zaman_obj = eski_zaman_obj + timedelta(minutes=agirlikli_dakika)
            yeni_acilis_zamani_str = yeni_zaman_obj.strftime("%d.%m.%Y %H:%M")
        else:
            yeni_acilis_zamani_str = suan_tr

        yeni_agirlikli_ortalama = ((eski_miktar * eski_giris) + (islem_miktari * giris_fiyat)) / yeni_toplam_miktar
        yeni_agirlikli_puan = ((eski_miktar * eski_puan) + (islem_miktari * matris_puan)) / yeni_toplam_miktar

        if eski_giris > 0:
            stop_oran = abs(stop - giris_fiyat) / giris_fiyat
            kar_al_oran = abs(kar_al - giris_fiyat) / giris_fiyat
        else:
            stop_oran, kar_al_oran = 0.01, 0.02

        if "Long" in eski_yon:
            yeni_stop = yeni_agirlikli_ortalama * (1.0 - stop_oran)
            yeni_kar_al = yeni_agirlikli_ortalama * (1.0 + kar_al_oran)
            beklenen_kar = yeni_toplam_miktar * KALDIRAC * ((yeni_kar_al - yeni_agirlikli_ortalama) / yeni_agirlikli_ortalama)
            olasi_stop = yeni_toplam_miktar * KALDIRAC * ((yeni_stop - yeni_agirlikli_ortalama) / yeni_agirlikli_ortalama)
        else:
            yeni_stop = yeni_agirlikli_ortalama * (1.0 + stop_oran)
            yeni_kar_al = yeni_agirlikli_ortalama * (1.0 - kar_al_oran)
            beklenen_kar = yeni_toplam_miktar * KALDIRAC * ((yeni_agirlikli_ortalama - yeni_kar_al) / yeni_agirlikli_ortalama)
            olasi_stop = yeni_toplam_miktar * KALDIRAC * ((yeni_agirlikli_ortalama - yeni_stop) / yeni_agirlikli_ortalama)

        # Matris puanı ve risk hedefini logaritmik güncelle
        _, _, guncel_risk_hedef_metin = calculate_coin_metrics_by_score(yeni_agirlikli_puan)
        basamak = 4 if yeni_agirlikli_ortalama < 10 else 2
        matris_rh_metin = f"{yeni_agirlikli_puan:.2f} ({guncel_risk_hedef_metin})"
        toplam_kasa, _, _, _, _ = bakiye_durumunu_getir()

        df.at[acik_islem_idx, "Giris_Fiyat"] = round(yeni_agirlikli_ortalama, basamak)
        df.at[acik_islem_idx, "Islem_Miktari"] = round(yeni_toplam_miktar, 2)
        df.at[acik_islem_idx, "Stop"] = round(yeni_stop, basamak)
        df.at[acik_islem_idx, "Kar_Al"] = round(yeni_kar_al, basamak)
        df.at[acik_islem_idx, "Acilis_Zamani"] = yeni_acilis_zamani_str  
        df.at[acik_islem_idx, "Beklenen_Kar"] = round(beklenen_kar, 2)
        df.at[acik_islem_idx, "Olasi_Stop"] = round(olasi_stop, 2)
        df.at[acik_islem_idx, "Matris_Puan_RH"] = matris_rh_metin
        df.at[acik_islem_idx, "Guncel_Kasa"] = round(toplam_kasa, 2)

        dataframe_guncelle_gsheets(df)
        elli_islem_arsiv_kontrol()
        return True, f"🔄 {coin} pozisyonuna ekleme yapıldı! Yeni Ort. Maliyet: {yeni_agirlikli_ortalama:,.{basamak}f} $"
    
    else:
        # Yeni İşlem Açılışı
        min_esik_kontrol = aktif_min_puan_esigi_getir()
        if matris_puan < min_esik_kontrol or "Nötr" in yon or "Beklemede" in yon:
            return False, f"⚠️ Nötr veya Min. Eşik ({min_esik_kontrol}) altındaki yeni işlemler engellenmiştir!"

        yeni_id = 1 if df.empty else int(pd.to_numeric(df["Islem_ID"], errors="coerce").max() or 0) + 1

        if "Long" in yon:
            beklenen_kar = islem_miktari * KALDIRAC * ((kar_al - giris_fiyat) / giris_fiyat)
            olasi_stop = islem_miktari * KALDIRAC * ((stop - giris_fiyat) / giris_fiyat)
        else:
            beklenen_kar = islem_miktari * KALDIRAC * ((giris_fiyat - kar_al) / giris_fiyat)
            olasi_stop = islem_miktari * KALDIRAC * ((giris_fiyat - stop) / giris_fiyat)

        basamak = 4 if giris_fiyat < 10 else 2
        matris_rh_metin = f"{matris_puan:.2f} ({risk_hedef_metin})"
        toplam_kasa, _, _, _, _ = bakiye_durumunu_getir()
        
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
        
        df = pd.concat([df, yeni_kayit], ignore_index=True).drop_duplicates(subset=["Islem_ID"], keep="last")
        dataframe_guncelle_gsheets(df)
        elli_islem_arsiv_kontrol()
        return True, f"✅ {coin} emri başarıyla verildi!"

# ==========================================
# 4. ENTEGRE EDİLMİŞ PANEL İŞLEM KAPATMA
# ==========================================
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
            fark_yuzde = ((anlik_kapatma_fiyati - giris_fiyat) / giris_fiyat) if "Long" in row["Yon"] else ((giris_fiyat - anlik_kapatma_fiyati) / giris_fiyat)
            kismi_kar = kapatilacak_miktar * KALDIRAC * fark_yuzde
            
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
            
            kasa_islem_ekle_deftere("Trade_Sonuc", float(round(kismi_kar, 2)), f"Kısmi K/Z: #{islem_id} {row['Coin']} ({kapatilacak_miktar}$ kapatıldı)")
            elli_islem_arsiv_kontrol()
            
            # MAİL TETİKLEYİCİSİ
            manuel_kapanis_maili_gonder(row['Coin'], row['Yon'], kapatilacak_miktar, kismi_kar, toplam_kasa + kismi_kar)
            
            return True, f"Kısmi kapama başarılı! Realize Edilen K/Z: {kismi_kar:,.2f} $"
        else:
            fark_yuzde = ((anlik_kapatma_fiyati - giris_fiyat) / giris_fiyat) if "Long" in row["Yon"] else ((giris_fiyat - anlik_kapatma_fiyati) / giris_fiyat)
            net_kar = mevcut_miktar * KALDIRAC * fark_yuzde
            
            durum_metni = "Kapandi (Zarar)" if net_kar < 0 else "Kapandi (Kar)"
            df.at[idx[0], "Durum"] = durum_metni
            df.at[idx[0], "Kapanis_Zamani"] = suan_tr
            df.at[idx[0], "Net_Kar_Zarar"] = float(round(net_kar, 2))
            df.at[idx[0], "Kapanis_Fiyati"] = float(round(anlik_kapatma_fiyati, 4))
            
            toplam_kasa, _, _, _, _ = bakiye_durumunu_getir()
            df.at[idx[0], "Guncel_Kasa"] = float(round(toplam_kasa + net_kar, 2))
            dataframe_guncelle_gsheets(df)
            kasa_islem_ekle_deftere("Trade_Sonuc", float(round(net_kar, 2)), f"Trade K/Z: #{islem_id} {row['Coin']} ({durum_metni})")
            elli_islem_arsiv_kontrol()
            
            # MAİL TETİKLEYİCİSİ
            manuel_kapanis_maili_gonder(row['Coin'], row['Yon'], mevcut_miktar, net_kar, toplam_kasa + net_kar)
            
            return True, f"İşlem tamamen kapatıldı. K/Z: {net_kar:.2f} $"
    except Exception as e:
        return False, f"Hata: {str(e)}"
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
            fark_yuzde = ((anlik_kapatma_fiyati - giris_fiyat) / giris_fiyat) if "Long" in row["Yon"] else ((giris_fiyat - anlik_kapatma_fiyati) / giris_fiyat)
            kismi_kar = kapatilacak_miktar * KALDIRAC * fark_yuzde
            
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
            return True, f"Kısmi kapama başarılı! Realize Edilen K/Z: {kismi_kar:,.2f} $"
        else:
            fark_yuzde = ((anlik_kapatma_fiyati - giris_fiyat) / giris_fiyat) if "Long" in row["Yon"] else ((giris_fiyat - anlik_kapatma_fiyati) / giris_fiyat)
            net_kar = mevcut_miktar * KALDIRAC * fark_yuzde

            durum_metni = "Kapandi (Zarar)" if net_kar < 0 else "Kapandi (Kar)"
            df.at[idx[0], "Durum"] = durum_metni
            df.at[idx[0], "Kapanis_Zamani"] = suan_tr
            df.at[idx[0], "Net_Kar_Zarar"] = float(round(net_kar, 2))
            df.at[idx[0], "Kapanis_Fiyati"] = float(round(anlik_kapatma_fiyati, 4))

            toplam_kasa, _, _, _, _ = bakiye_durumunu_getir()
            df.at[idx[0], "Guncel_Kasa"] = float(round(toplam_kasa + net_kar, 2))
            dataframe_guncelle_gsheets(df)
            kasa_islem_ekle_deftere(
                "Trade_Sonuc",
                float(round(net_kar, 2)),
                f"Trade K/Z: #{islem_id} {row['Coin']} ({durum_metni})",
            )
            elli_islem_arsiv_kontrol()
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
        if not ("kapandi" in durum_str or "kar" in durum_str or "zarar" in durum_str or "kısmi" in durum_str):
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
                    islem_kapatilacak, hedefe_ulasti, kapanis_fiyat_degeri = True, False, stop_f
                elif anl_f >= kar_al_f:
                    islem_kapatilacak, hedefe_ulasti, kapanis_fiyat_degeri = True, True, kar_al_f
            elif "Short" in yon:
                if anl_f >= stop_f:
                    islem_kapatilacak, hedefe_ulasti, kapanis_fiyat_degeri = True, False, stop_f
                elif anl_f <= kar_al_f:
                    islem_kapatilacak, hedefe_ulasti, kapanis_fiyat_degeri = True, True, kar_al_f

            if islem_kapatilacak:
                fark_yuzde = ((kapanis_fiyat_degeri - giris_fiyat) / giris_fiyat) if "Long" in yon else ((giris_fiyat - kapanis_fiyat_degeri) / giris_fiyat)
                net_kar = miktar * KALDIRAC * fark_yuzde
                durum_metni = "Kapandi (Kar)" if hedefe_ulasti else "Kapandi (Zarar)"

                df.at[idx, "Durum"] = durum_metni
                df.at[idx, "Kapanis_Zamani"] = suan_tr
                df.at[idx, "Net_Kar_Zarar"] = float(round(net_kar, 2))
                df.at[idx, "Kapanis_Fiyati"] = float(round(kapanis_fiyat_degeri, 4))

                toplam_kasa, _, _, _, _ = bakiye_durumunu_getir({} if ortak_fiyat_havuzu is None else ortak_fiyat_havuzu)
                df.at[idx, "Guncel_Kasa"] = float(round(toplam_kasa + net_kar, 2))

                islem_turu_etiket = "Hedef Kâr" if hedefe_ulasti else "Otomatik Stop"
                kasa_islem_ekle_deftere(
                    "Trade_Sonuc",
                    float(round(net_kar, 2)),
                    f"{islem_turu_etiket}: #{islem_id} {coin} ({'Kar' if hedefe_ulasti else 'Zarar'})",
                )
                
                hafiza = hafizayi_oku()
                islem_mail_anahtari = f"otomatik_kapanma_{islem_id}"
                
                if not hafiza.get(islem_mail_anahtari, False):
                    hafiza[islem_mail_anahtari] = True
                    hafizayi_kaydet(hafiza)

                    konu_mail = f"⚡ {islem_turu_etiket}: #{islem_id} {coin} ({durum_metni})"
                    icerik_mail = f"<h3>Otomatik İşlem Kapatıldı</h3><p><b>Coin:</b> {coin}</p><p><b>Yön:</b> {yon}</p><p><b>Sebep:</b> {islem_turu_etiket}</p><p><b>Net K/Z:</b> {net_kar:,.2f} $</p><p><b>Güncel Kasa:</b> {toplam_kasa + net_kar:,.2f} $</p>"
                    
                    basari, sonuc_mesaji = gmail_bildirim_gonder(konu_mail, icerik_mail)
                    print(f"Mail Bildirim Durumu (#{islem_id}): {sonuc_mesaji}")

                degisiklik_oldu = True

    if degisiklik_oldu:
        dataframe_guncelle_gsheets(df)
        elli_islem_arsiv_kontrol()

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
        konu = f"🔥🔥 Çok Güçlü Trend Sinyali (5. Aşama): {sembol} (Puan: {nihai_puan:.1f})"
        icerik = f"<h3>Çok Güçlü Trende Ulaşıldı!</h3><p><b>Sembol/Coin:</b> {sembol}</p><p><b>Matris Puanı:</b> {nihai_puan:.1f} / 100</p><p><b>Yön:</b> {aktif_yon}</p>"
        basari, sonuc_mesaji = gmail_bildirim_gonder(konu, icerik)
        print(f"Aşama 5 Mail Durumu ({sembol}): {sonuc_mesaji}")
    elif not asama_5_sart and hafiza[sembol]["asama_5_tetiklendi"]:
        hafiza[sembol]["asama_5_tetiklendi"] = False
        hafizayi_kaydet(hafiza)

    if asama_6_sart and not hafiza[sembol]["asama_6_tetiklendi"]:
        hafiza[sembol]["asama_6_tetiklendi"] = True
        hafizayi_kaydet(hafiza)
        konu = f"🔥🔥🔥 Zirve Sinyali (6. Aşama - Boğa/Ayı Vuruşu): {sembol} (Puan: {nihai_puan:.1f})"
        icerik = f"<h3>6. Aşama Zirveye Ulaşıldı!</h3><p><b>Sembol/Coin:</b> {sembol}</p><p><b>Matris Puanı:</b> {nihai_puan:.1f} / 100</p><p><b>Durum:</b> Boğa Vuruşu / Ayı Pençesi</p><p><b>Yön:</b> {aktif_yon}</p>"
        basari, sonuc_mesaji = gmail_bildirim_gonder(konu, icerik)
        print(f"Aşama 6 Mail Durumu ({sembol}): {sonuc_mesaji}")
    elif not asama_6_sart and hafiza[sembol]["asama_6_tetiklendi"]:
        hafiza[sembol]["asama_6_tetiklendi"] = False
        hafizayi_kaydet(hafiza)

def arka_plan_dinleyicisi():
    while True:
        try:
            tum_semboller = coinler + ["TOTAL"]
            anlik_fiyat_havuzu = {}
            for s in tum_semboller:
                anlik_fiyat_havuzu[s] = fiyat_cek_binance(s)
            for s in tum_semboller:
                _, puan, yon, _, _, _ = kurgusal_matris_hesapla(s)
                trend_metni, _, _, _ = trend_asamasini_ve_ikon_belirle(puan, yon)
                sinyal_ve_trend_mail_kontrolu(s, puan, yon, trend_metni, coin_mi=(s != "TOTAL"))
            otomatik_stop_kar_kontrolu(anlik_fiyat_havuzu)
        except Exception as e:
            print(f"Arka plan hata: {e}")
        time.sleep(60)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--check-only":
        print("GitHub Actions üzerinden tek seferlik piyasa ve mail kontrolü başlatılıyor...")
        try:
            tum_semboller = coinler + ["TOTAL"]
            anlik_fiyat_havuzu = {}
            for s in tum_semboller:
                anlik_fiyat_havuzu[s] = fiyat_cek_binance(s)
            for s in tum_semboller:
                _, puan, yon, _, _, _ = kurgusal_matris_hesapla(s)
                trend_metni, _, _, _ = trend_asamasini_ve_ikon_belirle(puan, yon)
                sinyal_ve_trend_mail_kontrolu(s, puan, yon, trend_metni, coin_mi=(s != "TOTAL"))
            otomatik_stop_kar_kontrolu(anlik_fiyat_havuzu)
            print("Kontroller başarıyla tamamlandı.")
        except Exception as e:
            print(f"Tek seferlik kontrol hatası: {e}")
        sys.exit(0)

@st.cache_resource
def botu_baslat_bir_kez():
    t = threading.Thread(target=arka_plan_dinleyicisi, daemon=True)
    t.start()
    return t

arka_plan_thread = botu_baslat_bir_kez()

st.title("Piyasa Genel Bakış")
min_esik_bilgi = aktif_min_puan_esigi_getir()
mod_bilgi_metni = "Hafta Sonu / Sığ Piyasa Modu (Min Eşik: 60)" if min_esik_bilgi == 60.0 else "Hafta İçi Normal Mod (Min Eşik: 55)"
st.caption(f"Oransal Matris Omurgası + EMA, RSI Mıknatısı & Fib Katkıları | ⚙️ **{mod_bilgi_metni}**")
elli_islem_arsiv_kontrol()

if "kasa_islem_acik" not in st.session_state:
    st.session_state["kasa_islem_acik"] = False
if "kasa_islem_turu" not in st.session_state:
    st.session_state["kasa_islem_turu"] = "Para Yatır"
if "sadece_aktifleri_goster" not in st.session_state:
    st.session_state["sadece_aktifleri_goster"] = False
if "kapama_paneli_acik" not in st.session_state:
    st.session_state["kapama_paneli_acik"] = False
if "islem_emri_kilit_acik" not in st.session_state:
    st.session_state["islem_emri_kilit_acik"] = False

tum_takip_edilenler = coinler + ["TOTAL"]
islenen_ham_veriler = []
ortak_fiyat_havuzu = {}

for sembol in tum_takip_edilenler:
    anlik_fiyat, nihai_puan, aktif_yon, l_puan, s_puan, zaman_katkilari = kurgusal_matris_hesapla(sembol)
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

otomatik_stop_kar_kontrolu(ortak_fiyat_havuzu)

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

    detay_matris_html = (
        f'<div style="text-align: center; line-height: 1.2;"><div style="font-size: 15px; margin-bottom: 2px; letter-spacing: 1px;">{"🟢" * yesil_led_sayisi}{"🔴" * kirmizi_led_sayisi}</div><div style="font-size: 11px; font-weight: 600;"><span style="color: #00FF00; display: inline-block; width: 10px; height: 10px; background-color: #00FF00; border-radius: 50%; margin-right: 2px;"></span>%{y_yuzde:.1f} | <span style="color: rgb(255, 75, 0); display: inline-block; width: 10px; height: 10px; background-color: rgb(255, 75, 0); border-radius: 50%; margin-left: 4px; margin-right: 2px;"></span>%{k_yuzde:.1f}</div></div>'
    )

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

    yon_renk = "#00FF00" if aktif_yon == "Long" else "rgb(255, 75, 0)"
    puan_html = f'<div style="font-weight: bold; color: {"#00FF00" if not is_notr and aktif_yon == "Long" else ("rgb(255, 75, 0)" if not is_notr and aktif_yon == "Short" else "#e8eef8")};">{nihai_puan:.1f} / 100<br><span style="font-size: 10px; color: {yon_renk};">(Nötr)</span></div>'

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
    kapananlar_mask = df_metrik_trade["Durum"].astype(str).str.contains("Kapandi|Kar|Zarar|Kismi", case=False, na=False)
    realize_kar = pd.to_numeric(df_metrik_trade[kapananlar_mask]["Net_Kar_Zarar"], errors="coerce").fillna(0.0).sum()

aktif_oran = (aktif_yatirim_tutari / toplam_kasa * 100) if toplam_kasa > 0 else 0.0
bostaki_oran = (mevcut_bakiye / toplam_kasa * 100) if toplam_kasa > 0 else 0.0
aktif_kar_oran = (toplam_acik_kz / aktif_yatirim_tutari * 100) if aktif_yatirim_tutari > 0 else 0.0
realize_kar_oran = (realize_kar / BASLANGIC_BAKIYE * 100)
ef_kasa_oran = (toplam_acik_kz / toplam_kasa * 100) if toplam_kasa > 0 else 0.0
toplam_kasa_oran = ((toplam_kasa - BASLANGIC_BAKIYE) / BASLANGIC_BAKIYE * 100)

def format_yuzde(val, is_change=False):
    if is_change:
        return f"+%{val:.1f}" if val > 0 else f"-%{abs(val):.1f}" if val < 0 else "%0.0"
    return f"%{val:.1f}"

aktif_renk = "#00FF00" if toplam_acik_kz >= 0 else "rgb(255, 75, 0)"
with col_ust1:
    st.markdown(f"""<div class="metric-container"><div style="margin:0; font-size:13px; font-weight:bold; color:#91a0b8;">📊 Aktif Yatırım</div><div style="display:flex; align-items:baseline; gap:6px; margin:5px 0 0 0;"><div style="color:{aktif_renk}; font-size:22px; font-weight:800;">{aktif_yatirim_tutari:,.2f} $</div><div style="color:#ffffff; font-size:13px; font-weight:700;">{format_yuzde(aktif_oran)}</div></div></div>""", unsafe_allow_html=True)

with col_ust2:
    st.markdown(f"""<div class="metric-container"><div style="margin:0; font-size:13px; font-weight:bold; color:#91a0b8;">🔥 Aktif Kâr</div><div style="display:flex; align-items:baseline; gap:6px; margin:5px 0 0 0;"><div style="color:{aktif_renk}; font-size:22px; font-weight:800;">{toplam_acik_kz:+,.2f} $</div><div style="color:#ffffff; font-size:13px; font-weight:700;">{format_yuzde(aktif_kar_oran, True)}</div></div></div>""", unsafe_allow_html=True)

with col_ust3:
    st.markdown(f"""<div class="metric-container"><div style="margin:0; font-size:13px; font-weight:bold; color:#91a0b8;">🟢 Boştaki Nakit</div><div style="display:flex; align-items:baseline; gap:6px; margin:5px 0 0 0;"><div style="color:#e8eef8; font-size:22px; font-weight:800;">{mevcut_bakiye:,.2f} $</div><div style="color:#ffffff; font-size:13px; font-weight:700;">{format_yuzde(bostaki_oran)}</div></div></div>""", unsafe_allow_html=True)

realize_kar_renk = "#00FF00" if realize_kar >= 0 else "rgb(255, 75, 0)"
with col_ust4:
    st.markdown(f"""<div class="metric-container"><div style="margin:0; font-size:13px; font-weight:bold; color:#91a0b8;">⚡ Net Kâr (Realize)</div><div style="display:flex; align-items:baseline; gap:6px; margin:5px 0 0 0;"><div style="color:{realize_kar_renk}; font-size:22px; font-weight:800;">{realize_kar:+,.2f} $</div><div style="color:#ffffff; font-size:13px; font-weight:700;">{format_yuzde(realize_kar_oran, True)}</div></div></div>""", unsafe_allow_html=True)

efektif_renk = "#00FF00" if efektif_kasa >= toplam_kasa else "rgb(255, 75, 0)"
with col_ust5:
    st.markdown(f"""<div class="metric-container"><div style="margin:0; font-size:13px; font-weight:bold; color:#91a0b8;">💎 Efektif Kasa</div><div style="display:flex; align-items:baseline; gap:6px; margin:5px 0 0 0;"><div style="color:{efektif_renk}; font-size:22px; font-weight:800;">{efektif_kasa:,.2f} $</div><div style="color:#ffffff; font-size:13px; font-weight:700;">{format_yuzde(ef_kasa_oran, True)}</div></div></div>""", unsafe_allow_html=True)

toplam_kasa_renk = "#00FF00" if toplam_kasa >= BASLANGIC_BAKIYE else "rgb(255, 75, 0)"
with col_ust6:
    st.markdown(f"""<div class="metric-container"><div style="margin:0; font-size:13px; font-weight:bold; color:#91a0b8;">💼 Toplam Kasa</div><div style="display:flex; align-items:baseline; gap:6px; margin:5px 0 0 0;"><div style="color:{toplam_kasa_renk}; font-size:22px; font-weight:800;">{toplam_kasa:,.2f} $</div><div style="color:#ffffff; font-size:13px; font-weight:700;">{format_yuzde(toplam_kasa_oran, True)}</div></div></div>""", unsafe_allow_html=True)

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
    if st.button("🏦 Kasa İşlemleri", use_container_width=True, key="ana_kasa_butonu"):
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
            if st.button("💵 Ekle", use_container_width=True, key="btn_mod_ekle"):
                st.session_state["kasa_islem_turu"] = "Para Yatır"
                st.rerun()
        with h_btn_col2:
            if st.button("🏦 Çek", use_container_width=True, key="btn_mod_cek"):
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
        if st.button("💾 Onayla", use_container_width=True, key="kasa_onayla"):
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
        if st.button("✖ Kapat", use_container_width=True, key="kasa_kapat"):
            st.session_state["kasa_islem_acik"] = False
            st.rerun()

st.markdown("---")

table_html = """<table class="custom-table"><thead class="custom-table-header"><tr><th>Logo</th><th>Coin<br>Adı</th><th>Güncel<br>Fiyat</th><th>Trend<br>Durumu</th><th>Matris Teyit</th><th>Piyasa &<br>Dominans</th><th>Matris<br>Puanı</th><th>Günlük<br>Değişim</th><th>Önerilen<br>Oran</th><th>Yatırım<br>Tutarı</th><th>Kar Al<br>Hedefi</th><th>Stop<br>Seviyesi</th><th>Risk / Hedef</th></tr></thead><tbody>"""
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

    table_html += f"<tr><td>{v['Logo']}</td><td>{v['Coin']}</td><td style='font-weight: bold; color: #5b8cff; background-color: rgba(91, 140, 255, 0.08);'>{fiyat_str}</td><td>{v['Yon']}</td><td>{v['Teyit_Sunumu']}</td><td>{v['Dom_Sunumu']}</td><td style='background-color: rgba(0,0,0,0.02);'>{v['Matris_Puan_Sunumu']}</td><td>{v['Gunluk_Oran']}</td><td>{oran_html}</td><td>{v['Yatırım_Bedeli']}</td><td>{kar_al_str}</td><td>{stopla_str}</td><td style='font-weight: bold; color: #ff79c6;'>{risk_hedef_gosterim}</td></tr>"
table_html += "</tbody></table>"
st.markdown(f'<div class="table-container">{table_html}</div>', unsafe_allow_html=True)

col_sol_panel, col_orta_grafik, col_sag_endeks = st.columns([1.2, 2.5, 1.0])

with col_sol_panel:
    st.markdown("<h3>🚀 İşlem Emri Ver</h3>", unsafe_allow_html=True)
    df_gosterge = pd.DataFrame(islenen_veriler)
    df_gecmis_temp = islem_gecmisi_getir(sheet_guncelle=False)
    acik_coinler = []
    if not df_gecmis_temp.empty and "Durum" in df_gecmis_temp.columns:
        acik_mask = ~df_gecmis_temp["Durum"].astype(str).str.contains("kapandi|kar|zarar|kısmi", case=False, na=False)
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
        acik_mask = ~df_gecmis_temp["Durum"].astype(str).str.contains("kapandi|kar|zarar|kısmi", case=False, na=False)
        if secilen_coin and secilen_coin in df_gecmis_temp[acik_mask]["Coin"].values:
            acik_pozisyon_var = True

    onerilen_tutar_hesap = round(mevcut_bakiye * (onerilen_oran_val / 100.0), 2)

    if acik_pozisyon_var:
        st.markdown("""<div style="background:linear-gradient(145deg,#1f2b3e,#162234); color:#e8eef8; border:1px solid #3b82f6; padding:12px; border-radius:10px; margin-bottom:12px; font-size:13px; line-height:1.8;"><div style="font-weight:750; color:#60a5fa; margin-bottom:4px;">🔄 Açık Pozisyona Ekleme Modu</div><div style="color:#dce6f5;">Bu coin için açık bir pozisyonunuz var. Girilen tutar ağırlıklı ortalama ile maliyete eklenecektir.</div></div>""", unsafe_allow_html=True)
    elif secilen_coin:
        st.markdown(f"""<div style="background:linear-gradient(145deg,#17263b,#111b2b); color:#e8eef8; border:1px solid #30415b; padding:12px; border-radius:10px; margin-bottom:12px; font-size:13px; line-height:1.8;"><div style="font-weight:750; color:#ffd166; margin-bottom:4px;">💡 Matris Önerisi (Oransal & Akışkan)</div><div style="color:#dce6f5;">Önerilen oran: <b style="color:#ffffff;">%{onerilen_oran_val:.1f}</b></div><div style="color:#dce6f5;">Önerilen tutar: <b style="color:#ffffff;">{onerilen_tutar_hesap:,.2f} $</b></div></div>""", unsafe_allow_html=True)

    st.markdown('<div style="height: 5px;"></div>', unsafe_allow_html=True)

    if not st.session_state.get("islem_emri_kilit_acik", False):
        if st.button("🔓 İşlem Açma Kilidini Aç", use_container_width=True, key="btn_islem_kilidi_ac"):
            if coin_listesi:
                st.session_state["islem_emri_kilit_acik"] = True
                st.rerun()
            else:
                st.warning("Uygun işlem yapılacak coin bulunmuyor!")
    else:
        with st.form(key="manuel_islem_formu"):
            hesaplanan_tutar = min(100.0, float(mevcut_bakiye)) if acik_pozisyon_var else float(onerilen_tutar_hesap)
            guvenli_tutar = max(0.0, float(hesaplanan_tutar))
            max_tutar = max(float(guvenli_tutar), float(mevcut_bakiye)) if mevcut_bakiye > 0 else 999999.0

            manuel_girilen_tutar = st.number_input("Tutar ($ Giriniz):", min_value=0.0, max_value=float(max_tutar), value=float(guvenli_tutar), step=10.0)
            st.markdown(f'<div style="font-size: 14px; font-weight: 800; color: #00FF00; padding: 5px 0 10px 0;">Boştaki Nakit: {mevcut_bakiye:,.2f} $</div>', unsafe_allow_html=True)
            
            col_islem_yap, col_kapat_kilit = st.columns(2)
            with col_islem_yap:
                submit_islem = st.form_submit_button("🔄 Ekleme Yap" if acik_pozisyon_var else "🚀 İşlemi Başlat", use_container_width=True)
            with col_kapat_kilit:
                kapat_kilit_tik = st.form_submit_button("🔒 Kilidi Kapat", use_container_width=True)
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
            0.0: min_f, 0.236: min_f + 0.236 * fiyat_fark, 0.382: min_f + 0.382 * fiyat_fark,
            0.5: min_f + 0.5 * fiyat_fark, 0.618: min_f + 0.618 * fiyat_fark,
            0.786: min_f + 0.786 * fiyat_fark, 1.0: max_f,
        }

        min_zaman, max_zaman_grafik = t_df["timestamp"].min(), t_df["timestamp"].max() + pd.Timedelta(hours=1)
        alt_sinir, ust_sinir = min_f - (fiyat_fark * 0.05), max_f + (fiyat_fark * 0.05)

        fig_total = make_subplots(specs=[[{"secondary_y": True}]])
        for b_alt, b_ust, renk in [
            (0.0, 0.236, "rgba(180, 20, 50, 0.35)"), (0.236, 0.382, "rgba(220, 90, 0, 0.32)"),
            (0.382, 0.5, "rgba(255, 200, 0, 0.35)"), (0.5, 0.618, "rgba(255, 200, 0, 0.35)"),
            (0.618, 0.786, "rgba(40, 180, 80, 0.32)"), (0.786, 1.0, "rgba(0, 200, 90, 0.38)"),
        ]:
            x_coords = list(t_df["timestamp"]) + [max_zaman_grafik, max_zaman_grafik] + list(t_df["timestamp"][::-1])
            y_coords = [fib_levels[b_ust]] * len(t_df) + [fib_levels[b_ust], fib_levels[b_alt]] + [fib_levels[b_alt]] * len(t_df)
            fig_total.add_trace(go.Scatter(x=x_coords, y=y_coords, fill="toself", fillcolor=renk, line=dict(color="rgba(255,255,255,0)"), showlegend=False, hoverinfo="skip"), secondary_y=False)

        fig_total.add_trace(go.Scatter(x=t_df["timestamp"], y=t_df["Close"], mode="lines", name="Total Market", line=dict(color="#5b8cff", width=2.5)), secondary_y=False)
        fig_total.add_trace(go.Scatter(x=t_df["timestamp"], y=t_df["RSI_Norm"], mode="lines", name="RSI (0-1)", line=dict(color="#FF9900", width=1.5, dash="solid")), secondary_y=False)

        for oran, val in fib_levels.items():
            fig_total.add_hline(y=val, line_dash="dash", line_color="#CCCC00" if oran == 0.5 else ("#006400" if oran > 0.5 else "#800020"), line_width=1)

        fig_total.update_layout(
            template="plotly_dark", margin=dict(t=15, b=25, l=10, r=0), height=340,
            xaxis=dict(range=[min_zaman, max_zaman_grafik], dtick=3600000, tickformat="%H:%M", tickangle=25, gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(showticklabels=False, range=[alt_sinir, ust_sinir], gridcolor="rgba(255,255,255,0.05)"),
            xaxis_rangeslider_visible=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#e8eef8")),
        )
        st.plotly_chart(fig_total, use_container_width=True)

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
acik_islem_listesi = df_gecmis[~df_gecmis["Durum"].astype(str).str.contains("kapandi|kar|zarar|kısmi", case=False, na=False)]["Islem_ID"].tolist() if not df_gecmis.empty and "Durum" in df_gecmis.columns else []

col_sol_analiz, col_orta_durum, col_sag_sonlandir = st.columns([2.5, 1, 1], gap="medium")

with col_sol_analiz:
    st.markdown("<h3>📊 Kapanan İşlemler & Para Akışı Analizi</h3>", unsafe_allow_html=True)
    kapananlar_df = pd.DataFrame() if df_gecmis.empty or "Durum" not in df_gecmis.columns else df_gecmis[df_gecmis["Durum"].astype(str).str.contains("Kapandi|Kar|Zarar|Kismi", case=False, na=False)]

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
            st.plotly_chart(fig, use_container_width=True, config={"responsive": True, "displayModeBar": False})

        with sub_p2:
            st.markdown(f"""<div style="font-size: 15px; font-weight: bold; color: #e8eef8; margin-bottom: 4px;">📈 Strateji Metrikleri</div><p style="margin: 4px 0px 0px 0px; font-size: 13px; color: #91a0b8;">Toplam Kapanan</p><p style="margin: 0px; font-size: 18px; font-weight: bold; color: #e8eef8;">{toplam_kapanan} Adet</p><p style="margin: 8px 0px 0px 0px; font-size: 14px; color: #00FF00; font-weight: bold;">🟢 Kârlı: {karli_sayisi} (%{kar_yuzde:.1f})</p><p style="margin: 5px 0px 0px 0px; font-size: 14px; color: rgb(255, 75, 0); font-weight: bold;">🔴 Zararlı: {zararli_sayisi} (%{zarar_yuzde:.1f})</p>""", unsafe_allow_html=True)

        with sub_p3:
            net_renk = "#00FF00" if net_fark_dolar >= 0 else "rgb(255, 75, 0)"
            st.markdown(f"""<div style="display: flex; flex-direction: column; justify-content: center; height: 100%; padding-top: 15px;"><div style="font-size: 14px; font-weight: bold; color: #00FF00; margin-bottom: 8px;">Toplam Kâr: +{toplam_kazanc_dolar:,.2f} $</div><div style="font-size: 14px; font-weight: bold; color: rgb(255, 75, 0); margin-bottom: 8px;">Toplam Zarar: -{toplam_kayip_dolar:,.2f} $</div><div style="font-size: 15px; font-weight: bold; color: {net_renk}; margin-top: 4px; border-top: 1px solid #30415b; padding-top: 8px;">Net Fark: {net_fark_dolar:+,.2f} $</div></div>""", unsafe_allow_html=True)
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
    st.info("ℹ️ Sadece Aktifler." if st.session_state["sadece_aktifleri_goster"] else "ℹ️ Tüm işlemler.")

with col_sag_sonlandir:
    st.markdown("<h3>🛑 İşlemi Kapat</h3>", unsafe_allow_html=True)
    st.markdown('<div style="height: 10px;"></div>', unsafe_allow_html=True)
    
    def paneli_kilitle():
        st.session_state["kapama_paneli_acik"] = False

    kapatilacak_id = st.selectbox("ID Kodu:", acik_islem_listesi if acik_islem_listesi else [0], key="k_id_secim_en_yeni_kilitli", on_change=paneli_kilitle)
    st.markdown('<div style="height: 5px;"></div>', unsafe_allow_html=True)
    
    if not st.session_state.get("kapama_paneli_acik", False):
        if st.button("🔒 İşlem Kapatma Kilidini Aç", use_container_width=True, key="btn_kilit_ac_yeni"):
            if acik_islem_listesi and kapatilacak_id in acik_islem_listesi:
                st.session_state["kapama_paneli_acik"] = True
                st.rerun()
            else:
                st.warning("Seçilen ID'ye ait açık işlem bulunmuyor!")
    else:
        secilen_islem_miktar, secilen_coin = 100.0, "BTC/USDT"
        if acik_islem_listesi and kapatilacak_id in acik_islem_listesi:
            secilen_islem_satir = df_gecmis[df_gecmis["Islem_ID"] == kapatilacak_id]
            if not secilen_islem_satir.empty:
                secilen_islem_miktar = float(secilen_islem_satir["Islem_Miktari"].iloc[0])
                secilen_coin = str(secilen_islem_satir["Coin"].iloc[0])

        st.markdown(f"""<div style="background:linear-gradient(145deg,#2b1111,#1a0b0b); color:#e8eef8; border:1px solid #5b3030; padding:10px; border-radius:8px; margin-bottom:10px; font-size:12px;"><b>{secilen_coin}</b> (#{kapatilacak_id}) Pozisyonu:<br>Yatırım: <b style="color:#ff6b6b;">{secilen_islem_miktar:,.2f} $</b></div>""", unsafe_allow_html=True)

        girilen_tutar = st.number_input("Kapatılacak Tutar ($):", min_value=0.0, max_value=float(secilen_islem_miktar), value=float(secilen_islem_miktar), step=10.0, key="input_tek_tutar_en_yeni")

        col_islem_yap, col_iptal = st.columns(2)
        with col_islem_yap:
            if st.button("🛑 Emri Al", use_container_width=True, key="btn_emri_al_en_yeni"):
                if girilen_tutar <= 0:
                    st.error("Kapatılacak miktar 0'dan büyük olmalıdır!")
                else:
                    hedef_miktar = None if girilen_tutar >= secilen_islem_miktar else girilen_tutar
                    b_durum, b_mesaj = manuel_islem_kapat(kapatilacak_id, ortak_fiyat_havuzu.get(secilen_coin, baz_fiyatlar.get(secilen_coin, 100.0)), kapatilacak_miktar=hedef_miktar)
                    if b_durum:
                        st.session_state["kapama_paneli_acik"] = False
                        st.success(b_mesaj)
                        time.sleep(1.2)
                        st.rerun()
                    else:
                        st.error(b_mesaj)
        with col_iptal:
            if st.button("İptal", use_container_width=True, key="btn_iptal_en_yeni"):
                st.session_state["kapama_paneli_acik"] = False
                st.rerun()

st.markdown("---")

df_gecmisile_goster = islem_gecmisi_getir(sheet_guncelle=False)
df_gosterilecek = pd.DataFrame()
if not df_gecmisile_goster.empty:
    df_gosterilecek = df_gecmisile_goster[~df_gecmisile_goster["Durum"].astype(str).str.contains("kapandi|kar|zarar|kısmi", case=False, na=False)] if st.session_state["sadece_aktifleri_goster"] else df_gecmisile_goster.copy()

anlik_fiyat_sozluk, anlik_kz_sozluk, hedef_kar_sozluk, olasi_stop_sozluk = {}, {}, {}, {}
if not df_gecmisile_goster.empty:
    for _, row in df_gecmisile_goster.iterrows():
        islem_id, coin, giris_fiyat, miktar, kar_al_f, stop_f, yon = (
            row["Islem_ID"], row["Coin"], float(row["Giris_Fiyat"]),
            float(row["Islem_Miktari"]), float(row["Kar_Al"]), float(row["Stop"]), row["Yon"]
        )
        anl_f = ortak_fiyat_havuzu.get(coin, baz_fiyatlar.get(coin, 100.0))
        anlik_fiyat_sozluk[islem_id] = anl_f
        hedef_kar_sozluk[islem_id] = float(row["Beklenen_Kar"])
        olasi_stop_sozluk[islem_id] = float(row["Olasi_Stop"])

        if not ("kapandi" in str(row["Durum"]).lower() or "kar" in str(row["Durum"]).lower() or "zarar" in str(row["Durum"]).lower() or "kısmi" in str(row["Durum"]).lower()):
            anlik_kz_sozluk[islem_id] = round(miktar * KALDIRAC * (((anl_f - giris_fiyat) / giris_fiyat) if "Long" in yon else ((giris_fiyat - anl_f) / giris_fiyat)), 2)
        else:
            anlik_kz_sozluk[islem_id] = float(row["Net_Kar_Zarar"])

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
st.markdown(f'<div class="table-container">{portfoy_html}</div>', unsafe_allow_html=True)

st.markdown("---")
st.markdown("<h3>📁 50'şerli İşlem Arşivleri (Analiz Klasörü)</h3>", unsafe_allow_html=True)
if os.path.exists(ARSIV_KLASORU):
    try:
        arsiv_dosyalari = sorted(os.listdir(ARSIV_KLASORU))
        if secilen_arsiv := (st.selectbox("Geçmiş 50'li Blok Dönemini Seçin:", arsiv_dosyalari, key="arsiv_select_50") if arsiv_dosyalari else None):
            st.write(pd.read_csv(os.path.join(ARSIV_KLASORU, secilen_arsiv), delimiter=";").to_html(escape=False, index=False), unsafe_allow_html=True)
    except:
        pass
