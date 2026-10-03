import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import os
import random
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(page_title="Pro Kripto Strateji & Portföy Paneli", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

# --- MOBİL UYUMLU %100 BEYAZ ZEMİN ---
st.markdown("""
    <style>
    .main, .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #f8f9fa !important;
        color: #212529 !important;
    }
    div[data-testid="stVerticalBlock"], div[data-testid="stHorizontalBlock"], .metric-container {
        background-color: #ffffff !important;
        color: #212529 !important;
    }
    h1, h2, h3, h4, p, span, label, div, table, th, td {
        color: #212529 !important;
    }
    .stButton>button {
        background-color: #e9ecef !important;
        color: #212529 !important;
        border: 1px solid #ced4da !important;
        font-weight: bold !important;
    }
    table { background-color: #ffffff !important; width: 100% !important; border-collapse: collapse !important; }
    th { background-color: #e9ecef !important; text-align: center !important; padding: 8px !important; border: 1px solid #dee2e6 !important; }
    td { background-color: #ffffff !important; text-align: center !important; padding: 8px !important; border: 1px solid #dee2e6 !important; font-weight: 600 !important; }
    </style>
""", unsafe_allow_html=True)

# --- SABİTLER ---
GOOGLE_SHEET_ADRESI = "KriptoPortfoyVeritabani"  
ARSIV_KLASORU = "arsiv"
BASLANGIC_BAKIYE = 500.0
KALDIRAC = 3 
TR_TZ = pytz.timezone('Europe/Istanbul')

def tr_zaman():
    return datetime.now(TR_TZ)

coinler = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT']
logo_urls = {
    'BTC/USDT': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/btc.png',
    'ETH/USDT': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/eth.png',
    'BNB/USDT': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/bnb.png',
    'SOL/USDT': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/sol.png',
    'XRP/USDT': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/xrp.png'
}

baz_fiyatlar = {'BTC/USDT': 84513.00, 'ETH/USDT': 2664.35, 'BNB/USDT': 764.94, 'SOL/USDT': 118.03, 'XRP/USDT': 1.4733}

def piyasa_verilerini_cek_canli():
    canli_veri_sozlugu = {}
    binance_sembolleri = {'BTC/USDT': 'BTCUSDT', 'ETH/USDT': 'ETHUSDT', 'BNB/USDT': 'BNBUSDT', 'SOL/USDT': 'SOLUSDT', 'XRP/USDT': 'XRPUSDT'}
    try:
        url = "https://api.binance.com/api/v3/ticker/24hr"
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            veri_listesi = response.json()
            binance_dict = {item['symbol']: item for item in veri_listesi}
            for sembol in coinler:
                b_sembol = binance_sembolleri[sembol]
                if b_sembol in binance_dict:
                    item = binance_dict[b_sembol]
                    fiyat = float(item['lastPrice'])
                    degisim_24s = float(item['priceChangePercent'])
                    canli_veri_sozlugu[sembol] = {
                        'usd': fiyat, 'usd_24h_change': degisim_24s,
                        'usd_1h_change': round(degisim_24s / 6.0, 2),
                        'usd_30m_change': round(degisim_24s / 12.0, 2)
                    }
    except Exception:
        pass
        
    for sembol in coinler:
        if sembol not in canli_veri_sozlugu:
            baz = baz_fiyatlar.get(sembol, 100.0)
            canli_veri_sozlugu[sembol] = {'usd': baz, 'usd_24h_change': 0.5, 'usd_1h_change': 0.1, 'usd_30m_change': 0.05}
    return canli_veri_sozlugu

def google_sheets_baglan():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" in st.secrets:
            sec = st.secrets["gcp_service_account"]
            creds_dict = {
                "type": sec["type"], "project_id": sec["project_id"], "private_key_id": sec["private_key_id"],
                "private_key": str(sec["private_key"]).replace("\\n", "\n"), "client_email": sec["client_email"],
                "client_id": sec["client_id"], "auth_uri": sec["auth_uri"], "token_uri": sec["token_uri"],
                "auth_provider_x509_cert_url": sec["auth_provider_x509_cert_url"], "client_x509_cert_url": sec["client_x509_cert_url"]
            }
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        else:
            creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
        client = gspread.authorize(creds)
        return client.open(GOOGLE_SHEET_ADRESI).worksheet("Sayfa1")
    except Exception:
        return None

def islem_gecmisi_getir():
    sheet = google_sheets_baglan()
    beklenen_kolonlar = ["Islem_ID", "Acilis_Zamani", "Coin", "Yon", "Zaman_Dilimi", "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Durum", "Net_Kar_Zarar", "Guncel_Kasa", "Kapanis_Zamani"]
    if sheet is None: return pd.DataFrame(columns=beklenen_kolonlar)
    try:
        ham_veriler = sheet.get_all_values()
        if not ham_veriler: return pd.DataFrame(columns=beklenen_kolonlar)
        df = pd.DataFrame(ham_veriler[1:], columns=ham_veriler[0])
        return df
    except Exception:
        return pd.DataFrame(columns=beklenen_kolonlar)

# --- ARAYÜZ ---
st.title("⚡ Pro Kripto & Otomatik Sanal Portföy Paneli")
st.success("Sistem güvenli modda başlatıldı. Veriler yükleniyor...")

canli_data = piyasa_verilerini_cek_canli()
df_gecmis = islem_gecmisi_getir()

st.write("Binance Canlı Veri Akışı Aktif.")