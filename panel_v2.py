import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime
import pytz
import os
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import time
from streamlit_autorefresh import st_autorefresh

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(page_title="Pro Kripto Canlı Akış ve Mikro Matris Paneli", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

# --- OTOMATİK YENİLEME (60 SANİYE) ---
st_autorefresh(interval=60000, key="kripto_panel_otomatik_yenileme")

# --- CSS STİLLERİ ---
st.markdown("""
    <style>
    .main, .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #f8f9fa !important;
        color: #212529 !important;
    }
    div[data-testid="stVerticalBlock"], div[data-testid="stHorizontalBlock"], .para-blogu {
        background-color: #ffffff !important;
        color: #212529 !important;
    }
    
    .metric-container {
        background-color: #e9ecef !important;
        border: 1px solid #ced4da !important;
        padding: 15px !important;
        border-radius: 8px !important;
    }

    h1, h2, h3, h4, h5, h6, p, span, label, div, table, th, td {
        color: #212529 !important;
    }
    
    .stButton > button {
        background-color: #e9ecef !important;
        color: #212529 !important;
        border: 1px solid #ced4da !important;
        font-weight: bold !important;
    }
    .stButton > button:hover {
        background-color: #0d6efd !important;
        color: #ffffff !important;
    }

    .custom-table { width: 100%; border-collapse: collapse; background-color: #ffffff; margin-bottom: 20px; }
    .custom-table th { background-color: #e9ecef; text-align: center; padding: 6px 4px; border: 1px solid #dee2e6; font-weight: bold; color: #212529; font-size: 13px; line-height: 1.2; }
    .custom-table td { background-color: #ffffff; text-align: center; padding: 6px 4px; border: 1px solid #dee2e6; font-weight: 600; vertical-align: middle; color: #212529; white-space: nowrap; font-size: 13px; }
    .custom-table td img { width: 22px; height: 22px; object-fit: contain; }
    </style>
""", unsafe_allow_html=True)

# --- SABİTLER ---
GOOGLE_SHEET_DOSYA = "KriptoPortfoyVeritabani" 
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
baz_fiyatlar = {'BTC/USDT': 84805.0, 'ETH/USDT': 2690.0, 'BNB/USDT': 786.2, 'SOL/USDT': 119.9, 'XRP/USDT': 1.489}

def fiyat_cek_coinbase(coin_symbol):
    cb_map = {'BTC/USDT': 'BTC-USD', 'ETH/USDT': 'ETH-USD', 'BNB/USDT': 'BNB-USD', 'SOL/USDT': 'SOL-USD', 'XRP/USDT': 'XRP-USD'}
    cb_sym = cb_map.get(coin_symbol, 'BTC-USD')
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    try:
        url = f"https://api.coinbase.com/v2/prices/{cb_sym}/spot"
        resp = requests.get(url, headers=headers, timeout=15.0)
        if resp.status_code == 200:
            val = float(resp.json().get('data', {}).get('amount', 0))
            if val > 0: return val
    except: pass
    return baz_fiyatlar.get(coin_symbol, 100.0)

@st.cache_data(ttl=300)
def load_1200_bar_market_data(coin_symbol: str):
    cb_map = {'BTC/USDT': 'BTC-USD', 'ETH/USDT': 'ETH-USD', 'BNB/USDT': 'BNB-USD', 'SOL/USDT': 'SOL-USD', 'XRP/USDT': 'XRP-USD'}
    cb_sym = cb_map.get(coin_symbol, 'BTC-USD')
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    try:
        url = f"https://api.exchange.coinbase.com/products/{cb_sym}/candles?granularity=60"
        r = requests.get(url, headers=headers, timeout=15.0)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data, columns=['timestamp', 'Low', 'High', 'Open', 'Close', 'Volume'])
                for col in ['Open', 'High', 'Low', 'Close']:
                    df[col] = df[col].astype(float)
                return df.sort_values('timestamp').reset_index(drop=True)
    except: pass
    
    limit = 1200
    dates = pd.date_range(end=datetime.now(), periods=limit, freq='1min')
    base_price = baz_fiyatlar.get(coin_symbol, 100.0)
    vol_f = base_price * 0.001
    np.random.seed(hash(coin_symbol) % 2**32)
    close_prices = base_price + np.random.normal(0, vol_f, limit).cumsum() / 10
    high_prices = close_prices + np.abs(np.random.normal(0, vol_f/2, limit))
    low_prices = close_prices - np.abs(np.random.normal(0, vol_f/2, limit))
    return pd.DataFrame({'timestamp': dates, 'Close': close_prices, 'High': high_prices, 'Low': low_prices})

def calculate_coin_atr_metrics(df, skor):
    s_sinirli = max(50.0, min(200.0, abs(skor)))
    t = (s_sinirli - 50.0) / 150.0
    hedef_carpan = round(2.0 + 2.0 * (t ** 1.6), 1)

    if df is None or df.empty or 'Close' not in df.columns:
        return 1.0, hedef_carpan

    df['H-L'] = df['High'] - df['Low']
    df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
    df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    
    atr_val = df['TR'].rolling(window=14).mean().iloc[-1]
    current_price = df['Close'].iloc[-1]
    vol_percentage = (atr_val / current_price) * 100 if current_price > 0 else 1.0
    stop_pct = max(0.5, round(vol_percentage * 1.5, 1))
    return stop_pct, hedef_carpan

def resample_ve_analiz_et(df_1m, period_dakika, toplam_bar_sayisi, hedef_onay_sayisi):
    if df_1m is None or df_1m.empty:
        return 0, 0, "Nötr"
        
    df = df_1m.copy()
    if 'timestamp' in df.columns:
        df['dt'] = pd.to_datetime(df['timestamp'], unit='s', errors='coerce')
        df = df.set_index('dt')
    
    rule_str = f"{period_dakika}min"
    try:
        df_resampled = df.resample(rule_str).agg({
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
        }).dropna()
    except:
        df_resampled = df.tail(toplam_bar_sayisi * period_dakika)

    aktif_borsa_barlari = df_resampled.tail(toplam_bar_sayisi)
    yesil, kirmizi = 0, 0
    for _, bar in aktif_borsa_barlari.iterrows():
        o, c = float(bar['Open']), float(bar['Close'])
        if c > o: yesil += 1
        elif c < o: kirmizi += 1
        
    toplam_incelenen = yesil + kirmizi
    if toplam_incelenen == 0: return 0, 0, "Nötr"
        
    if yesil >= hedef_onay_sayisi: return yesil, kirmizi, "Long"
    elif kirmizi >= hedef_onay_sayisi: return yesil, kirmizi, "Short"
    else: return yesil, kirmizi, "Nötr"

def yeni_matris_hesapla(coin_symbol, guvenilirlik_modu="100"):
    anlik_fiyat = fiyat_cek_coinbase(coin_symbol)
    df_1m = load_1200_bar_market_data(coin_symbol)
    
    if guvenilirlik_modu == "100":
        p_16h = resample_ve_analiz_et(df_1m, period_dakika=4, toplam_bar_sayisi=240, hedef_onay_sayisi=192)
        p_8h  = resample_ve_analiz_et(df_1m, period_dakika=2, toplam_bar_sayisi=240, hedef_onay_sayisi=192)
        p_4h  = resample_ve_analiz_et(df_1m, period_dakika=1, toplam_bar_sayisi=240, hedef_onay_sayisi=192)
        p_2h  = resample_ve_analiz_et(df_1m, period_dakika=1, toplam_bar_sayisi=120, hedef_onay_sayisi=96)
        p_1h  = resample_ve_analiz_et(df_1m, period_dakika=1, toplam_bar_sayisi=60,  hedef_onay_sayisi=48)
        
        puan_16 = 80.0 if p_16h[2] == "Long" else (-80.0 if p_16h[2] == "Short" else 0.0)
        puan_8  = 60.0 if p_8h[2] == "Long"  else (-60.0 if p_8h[2] == "Short"  else 0.0)
        puan_4  = 30.0 if p_4h[2] == "Long"  else (-30.0 if p_4h[2] == "Short"  else 0.0)
        puan_2  = 20.0 if p_2h[2] == "Long"  else (-20.0 if p_2h[2] == "Short"  else 0.0)
        puan_1  = 10.0 if p_1h[2] == "Long"  else (-10.0 if p_1h[2] == "Short"  else 0.0)
    else:
        p_16h = resample_ve_analiz_et(df_1m, period_dakika=4, toplam_bar_sayisi=240, hedef_onay_sayisi=120)
        p_8h  = resample_ve_analiz_et(df_1m, period_dakika=2, toplam_bar_sayisi=240, hedef_onay_sayisi=120)
        p_4h  = resample_ve_analiz_et(df_1m, period_dakika=1, toplam_bar_sayisi=240, hedef_onay_sayisi=120)
        p_2h  = resample_ve_analiz_et(df_1m, period_dakika=1, toplam_bar_sayisi=120, hedef_onay_sayisi=60)
        p_1h  = resample_ve_analiz_et(df_1m, period_dakika=1, toplam_bar_sayisi=60,  hedef_onay_sayisi=30)
        
        puan_16 = 19.0 if p_16h[2] == "Long" else (-19.0 if p_16h[2] == "Short" else 0.0)
        puan_8  = 15.0 if p_8h[2] == "Long"  else (-15.0 if p_8h[2] == "Short"  else 0.0)
        puan_4  = 8.0  if p_4h[2] == "Long"  else (-8.0  if p_4h[2] == "Short"  else 0.0)
        puan_2  = 5.0  if p_2h[2] == "Long"  else (-5.0  if p_2h[2] == "Short"  else 0.0)
        puan_1  = 3.0  if p_1h[2] == "Long"  else (-3.0  if p_1h[2] == "Short"  else 0.0)

    toplam_puan = puan_16 + puan_8 + puan_4 + puan_2 + puan_1
    ham_skor = abs(toplam_puan)
    
    if ham_skor == 0:
        nihai_puan = 50.0
        aktif_yon = "Nötr"
    else:
        aktif_yon = "Long" if toplam_puan > 0 else "Short"
        nihai_puan = round(50.0 + (ham_skor / (80.0 if guvenilirlik_modu=="100" else 50.0)) * 150.0, 1)
        nihai_puan = min(200.0, max(50.0, nihai_puan))

    toplam_y_bar = p_16h[0] + p_8h[0] + p_4h[0] + p_2h[0] + p_1h[0]
    toplam_k_bar = p_16h[1] + p_8h[1] + p_4h[1] + p_2h[1] + p_1h[1]
    net_b = toplam_y_bar + toplam_k_bar
    anlik_y_yuzde = (toplam_y_bar / net_b * 100.0) if net_b > 0 else 50.0

    if 'trend_hafiza' not in st.session_state: st.session_state['trend_hafiza'] = {}
    onceki_y = st.session_state['trend_hafiza'].get(coin_symbol, anlik_y_yuzde)
    y_yuzde = (onceki_y * 0.7) + (anlik_y_yuzde * 0.3)
    st.session_state['trend_hafiza'][coin_symbol] = y_yuzde

    if nihai_puan < 50.0 or (50.0 <= nihai_puan < 70.0 and (45.0 <= y_yuzde <= 55.0)):
        aktif_yon = "Nötr"

    return anlik_fiyat, nihai_puan, aktif_yon, y_yuzde

def google_sheets_baglan(sayfa_adi):
    try:
        if "gcp_service_account" in st.secrets:
            sec_dict = dict(st.secrets["gcp_service_account"])
            if "private_key" in sec_dict: sec_dict["private_key"] = sec_dict["private_key"].replace("\\n", "\n")
            client = gspread.service_account_from_dict(sec_dict)
        else:
            client = gspread.service_account(filename="credentials.json")
        return client.open(GOOGLE_SHEET_DOSYA).worksheet(sayfa_adi)
    except: return None

def islem_gecmisi_getir(sheet_guncelle=True):
    cols = ["Islem_ID", "Acilis_Zamani", "Coin", "Yon", "Zaman_Dilimi", "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Durum", "Net_Kar_Zarar", "Guncel_Kasa", "Kapanis_Zamani", "Kapanis_Fiyati"]
    sheet = google_sheets_baglan("KriptoPortfoyVeritabani")
    if sheet is None: return pd.DataFrame(columns=cols)
    try: ham = sheet.get_all_values()
    except: return pd.DataFrame(columns=cols)
    if not ham or len(ham) == 0: return pd.DataFrame(columns=cols)
    df = pd.DataFrame(ham[1:], columns=cols)
    df['Islem_ID'] = pd.to_numeric(df['Islem_ID'], errors='coerce').fillna(0).astype(int)
    for c in ['Giris_Fiyat', 'Islem_Miktari', 'Stop', 'Kar_Al', 'Net_Kar_Zarar', 'Guncel_Kasa', 'Kapanis_Fiyati']:
        if c in df.columns: df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', '.').str.strip(), errors='coerce').fillna(0.0)
    return df

def dataframe_guncelle_gsheets(df):
    sheet = google_sheets_baglan("KriptoPortfoyVeritabani")
    if sheet is not None:
        try:
            sheet.clear()
            sheet.append_row(list(df.columns))
            for _, row in df.iterrows(): sheet.append_row(list(row.values))
        except: pass

def kasa_defteri_getir():
    cols = ["Islem_ID", "Zaman", "Islem_Turu", "Tutar", "Aciklama"]
    sheet = google_sheets_baglan("KasaDefteri")
    if sheet is None: return pd.DataFrame(columns=cols)
    try: ham = sheet.get_all_values()
    except: return pd.DataFrame(columns=cols)
    if not ham: return pd.DataFrame(columns=cols)
    df = pd.DataFrame(ham[1:], columns=cols)
    df['Tutar'] = pd.to_numeric(df['Tutar'].astype(str).str.replace(',', '.').str.strip(), errors='coerce').fillna(0.0)
    return df

def kasa_defteri_guncelle_gsheets(df):
    sheet = google_sheets_baglan("KasaDefteri")
    if sheet is not None:
        try:
            sheet.clear()
            sheet.append_row(list(df.columns))
            for _, row in df.iterrows(): sheet.append_row(list(row.values))
        except: pass

def kasa_islem_ekle_deftere(tip, tutar, aciklama):
    df_k = kasa_defteri_getir()
    y_id = 1 if df_k.empty else int(pd.to_numeric(df_k['Islem_ID'], errors='coerce').max() or 0) + 1
    suan = tr_zaman().strftime("%d.%m.%Y %H:%M")
    y_kayit = pd.DataFrame([{"Islem_ID": y_id, "Zaman": suan, "Islem_Turu": tip, "Tutar": round(tutar, 2), "Aciklama": aciklama}])
    kasa_defteri_guncelle_gsheets(pd.concat([df_k, y_kayit], ignore_index=True))

def bakiye_durumunu_getir(ortak_fiyat_havuzu={}):
    df_t = islem_gecmisi_getir(False)
    df_k = kasa_defteri_getir()
    net_k = BASLANGIC_BAKIYE
    if not df_k.empty: net_k += df_k['Tutar'].sum()
    if not df_t.empty:
        kap = df_t[df_t['Durum'].str.contains('Kapandi|Kar|Zarar', case=False, na=False)]
        if not kap.empty:
            t_s = df_k[df_k['Islem_Turu'] == 'Trade_Sonuc']['Tutar'].sum() if not df_k.empty else 0.0
            g_t = kap['Net_Kar_Zarar'].sum()
            if g_t != t_s: net_k += (g_t - t_s)
    acik = df_t[df_t['Durum'] == 'Acik'] if not df_t.empty else pd.DataFrame()
    aktif_m, acik_kz = 0.0, 0.0
    if not acik.empty:
        aktif_m = acik['Islem_Miktari'].sum()
        for _, rw in acik.iterrows():
            c, g, m, y = rw['Coin'], float(rw['Giris_Fiyat']), float(rw['Islem_Miktari']), rw['Yon']
            anl = ortak_fiyat_havuzu.get(c, baz_fiyatlar.get(c, 100.0))
            f_y = ((anl - g) / g) if 'Long' in y else ((g - anl) / g)
            acik_kz += m * KALDIRAC * f_y
    return float(net_k), float(net_k + acik_kz), float(net_k - aktif_m), float(aktif_m)

def yeni_islem_ekle(coin, yon, giris_fiyat, sepet_orani, stop, kar_al, zaman_dilimi):
    if "Nötr" in yon: return False, "⚠️ Bu coin Nötr, işlem açılamaz!"
    _, _, mev_b, _ = bakiye_durumunu_getir()
    mik = mev_b * (sepet_orani / 100.0)
    if mik < 10: return False, "İşlem miktarı 10 $'dan küçük olamaz!"
    df = islem_gecmisi_getir()
    y_id = 1 if df.empty else int(df['Islem_ID'].max() or 0) + 1
    suan = tr_zaman().strftime("%d.%m.%Y %H:%M")
    top_k, _, _, _ = bakiye_durumunu_getir()
    y_kayit = pd.DataFrame([{
        "Islem_ID": y_id, "Acilis_Zamani": suan, "Coin": coin, "Yon": yon, "Zaman_Dilimi": zaman_dilimi,
        "Giris_Fiyat": giris_fiyat, "Islem_Miktari": round(mik, 2), "Stop": stop, "Kar_Al": kar_al,
        "Durum": "Acik", "Net_Kar_Zarar": 0.0, "Guncel_Kasa": round(top_k, 2), "Kapanis_Zamani": "-", "Kapanis_Fiyati": 0.0
    }])
    dataframe_guncelle_gsheets(pd.concat([df, y_kayit], ignore_index=True))
    return True, f"✅ {coin} emri verildi!"

def manuel_islem_kapat(islem_id, anlik_fiyat):
    df = islem_gecmisi_getir()
    idx = df[df['Islem_ID'] == islem_id].index
    if idx.empty: return False, "İşlem bulunamadı!"
    row = df.loc[idx[0]]
    if row['Durum'] != 'Acik': return False, "Kapalı işlem!"
    try:
        g_f, mik = float(row['Giris_Fiyat']), float(row['Islem_Miktari'])
        f_y = ((anlik_fiyat - g_f) / g_f) if 'Long' in row['Yon'] else ((g_f - anlik_fiyat) / g_f)
        net_kar = mik * KALDIRAC * f_y
        suan = tr_zaman().strftime("%d.%m.%Y %H:%M")
        durum_m = 'Kapandi (Zarar)' if net_kar < 0 else 'Kapandi (Kar)'
        df.at[idx[0], 'Durum'] = durum_m
        df.at[idx[0], 'Kapanis_Zamani'] = suan
        df.at[idx[0], 'Net_Kar_Zarar'] = float(round(net_kar, 2))
        df.at[idx[0], 'Kapanis_Fiyati'] = float(round(anlik_fiyat, 4))
        top_k, _, _, _ = bakiye_durumunu_getir()
        df.at[idx[0], 'Guncel_Kasa'] = float(round(top_k + net_kar, 2))
        dataframe_guncelle_gsheets(df)
        kasa_islem_ekle_deftere("Trade_Sonuc", float(round(net_kar, 2)), f"Trade: #{islem_id} {row['Coin']} ({durum_m})")
        return True, f"Kapatıldı. K/Z: {net_kar:.2f} $"
    except Exception as e: return False, str(e)

# --- ARAYÜZ ---
st.title("⚡ Pro Kripto Canlı Akış ve Mikro Matris Paneli")

with st.sidebar:
    st.header("⚙️ Strateji Ayarları")
    secilen_mod = st.selectbox("Güvenilirlik Modu:", ["100 (%80 Konsensüs)", "50 (%50 Konsensüs)"], index=0)
    aktif_mod_kodu = "100" if "100" in secilen_mod else "50"
    st.info("ℹ️ 16h, 8h, 4h, 2h ve 1h periyotlu mikro zaman matrisi devrede.")

islenen_ham_veriler = []
ortak_fiyat_havuzu = {} 

for sembol in coinler:
    anlik_fiyat, nihai_puan, aktif_yon, y_yuzde = yeni_matris_hesapla(sembol, guvenilirlik_modu=aktif_mod_kodu)
    ortak_fiyat_havuzu[sembol] = anlik_fiyat 
    df_1200 = load_1200_bar_market_data(sembol)
    stop_uzde, hedef_carpan = calculate_coin_atr_metrics(df_1200, nihai_puan)
    islenen_ham_veriler.append({
        "sembol": sembol, "anlik_fiyat": anlik_fiyat, "nihai_puan": nihai_puan,
        "aktif_yon": aktif_yon, "y_yuzde": y_yuzde, "stop_uzde": stop_uzde, "hedef_carpan": hedef_carpan
    })

usdt_puan_ort = sum([d["nihai_puan"] for d in islenen_ham_veriler]) / len(islenen_ham_veriler)

islenen_veriler = []
for data in islenen_ham_veriler:
    sembol, nihai_puan, aktif_yon = data["sembol"], data["nihai_puan"], data["aktif_yon"]
    y_yuzde, k_yuzde = data["y_yuzde"], 100.0 - data["y_yuzde"]
    anlik_fiyat, stop_uzde, hedef_carpan = data["anlik_fiyat"], data["stop_uzde"], data["hedef_carpan"]
    
    c_led = "🟢" if (nihai_puan >= 50.0 and aktif_yon == "Long") else ("🔴" if (nihai_puan >= 50.0 and aktif_yon == "Short") else "🟡")
    u_led = "🟢" if usdt_puan_ort >= 50.0 else "🟡"
    
    y_gorsel = max(0, min(10, int(round(y_yuzde / 10.0))))
    k_gorsel = 10 - y_gorsel
    detay_matris_html = f'<div style="text-align: center;"><div style="font-size: 15px;">{"🟢"*y_gorsel}{"🔴"*k_gorsel}</div><div style="font-size: 11px; font-weight: 600;"><span style="color: #00FF00;">%{y_yuzde:.1f}</span> | <span style="color: #FF0000;">%{k_yuzde:.1f}</span></div></div>'
    
    is_notr = (aktif_yon == "Nötr")
    if is_notr:
        trend = "Nötr (Beklemede)"
        aktif_yon_turu = "Nötr"
    else:
        aktif_yon_turu = aktif_yon
        trend = f"Güçlü Trend {aktif_yon_turu}" if nihai_puan >= 145.0 else f"{aktif_yon_turu} (Onaylı)"
        
    hedef_uzde = round(stop_uzde * hedef_carpan, 1)
    if aktif_yon_turu == "Long":
        stop_fiyat = anlik_fiyat * (1.0 - stop_uzde / 100.0)
        hedef_fiyat = anlik_fiyat * (1.0 + hedef_uzde / 100.0)
    elif aktif_yon_turu == "Short":
        stop_fiyat = anlik_fiyat * (1.0 + stop_uzde / 100.0)
        hedef_fiyat = anlik_fiyat * (1.0 - hedef_uzde / 100.0)
    else:
        stop_fiyat = anlik_fiyat * (1.0 - stop_uzde / 100.0)
        hedef_fiyat = anlik_fiyat * (1.0 + hedef_uzde / 100.0)
        
    dom_html = f'<div style="text-align: center;"><div style="font-size: 16px;">{c_led}{u_led}{c_led}</div></div>'
    puan_html = f'<div style="font-weight: bold; color: {"#00FF00" if aktif_yon_turu=="Long" else ("#FF0000" if aktif_yon_turu=="Short" else "#6c757d")};">{nihai_puan:.1f} / 200<br>({aktif_yon_turu})</div>'
    
    basamak = 4 if anlik_fiyat < 10 else 2
    logo_html = f'<img src="{logo_urls.get(sembol, "")}" width="24" height="24">'
    
    if "Güçlü Trend" in trend:
        yon_html = f'<div style="background-color: {"#00FF00" if "Long" in trend else "#FF0000"}; padding: 6px; border-radius: 6px; color: white; font-weight: bold;">🔥 {trend}</div>'
    elif "Long" in trend:
        yon_html = '<div style="background-color: #00FF00; padding: 6px; border-radius: 6px; color: white; font-weight: bold;">' + trend + '</div>'
    elif "Short" in trend:
        yon_html = '<div style="background-color: #FF0000; padding: 6px; border-radius: 6px; color: white; font-weight: bold;">' + trend + '</div>'
    else:
        yon_html = f'<div style="background-color: #ffc107; padding: 6px; border-radius: 6px; color: #212529; font-weight: bold;">{trend}</div>'
        
    sepet_orani = 0.0 if is_notr else round(50.0 + 50.0 * (((max(50.0, min(200.0, nihai_puan)) - 50.0) / 150.0) ** 1.4), 1)

    islenen_veriler.append({
        "Logo": logo_html, "Coin": sembol, "Fiyat": round(anlik_fiyat, basamak), 
        "Yon": yon_html, "Teyit_Sunumu": detay_matris_html, "Dom_Sunumu": dom_html, 
        "Matris_Puan_Sunumu": puan_html, "Kar_Al": round(hedef_fiyat, basamak), 
        "Stopla": round(stop_fiyat, basamak), "Skor": nihai_puan, "Sepet_Orani": sepet_orani,
        "Basamak": basamak, "Notr": is_notr, "Ham_Yon": trend, "Aktif_Yon": aktif_yon_turu,
        "Risk_Hedef_Metin": f"1 / {hedef_carpan:.1f}".replace('.', ',')
    })

islenen_veriler = sorted(islenen_veriler, key=lambda x: (1 if x["Notr"] else 0, -x["Skor"]))
toplam_kasa, efektif_kasa, mevcut_bakiye, aktif_yatirim_tutari = bakiye_durumunu_getir(ortak_fiyat_havuzu)

for v in islenen_veriler:
    v["Yatırım_Bedeli"] = f"{mevcut_bakiye * (v['Sepet_Orani'] / 100.0):,.2f} $"

# --- ÜST BİLGİ PANELİ ---
col_ust1, col_ust2, col_ust3, col_ust4, col_ust5 = st.columns([2, 2, 2, 2, 1])
with col_ust1: st.markdown(f'<div class="metric-container"><p style="font-size: 14px; font-weight: bold;">📊 Aktif Yatırım</p><h1 style="font-size: 24px;">{aktif_yatirim_tutari:,.2f} $</h1></div>', unsafe_allow_html=True)
with col_ust2: st.markdown(f'<div class="metric-container"><p style="font-size: 14px; font-weight: bold;">🟢 Boştaki Nakit</p><h1 style="font-size: 24px;">{mevcut_bakiye:,.2f} $</h1></div>', unsafe_allow_html=True)
with col_ust3: st.markdown(f'<div class="metric-container"><p style="font-size: 14px; font-weight: bold;">💎 Efektif Kasa</p><h1 style="font-size: 24px;">{efektif_kasa:,.2f} $</h1></div>', unsafe_allow_html=True)
with col_ust4: st.markdown(f'<div class="metric-container"><p style="font-size: 14px; font-weight: bold;">💰 Toplam Kasa</p><h1 style="font-size: 24px;">{toplam_kasa:,.2f} $</h1></div>', unsafe_allow_html=True)
with col_ust5:
    st.write("")
    if st.button("🔄 Yenile", use_container_width=True): st.rerun()

st.markdown("---")

# --- TABLO GÖSTERİMİ ---
table_html = """
<table class="custom-table">
 <thead class="custom-table-header">
 <tr>
 <th>Logo</th><th>Coin</th><th>Güncel Fiyat</th><th>Trend Durumu</th>
 <th>Matris Teyit</th><th>Dominans</th><th>Matris Puanı</th><th>Önerilen Oran</th>
 <th>Yatırım Tutarı</th><th>Kar Al Hedefi</th><th>Stop Seviyesi</th><th>Risk / Hedef</th>
 </tr>
 </thead><tbody>
"""
for v in islenen_veriler:
    f_str = f"{v['Fiyat']:,.4f}&nbsp;$" if v['Basamak'] == 4 else f"{v['Fiyat']:,.2f}&nbsp;$"
    k_str = f"{v['Kar_Al']:,.4f}&nbsp;$" if v['Basamak'] == 4 else f"{v['Kar_Al']:,.2f}&nbsp;$"
    s_str = f"{v['Stopla']:,.4f}&nbsp;$" if v['Basamak'] == 4 else f"{v['Stopla']:,.2f}&nbsp;$"
    oran_h = '<div style="background-color: rgba(255, 235, 59, 0.3); padding: 5px;">%0<br>(Beklemede)</div>' if v['Notr'] else f'<div style="background-color: {"#00FF00" if "Long" in v["Ham_Yon"] else "#FF0000"}; color: white; padding: 5px;">%{v["Sepet_Orani"]:.1f}</div>'
    table_html += f"<tr><td>{v['Logo']}</td><td>{v['Coin']}</td><td style='color: #0d6efd;'>{f_str}</td><td>{v['Yon']}</td><td>{v['Teyit_Sunumu']}</td><td>{v['Dom_Sunumu']}</td><td>{v['Matris_Puan_Sunumu']}</td><td>{oran_h}</td><td>{v['Yatırım_Bedeli']}</td><td>{k_str}</td><td>{s_str}</td><td style='color: #d63384;'>{v['Risk_Hedef_Metin']}</td></tr>"
table_html += "</tbody></table>"
st.markdown(table_html, unsafe_allow_html=True)

# --- HIZLI İŞLEM EMRİ ---
st.markdown("### 🚀 Hızlı İşlem Emri Ver")
df_gosterge = pd.DataFrame(islenen_veriler)
secilen_coin = st.selectbox("İşleme Girmek İstediğiniz Coini Seçin:", df_gosterge['Coin'].tolist())
coin_verisi = df_gosterge[df_gosterge['Coin'] == secilen_coin].iloc[0]
secilen_oran = st.slider("Yatırım Oranını Seçin (%):", 0.0, 100.0, float(coin_verisi['Sepet_Orani']), 0.5)
hesaplanan_tutar = mevcut_bakiye * (secilen_oran / 100.0)
st.markdown(f"💼 **Yatırım Tutarı:** `{hesaplanan_tutar:,.2f} $` &nbsp;&nbsp;|&nbsp;&nbsp; **Boştaki Nakit:** `{mevcut_bakiye:,.2f} $`", unsafe_allow_html=True)

if st.button("🚀 İşlemi Başlat ve Emri Al"):
    basari, mesaj = yeni_islem_ekle(secilen_coin, coin_verisi['Aktif_Yon'], coin_verisi['Fiyat'], secilen_oran, coin_verisi['Stopla'], coin_verisi['Kar_Al'], "Mikro Matris")
    if basari: st.success(mesaj); st.balloons()
    else: st.error(mesaj)

st.markdown("---")

# --- PORTFÖY VE POZİSYONLAR ---
st.markdown("### 💼 Sanal Portföy ve Pozisyonlar")
df_gecmis = islem_gecmisi_getir(sheet_guncelle=False)
if not df_gecmis.empty and 'Durum' in df_gecmis.columns:
    acik_list = df_gecmis[df_gecmis['Durum'] == 'Acik']['Islem_ID'].tolist()
    if acik_list:
        st.markdown("#### 🛑 İşlem Kapatma Paneli")
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1: kapat_id = st.selectbox("Kapatılacak İşlem ID:", acik_list)
        with c2: onay = st.checkbox(f"ID #{kapat_id} işlemini kapatmayı onaylıyorum")
        with c3:
            st.write("")
            if st.button("🔒 Kapat"):
                if onay:
                    k_coin = df_gecmis[df_gecmis['Islem_ID'] == kapat_id]['Coin'].iloc[0]
                    k_fiyat = ortak_fiyat_havuzu.get(k_coin, baz_fiyatlar.get(k_coin, 100.0))
                    b_durum, b_mesaj = manuel_islem_kapat(kapat_id, k_fiyat)
                    if b_durum: st.success(b_mesaj); time.sleep(1); st.rerun()
                    else: st.error(b_mesaj)
                else: st.warning("Onaylayın!")
    st.markdown("---")

    # Kapanan İşlemler Analizi
    kapananlar_df = df_gecmis[df_gecmis['Durum'].astype(str).str.contains('Kapandi|Kar|Zarar', case=False, na=False)]
    if not kapananlar_df.empty:
        karli_s, zararli_s = 0, 0
        top_kazanc, top_kayip = 0.0, 0.0
        for _, r in kapananlar_df.iterrows():
            v = float(pd.to_numeric(r['Net_Kar_Zarar'], errors='coerce') or 0.0)
            if v >= 0: karli_s += 1; top_kazanc += v
            else: zararli_s += 1; top_kayip += abs(v)
            
        top_kap = len(kapananlar_df)
        net_fark = top_kazanc - top_kayip
        
        col_p1, col_p2, col_p3 = st.columns([1.5, 1, 1])
        with col_p1:
            df_pie = pd.DataFrame({'Durum': ['Kârlı', 'Zararlı'], 'Adet': [karli_s, zararli_s]})
            fig = px.pie(df_pie, names='Durum', values='Adet', hole=0.35, color='Durum', color_discrete_map={'Kârlı': '#00FF00', 'Zararlı': '#FF0000'})
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)
        with col_p2:
            st.metric("Toplam Kapanan", f"{top_kap} Adet")
            st.metric("Kârlı", f"{karli_s} Adet")
            st.metric("Zararlı", f"{zararli_s} Adet")
        with col_p3:
            st.markdown(
                f'<div class="para-blogu">'
                f'<p style="color: #00FF00; margin: 0px; font-weight: bold;">Toplam Kâr:</p>'
                f'<h3 style="color: #00FF00; margin: 0px 0px 10px 0px;">+{top_kazanc:,.2f} $</h3>'
                f'<p style="color: #FF0000; margin: 0px; font-weight: bold;">Toplam Zarar:</p>'
                f'<h3 style="color: #FF0000; margin: 0px 0px 10px 0px;">-{top_kayip:,.2f} $</h3>'
                f'<hr style="margin: 8px 0px;">'
                f'<p style="margin: 0px; font-weight: bold;">Net Fark:</p>'
                f'<h3 style="color: {"#00FF00" if net_fark >= 0 else "#FF0000"}; margin: 0px;">{net_fark:+,.2f} $</h3>'
                f'</div>',
                unsafe_allow_html=True
            )
