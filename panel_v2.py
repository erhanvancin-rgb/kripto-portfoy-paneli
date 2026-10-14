import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import pytz
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import time
import json
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from streamlit_autorefresh import st_autorefresh

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(page_title="Pro Kripto Canlı Akış ve Paneli", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

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

    h1, h2, h3, h4, h5, h6, p, label, div, table, th, td {
        color: #212529 !important;
    }
    
    h3, .stMarkdown h3 {
        font-size: 22px !important;
    }
    
    .stButton > button, div.stFormSubmitButton > button {
        background-color: #e9ecef !important;
        color: #212529 !important;
        border: 1px solid #ced4da !important;
        font-weight: bold !important;
    }
    .stButton > button:hover, div.stFormSubmitButton > button:hover {
        background-color: rgb(70, 0, 255) !important;
        color: #ffffff !important;
    }

    .table-container { width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; margin-bottom: 20px; }
    .custom-table { width: 100%; border-collapse: collapse; background-color: #ffffff; }
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
    'XRP/USDT': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/xrp.png',
    'TOTAL': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/usdt.png'
}
baz_fiyatlar = {'BTC/USDT': 83750.0, 'ETH/USDT': 2511.0, 'BNB/USDT': 745.0, 'SOL/USDT': 107.6, 'XRP/USDT': 1.373, 'TOTAL': 2.77e12}

def gmail_bildirim_gonder(konu, icerik_html):
    gonderici_mail = "erhanvancin@gmail.com"
    uygulama_sifresi = "jkef zgaf zwtg qyom"
    alici_mail = "erhanvancin@gmail.com"
    
    try:
        msg = MIMEMultipart()
        msg['From'] = gonderici_mail
        msg['To'] = alici_mail
        msg['Subject'] = konu
        msg.attach(MIMEText(icerik_html, 'html'))
        
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(gonderici_mail, uygulama_sifresi)
        server.sendmail(gonderici_mail, alici_mail, msg.as_string())
        server.quit()
        return True, "E-posta başarıyla gönderildi."
    except Exception as e:
        return False, str(e)

# --- BİNANCE API ENTEGRASYONU (ENGELSİZ) ---
def fiyat_cek_binance(coin_symbol):
    if coin_symbol == 'TOTAL':
        df_btc = kline_cek_binance('BTC/USDT', '15m', 2)
        if not df_btc.empty:
            current_btc = float(df_btc['Close'].iloc[-1])
            return current_btc * 33200.0 
        return baz_fiyatlar['TOTAL']

    sym = coin_symbol.replace('/', '')
    endpoints = [
        f"https://data-api.binance.vision/api/v3/ticker/price?symbol={sym}",
        f"https://api.binance.com/api/v3/ticker/price?symbol={sym}"
    ]
    for ep in endpoints:
        try:
            r = requests.get(ep, timeout=3)
            if r.status_code == 200:
                val = float(r.json()['price'])
                if val > 0: return val
        except: continue
    
    return baz_fiyatlar.get(coin_symbol, 100.0)

def kline_cek_binance(coin_symbol, interval, limit):
    sym = coin_symbol.replace('/', '')
    endpoints = [
        f"https://data-api.binance.vision/api/v3/klines?symbol={sym}&interval={interval}&limit={limit}",
        f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={interval}&limit={limit}"
    ]
    for ep in endpoints:
        try:
            r = requests.get(ep, timeout=5)
            if r.status_code == 200:
                data = r.json()
                df = pd.DataFrame(data, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close_Time', 'QAV', 'Num_Trades', 'Taker_BBAV', 'Taker_BQAV', 'Ignore'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert(TR_TZ)
                for col in ['Open', 'High', 'Low', 'Close']:
                    df[col] = df[col].astype(float)
                return df[['timestamp', 'Open', 'High', 'Low', 'Close']]
        except: continue
    return pd.DataFrame()

@st.cache_data(ttl=30)
def load_15min_market_data(coin_symbol: str):
    limit = 64
    if coin_symbol == 'TOTAL':
        anlik_total = fiyat_cek_binance('TOTAL')
        df_btc = kline_cek_binance('BTC/USDT', '15m', limit)
        if not df_btc.empty:
            current_btc = float(df_btc['Close'].iloc[-1])
            if current_btc > 0:
                carpan = anlik_total / current_btc
                df_btc['Open'] = df_btc['Open'] * carpan
                df_btc['High'] = df_btc['High'] * carpan
                df_btc['Low'] = df_btc['Low'] * carpan
                df_btc['Close'] = df_btc['Close'] * carpan
                return df_btc
                
    if coin_symbol != 'TOTAL':
        df = kline_cek_binance(coin_symbol, '15m', limit)
        if not df.empty: return df
    
    dates = pd.date_range(end=datetime.now(TR_TZ), periods=limit, freq='15min')
    base_p = baz_fiyatlar.get(coin_symbol, 2.77e12 if coin_symbol == 'TOTAL' else 100.0)
    return pd.DataFrame({'timestamp': dates, 'Open': [base_p]*limit, 'High': [base_p]*limit, 'Low': [base_p]*limit, 'Close': [base_p]*limit})

def calculate_coin_atr_metrics(df, skor):
    stop_pct = 0.70
    t = (max(102.5, min(200.0, skor)) - 102.5) / 97.5
    hedef_carpan = round(1.7 + (4.0 - 1.7) * (t ** 1.2), 1)
    return stop_pct, hedef_carpan

def kline_cek_detayli_binance_ozel(coin_symbol, bar_saniye, toplam_bar):
    if coin_symbol == 'TOTAL': coin_symbol = 'BTC/USDT'
    
    intervals = {900: '15m', 300: '5m', 60: '1m'}
    interval = intervals.get(bar_saniye, '5m')
    
    df = kline_cek_binance(coin_symbol, interval, toplam_bar)
    if not df.empty:
        yesil = len(df[df['Close'] > df['Open']])
        kirmizi = len(df[df['Close'] < df['Open']])
        if (yesil + kirmizi) > 0: return yesil, kirmizi
        
    return int(toplam_bar * 0.5), int(toplam_bar * 0.5)

def hesapla_zaman_dilimi_puan_200(y, k, max_puan):
    toplam = y + k
    if toplam <= 0: return 0.0, 0.0, 0.0, 0, 0
    
    s_long = (y / toplam) * max_puan
    s_short = (k / toplam) * max_puan
    net_katki = s_long - s_short
    
    return s_long, s_short, net_katki, y, k

def kurgusal_matris_hesapla(coin_symbol):
    anlik_fiyat = fiyat_cek_binance(coin_symbol)
    
    y16, k16 = kline_cek_detayli_binance_ozel(coin_symbol, 900, 64)
    y8, k8 = kline_cek_detayli_binance_ozel(coin_symbol, 300, 96)
    y4, k4 = kline_cek_detayli_binance_ozel(coin_symbol, 300, 48)
    y2, k2 = kline_cek_detayli_binance_ozel(coin_symbol, 60, 120)
    y1, k1 = kline_cek_detayli_binance_ozel(coin_symbol, 60, 60)
    
    dilimler = [
        (y16, k16, 14.0),
        (y8, k8, 26.0),
        (y4, k4, 40.0),
        (y2, k2, 50.0),
        (y1, k1, 70.0)
    ]
    
    toplam_long_puan = 0.0
    toplam_short_puan = 0.0
    zaman_katkilari = {}
    
    zaman_isimleri = ["16 S", "8 S", "4 S", "2 S", "1 S"]
    for idx, (y, k, max_puan) in enumerate(dilimler):
        sl, ss, net_katki, y_adet, k_adet = hesapla_zaman_dilimi_puan_200(y, k, max_puan)
        toplam_long_puan += sl
        toplam_short_puan += ss
        
        zaman_katkilari[zaman_isimleri[idx]] = {
            "sl": sl, "ss": ss, "y_adet": y_adet, "k_adet": k_adet
        }
        
    nihai_long = round(toplam_long_puan, 2)
    nihai_short = round(toplam_short_puan, 2)
    
    if nihai_long >= nihai_short:
        nihai_puan = nihai_long
        aktif_yon = "Long"
    else:
        nihai_puan = nihai_short
        aktif_yon = "Short"
        
    if nihai_puan < 102.5:
        aktif_yon = "Nötr"
        
    return anlik_fiyat, nihai_puan, aktif_yon, nihai_long, nihai_short, zaman_katkilari

def google_sheets_baglan(sayfa_adi):
    try:
        if "gcp_service_account" in st.secrets:
            sec_dict = dict(st.secrets["gcp_service_account"])
            if "private_key" in sec_dict: sec_dict["private_key"] = sec_dict["private_key"].replace("\\n", "\n")
            client = gspread.service_account_from_dict(sec_dict)
        else:
            client = gspread.service_account(filename="credentials.json")
        return client.open(GOOGLE_SHEET_DOSYA).worksheet(sayfa_adi)
    except Exception: return None

def islem_gecmisi_getir(sheet_guncelle=True):
    beklenen_kolonlar = ["Islem_ID", "Acilis_Zamani", "Coin", "Yon", "Zaman_Dilimi", "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Beklenen_Kar", "Matris_Puan_RH", "Olasi_Stop", "Durum", "Net_Kar_Zarar", "Guncel_Kasa", "Kapanis_Zamani", "Kapanis_Fiyati"]
    sheet = google_sheets_baglan("KriptoPortfoyVeritabani")
    if sheet is None: return pd.DataFrame(columns=beklenen_kolonlar)
    try: ham_veriler = sheet.get_all_values()
    except Exception: return pd.DataFrame(columns=beklenen_kolonlar)
        
    if not ham_veriler or len(ham_veriler) == 0:
        if sheet_guncelle:
            try: sheet.append_row(beklenen_kolonlar)
            except: pass
        return pd.DataFrame(columns=beklenen_kolonlar)
        
    satirlar = ham_veriler[1:] if len(ham_veriler) > 1 else []
    duzeltilmis_satirlar = []
    for satir in satirlar:
        if len(satir) < len(beklenen_kolonlar): satir.extend([""] * (len(beklenen_kolonlar) - len(satir)))
        elif len(satir) > len(beklenen_kolonlar): satir = satir[:len(beklenen_kolonlar)]
        duzeltilmis_satirlar.append(satir)
        
    df = pd.DataFrame(duzeltilmis_satirlar, columns=beklenen_kolonlar)
    if not df.empty and 'Islem_ID' in df.columns:
        df = df[df['Islem_ID'].notna() & (df['Islem_ID'] != "") & (df['Islem_ID'].astype(str) != "Islem_ID")]
        df['Islem_ID'] = pd.to_numeric(df['Islem_ID'], errors='coerce').fillna(0).astype(int)
        df = df.drop_duplicates(subset=['Islem_ID'], keep='last').sort_values(by='Islem_ID').reset_index(drop=True)
        sayisal_kolonlar = ['Giris_Fiyat', 'Islem_Miktari', 'Stop', 'Kar_Al', 'Beklenen_Kar', 'Olasi_Stop', 'Net_Kar_Zarar', 'Guncel_Kasa', 'Kapanis_Fiyati']
        for col in sayisal_kolonlar:
            if col in df.columns: df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.').str.strip(), errors='coerce').fillna(0.0).astype(float)
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
    kolonlar = ["Islem_ID", "Zaman", "Islem_Turu", "Tutar", "Aciklama"]
    sheet = google_sheets_baglan("KasaDefteri")
    if sheet is None: return pd.DataFrame(columns=kolonlar)
    try: ham = sheet.get_all_values()
    except: return pd.DataFrame(columns=kolonlar)
        
    if not ham or len(ham) == 0:
        try: sheet.append_row(kolonlar)
        except: pass
        return pd.DataFrame(columns=kolonlar)
        
    satirlar = ham[1:] if len(ham) > 1 else []
    duz_satirlar = []
    for s in satirlar:
        if len(s) < len(kolonlar): s.extend([""] * (len(kolonlar) - len(s)))
        elif len(s) > len(kolonlar): s = s[:len(kolonlar)]
        duz_satirlar.append(s)
        
    df = pd.DataFrame(duz_satirlar, columns=kolonlar)
    if not df.empty and 'Islem_ID' in df.columns:
        df = df[df['Islem_ID'].notna() & (df['Islem_ID'] != "") & (df['Islem_ID'].astype(str) != "Islem_ID")]
        df['Islem_ID'] = pd.to_numeric(df['Islem_ID'], errors='coerce').fillna(0).astype(int)
        df['Tutar'] = pd.to_numeric(df['Tutar'].astype(str).str.replace(',', '.').str.strip(), errors='coerce').fillna(0.0).astype(float)
    return df

def kasa_defteri_guncelle_gsheets(df):
    sheet = google_sheets_baglan("KasaDefteri")
    if sheet is not None:
        try:
            sheet.clear()
            sheet.append_row(list(df.columns))
            for _, row in df.iterrows(): sheet.append_row(list(row.values))
        except: pass

def kasa_islem_ekle_deftere(islem_turu, tutar, aciklama):
    df_kasa = kasa_defteri_getir()
    yeni_id = 1 if df_kasa.empty else int(pd.to_numeric(df_kasa['Islem_ID'], errors='coerce').max() or 0) + 1
    suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")
    yeni_kayit = pd.DataFrame([{"Islem_ID": yeni_id, "Zaman": suan_tr, "Islem_Turu": islem_turu, "Tutar": round(tutar, 2), "Aciklama": aciklama}])
    df_kasa = pd.concat([df_kasa, yeni_kayit], ignore_index=True).drop_duplicates(subset=['Islem_ID'], keep='last')
    kasa_defteri_guncelle_gsheets(df_kasa)

def elli_islem_arsiv_kontrol():
    try:
        df = islem_gecmisi_getir(sheet_guncelle=False)
        if df.empty: return
        toplam_islem = len(df)
        if toplam_islem >= 50:
            if not os.path.exists(ARSIV_KLASORU): os.makedirs(ARSIV_KLASORU)
            blok_sayisi = toplam_islem // 50
            for b in range(blok_sayisi):
                bas_i, bit_i = b * 50, (b + 1) * 50
                blok_df = df.iloc[bas_i:bit_i]
                yol = os.path.join(ARSIV_KLASORU, f"islem_arsivi_{bas_i+1}_{bit_i}.csv")
                if not os.path.exists(yol): blok_df.to_csv(yol, sep=';', index=False)
    except: pass

def bakiye_durumunu_getir(ortak_fiyat_havuzu={}):
    df_trade = islem_gecmisi_getir(sheet_guncelle=False)
    df_kasa = kasa_defteri_getir()
    net_kasa_hareketleri = BASLANGIC_BAKIYE
    
    if not df_kasa.empty: net_kasa_hareketleri += pd.to_numeric(df_kasa['Tutar'], errors='coerce').fillna(0.0).sum()
        
    if not df_trade.empty:
        kap_trades = df_trade[df_trade['Durum'].astype(str).str.contains('Kapandi|Kar|Zarar', case=False, na=False)]
        if not kap_trades.empty:
            trade_sonuc_defterde = 0.0
            if not df_kasa.empty and 'Islem_Turu' in df_kasa.columns:
                ts_df = df_kasa[df_kasa['Islem_Turu'] == 'Trade_Sonuc']
                if not ts_df.empty: trade_sonuc_defterde = pd.to_numeric(ts_df['Tutar'], errors='coerce').fillna(0.0).sum()
            gercek_trade_toplam = pd.to_numeric(kap_trades['Net_Kar_Zarar'], errors='coerce').fillna(0.0).sum()
            if gercek_trade_toplam != trade_sonuc_defterde: net_kasa_hareketleri += (gercek_trade_toplam - trade_sonuc_defterde)
                
    toplam_kasa = net_kasa_hareketleri
    acik_df = pd.DataFrame()
    if not df_trade.empty and 'Durum' in df_trade.columns:
        kapali_mask = df_trade['Durum'].astype(str).str.contains('kapandi|kar|zarar', case=False, na=False)
        acik_df = df_trade[~kapali_mask]
        
    aktif_marjin_toplami = 0.0
    acik_kz_toplam = 0.0
    
    if not acik_df.empty:
        aktif_marjin_toplami = pd.to_numeric(acik_df['Islem_Miktari'], errors='coerce').fillna(0.0).sum()
        for _, rw in acik_df.iterrows():
            c_SYM = rw['Coin']
            g_F = float(rw['Giris_Fiyat'])
            m_M = float(rw['Islem_Miktari'])
            y_Y = rw['Yon']
            if not ortak_fiyat_havuzu:
                anl_F = fiyat_cek_binance(c_SYM)
            else:
                anl_F = ortak_fiyat_havuzu.get(c_SYM, baz_fiyatlar.get(c_SYM, 100.0))
            f_y = ((anl_F - g_F) / g_F) if 'Long' in y_Y else ((g_F - anl_F) / g_F)
            acik_kz_toplam += m_M * KALDIRAC * f_y
            
    efektif_kasa = toplam_kasa + acik_kz_toplam
    bos_bakiye = toplam_kasa - aktif_marjin_toplami
    return float(toplam_kasa), float(efektif_kasa), float(bos_bakiye), float(aktif_marjin_toplami)

def kasa_islem_ekle(islem_tipi, miktar, aciklama):
    toplam_kasa, efektif_kasa, mevcut_bakiye, aktif_yatirim = bakiye_durumunu_getir()
    if islem_tipi == "Para_Cek" and miktar > mevcut_bakiye: return False, f"⚠️ Çekilmek istenen tutar boştaki bakiyenizden ({mevcut_bakiye:.2f} $) büyük olamaz!"
    if miktar <= 0: return False, "⚠️ Tutar 0'dan büyük olmalıdır!"
    tutar_val = miktar if islem_tipi == "Para_Yatir" else -miktar
    kasa_islem_ekle_deftere(islem_tipi, tutar_val, aciklama)
    return True, f"✅ Kasa güncellendi! İşlem Tutarı: {miktar:,.2f} $"

def yeni_islem_ekle(coin, yon, giris_fiyat, islem_miktari, stop, kar_al, zaman_dilimi, matris_puan, risk_hedef_metin):
    if matris_puan < 102.5 or "Nötr" in yon or "Beklemede" in yon: return False, "⚠️ Nötr konumda (102.5 puan altı) işlem açılamaz!"
    _, _, mevcut_bakiye, _ = bakiye_durumunu_getir()
    if islem_miktari >= mevcut_bakiye: return False, f"Bakiye yetersiz! Gereken: {islem_miktari:.2f} $"
    if islem_miktari < 10: return False, "İşlem miktarı 10 $'dan küçük olamaz!"
    
    df = islem_gecmisi_getir()
    yeni_id = 1 if df.empty else int(pd.to_numeric(df['Islem_ID'], errors='coerce').max() or 0) + 1
    suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")
    
    if 'Long' in yon:
        beklenen_kar = islem_miktari * KALDIRAC * ((kar_al - giris_fiyat) / giris_fiyat)
        olasi_stop = islem_miktari * KALDIRAC * ((stop - giris_fiyat) / giris_fiyat)
    else:
        beklenen_kar = islem_miktari * KALDIRAC * ((giris_fiyat - kar_al) / giris_fiyat)
        olasi_stop = islem_miktari * KALDIRAC * ((giris_fiyat - stop) / giris_fiyat)
        
    matris_rh_metin = f"{matris_puan} ({risk_hedef_metin})"
    toplam_kasa, _, _, _ = bakiye_durumunu_getir()
    yeni_kayit = pd.DataFrame([{
        "Islem_ID": yeni_id, "Acilis_Zamani": suan_tr, "Coin": coin, "Yon": yon, "Zaman_Dilimi": zaman_dilimi, "Giris_Fiyat": giris_fiyat, 
        "Islem_Miktari": round(islem_miktari, 2), "Stop": stop, "Kar_Al": kar_al, "Beklenen_Kar": round(beklenen_kar, 2), 
        "Matris_Puan_RH": matris_rh_metin, "Olasi_Stop": round(olasi_stop, 2), "Durum": "Acik", "Net_Kar_Zarar": 0.0, 
        "Guncel_Kasa": round(toplam_kasa, 2), "Kapanis_Zamani": "-", "Kapanis_Fiyati": 0.0
    }])
    df = pd.concat([df, yeni_kayit], ignore_index=True).drop_duplicates(subset=['Islem_ID'], keep='last')
    dataframe_guncelle_gsheets(df)
    elli_islem_arsiv_kontrol()
    return True, f"✅ {coin} emri başarıyla verildi!"

def manuel_islem_kapat(islem_id, anlik_kapatma_fiyati):
    df = islem_gecmisi_getir()
    idx = df[df['Islem_ID'] == islem_id].index
    if idx.empty: return False, "İşlem bulunamadı!"
    row = df.loc[idx[0]]
    try:
        giris_fiyat = float(row['Giris_Fiyat'])
        miktar = float(row['Islem_Miktari'])
        fark_yuzde = ((anlik_kapatma_fiyati - giris_fiyat) / giris_fiyat) if 'Long' in row['Yon'] else ((giris_fiyat - anlik_kapatma_fiyati) / giris_fiyat)
        net_kar = miktar * KALDIRAC * fark_yuzde
        suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")
        
        durum_metni = 'Kapandi (Zarar)' if net_kar < 0 else 'Kapandi (Kar)'
        df.at[idx[0], 'Durum'] = durum_metni
        df.at[idx[0], 'Kapanis_Zamani'] = suan_tr
        df.at[idx[0], 'Net_Kar_Zarar'] = float(round(net_kar, 2))
        df.at[idx[0], 'Kapanis_Fiyati'] = float(round(anlik_kapatma_fiyati, 4))
        
        toplam_kasa, _, _, _ = bakiye_durumunu_getir()
        df.at[idx[0], 'Guncel_Kasa'] = float(round(toplam_kasa + net_kar, 2))
        dataframe_guncelle_gsheets(df)
        kasa_islem_ekle_deftere("Trade_Sonuc", float(round(net_kar, 2)), f"Trade K/Z: #{islem_id} {row['Coin']} ({durum_metni})")
        elli_islem_arsiv_kontrol()
        
        mail_icerik = f"<h3>İşlem Manuel Olarak Kapatıldı</h3><p><b>İşlem ID:</b> #{islem_id}</p><p><b>Coin:</b> {row['Coin']}</p><p><b>Yön:</b> {row['Yon']}</p><p><b>Durum:</b> {durum_metni}</p><p><b>Net Kâr/Zarar:</b> {net_kar:+,.2f} $</p><p><b>Güncel Kasa:</b> {toplam_kasa + net_kar:,.2f} $</p>"
        gmail_bildirim_gonder(f"🔔 Manuel Kapatma Raporu: #{islem_id} {row['Coin']} ({durum_metni})", mail_icerik)
        return True, f"Kapatıldı. K/Z: {net_kar:.2f} $"
    except Exception as e: return False, f"Hata: {str(e)}"

def otomatik_stop_kar_kontrolu(ortak_fiyat_havuzu=None):
    df = islem_gecmisi_getir(sheet_guncelle=False)
    if df.empty or 'Durum' not in df.columns: return
    
    degisiklik_oldu = False
    suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")
    
    for idx, row in df.iterrows():
        durum_str = str(row['Durum']).lower()
        if not ('kapandi' in durum_str or 'kar' in durum_str or 'zarar' in durum_str):
            islem_id = int(row['Islem_ID'])
            coin = row['Coin']
            yon = row['Yon']
            giris_fiyat = float(row['Giris_Fiyat'])
            stop_f = float(row['Stop'])
            kar_al_f = float(row['Kar_Al'])
            miktar = float(row['Islem_Miktari'])
            
            if ortak_fiyat_havuzu is not None and coin in ortak_fiyat_havuzu:
                anl_f = ortak_fiyat_havuzu[coin]
            else:
                anl_f = fiyat_cek_binance(coin)
            
            islem_kapatilacak = False
            hedefe_ulasti = False
            kapanis_fiyat_degeri = 0.0
            
            if 'Long' in yon:
                if anl_f <= stop_f: islem_kapatilacak, hedefe_ulasti, kapanis_fiyat_degeri = True, False, stop_f
                elif anl_f >= kar_al_f: islem_kapatilacak, hedefe_ulasti, kapanis_fiyat_degeri = True, True, kar_al_f
            elif 'Short' in yon:
                if anl_f >= stop_f: islem_kapatilacak, hedefe_ulasti, kapanis_fiyat_degeri = True, False, stop_f
                elif anl_f <= kar_al_f: islem_kapatilacak, hedefe_ulasti, kapanis_fiyat_degeri = True, True, kar_al_f
                
            if islem_kapatilacak:
                fark_yuzde = ((kapanis_fiyat_degeri - giris_fiyat) / giris_fiyat) if 'Long' in yon else ((giris_fiyat - kapanis_fiyat_degeri) / giris_fiyat)
                net_kar = miktar * KALDIRAC * fark_yuzde
                durum_metni = 'Kapandi (Kar)' if hedefe_ulasti else 'Kapandi (Zarar)'
                
                df.at[idx, 'Durum'] = durum_metni
                df.at[idx, 'Kapanis_Zamani'] = suan_tr
                df.at[idx, 'Net_Kar_Zarar'] = float(round(net_kar, 2))
                df.at[idx, 'Kapanis_Fiyati'] = float(round(kapanis_fiyat_degeri, 4))
                
                toplam_kasa, _, _, _ = bakiye_durumunu_getir({} if ortak_fiyat_havuzu is None else ortak_fiyat_havuzu)
                df.at[idx, 'Guncel_Kasa'] = float(round(toplam_kasa + net_kar, 2))
                
                islem_turu_etiket = "Hedef Kâr" if hedefe_ulasti else "Otomatik Stop"
                kasa_islem_ekle_deftere("Trade_Sonuc", float(round(net_kar, 2)), f"{islem_turu_etiket}: #{islem_id} {coin} ({'Kar' if hedefe_ulasti else 'Zarar'})")
                degisiklik_oldu = True
                
                mail_icerik = f"<h3>İşlem Hedefe Ulaştı ve Otomatik Kapatıldı</h3><p><b>Kapanış Türü:</b> {islem_turu_etiket}</p><p><b>İşlem ID:</b> #{islem_id}</p><p><b>Coin:</b> {coin}</p><p><b>Yön:</b> {yon}</p><p><b>Net Kâr/Zarar:</b> {net_kar:+,.2f} $</p><p><b>Güncel Kasa:</b> {toplam_kasa + net_kar:,.2f} $</p>"
                gmail_bildirim_gonder(f"🔔 Otomatik İşlem Raporu: #{islem_id} {coin} ({'Kâr' if hedefe_ulasti else 'Zarar'})", mail_icerik)
                
    if degisiklik_oldu:
        dataframe_guncelle_gsheets(df)
        elli_islem_arsiv_kontrol()

def arka_plan_dinleyicisi():
    while True:
        try:
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

st.title("⚡ Pro Kripto & Canlı Piyasa Paneli (200 Puanlık Kesin Matris)")
elli_islem_arsiv_kontrol()

if 'kasa_islem_acik' not in st.session_state: st.session_state['kasa_islem_acik'] = False
if 'kasa_islem_turu' not in st.session_state: st.session_state['kasa_islem_turu'] = "Para Yatır"
if 'sadece_aktifleri_goster' not in st.session_state: st.session_state['sadece_aktifleri_goster'] = False
if 'gonderilen_mailler' not in st.session_state: st.session_state['gonderilen_mailler'] = set()
if 'total_sermaye_alarm' not in st.session_state: st.session_state['total_sermaye_alarm'] = None

tum_takip_edilenler = coinler + ['TOTAL']
islenen_ham_veriler = []
ortak_fiyat_havuzu = {} 

for sembol in tum_takip_edilenler:
    anlik_fiyat, nihai_puan, aktif_yon, l_puan, s_puan, zaman_katkilari = kurgusal_matris_hesapla(sembol)
    if sembol == 'TOTAL': anlik_fiyat = fiyat_cek_binance('TOTAL')
    ortak_fiyat_havuzu[sembol] = anlik_fiyat 
    
    df_market = load_15min_market_data(sembol)
    stop_uzde, hedef_carpan = calculate_coin_atr_metrics(df_market, nihai_puan)
    if not df_market.empty and 'Open' in df_market.columns and 'Close' in df_market.columns:
        gunluk_oran = ((float(df_market.iloc[-1]['Close']) - float(df_market.iloc[0]['Open'])) / float(df_market.iloc[0]['Open'])) * 100.0
    else: gunluk_oran = 0.0

    islenen_ham_veriler.append({"sembol": sembol, "anlik_fiyat": anlik_fiyat, "nihai_puan": nihai_puan, "aktif_yon": aktif_yon, "l_puan": l_puan, "s_puan": s_puan, "zaman_katkilari": zaman_katkilari, "stop_uzde": stop_uzde, "hedef_carpan": hedef_carpan, "gunluk_oran": gunluk_oran, "df_market": df_market})

otomatik_stop_kar_kontrolu(ortak_fiyat_havuzu)

coin_ham_veriler = [d for d in islenen_ham_veriler if d["sembol"] != 'TOTAL']
total_ham_veri = [d for d in islenen_ham_veriler if d["sembol"] == 'TOTAL'][0]

t_puan_val, t_l_puan, t_s_puan = total_ham_veri["nihai_puan"], total_ham_veri["l_puan"], total_ham_veri["s_puan"]
t_toplam_puan = t_l_puan + t_s_puan
t_yuzde = (t_l_puan / t_toplam_puan * 100.0) if t_toplam_puan > 0 else 50.0

if t_puan_val >= 130.0:
    if total_ham_veri["aktif_yon"] == "Long": total_sermaye_durumu, t_alarm_renk = "Boğa Vuruşu", "#00FF00"
    else: total_sermaye_durumu, t_alarm_renk = "Ayı Pençesi", "rgb(255, 75, 0)"
        
    alarm_anahtar = f"total_mail_{datetime.now(TR_TZ).strftime('%Y%m%d_%H')}"
    if st.session_state.get('total_sermaye_alarm_zaman') != alarm_anahtar:
        st.session_state['total_sermaye_alarm_zaman'] = alarm_anahtar
        m_icerik = f"<h3>Piyasada Güçlü Sermaye Hareketi Tespit Edildi!</h3><p><b>Durum:</b> <span style='color: {t_alarm_renk}; font-weight: bold;'>{total_sermaye_durumu}</span></p><p><b>Matris Puanı:</b> {t_puan_val:.1f} / 200 (Eşik: 130)</p><p><b>Long Oranı:</b> %{t_yuzde:.1f}</p><p><b>Zaman:</b> {tr_zaman().strftime('%d.%m.%Y %H:%M')}</p>"
        gmail_bildirim_gonder(f"🚨 Total Market Alarmı: {total_sermaye_durumu}!", m_icerik)

total_puan_val = total_ham_veri["nihai_puan"]
total_yon_val = total_ham_veri["aktif_yon"]
islenen_veriler = []

for data in coin_ham_veriler:
    sembol, nihai_puan, aktif_yon, l_puan, s_puan, anlik_fiyat, stop_uzde = data["sembol"], data["nihai_puan"], data["aktif_yon"], data["l_puan"], data["s_puan"], data["anlik_fiyat"], data["stop_uzde"]
    hedef_carpan, gunluk_oran = data["hedef_carpan"], data["gunluk_oran"]
    
    puan_toplam = l_puan + s_puan
    y_yuzde = (l_puan / puan_toplam * 100.0) if puan_toplam > 0 else 50.0
    k_yuzde = 100.0 - y_yuzde
    
    # LED Renk Kuralı: >= 102.5 ve Long -> 🟢, >= 102.5 ve Short -> 🔴, < 102.5 -> 🟡
    def led_rengini_belirle(puan, yon):
        if puan < 102.5: return "🟡"
        return "🟢" if yon == "Long" else "🔴"

    c_led = led_rengini_belirle(nihai_puan, aktif_yon)
    t_led = led_rengini_belirle(total_puan_val, total_yon_val)
    
    yesil_led_sayisi = round((y_yuzde / 100.0) * 10.0)
    yesil_led_sayisi = max(0, min(10, yesil_led_sayisi))
    kirmizi_led_sayisi = 10 - yesil_led_sayisi
    
    detay_matris_html = f'<div style="text-align: center; line-height: 1.2;"><div style="font-size: 15px; margin-bottom: 2px; letter-spacing: 1px;">{"🟢" * yesil_led_sayisi}{"🔴" * kirmizi_led_sayisi}</div><div style="font-size: 11px; font-weight: 600;"><span style="color: #00FF00; display: inline-block; width: 10px; height: 10px; background-color: #00FF00; border-radius: 50%; margin-right: 2px;"></span>%{y_yuzde:.1f} | <span style="color: rgb(255, 75, 0); display: inline-block; width: 10px; height: 10px; background-color: rgb(255, 75, 0); border-radius: 50%; margin-left: 4px; margin-right: 2px;"></span>%{k_yuzde:.1f}</div></div>'
    
    is_notr = (nihai_puan < 102.5 or aktif_yon == "Nötr")
    if is_notr: trend, aktif_yon_turu = "Nötr (Beklemede)", "Nötr"
    else:
        aktif_yon_turu = aktif_yon
        trend = f"Güçlü Trend {aktif_yon_turu}" if nihai_puan >= 130.0 else f"{aktif_yon_turu} (Onaylı)"
        
    if nihai_puan >= 130.0 and sembol not in st.session_state['gonderilen_mailler']:
        st.session_state['gonderilen_mailler'].add(sembol)
        gmail_bildirim_gonder(f"🔥 Güçlü Trend Alarmı: {sembol} ({trend})", f"<h3>Piyasada Güçlü Trend Sinyali Tespit Edildi!</h3><p><b>Coin:</b> {sembol}</p><p><b>Durum:</b> {trend}</p><p><b>Matris Puanı:</b> {nihai_puan:.1f} / 200</p><p><b>Güncel Fiyat:</b> {anlik_fiyat:,.2f} $</p><p><b>Zaman:</b> {tr_zaman().strftime('%d.%m.%Y %H:%M')}</p>")

    hedef_uzde = round(stop_uzde * hedef_carpan, 1)
    if aktif_yon_turu == "Long": stop_fiyat, hedef_fiyat = anlik_fiyat * (1.0 - stop_uzde / 100.0), anlik_fiyat * (1.0 + hedef_uzde / 100.0)
    elif aktif_yon_turu == "Short": stop_fiyat, hedef_fiyat = anlik_fiyat * (1.0 + stop_uzde / 100.0), anlik_fiyat * (1.0 - hedef_uzde / 100.0)
    else: stop_fiyat, hedef_fiyat = anlik_fiyat * (1.0 - stop_uzde / 100.0), anlik_fiyat * (1.0 + hedef_uzde / 100.0)
        
    dom_html = f'<div style="text-align: center;"><div style="font-size: 16px; margin-bottom: 2px; letter-spacing: 6px;">{c_led}{t_led}</div><div style="font-size: 10px; font-weight: bold; color: #495057;">C &nbsp;&nbsp; D</div></div>'
    
    if is_notr: puan_html = f'<div style="font-weight: bold; color: #6c757d;">{nihai_puan:.1f} / 200<br><span style="font-size: 10px;">(Nötr)</span></div>'
    else: puan_html = f'<div style="font-weight: bold; color: {"#00FF00" if aktif_yon_turu == "Long" else "rgb(255, 75, 0)"};">{nihai_puan:.1f} / 200<br><span style="font-size: 10px;">({aktif_yon_turu})</span></div>'
    
    basamak = 4 if anlik_fiyat < 10 else 2
    logo_html = f'<img src="{logo_urls.get(sembol, "")}" width="24" height="24">'
    
    if nihai_puan >= 130.0: yon_html = f'<div style="background-color: {"#00FF00" if "Long" in aktif_yon_turu else "rgb(255, 75, 0)"}; padding: 6px; border-radius: 6px; color: white; font-weight: bold;">🔥 Güçlü Trend {aktif_yon_turu}</div>'
    elif "Long" in trend: yon_html = f'<div style="background-color: #00FF00; padding: 6px; border-radius: 6px; color: white; font-weight: bold;">{trend}</div>'
    elif "Short" in trend: yon_html = f'<div style="background-color: rgb(255, 75, 0); padding: 6px; border-radius: 6px; color: white; font-weight: bold;">{trend}</div>'
    else: yon_html = f'<div style="background-color: #ffc107; padding: 6px; border-radius: 6px; color: #212529; font-weight: bold;">{trend}</div>'
        
    sepet_orani = 0.0 if is_notr else round(40.0 + 60.0 * (((max(102.5, min(200.0, nihai_puan)) - 102.5) / 97.5) ** 1.1), 1)
    sepet_orani = min(100.0, max(0.0, sepet_orani))
    
    islenen_veriler.append({
        "Sira_Anahtar": list(logo_urls.keys()).index(sembol),
        "Logo": logo_html, "Coin": sembol, "Fiyat": round(anlik_fiyat, basamak), "Yon": yon_html, "Teyit_Sunumu": detay_matris_html, 
        "Dom_Sunumu": dom_html, "Matris_Puan_Sunumu": puan_html, "Gunluk_Oran": f"<span>{gunluk_oran:+,.2f}%</span>",
        "Kar_Al": round(hedef_fiyat, basamak), "Stopla": round(stop_fiyat, basamak), "Skor": nihai_puan, "Sepet_Orani": sepet_orani,
        "Basamak": basamak, "Notr": is_notr, "Ham_Yon": trend, "Aktif_Yon": aktif_yon_turu, "Risk_Hedef_Metin": f"1 / {hedef_carpan:.1f}".replace('.', ',')
    })

islenen_veriler = sorted(islenen_veriler, key=lambda x: (1 if x["Notr"] else 0, -x["Skor"]))
toplam_kasa, efektif_kasa, mevcut_bakiye, aktif_yatirim_tutari = bakiye_durumunu_getir(ortak_fiyat_havuzu)

for v in islenen_veriler: v["Yatırım_Bedeli"] = f"{mevcut_bakiye * (v['Sepet_Orani'] / 100.0):,.2f} $"

col_ust1, col_ust2, col_ust3, col_ust4, col_ust5, col_ust6 = st.columns([2, 2, 2, 2, 1.5, 1.2])
with col_ust1: st.markdown(f'<div class="metric-container"><p style="margin: 0px; font-size: 14px; font-weight: bold;">📊 Aktif Yatırım</p><h1 style="color: rgb(70, 0, 255); margin: 5px 0px 0px 0px; font-size: 24px;">{aktif_yatirim_tutari:,.2f} $</h1></div>', unsafe_allow_html=True)
with col_ust2: st.markdown(f'<div class="metric-container"><p style="margin: 0px; font-size: 14px; font-weight: bold;">🟢 Boştaki Nakit</p><h1 style="margin: 5px 0px 0px 0px; font-size: 24px;">{mevcut_bakiye:,.2f} $</h1></div>', unsafe_allow_html=True)
with col_ust3: st.markdown(f'<div class="metric-container"><p style="margin: 0px; font-size: 14px; font-weight: bold;">💎 Efektif Kasa</p><h1 style="margin: 5px 0px 0px 0px; font-size: 24px;">{efektif_kasa:,.2f} $</h1></div>', unsafe_allow_html=True)
with col_ust4: st.markdown(f'<div class="metric-container"><p style="margin: 0px; font-size: 14px; font-weight: bold;">💰 Toplam Kasa</p><h1 style="margin: 5px 0px 0px 0px; font-size: 24px;">{toplam_kasa:,.2f} $</h1></div>', unsafe_allow_html=True)
with col_ust5:
    st.markdown('<div class="metric-container" style="padding: 11px !important;"><p style="margin: 0px; font-size: 13px; font-weight: bold;">👍 Kasa Sermaye</p>', unsafe_allow_html=True)
    if st.button("🗂️ Yatır / Çek", use_container_width=True): st.session_state['kasa_islem_acik'] = not st.session_state['kasa_islem_acik']; st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
with col_ust6:
    st.write("")
    st.write("")
    if st.button("🔄 Yenile", use_container_width=True): st.rerun()

if st.session_state['kasa_islem_acik']:
    with st.container():
        st.markdown(f'<div style="background-color: #ffffff; padding: 20px; border: 2px solid rgb(70, 0, 255); border-radius: 10px; margin-bottom: 20px;"><h4 style="margin-top: 0px; color: rgb(70, 0, 255);">👍 Kasa Sermaye Yönetimi</h4>', unsafe_allow_html=True)
        col_sec1, col_sec2 = st.columns(2)
        with col_sec1:
            if st.button("🟢 Para Yatır", use_container_width=True): st.session_state['kasa_islem_turu'] = "Para Yatır"; st.rerun()
        with col_sec2:
            if st.button("🔴 Para Çek", use_container_width=True): st.session_state['kasa_islem_turu'] = "Para Çek"; st.rerun()
        
        col_k1, col_k2 = st.columns([1, 2])
        with col_k1: kasa_tutar = st.number_input("Tutar ($):", min_value=1.0, value=100.0, step=10.0, key="k_tutar")
        with col_k2: kasa_aciklama = st.text_input("Açıklama:", value="Ekstra sermaye", key="k_acik")
        
        col_islem1, col_islem2 = st.columns([1, 4])
        with col_islem1:
            if st.button("💾 Onayla", use_container_width=True):
                basarili, mesaj = kasa_islem_ekle("Para_Yatir" if st.session_state['kasa_islem_turu'] == "Para Yatır" else "Para_Cek", kasa_tutar, kasa_aciklama)
                if basarili: st.success(mesaj); st.session_state['kasa_islem_acik'] = False; time.sleep(1); st.rerun()
                else: st.error(mesaj)
        with col_islem2:
            if st.button("❌ Kapat", use_container_width=True): st.session_state['kasa_islem_acik'] = False; st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")

table_html = """
<table class="custom-table"><thead class="custom-table-header"><tr>
 <th>Logo</th><th>Coin<br>Adı</th><th>Güncel<br>Fiyat</th><th>Trend<br>Durumu</th>
 <th>Matris Teyit</th><th>Piyasa &<br>Dominans</th><th>Matris<br>Puanı</th><th>Günlük<br>Oran</th><th>Önerilen<br>Oran</th>
 <th>Yatırım<br>Tutarı</th><th>Kar Al<br>Hedefi</th><th>Stop<br>Seviyesi</th><th>Risk / Hedef</th>
 </tr></thead><tbody>
"""
for v in islenen_veriler:
    fiyat_str = f"{v['Fiyat']:,.4f}&nbsp;$" if v['Basamak'] == 4 else f"{v['Fiyat']:,.2f}&nbsp;$"
    kar_al_str = f"{v['Kar_Al']:,.4f}&nbsp;$" if v['Basamak'] == 4 else f"{v['Kar_Al']:,.2f}&nbsp;$"
    stopla_str = f"{v['Stopla']:,.4f}&nbsp;$" if v['Basamak'] == 4 else f"{v['Stopla']:,.2f}&nbsp;$"
    val_str = f"%{v['Sepet_Orani']:.1f}" if v['Sepet_Orani'] != int(v['Sepet_Orani']) else f"%{int(v['Sepet_Orani'])}"
    
    if v['Notr']: oran_html = '<div style="background-color: rgba(255, 235, 59, 0.3); padding: 5px; font-weight: bold;">%0<br>(Beklemede)</div>'
    else: oran_html = f'<div style="background-color: {"#00FF00" if "Long" in v["Ham_Yon"] else "rgb(255, 75, 0)"}; color: white; padding: 5px; font-weight: bold;">{val_str}<br>({"Güçlü Trend" if "Güçlü Trend" in v["Ham_Yon"] else "Onaylı"})</div>'

    table_html += f"<tr><td>{v['Logo']}</td><td>{v['Coin']}</td><td style='font-weight: bold; color: rgb(70, 0, 255); background-color: rgba(70, 0, 255, 0.05);'>{fiyat_str}</td><td>{v['Yon']}</td><td>{v['Teyit_Sunumu']}</td><td>{v['Dom_Sunumu']}</td><td style='background-color: rgba(0,0,0,0.02);'>{v['Matris_Puan_Sunumu']}</td><td>{v['Gunluk_Oran']}</td><td>{oran_html}</td><td>{v['Yatırım_Bedeli']}</td><td>{kar_al_str}</td><td>{stopla_str}</td><td style='font-weight: bold; color: #d63384;'>{v['Risk_Hedef_Metin']}</td></tr>"
table_html += "</tbody></table>"
st.markdown(f'<div class="table-container">{table_html}</div>', unsafe_allow_html=True)

col_sol_panel, col_orta_grafik, col_sag_endeks = st.columns([1.2, 2.5, 1.0])

with col_sol_panel:
    st.markdown("<h3>🚀 İşlem Emri Ver</h3>", unsafe_allow_html=True)
    df_gosterge = pd.DataFrame(islenen_veriler)
    df_islem_yapilabilir = df_gosterge[df_gosterge['Notr'] == False]
    coin_listesi = df_islem_yapilabilir['Coin'].tolist() if not df_islem_yapilabilir.empty else []

    secilen_coin = st.selectbox("Coin Seç:", coin_listesi) if coin_listesi else None
    if not coin_listesi: 
        st.warning("Uygun coin yok.")

    onerilen_oran_val, anlik_matris_puani, anlik_risk_hedef_metin, coin_verisii = 0.0, 0.0, "1 / 2,0", None
    if secilen_coin:
        coin_verisii = df_gosterge[df_gosterge['Coin'] == secilen_coin].iloc[0]
        onerilen_oran_val, anlik_matris_puani, anlik_risk_hedef_metin = float(coin_verisii['Sepet_Orani']), float(coin_verisii['Skor']), coin_verisii['Risk_Hedef_Metin']

    onerilen_tutar_hesap = round(mevcut_bakiye * (onerilen_oran_val / 100.0), 2)

    st.markdown(f"""
        <div style="background-color: #e9ecef; padding: 10px; border-radius: 6px; margin-bottom: 12px; font-size: 13px;">
            <b>💡 Matris Önerisi:</b><br>
            • Oran: <b>%{onerilen_oran_val:.1f}</b><br>
            • Tutar: <b>{onerilen_tutar_hesap:,.2f} $</b>
        </div>
    """, unsafe_allow_html=True)

    with st.form(key="manuel_islem_formu"):
        manuel_girilen_tutar = st.number_input(
            "Tutar ($ Giriniz):", 
            min_value=0.0, 
            max_value=999999.0, 
            value=float(onerilen_tutar_hesap), 
            step=10.0
        )

        st.markdown(f"🟢 **Boştaki Nakit:** `{mevcut_bakiye:,.2f} $`", unsafe_allow_html=True)

        submit_islem = st.form_submit_button("🚀 İşlemi Başlat", use_container_width=True)

        if submit_islem:
            if not secilen_coin or coin_listesi == []:
                st.error("⚠️ Geçerli bir coin seçmelisiniz!")
            elif coin_verisii is not None and coin_verisii['Notr']:
                st.error("⚠️ Nötr coin!")
            elif coin_verisii is not None:
                basari, mesaj = yeni_islem_ekle(
                    secilen_coin, 
                    coin_verisii['Aktif_Yon'], 
                    coin_verisii['Fiyat'], 
                    manuel_girilen_tutar, 
                    coin_verisii['Stopla'], 
                    coin_verisii['Kar_Al'], 
                    "Matris Kurgusu", 
                    anlik_matris_puani, 
                    anlik_risk_hedef_metin
                )
                if basari:
                    st.success(mesaj)
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(mesaj)

with col_orta_grafik:
    st.markdown("<h3>🌐 Total Market (16 Saatlik Akış - Fibonacci & RSI)</h3>", unsafe_allow_html=True)
    t_df_ham = total_ham_veri["df_market"]
    t_df = t_df_ham.tail(64).reset_index(drop=True)
    
    if not t_df.empty:
        delta = t_df['Close'].diff()
        rs = (delta.where(delta > 0, 0)).rolling(window=14).mean() / (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        t_df['RSI'] = (100 - (100 / (1 + rs))).fillna(50)
        
        min_f = float(t_df['Close'].min())
        max_f = float(t_df['Close'].max())
        
        if max_f - min_f < (max_f * 0.0001): 
            min_f = min_f * 0.999
            max_f = max_f * 1.001
            
        fiyat_fark = max_f - min_f
        t_df['RSI_Norm'] = min_f + (t_df['RSI'] / 100.0) * fiyat_fark
        
        fib_levels = {0.0: min_f, 0.236: min_f + 0.236 * fiyat_fark, 0.382: min_f + 0.382 * fiyat_fark, 0.5: min_f + 0.5 * fiyat_fark, 0.618: min_f + 0.618 * fiyat_fark, 0.786: min_f + 0.786 * fiyat_fark, 1.0: max_f}
        min_zaman, max_zaman = t_df['timestamp'].min(), t_df['timestamp'].max()
        
        alt_sinir = min_f - (fiyat_fark * 0.05)
        ust_sinir = max_f + (fiyat_fark * 0.05)
        
        fig_total = make_subplots(specs=[[{"secondary_y": True}]])
        
        for b_alt, b_ust, renk in [(0.0, 0.236, 'rgba(128, 0, 32, 0.16)'), (0.236, 0.382, 'rgba(180, 80, 0, 0.14)'), (0.382, 0.5, 'rgba(255, 255, 0, 0.18)'), (0.5, 0.618, 'rgba(255, 255, 0, 0.18)'), (0.618, 0.786, 'rgba(100, 180, 50, 0.15)'), (0.786, 1.0, 'rgba(0, 100, 0, 0.18)')]:
            fig_total.add_trace(go.Scatter(x=list(t_df['timestamp']) + list(t_df['timestamp'][::-1]), y=[fib_levels[b_ust]] * len(t_df) + [fib_levels[b_alt]] * len(t_df), fill='toself', fillcolor=renk, line=dict(color='rgba(255,255,255,0)'), showlegend=False, hoverinfo='skip'), secondary_y=False)

        fig_total.add_trace(go.Scatter(x=t_df['timestamp'], y=t_df['Close'], mode='lines', name='Total Market', line=dict(color='rgb(70, 0, 255)', width=2)), secondary_y=False)
        fig_total.add_trace(go.Scatter(x=t_df['timestamp'], y=t_df['RSI_Norm'], mode='lines', name='RSI (0-1)', line=dict(color='#FF8000', width=1.5, dash='solid')), secondary_y=False)

        for oran, val in fib_levels.items():
            renk_cizgi = "#CCCC00" if oran == 0.5 else ("#006400" if oran > 0.5 else "#800020")
            fig_total.add_hline(y=val, line_dash="dash", line_color=renk_cizgi, line_width=1, annotation_text=f"<b>Fib {oran}</b>  <b>{f'${val/1e12:.3f}T' if val > 1e9 else f'{val:.2f}'}</b>", annotation_position="right", annotation_font_size=10, annotation_font_color="#000000")

        fig_total.update_layout(
            template="plotly_white", 
            margin=dict(t=10, b=30, l=5, r=140), 
            height=380, 
            xaxis=dict(
                range=[min_zaman, max_zaman], 
                dtick=7200000, 
                tickformat="%H:%M",
                tickangle=25
            ), 
            yaxis=dict(showticklabels=False, range=[alt_sinir, ust_sinir]), 
            xaxis_rangeslider_visible=False, 
            paper_bgcolor='rgba(0,0,0,0)', 
            plot_bgcolor='rgba(0,0,0,0)', 
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_total, use_container_width=True)

with col_sag_endeks:
    st.markdown("<h3>Total Market Endeksi</h3>", unsafe_allow_html=True)
    t_toplam_puan = t_l_puan + t_s_puan
    t_yuzde = (t_l_puan / t_toplam_puan * 100.0) if t_toplam_puan > 0 else 50.0
    t_yesil_led = round((t_yuzde / 100.0) * 10.0)
    t_yesil_led = max(0, min(10, t_yesil_led))
    t_kirmizi_led = 10 - t_yesil_led
    
    st.markdown(f'<div style="text-align: center; line-height: 1.2; margin-bottom: 6px;"><div style="font-size: 14px; margin-bottom: 2px; letter-spacing: 1px;">{"🟢" * t_yesil_led}{"🔴" * t_kirmizi_led}</div><div style="font-size: 10px; font-weight: 600;"><span style="color: #00FF00; display: inline-block; width: 8px; height: 8px; background-color: #00FF00; border-radius: 50%; margin-right: 2px;"></span>%{t_yuzde:.1f} | <span style="color: rgb(255, 75, 0); display: inline-block; width: 8px; height: 8px; background-color: rgb(255, 75, 0); border-radius: 50%; margin-left: 2px; margin-right: 2px;"></span>%{100.0 - t_yuzde:.1f}</div></div>', unsafe_allow_html=True)
    
    t_zaman_kat = total_ham_veri["zaman_katkilari"]
    boxes_listesi = []
    for etk, veri in t_zaman_kat.items():
        sl, ss = veri["sl"], veri["ss"]
        y_ad, k_ad = veri["y_adet"], veri["k_adet"]
        kazanan_renk = "#00FF00" if sl >= ss else "rgb(255, 75, 0)"
        kutucuk_html = f'<div style="background-color: {kazanan_renk}; color: #000000; padding: 6px; border-radius: 6px; text-align: center; font-weight: bold; font-size: 11px; margin-bottom: 5px; line-height: 1.3;">{etk}<br>L: {sl:.2f}p ({y_ad}) | S: {ss:.2f}p ({k_ad})</div>'
        boxes_listesi.append(kutucuk_html)
    boxes_birlestirilmis = "".join(boxes_listesi)
    
    st.markdown(f'<div class="metric-container" style="text-align: center; padding: 10px !important;"><div style="font-size: 12px; font-weight: bold; margin-bottom: 6px;">Değer: <span style="color: rgb(70, 0, 255);">${total_ham_veri["anlik_fiyat"] / 1e12:.2f}T</span><br>Puan: <span style="color: {"#00FF00" if total_ham_veri["aktif_yon"] == "Long" else ("rgb(255, 75, 0)" if total_ham_veri["aktif_yon"] == "Short" else "#ffc107")};">{total_ham_veri["nihai_puan"]:.1f} / 200 ({total_ham_veri["aktif_yon"]})</span></div>{boxes_birlestirilmis}</div>', unsafe_allow_html=True)

st.markdown("---")

df_gecmis = islem_gecmisi_getir(sheet_guncelle=False)
acik_islem_listesi = df_gecmis[~df_gecmis['Durum'].astype(str).str.contains('kapandi|kar|zarar', case=False, na=False)]['Islem_ID'].tolist() if not df_gecmis.empty and 'Durum' in df_gecmis.columns else []

col_sol_analiz, col_orta_durum, col_sag_sonlandir = st.columns([2.9, 0.9, 1.3])

with col_sol_analiz:
    st.markdown("<h3>📊 Kapanan İşlemler Pasta Grafik & Para Akışı Analizi</h3>", unsafe_allow_html=True)
    kapananlar_df = pd.DataFrame() if df_gecmis.empty or 'Durum' not in df_gecmis.columns else df_gecmis[df_gecmis['Durum'].astype(str).str.contains('Kapandi|Kar|Zarar', case=False, na=False)]
    
    if not kapananlar_df.empty:
        karli_sayisi, zararli_sayisi = 0, 0
        toplam_kazanc_dolar, toplam_kayip_dolar = 0.0, 0.0
        for _, r in kapananlar_df.iterrows():
            val = float(pd.to_numeric(r['Net_Kar_Zarar'], errors='coerce') or 0.0)
            if val >= 0: karli_sayisi += 1; toplam_kazanc_dolar += val
            else: zararli_sayisi += 1; toplam_kayip_dolar += abs(val)
            
        toplam_kapanan = len(kapananlar_df)
        net_fark_dolar = toplam_kazanc_dolar - toplam_kayip_dolar
        kar_yuzde = (karli_sayisi / toplam_kapanan * 100.0) if toplam_kapanan > 0 else 0.0
        zarar_yuzde = (zararli_sayisi / toplam_kapanan * 100.0) if toplam_kapanan > 0 else 0.0
        
        sub_p1, sub_p2, sub_p3 = st.columns([1.1, 1.45, 1.45])
        with sub_p1:
            fig = px.pie(pd.DataFrame({'Durum': ['Kârlı', 'Zararlı'], 'Adet': [karli_sayisi, zararli_sayisi]}), names='Durum', values='Adet', hole=0.45, color='Durum', color_discrete_map={'Kârlı': '#00FF00', 'Zararlı': 'rgb(255, 75, 0)'})
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#212529', size=15), margin=dict(t=0, b=0, l=0, r=0), height=210, showlegend=False)
            fig.update_traces(textfont_size=15, textinfo='percent')
            st.plotly_chart(fig, use_container_width=True)
        with sub_p2:
            st.markdown(f'<div style="font-size: 15px; font-weight: bold; color: #212529; margin-bottom: 4px;">📈 Strateji Metrikleri</div><p style="margin: 4px 0px 0px 0px; font-size: 13px; color: #495057;">Toplam Kapanan</p><p style="margin: 0px; font-size: 18px; font-weight: bold; color: #212529;">{toplam_kapanan} Adet</p><p style="margin: 8px 0px 0px 0px; font-size: 14px; color: #00FF00; font-weight: bold;">🟢 Kârlı: {karli_sayisi} (%{kar_yuzde:.1f})</p><p style="margin: 5px 0px 0px 0px; font-size: 14px; color: rgb(255, 75, 0); font-weight: bold;">🔴 Zararlı: {zararli_sayisi} (%{zarar_yuzde:.1f})</p>', unsafe_allow_html=True)
        with sub_p3:
            st.markdown(f'<div style="font-size: 15px; font-weight: bold; color: #212529; margin-bottom: 4px;">💰 Para Değerleri</div><p style="margin: 4px 0px 0px 0px; font-size: 13px; color: #495057;">Toplam Kâr:</p><p style="margin: 0px; font-size: 16px; font-weight: bold; color: #00FF00;">+{toplam_kazanc_dolar:,.2f} $</p><p style="margin: 6px 0px 0px 0px; font-size: 13px; color: #495057;">Toplam Zarar:</p><p style="margin: 0px; font-size: 16px; font-weight: bold; color: rgb(255, 75, 0);">-{toplam_kayip_dolar:,.2f} $</p><hr style="margin: 6px 0px;"><p style="margin: 0px; font-size: 13px; color: #495057;">Net Fark:</p><p style="margin: 0px; font-size: 16px; font-weight: bold; color: {"#00FF00" if net_fark_dolar >= 0 else "rgb(255, 75, 0)"};">{net_fark_dolar:+,.2f} $</p>', unsafe_allow_html=True)
    else:
        st.info("ℹ️ Henüz kapanmış işlem bulunmuyor.")

with col_orta_durum:
    st.markdown("<h3>İşlem Sunumu</h3>", unsafe_allow_html=True)
    if st.button("Aktif İşlemler", use_container_width=True): 
        st.session_state['sadece_aktifleri_goster'] = True
        st.rerun()
    if st.button("Tüm İşlemler", use_container_width=True): 
        st.session_state['sadece_aktifleri_goster'] = False
        st.rerun()
    
    if st.session_state['sadece_aktifleri_goster']: 
        st.info("ℹ️ Sadece Aktif pozisyonlar gösteriliyor.")
    else:
        st.info("ℹ️ Tüm pozisyonlar gösteriliyor.")

with col_sag_sonlandir:
    st.markdown("<h3>🛑 İşlemi Sonlandır</h3>", unsafe_allow_html=True)
    with st.form(key="pozisyon_kapat_form"):
        kapatilacak_id = st.selectbox("ID Kodu:", acik_islem_listesi if acik_islem_listesi else [0], key="k_id")
        onay_verildi = st.checkbox("İşlemi Kapatmayı Onayla", key="onay_chk")
        submit_kapat = st.form_submit_button("İşlemi Kapat", use_container_width=True)
        
        if submit_kapat:
            if acik_islem_listesi and kapatilacak_id in acik_islem_listesi:
                if onay_verildi:
                    kapanacak_coin = df_gecmis[df_gecmis['Islem_ID'] == kapatilacak_id]['Coin'].iloc[0]
                    b_durum, b_mesaj = manuel_islem_kapat(kapatilacak_id, ortak_fiyat_havuzu.get(kapanacak_coin, baz_fiyatlar.get(kapanacak_coin, 100.0)))
                    if b_durum: st.success(b_mesaj); time.sleep(1); st.rerun()
                    else: st.error(b_mesaj)
                else: st.warning("Onay kutusunu işaretleyin!")
            else: st.info("Kapatılacak açık işlem yok.")

st.markdown("---")

df_gosterilecek = pd.DataFrame()
if not df_gecmis.empty:
    df_gosterilecek = df_gecmis[~df_gecmis['Durum'].astype(str).str.contains('kapandi|kar|zarar', case=False, na=False)] if st.session_state['sadece_aktifleri_goster'] else df_gecmis.copy()

anlik_fiyat_sozluk, anlik_kz_sozluk, hedef_kar_sozluk, olasi_stop_sozluk = {}, {}, {}, {}
if not df_gecmis.empty:
    for _, row in df_gecmis.iterrows():
        islem_id, coin, giris_fiyat, miktar, kar_al_f, stop_f, yon = row['Islem_ID'], row['Coin'], float(row['Giris_Fiyat']), float(row['Islem_Miktari']), float(row['Kar_Al']), float(row['Stop']), row['Yon']
        anl_f = ortak_fiyat_havuzu.get(coin, baz_fiyatlar.get(coin, 100.0))
        anlik_fiyat_sozluk[islem_id] = anl_f
        
        if giris_fiyat > 0 and kar_al_f > 0 and stop_f > 0:
            hedef_kar_sozluk[islem_id] = round(miktar * KALDIRAC * (((kar_al_f - giris_fiyat) / giris_fiyat) if 'Long' in yon else ((giris_fiyat - kar_al_f) / giris_fiyat)), 2)
            olasi_stop_sozluk[islem_id] = round(miktar * KALDIRAC * (((stop_f - giris_fiyat) / giris_fiyat) if 'Long' in yon else ((giris_fiyat - stop_f) / giris_fiyat)), 2)
        else: hedef_kar_sozluk[islem_id], olasi_stop_sozluk[islem_id] = 0.0, 0.0

        if not ('kapandi' in str(row['Durum']).lower() or 'kar' in str(row['Durum']).lower() or 'zarar' in str(row['Durum']).lower()):
            anlik_kz_sozluk[islem_id] = round(miktar * KALDIRAC * (((anl_f - giris_fiyat) / giris_fiyat) if 'Long' in yon else ((giris_fiyat - anl_f) / giris_fiyat)), 2)
        else: anlik_kz_sozluk[islem_id] = float(row['Net_Kar_Zarar'])

portfoy_html = """
<table class="custom-table"><thead class="custom-table-header"><tr>
 <th>ID</th><th>Açılış</th><th>Logo</th><th>Coin</th><th>Yön</th><th>Giriş</th><th>Anlık</th><th>Kapanış</th>
 <th>Yatırım</th><th>Stop</th><th>Hedef</th><th>Beklenen Kâr</th><th>Matris Puanı</th><th>Olası Stop</th>
 <th>Durum</th><th>Anlık K/Z</th><th>Kapanış Zamanı</th><th>Güncel Kasa</th>
 </tr></thead><tbody>
"""

if not df_gosterilecek.empty:
    df_gecmis_copy = df_gosterilecek.copy()
    df_gecmis_copy['Anlik_Fiyat_Deger'] = df_gecmis_copy['Islem_ID'].map(anlik_fiyat_sozluk)
    df_gecmis_copy['Canli_Beklenen_Kar'] = df_gecmis_copy['Islem_ID'].map(hedef_kar_sozluk)
    df_gecmis_copy['Canli_Olasi_Stop'] = df_gecmis_copy['Islem_ID'].map(olasi_stop_sozluk)
    df_gecmis_copy['Anlik_KZ_Deger'] = df_gecmis_copy['Islem_ID'].map(anlik_kz_sozluk)

    for _, row in df_gecmis_copy.iterrows():
        logo_h = f'<img src="{logo_urls.get(row["Coin"], "")}" width="24" height="24">'
        yon_h = f'<div style="background-color: {"#00FF00" if "Long" in row["Yon"] else "rgb(255, 75, 0)"}; padding: 6px; border-radius: 6px; color: white; font-weight: bold;">{row["Yon"]}</div>'
        anlik_fiyat_h = f'<div style="background-color: {"#00FF00" if float(row["Anlik_Fiyat_Deger"] or 0) > float(row["Giris_Fiyat"]) else "rgb(255, 75, 0)"}; color: white; padding: 5px; font-weight: bold;">{float(row["Anlik_Fiyat_Deger"] or 0):,.{4 if row["Coin"] == "XRP/USDT" else 2}f}&nbsp;$</div>'
        
        if not ('kapandi' in str(row['Durum']).lower() or 'kar' in str(row['Durum']).lower() or 'zarar' in str(row['Durum']).lower()):
            kapanis_fiyat_h, durum_h = '<div style="padding: 5px; color: #6c757d;">-</div>', '<div style="background-color: rgb(70, 0, 255); color: white; padding: 4px; border-radius: 4px; font-weight: bold;">Aktif</div>'
        else:
            is_kar = float(row['Net_Kar_Zarar']) >= 0
            k_stil = "#00FF00" if is_kar else "rgb(255, 75, 0)"
            kapanis_fiyat_h = f'<div style="background-color: {k_stil}; color: white; padding: 5px; font-weight: bold;">{float(row.get("Kapanis_Fiyati", 0.0) or row["Giris_Fiyat"]):,.{4 if row["Coin"] == "XRP/USDT" else 2}f}&nbsp;$</div>'
            durum_h = f'<div style="background-color: {k_stil}; color: white; padding: 4px; border-radius: 4px; font-weight: bold;">{"Kâr" if is_kar else "Zarar"}</div>'

        kz_h = f'<div style="background-color: {"#00FF00" if float(row["Anlik_KZ_Deger"] or 0) >= 0 else "rgb(255, 75, 0)"}; color: white; padding: 5px; font-weight: bold; white-space: nowrap;">{float(row["Anlik_KZ_Deger"] or 0):+,.2f}&nbsp;$</div>'

        portfoy_html += f"<tr><td>{row['Islem_ID']}</td><td>{row['Acilis_Zamani']}</td><td>{logo_h}</td><td>{row['Coin']}</td><td>{yon_h}</td><td>{float(row['Giris_Fiyat']):,.{4 if row['Coin'] == 'XRP/USDT' else 2}f}&nbsp;$</td><td>{anlik_fiyat_h}</td><td>{kapanis_fiyat_h}</td><td>{float(row['Islem_Miktari']):,.2f}&nbsp;$</td><td>{float(row['Stop']):,.{4 if row['Coin'] == 'XRP/USDT' else 2}f}&nbsp;$</td><td>{float(row['Kar_Al']):,.{4 if row['Coin'] == 'XRP/USDT' else 2}f}&nbsp;$</td><td>{float(row['Canli_Beklenen_Kar']):,.2f}&nbsp;$</td><td style='font-weight: bold; color: #495057;'>{str(row.get('Matris_Puan_RH', '150.0 (1 / 2.5)'))}</td><td>{float(row['Canli_Olasi_Stop']):,.2f}&nbsp;$</td><td>{durum_h}</td><td>{kz_h}</td><td>{row['Kapanis_Zamani']}</td><td>{float(row['Guncel_Kasa']):,.2f}&nbsp;$</td></tr>"
else:
    portfoy_html += "<tr><td colspan='18' style='text-align: center; color: #6c757d; padding: 20px;'>Kayıtlı işlem bulunmuyor.</td></tr>"

portfoy_html += "</tbody></table>"
st.markdown(f'<div class="table-container">{portfoy_html}</div>', unsafe_allow_html=True)

st.markdown("---")
st.markdown("<h3>📁 50'şerli İşlem Arşivleri (Analiz Klasörü)</h3>", unsafe_allow_html=True)
if os.path.exists(ARSIV_KLASORU):
    try:
        arsiv_dosyalari = sorted(os.listdir(ARSIV_KLASORU))
        if secilen_arsiv := st.selectbox("Geçmiş 50'li Blok Dönemini Seçin:", arsiv_dosyalari, key="arsiv_select_50") if arsiv_dosyalari else None:
            st.write(pd.read_csv(os.path.join(ARSIV_KLASORU, secilen_arsiv), delimiter=';').to_html(escape=False, index=False), unsafe_allow_html=True)
        elif not arsiv_dosyalari: st.info("Henüz 50 işleme ulaşılmadı.")
    except: st.info("Arşiv yüklenirken bilgi alınamadı.")
else: st.info("Arşiv klasörü henüz oluşturulmadı.")
