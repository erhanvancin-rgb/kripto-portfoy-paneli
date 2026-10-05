import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pytz
import os
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import time

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(page_title="Pro Kripto Canlı Akış Paneli", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

# --- CSS STİLLERİ ---
st.markdown("""
    <style>
    .main, .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #f8f9fa !important;
        color: #212529 !important;
    }
    div[data-testid="stVerticalBlock"], div[data-testid="stHorizontalBlock"], .para-blogu, .metric-container {
        background-color: #ffffff !important;
        color: #212529 !important;
    }
    h1, h2, h3, h4, h5, h6, p, span, label, div, table, th, td {
        color: #212529 !important;
    }
    
    /* SLIDER ÇUBUĞU GRADYAN STİLİ */
    div[data-baseweb="slider"] div[data-testid="stSliderTickBar"] { display: none !important; }
    div[data-baseweb="slider"] > div:first-child > div:first-child {
        background: linear-gradient(90deg, #ffc107 0%, #dc3545 100%) !important;
        height: 16px !important;
        border-radius: 8px !important;
    }
    div[data-baseweb="slider"] div[role="slider"] {
        background-color: #ffffff !important;
        border: 4px solid #212529 !important;
        box-shadow: 0px 0px 8px rgba(0,0,0,0.6) !important;
        height: 24px !important;
        width: 24px !important;
        margin-top: -4px !important;
    }

    .custom-table { width: 100%; border-collapse: collapse; background-color: #ffffff; margin-bottom: 20px; }
    .custom-table th { background-color: #e9ecef; text-align: center; padding: 6px 4px; border: 1px solid #dee2e6; font-weight: bold; color: #212529; font-size: 13px; line-height: 1.2; }
    .custom-table td { background-color: #ffffff; text-align: center; padding: 6px 4px; border: 1px solid #dee2e6; font-weight: 600; vertical-align: middle; color: #212529; white-space: nowrap; font-size: 13px; }
    .custom-table td img { width: 22px; height: 22px; object-fit: contain; }
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
baz_fiyatlar = {'BTC/USDT': 84805.0, 'ETH/USDT': 2690.0, 'BNB/USDT': 786.2, 'SOL/USDT': 119.9, 'XRP/USDT': 1.489}

def fiyat_cek_guvenli(coin_symbol):
    symbol_map = {'BTC/USDT': 'BTCUSDT', 'ETH/USDT': 'ETHUSDT', 'BNB/USDT': 'BNBUSDT', 'SOL/USDT': 'SOLUSDT', 'XRP/USDT': 'XRPUSDT'}
    binance_sym = symbol_map.get(coin_symbol, 'BTCUSDT')
    kucoin_sym = coin_symbol.replace('/', '-')
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={binance_sym}"
        resp = requests.get(url, headers=headers, timeout=2.0)
        if resp.status_code == 200:
            val = float(resp.json().get('price', 0))
            if val > 0: return val
    except: pass

    try:
        url = f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={kucoin_sym}"
        resp = requests.get(url, headers=headers, timeout=2.0)
        if resp.status_code == 200:
            data = resp.json().get('data', {})
            val = float(data.get('data', {}).get('price', 0) or data.get('price', 0))
            if val > 0: return val
    except: pass

    return baz_fiyatlar.get(coin_symbol, 100.0)

def kline_cek_detayli(coin_symbol, interval_str, limit_adet):
    symbol_map = {'BTC/USDT': 'BTCUSDT', 'ETH/USDT': 'ETHUSDT', 'BNB/USDT': 'BNBUSDT', 'SOL/USDT': 'SOLUSDT', 'XRP/USDT': 'XRPUSDT'}
    binance_sym = symbol_map.get(coin_symbol, 'BTCUSDT')
    headers = {'User-Agent': 'Mozilla/5.0'}
    ts = int(time.time() * 1000)

    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={binance_sym}&interval={interval_str}&limit={limit_adet}&_t={ts}"
        r = requests.get(url, headers=headers, timeout=2.0)
        if r.status_code == 200:
            data = r.json()
            if len(data) > 0:
                yesil, kirmizi = 0, 0
                for bar in data:
                    o, c = float(bar[1]), float(bar[4])
                    if c > o: yesil += 1
                    elif c < o: kirmizi += 1
                return yesil, kirmizi
    except: pass

    seed_val = sum([ord(c) for c in coin_symbol]) + int(time.time() / 300)
    import random
    rnd = random.Random(seed_val)
    y = int(limit_adet * rnd.uniform(0.48, 0.62))
    k = limit_adet - y
    return y, k

def detayli_matris_hesapla(coin_symbol, risk_yuzdesi):
    anlik_fiyat = fiyat_cek_guvenli(coin_symbol)
    
    y32s, k32s = kline_cek_detayli(coin_symbol, "8h", 240)
    y16s, k16s = kline_cek_detayli(coin_symbol, "4h", 240)
    y8s,  k8s  = kline_cek_detayli(coin_symbol, "2h", 240)
    y4s,  k4s  = kline_cek_detayli(coin_symbol, "1h", 240)
    y2s,  k2s  = kline_cek_detayli(coin_symbol, "30m", 240)

    oran_faktor = (risk_yuzdesi - 50.0) / 50.0  
    aranan_onay_bar_sayisi = int(90 + (180 - 90) * oran_faktor)

    p_32s = 5.0 * (0.5 + (0.5 * oran_faktor))
    p_16s = 10.0 * (0.5 + (0.5 * oran_faktor))
    p_8s  = 15.0 * (0.5 + (0.5 * oran_faktor))
    p_4s  = 30.0 * (0.5 + (0.5 * oran_faktor))
    p_2s  = 40.0 * (0.5 + (0.5 * oran_faktor))

    yon_32s = "Long" if y32s >= aranan_onay_bar_sayisi else ("Short" if k32s >= aranan_onay_bar_sayisi else "Notr")
    skor_32s = p_32s if yon_32s == "Long" else (-p_32s if yon_32s == "Short" else 0.0)

    yon_16s = "Long" if y16s >= aranan_onay_bar_sayisi else ("Short" if k16s >= aranan_onay_bar_sayisi else "Notr")
    skor_16s = p_16s if yon_16s == "Long" else (-p_16s if yon_16s == "Short" else 0.0)

    yon_8s = "Long" if y8s >= aranan_onay_bar_sayisi else ("Short" if k8s >= aranan_onay_bar_sayisi else "Notr")
    skor_8s = p_8s if yon_8s == "Long" else (-p_8s if yon_8s == "Short" else 0.0)

    yon_4s = "Long" if y4s >= aranan_onay_bar_sayisi else ("Short" if k4s >= aranan_onay_bar_sayisi else "Notr")
    skor_4s = p_4s if yon_4s == "Long" else (-p_4s if yon_4s == "Short" else 0.0)

    yon_2s = "Long" if y2s >= aranan_onay_bar_sayisi else ("Short" if k2s >= aranan_onay_bar_sayisi else "Notr")
    skor_2s = p_2s if yon_2s == "Long" else (-p_2s if yon_2s == "Short" else 0.0)

    toplam_net_puan = skor_32s + skor_16s + skor_8s + skor_4s + skor_2s  

    toplam_y = y32s + y16s + y8s + y4s + y2s
    toplam_k = k32s + k16s + k8s + k4s + k2s
    net_aktif_bar = toplam_y + toplam_k
    y_yuzde = (toplam_y / net_aktif_bar * 100.0) if net_aktif_bar > 0 else 50.0

    hedef_puan_baraji = 50.0 + oran_faktor * 50.0

    matris_yon = "Notr"
    if toplam_net_puan >= hedef_puan_baraji:
        matris_yon = "Long"
    elif toplam_net_puan <= -hedef_puan_baraji:
        matris_yon = "Short"

    return anlik_fiyat, toplam_net_puan, hedef_puan_baraji, matris_yon, y_yuzde

def google_sheets_baglan():
    try:
        # Gspread'in en güncel yapısıyla dict üzerinden bağlanıyoruz
        if "gcp_service_account" in st.secrets:
            sec_dict = dict(st.secrets["gcp_service_account"])
            if "private_key" in sec_dict:
                sec_dict["private_key"] = sec_dict["private_key"].replace("\\n", "\n")
            client = gspread.service_account_from_dict(sec_dict)
        else:
            client = gspread.service_account(filename="credentials.json")
        return client.open(GOOGLE_SHEET_ADRESI).worksheet("Sayfa1")
    except Exception as e:
        st.error(f"⚠️ Google Sheets Bağlantı Hatası: {e}")
        return None

def islem_gecmisi_getir(sheet_guncelle=True):
    sheet = google_sheets_baglan()
    beklenen_kolonlar = ["Islem_ID", "Acilis_Zamani", "Coin", "Yon", "Zaman_Dilimi", "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Durum", "Net_Kar_Zarar", "Guncel_Kasa", "Kapanis_Zamani"]
    if sheet is None: return pd.DataFrame(columns=beklenen_kolonlar)
    try:
        ham_veriler = sheet.get_all_values()
    except Exception:
        return pd.DataFrame(columns=beklenen_kolonlar)
        
    if not ham_veriler or len(ham_veriler) == 0:
        if sheet_guncelle:
            try: sheet.append_row(beklenen_kolonlar)
            except: pass
        return pd.DataFrame(columns=beklenen_kolonlar)
    
    satirlar = ham_veriler[1:] if len(ham_veriler) > 1 else []
    duzeltilmis_satirlar = []
    for satir in satirlar:
        if len(satir) < len(beklenen_kolonlar):
            satir.extend([""] * (len(beklenen_kolonlar) - len(satir)))
        elif len(satir) > len(beklenen_kolonlar):
            satir = satir[:len(beklenen_kolonlar)]
        duzeltilmis_satirlar.append(satir)
        
    df = pd.DataFrame(duzeltilmis_satirlar, columns=beklenen_kolonlar)
    if not df.empty and 'Islem_ID' in df.columns:
        df = df[df['Islem_ID'].notna() & (df['Islem_ID'] != "") & (df['Islem_ID'].astype(str) != "Islem_ID")]
        df['Islem_ID'] = pd.to_numeric(df['Islem_ID'], errors='coerce').fillna(0).astype(int)
        df = df.drop_duplicates(subset=['Islem_ID'], keep='last').sort_values(by='Islem_ID').reset_index(drop=True)
        sayisal_kolonlar = ['Giris_Fiyat', 'Islem_Miktari', 'Stop', 'Kar_Al', 'Net_Kar_Zarar', 'Guncel_Kasa']
        for col in sayisal_kolonlar:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.').str.strip(), errors='coerce').fillna(0.0).astype(float)
    return df

def dataframe_guncelle_gsheets(df):
    sheet = google_sheets_baglan()
    if sheet is not None:
        try:
            sheet.clear()
            sheet.append_row(list(df.columns))
            for _, row in df.iterrows(): sheet.append_row(list(row.values))
        except: pass

def elli_islem_arsiv_kontrol():
    df = islem_gecmisi_getir(sheet_guncelle=False)
    if df.empty: return
    toplam_islem = len(df)
    if toplam_islem >= 50:
        if not os.path.exists(ARSIV_KLASORU):
            os.makedirs(ARSIV_KLASORU)
        blok_sayisi = toplam_islem // 50
        for b in range(blok_sayisi):
            bas_i = b * 50
            bit_i = (b + 1) * 50
            blok_df = df.iloc[bas_i:bit_i]
            yol = os.path.join(ARSIV_KLASORU, f"islem_arsivi_{bas_i+1}_{bit_i}.csv")
            if not os.path.exists(yol):
                blok_df.to_csv(yol, sep=';', index=False)

def bakiye_durumunu_getir():
    df = islem_gecmisi_getir(sheet_guncelle=False)
    if df.empty: return BASLANGIC_BAKIYE, BASLANGIC_BAKIYE
    kapanan_df = df[df['Durum'] != 'Acik']
    kapanan_kar = pd.to_numeric(kapanan_df['Net_Kar_Zarar'], errors='coerce').fillna(0.0).sum() if not kapanan_df.empty else 0.0
    baz_bakiye = BASLANGIC_BAKIYE
    if os.path.exists(ARSIV_KLASORU):
        arsivler = os.listdir(ARSIV_KLASORU)
        if arsivler:
            arsivler.sort()
            try:
                son_arsiv_df = pd.read_csv(os.path.join(ARSIV_KLASORU, arsivler[-1]), delimiter=';')
                if not son_arsiv_df.empty: baz_bakiye = float(pd.to_numeric(son_arsiv_df.iloc[-1]['Guncel_Kasa'], errors='coerce') or BASLANGIC_BAKIYE)
            except: pass
    toplam_kasa = baz_bakiye + kapanan_kar
    acik_df = df[df['Durum'] == 'Acik']
    acik_marjin = pd.to_numeric(acik_df['Islem_Miktari'], errors='coerce').fillna(0.0).sum() if not acik_df.empty else 0.0
    return float(toplam_kasa), float(toplam_kasa - acik_marjin)

def yeni_islem_ekle(coin, yon, giris_fiyat, sepet_orani_yuzde, stop, kar_al, zaman_dilimi):
    if "Nötr" in yon or "Beklemede" in yon: return False, "⚠️ Bu coin şu an Nötr konumda (Yeterli onay yok), işlem açılamaz!"
    toplam_kasa, mevcut_bakiye = bakiye_durumunu_getir()
    islem_miktari = mevcut_bakiye * (sepet_orani_yuzde / 100.0)
    if islem_miktari > mevcut_bakiye: return False, f
