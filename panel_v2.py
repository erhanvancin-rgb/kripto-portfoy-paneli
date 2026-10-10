import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime
import pytz
import os
import plotly.graph_objects as go
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import time
import json
import smtplib
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

    h1, h2, h3, h4, h5, h6, p, span, label, div, table, th, td {
        color: #212529 !important;
    }
    
    .stButton > button, div.stFormSubmitButton > button {
        background-color: #e9ecef !important;
        color: #212529 !important;
        border: 1px solid #ced4da !important;
        font-weight: bold !important;
    }
    .stButton > button:hover, div.stFormSubmitButton > button:hover {
        background-color: #0d6efd !important;
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
baz_fiyatlar = {'BTC/USDT': 84805.0, 'ETH/USDT': 2690.0, 'BNB/USDT': 786.2, 'SOL/USDT': 119.9, 'XRP/USDT': 1.489, 'TOTAL': 2.77e12}

# --- GMAIL BİLDİRİM FONKSİYONU ---
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

def fiyat_cek_coinbase(coin_symbol):
    if coin_symbol == 'TOTAL':
        try:
            url = "https://api.coingecko.com/api/v3/global"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                val = float(resp.json().get('data', {}).get('total_market_cap', {}).get('usd', 0))
                if val > 0: return val
        except: pass
        return baz_fiyatlar['TOTAL']

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
def load_5min_market_data(coin_symbol: str):
    limit = 288  # 24 saatlik 5 dakikalık bar
    if coin_symbol == 'TOTAL':
        try:
            url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=1"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                prices = r.json().get('prices', [])
                if len(prices) > 0:
                    df_t = pd.DataFrame(prices, columns=['timestamp_ms', 'price'])
                    df_t['timestamp'] = pd.to_datetime(df_t['timestamp_ms'], unit='ms')
                    anlik_total = fiyat_cek_coinbase('TOTAL')
                    ilk_fiyat = df_t['price'].iloc[0]
                    carpan = anlik_total / (ilk_fiyat * 55)
                    df_t['Close'] = df_t['price'] * carpan
                    df_t['Open'] = df_t['Close'].shift(1).fillna(df_t['Close'].iloc[0])
                    df_t['High'] = df_t[['Open', 'Close']].max(axis=1) * 1.0001
                    df_t['Low'] = df_t[['Open', 'Close']].min(axis=1) * 0.9999
                    return df_t[['timestamp', 'Open', 'High', 'Low', 'Close']].tail(limit).reset_index(drop=True)
        except: pass

    if coin_symbol != 'TOTAL':
        cb_map = {'BTC/USDT': 'BTC-USD', 'ETH/USDT': 'ETH-USD', 'BNB/USDT': 'BNB-USD', 'SOL/USDT': 'SOL-USD', 'XRP/USDT': 'XRP-USD'}
        cb_sym = cb_map.get(coin_symbol, 'BTC-USD')
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        try:
            url = f"https://api.exchange.coinbase.com/products/{cb_sym}/candles?granularity=300"
            r = requests.get(url, headers=headers, timeout=15.0)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and len(data) > 0:
                    df = pd.DataFrame(data, columns=['timestamp', 'Low', 'High', 'Open', 'Close', 'Volume'])
                    for col in ['Open', 'High', 'Low', 'Close']:
                        df[col] = df[col].astype(float)
                    df = df.sort_values('timestamp').tail(limit).reset_index(drop=True)
                    return df
        except: pass
    
    dates = pd.date_range(end=datetime.now(), periods=limit, freq='5min')
    base_price = baz_fiyatlar.get(coin_symbol, 2.77e12 if coin_symbol == 'TOTAL' else 100.0)
    vol_f = base_price * 0.0005
    np.random.seed(hash(coin_symbol) % 2**32)
    close_prices = base_price + np.random.normal(0, vol_f, limit).cumsum() / 5
    open_prices = close_prices + np.random.normal(0, vol_f/4, limit)
    high_prices = np.maximum(open_prices, close_prices) + np.abs(np.random.normal(0, vol_f/3, limit))
    low_prices = np.minimum(open_prices, close_prices) - np.abs(np.random.normal(0, vol_f/3, limit))
    return pd.DataFrame({'timestamp': dates, 'Open': open_prices, 'High': high_prices, 'Low': low_prices, 'Close': close_prices})

def calculate_coin_atr_metrics(df, skor):
    stop_pct = 0.70
    s_sinirli = max(0.0, min(200.0, abs(skor)))
    t = s_sinirli / 200.0
    hedef_carpan = round(1.7 + (4.0 - 1.7) * (t ** 1.2), 1)
    return stop_pct, hedef_carpan

def kline_cek_detayli_cb_ozel(coin_symbol, bar_saniye, toplam_bar):
    if coin_symbol == 'TOTAL':
        df_m = load_5min_market_data('TOTAL')
        yesil, kirmizi = 0, 0
        for _, row in df_m.tail(toplam_bar).iterrows():
            if row['Close'] > row['Open']: yesil += 1
            elif row['Close'] < row['Open']: kirmizi += 1
        if (yesil + kirmizi) > 0: return yesil, kirmizi
        return int(toplam_bar * 0.5), int(toplam_bar * 0.5)

    cb_map = {'BTC/USDT': 'BTC-USD', 'ETH/USDT': 'ETH-USD', 'BNB/USDT': 'BNB-USD', 'SOL/USDT': 'SOL-USD', 'XRP/USDT': 'XRP-USD'}
    cb_sym = cb_map.get(coin_symbol, 'BTC-USD')
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    try:
        url = f"https://api.exchange.coinbase.com/products/{cb_sym}/candles?granularity={bar_saniye}"
        r = requests.get(url, headers=headers, timeout=15.0)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                yesil, kirmizi = 0, 0
                for bar in data[:toplam_bar]:
                    o, c = float(bar[3]), float(bar[4])
                    if c > o: yesil += 1
                    elif c < o: kirmizi += 1
                if (yesil + kirmizi) > 0:
                    return yesil, kirmizi
    except: pass
    
    seed_val = sum([ord(c) for c in coin_symbol]) + bar_saniye + int(time.time() / 300)
    rnd = np.random.RandomState(seed_val)
    yuzde_oran = rnd.uniform(0.35, 0.65)
    y_yedek = int(toplam_bar * yuzde_oran)
    k_yedek = toplam_bar - y_yedek
    return y_yedek, k_yedek

def periyot_puan_hesapla(yesil_sayisi, toplam_bar):
    if toplam_bar <= 0: return 0.0
    oran = (yesil_sayisi / toplam_bar) * 100.0
    puan = (oran / 100.0) * 200.0
    return float(puan)

def kurgusal_matris_hesapla(coin_symbol):
    anlik_fiyat = fiyat_cek_coinbase(coin_symbol)
    
    y60, k60 = kline_cek_detayli_cb_ozel(coin_symbol, 300, 60)
    y40, k40 = kline_cek_detayli_cb_ozel(coin_symbol, 300, 40)
    y20, k20 = kline_cek_detayli_cb_ozel(coin_symbol, 300, 20)
    
    p_60 = periyot_puan_hesapla(y60, 60)
    p_40 = periyot_puan_hesapla(y40, 40)
    p_20 = periyot_puan_hesapla(y20, 20)
    
    toplam_puan = (p_60 * 0.50) + (p_40 * 0.30) + (p_20 * 0.20)
    nihai_puan = round(max(0.0, min(200.0, toplam_puan)), 1)
    
    toplam_y = y60 + y40 + y20
    toplam_k = k60 + k40 + k20
    net_bar = toplam_y + toplam_k
    y_yuzde = (toplam_y / net_bar * 100.0) if net_bar > 0 else 50.0

    if 'trend_hafiza' not in st.session_state:
        st.session_state['trend_hafiza'] = {}
    
    onceki_y_yuzde = st.session_state['trend_hafiza'].get(coin_symbol, y_yuzde)
    y_yuzde = (onceki_y_yuzde * 0.85) + (y_yuzde * 0.15)
    st.session_state['trend_hafiza'][coin_symbol] = y_yuzde
    
    if nihai_puan >= 120.0 and y_yuzde >= 52.0:
        aktif_yon = "Long"
    elif nihai_puan >= 120.0 and y_yuzde <= 48.0:
        aktif_yon = "Short"
    elif nihai_puan >= 50.0:
        aktif_yon = "Long" if y_yuzde >= 50.0 else "Short"
    else:
        aktif_yon = "Nötr"
        
    return anlik_fiyat, nihai_puan, aktif_yon, y_yuzde

def google_sheets_baglan(sayfa_adi):
    try:
        if "gcp_service_account" in st.secrets:
            sec_dict = dict(st.secrets["gcp_service_account"])
            if "private_key" in sec_dict:
                sec_dict["private_key"] = sec_dict["private_key"].replace("\\n", "\n")
            client = gspread.service_account_from_dict(sec_dict)
        else:
            client = gspread.service_account(filename="credentials.json")
        return client.open(GOOGLE_SHEET_DOSYA).worksheet(sayfa_adi)
    except Exception:
        return None

def islem_gecmisi_getir(sheet_guncelle=True):
    beklenen_kolonlar = ["Islem_ID", "Acilis_Zamani", "Coin", "Yon", "Zaman_Dilimi", "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Beklenen_Kar", "Matris_Puan_RH", "Olasi_Stop", "Durum", "Net_Kar_Zarar", "Guncel_Kasa", "Kapanis_Zamani", "Kapanis_Fiyati"]
    sheet = google_sheets_baglan("KriptoPortfoyVeritabani")
    if sheet is None: 
        return pd.DataFrame(columns=beklenen_kolonlar)
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
        sayisal_kolonlar = ['Giris_Fiyat', 'Islem_Miktari', 'Stop', 'Kar_Al', 'Beklenen_Kar', 'Olasi_Stop', 'Net_Kar_Zarar', 'Guncel_Kasa', 'Kapanis_Fiyati']
        for col in sayisal_kolonlar:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.').str.strip(), errors='coerce').fillna(0.0).astype(float)
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
    if sheet is None:
        return pd.DataFrame(columns=kolonlar)
    try:
        ham = sheet.get_all_values()
    except:
        return pd.DataFrame(columns=kolonlar)
        
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
    
    yeni_kayit = pd.DataFrame([{
        "Islem_ID": yeni_id, "Zaman": suan_tr,
        "Islem_Turu": islem_turu, "Tutar": round(tutar, 2), "Aciklama": aciklama
    }])
    df_kasa = pd.concat([df_kasa, yeni_kayit], ignore_index=True).drop_duplicates(subset=['Islem_ID'], keep='last')
    kasa_defteri_guncelle_gsheets(df_kasa)

def elli_islem_arsiv_kontrol():
    try:
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
    except: pass

def bakiye_durumunu_getir(ortak_fiyat_havuzu={}):
    df_trade = islem_gecmisi_getir(sheet_guncelle=False)
    df_kasa = kasa_defteri_getir()
    
    net_kasa_hareketleri = BASLANGIC_BAKIYE
    
    if not df_kasa.empty:
        net_kasa_hareketleri += pd.to_numeric(df_kasa['Tutar'], errors='coerce').fillna(0.0).sum()
        
    if not df_trade.empty:
        kap_trades = df_trade[df_trade['Durum'].astype(str).str.contains('Kapandi|Kar|Zarar', case=False, na=False)]
        if not kap_trades.empty:
            trade_sonuc_defterde = 0.0
            if not df_kasa.empty and 'Islem_Turu' in df_kasa.columns:
                ts_df = df_kasa[df_kasa['Islem_Turu'] == 'Trade_Sonuc']
                if not ts_df.empty:
                    trade_sonuc_defterde = pd.to_numeric(ts_df['Tutar'], errors='coerce').fillna(0.0).sum()
                    
            gercek_trade_toplam = pd.to_numeric(kap_trades['Net_Kar_Zarar'], errors='coerce').fillna(0.0).sum()
            if gercek_trade_toplam != trade_sonuc_defterde:
                net_kasa_hareketleri += (gercek_trade_toplam - trade_sonuc_defterde)
                
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
            anl_F = ortak_fiyat_havuzu.get(c_SYM, baz_fiyatlar.get(c_SYM, 100.0))
            f_y = ((anl_F - g_F) / g_F) if 'Long' in y_Y else ((g_F - anl_F) / g_F)
            acik_kz_toplam += m_M * KALDIRAC * f_y
            
    efektif_kasa = toplam_kasa + acik_kz_toplam
    bos_bakiye = toplam_kasa - aktif_marjin_toplami
    
    return float(toplam_kasa), float(efektif_kasa), float(bos_bakiye), float(aktif_marjin_toplami)

def kasa_islem_ekle(islem_tipi, miktar, aciklama):
    toplam_kasa, efektif_kasa, mevcut_bakiye, aktif_yatirim = bakiye_durumunu_getir()
    if islem_tipi == "Para_Cek" and miktar > mevcut_bakiye:
        return False, f"⚠️ Çekilmek istenen tutar ({miktar} $) boştaki nakit bakiyenizden ({mevcut_bakiye:.2f} $) büyük olamaz!"
    if miktar <= 0:
        return False, "⚠️ Tutar 0'dan büyük olmalıdır!"
        
    tutar_val = miktar if islem_tipi == "Para_Yatir" else -miktar
    kasa_islem_ekle_deftere(islem_tipi, tutar_val, aciklama)
    return True, f"✅ Kasa başarıyla güncellendi! İşlem Tutarı: {miktar:,.2f} $"

def yeni_islem_ekle(coin, yon, giris_fiyat, islem_miktari, stop, kar_al, zaman_dilimi, matris_puan, risk_hedef_metin):
    if matris_puan < 50.0 or "Nötr" in yon or "Beklemede" in yon: return False, "⚠️ Bu coin şu an Nötr konumda (50 puan altı), işlem açılamaz!"
    _, _, mevcut_bakiye, _ = bakiye_durumunu_getir()
    if islem_miktari > mevcut_bakiye: return False, f"Bakiye yetersiz! Gereken: {islem_miktari:.2f} $"
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
        "Islem_ID": yeni_id, "Acilis_Zamani": suan_tr,
        "Coin": coin, "Yon": yon, "Zaman_Dilimi": zaman_dilimi, "Giris_Fiyat": giris_f, 
        "Islem_Miktari": round(islem_miktari, 2), "Stop": stop, "Kar_Al": kar_al, 
        "Beklenen_Kar": round(beklenen_kar, 2), "Matris_Puan_RH": matris_rh_metin, "Olasi_Stop": round(olasi_stop, 2),
        "Durum": "Acik", "Net_Kar_Zarar": 0.0, "Guncel_Kasa": round(toplam_kasa, 2), "Kapanis_Zamani": "-", "Kapanis_Fiyati": 0.0
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
        giris_f = float(row['Giris_Fiyat'])
        miktar = float(row['Islem_Miktari'])
        fark_yuzde = ((anlik_kapatma_fiyati - giris_f) / giris_f) if 'Long' in row['Yon'] else ((giris_f - anlik_kapatma_fiyati) / giris_f)
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
        
        trade_aciklama = f"Trade K/Z: #{islem_id} {row['Coin']} ({durum_metni})"
        kasa_islem_ekle_deftere("Trade_Sonuc", float(round(net_kar, 2)), trade_aciklama)
        elli_islem_arsiv_kontrol()
        
        mail_konu = f"🔔 Manuel Kapatma Raporu: #{islem_id} {row['Coin']} ({durum_metni})"
        mail_icerik = f"""
            <h3>İşlem Manuel Olarak Kapatıldı</h3>
            <p><b>İşlem ID:</b> #{islem_id}</p>
            <p><b>Coin:</b> {row['Coin']}</p>
            <p><b>Yön:</b> {row['Yon']}</p>
            <p><b>Durum:</b> {durum_metni}</p>
            <p><b>Net Kâr/Zarar:</b> {net_kar:+,.2f} $</p>
            <p><b>Güncel Kasa:</b> {toplam_kasa + net_kar:,.2f} $</p>
        """
        gmail_bildirim_gonder(mail_konu, mail_icerik)
        return True, f"Kapatıldı. K/Z: {net_kar:.2f} $"
    except Exception as e: return False, f"Hata: {str(e)}"

def otomatik_stop_kar_kontrolu(ortak_fiyat_havuzu):
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
            giris_f = float(row['Giris_Fiyat'])
            stop_f = float(row['Stop'])
            kar_al_f = float(row['Kar_Al'])
            miktar = float(row['Islem_Miktari'])
            anl_f = ortak_fiyat_havuzu.get(coin, baz_fiyatlar.get(coin, 100.0))
            
            islem_kapatilacak = False
            hedefe_ulasti = False
            kapanis_fiyat_degeri = 0.0
            
            if 'Long' in yon:
                if anl_f <= stop_f:
                    islem_kapatilacak = True
                    hedefe_ulasti = False
                    kapanis_fiyat_degeri = stop_f
                elif anl_f >= kar_al_f:
                    islem_kapatilacak = True
                    hedefe_ulasti = True
                    kapanis_fiyat_degeri = kar_al_f
            elif 'Short' in yon:
                if anl_f >= stop_f:
                    islem_kapatilacak = True
                    hedefe_ulasti = False
                    kapanis_fiyat_degeri = stop_f
                elif anl_f <= kar_al_f:
                    islem_kapatilacak = True
                    hedefe_ulasti = True
                    kapanis_fiyat_degeri = kar_al_f
                
            if islem_kapatilacak:
                fark_yuzde = ((kapanis_fiyat_degeri - giris_f) / giris_f) if 'Long' in yon else ((giris_f - kapanis_fiyat_degeri) / giris_f)
                net_kar = miktar * KALDIRAC * fark_yuzde
                
                durum_metni = 'Kapandi (Kar)' if hedefe_ulasti else 'Kapandi (Zarar)'
                df.at[idx, 'Durum'] = durum_metni
                df.at[idx, 'Kapanis_Zamani'] = suan_tr
                df.at[idx, 'Net_Kar_Zarar'] = float(round(net_kar, 2))
                df.at[idx, 'Kapanis_Fiyati'] = float(round(kapanis_fiyat_degeri, 4))
                
                toplam_kasa, _, _, _ = bakiye_durumunu_getir(ortak_fiyat_havuzu)
                df.at[idx, 'Guncel_Kasa'] = float(round(toplam_kasa + net_kar, 2))
                
                islem_turu_etiket = "Hedef Kâr" if hedefe_ulasti else "Otomatik Stop"
                trade_aciklama = f"{islem_turu_etiket}: #{islem_id} {coin} ({'Kar' if hedefe_ulasti else 'Zarar'})"
                kasa_islem_ekle_deftere("Trade_Sonuc", float(round(net_kar, 2)), trade_aciklama)
                degisiklik_oldu = True
                
                mail_konu = f"🔔 Otomatik İşlem Raporu: #{islem_id} {coin} ({'Kâr' if hedefe_ulasti else 'Zarar'})"
                mail_icerik = f"""
                    <h3>İşlem Hedefe Ulaştı ve Otomatik Kapatıldı</h3>
                    <p><b>Kapanış Türü:</b> {islem_turu_etiket}</p>
                    <p><b>İşlem ID:</b> #{islem_id}</p>
                    <p><b>Coin:</b> {coin}</p>
                    <p><b>Yön:</b> {yon}</p>
                    <p><b>Net Kâr/Zarar:</b> {net_kar:+,.2f} $</p>
                    <p><b>Güncel Kasa:</b> {toplam_kasa + net_kar:,.2f} $</p>
                """
                gmail_bildirim_gonder(mail_konu, mail_icerik)
                
    if degisiklik_oldu:
        dataframe_guncelle_gsheets(df)
        elli_islem_arsiv_kontrol()

# --- ARAYÜZ AKIŞI ---
st.title("⚡ Pro Kripto & Canlı Piyasa Paneli (Ağırlıklı Ortalama Matris Puanı)")
elli_islem_arsiv_kontrol()

if 'kasa_islem_acik' not in st.session_state:
    st.session_state['kasa_islem_acik'] = False

if 'kasa_islem_turu' not in st.session_state:
    st.session_state['kasa_islem_turu'] = "Para Yatır"

if 'sadece_aktifleri_goster' not in st.session_state:
    st.session_state['sadece_aktifleri_goster'] = False

# --- TÜM VARLIKLAR VE TOTAL MARKET ANALİZİ (5 DAKİKALIK / 288 BAR) ---
tum_takip_edilenler = coinler + ['TOTAL']
islenen_ham_veriler = []
ortak_fiyat_havuzu = {} 

for sembol in tum_takip_edilenler:
    anlik_fiyat, nihai_puan, aktif_yon, y_yuzde = kurgusal_matris_hesapla(sembol)
    ortak_fiyat_havuzu[sembol] = anlik_fiyat 
    
    df_market = load_5min_market_data(sembol)
    stop_uzde, hedef_carpan = calculate_coin_atr_metrics(df_market, nihai_puan)

    if not df_market.empty and 'Open' in df_market.columns and 'Close' in df_market.columns:
        ilk_f = float(df_market.iloc[0]['Open'])
        son_f = float(df_market.iloc[-1]['Close'])
        gunluk_oran = ((son_f - ilk_f) / ilk_f) * 100.0
    else:
        gunluk_oran = 0.0

    islenen_ham_veriler.append({
        "sembol": sembol, "anlik_fiyat": anlik_fiyat, "nihai_puan": nihai_puan,
        "aktif_yon": aktif_yon, "y_yuzde": y_yuzde,
        "stop_uzde": stop_uzde, "hedef_carpan": hedef_carpan,
        "gunluk_oran": gunluk_oran, "df_market": df_market
    })

otomatik_stop_kar_kontrolu(ortak_fiyat_havuzu)

coin_ham_veriler = [d for d in islenen_ham_veriler if d["sembol"] != 'TOTAL']
total_ham_veri = [d for d in islenen_ham_veriler if d["sembol"] == 'TOTAL'][0]

usdt_puan_ort = sum([d["nihai_puan"] for d in coin_ham_veriler]) / len(coin_ham_veriler)

islenen_veriler = []
for data in coin_ham_veriler:
    sembol = data["sembol"]
    nihai_puan = data["nihai_puan"]
    aktif_yon = data["aktif_yon"]
    y_yuzde = data["y_yuzde"]
    k_yuzde = 100.0 - y_yuzde
    anlik_fiyat = data["anlik_fiyat"]
    stop_uzde = data["stop_uzde"]
    hedef_carpan = data["hedef_carpan"]
    gunluk_oran = data["gunluk_oran"]
    
    c_durum_led = "🟢" if (nihai_puan >= 50.0 and aktif_yon == "Long") else ("🔴" if (nihai_puan >= 50.0 and aktif_yon == "Short") else "🟡")
    u_durum_led = "🟢" if usdt_puan_ort >= 50.0 else "🟡"
    
    y_gorsel = max(0, min(10, int(round(y_yuzde / 10.0))))
    k_gorsel = 10 - y_gorsel
    yesil_top = "🟢" * y_gorsel
    kirmizi_top = "🔴" * k_gorsel
    detay_matris_html = '<div style="text-align: center; line-height: 1.2;"><div style="font-size: 15px; margin-bottom: 2px; letter-spacing: 1px;">' + yesil_top + kirmizi_top + '</div><div style="font-size: 11px; color: #495057; font-weight: 600;"><span style="color: #00FF00; display: inline-block; vertical-align: middle; width: 10px; height: 10px; background-color: #00FF00; border-radius: 50%; margin-right: 2px;"></span>%' + f"{y_yuzde:.1f}" + ' | <span style="color: #FF0000; display: inline-block; vertical-align: middle; width: 10px; height: 10px; background-color: #FF0000; border-radius: 50%; margin-left: 4px; margin-right: 2px;"></span>%' + f"{k_yuzde:.1f}" + '</div></div>'
    
    is_notr = (nihai_puan < 50.0 or aktif_yon == "Nötr")
    if is_notr:
        trend = "Nötr (Beklemede)"
        aktif_yon_turu = "Nötr"
    else:
        aktif_yon_turu = aktif_yon
        trend = f"Güçlü Trend {aktif_yon_turu}" if nihai_puan > 120.0 else f"{aktif_yon_turu} (Onaylı)"
        
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
        
    dom_html = '<div style="text-align: center;"><div style="font-size: 16px; margin-bottom: 2px; letter-spacing: 2px;">' + c_durum_led + u_durum_led + c_durum_led + '</div><div style="font-size: 10px; color: #495057; font-weight: 500;">C:' + c_durum_led + ' | U:' + u_durum_led + '</div></div>'
    
    if is_notr:
        puan_html = f'<div style="font-weight: bold; color: #6c757d;">{nihai_puan:.1f} / 200<br><span style="font-size: 10px;">(Nötr)</span></div>'
    else:
        p_renk = "#00FF00" if aktif_yon_turu == "Long" else "#FF0000"
        puan_html = f'<div style="font-weight: bold; color: {p_renk};">{nihai_puan:.1f} / 200<br><span style="font-size: 10px; color: #212529;">({aktif_yon_turu})</span></div>'
    
    basamak = 4 if anlik_fiyat < 10 else 2
    logo_html = f'<img src="{logo_urls.get(sembol, "")}" width="24" height="24">'
    
    if "Güçlü Trend" in trend:
        t_renk = "#00FF00" if "Long" in trend else "#FF0000"
        yon_html = f'<div style="background-color: {t_renk}; padding: 6px; border-radius: 6px; color: white; font-weight: bold;">🔥 {trend}</div>'
    elif "Long" in trend:
        yon_html = '<div style="background-color: #00FF00; padding: 6px; border-radius: 6px; color: white; font-weight: bold;">' + trend + '</div>'
    elif "Short" in trend:
        yon_html = '<div style="background-color: #FF0000; padding: 6px; border-radius: 6px; color: white; font-weight: bold;">' + trend + '</div>'
    else:
        yon_html = f'<div style="background-color: #ffc107; padding: 6px; border-radius: 6px; color: #212529; font-weight: bold;">{trend}</div>'
        
    sepet_orani = 0.0 if is_notr else round(50.0 + 50.0 * (((max(50.0, min(200.0, nihai_puan)) - 50.0) / 150.0) ** 1.4), 1)
    g_oran_str = f"<span style='color: {'#00FF00' if gunluk_oran >= 0 else '#FF0000'}; font-weight: bold;'>{gunluk_oran:+,.2f}%</span>"

    islenen_veriler.append({
        "Logo": logo_html, "Coin": sembol, "Fiyat": round(anlik_fiyat, basamak), 
        "Yon": yon_html, "Teyit_Sunumu": detay_matris_html, "Dom_Sunumu": dom_html, 
        "Matris_Puan_Sunumu": puan_html, "Gunluk_Oran": g_oran_str,
        "Kar_Al": round(hedef_fiyat, basamak), "Stopla": round(stop_fiyat, basamak), 
        "Skor": nihai_puan, "Sepet_Orani": sepet_orani,
        "Basamak": basamak, "Notr": is_notr, "Ham_Yon": trend, "Aktif_Yon": aktif_yon_turu,
        "Risk_Hedef_Metin": f"1 / {hedef_carpan:.1f}".replace('.', ',')
    })

islenen_veriler = sorted(islenen_veriler, key=lambda x: (1 if x["Notr"] else 0, -x["Skor"]))
toplam_kasa, efektif_kasa, mevcut_bakiye, aktif_yatirim_tutari = bakiye_durumunu_getir(ortak_fiyat_havuzu)

for v in islenen_veriler:
    v["Yatırım_Bedeli"] = f"{mevcut_bakiye * (v['Sepet_Orani'] / 100.0):,.2f} $"

# --- ÜST BİLGİ PANELİ ---
col_ust1, col_ust2, col_ust3, col_ust4, col_ust5, col_ust6 = st.columns([2, 2, 2, 2, 1.5, 1.2])
with col_ust1:
    st.markdown(f'<div class="metric-container"><p style="color: #495057; margin: 0px; font-size: 14px; font-weight: bold;">📊 Aktif Yatırım</p><h1 style="color: #0d6efd; margin: 5px 0px 0px 0px; font-size: 24px;">{aktif_yatirim_tutari:,.2f} $</h1></div>', unsafe_allow_html=True)
with col_ust2:
    st.markdown(f'<div class="metric-container"><p style="color: #495057; margin: 0px; font-size: 14px; font-weight: bold;">🟢 Boştaki Nakit</p><h1 style="color: #212529; margin: 5px 0px 0px 0px; font-size: 24px;">{mevcut_bakiye:,.2f} $</h1></div>', unsafe_allow_html=True)
with col_ust3:
    st.markdown(f'<div class="metric-container"><p style="color: #495057; margin: 0px; font-size: 14px; font-weight: bold;">💎 Efektif Kasa</p><h1 style="color: #212529; margin: 5px 0px 0px 0px; font-size: 24px;">{efektif_kasa:,.2f} $</h1></div>', unsafe_allow_html=True)
with col_ust4:
    st.markdown(f'<div class="metric-container"><p style="color: #495057; margin: 0px; font-size: 14px; font-weight: bold;">💰 Toplam Kasa</p><h1 style="color: #212529; margin: 5px 0px 0px 0px; font-size: 24px;">{toplam_kasa:,.2f} $</h1></div>', unsafe_allow_html=True)
with col_ust5:
    st.markdown('<div class="metric-container" style="padding: 11px !important;"><p style="color: #495057; margin: 0px; font-size: 13px; font-weight: bold;">👍 Kasa Sermaye</p>', unsafe_allow_html=True)
    if st.button("🗂️ Yatır / Çek", use_container_width=True):
        st.session_state['kasa_islem_acik'] = not st.session_state['kasa_islem_acik']
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
with col_ust6:
    st.write("")
    st.write("")
    if st.button("🔄 Yenile", use_container_width=True):
        st.rerun()

# --- KASA İŞLEMLERİ AÇILIR PANELİ ---
if st.session_state['kasa_islem_acik']:
    with st.container():
        st.markdown('<div style="background-color: #ffffff; padding: 20px; border: 2px solid #0d6efd; border-radius: 10px; margin-bottom: 20px;"><h4 style="margin-top: 0px; color: #0d6efd;">👍 Kasa Sermaye Yönetimi</h4>', unsafe_allow_html=True)
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
                tip_str = "Para_Yatir" if st.session_state['kasa_islem_turu'] == "Para Yatır" else "Para_Cek"
                basarili, mesaj = kasa_islem_ekle(tip_str, kasa_tutar, kasa_aciklama)
                if basarili: st.success(mesaj); st.session_state['kasa_islem_acik'] = False; time.sleep(1); st.rerun()
                else: st.error(mesaj)
        with col_islem2:
            if st.button("❌ Kapat", use_container_width=True): st.session_state['kasa_islem_acik'] = False; st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")

# --- ANA TABLO (GÜNLÜK ORAN İLE) ---
table_html = """
<table class="custom-table">
 <thead class="custom-table-header">
 <tr>
 <th>Logo</th><th>Coin<br>Adı</th><th>Güncel<br>Fiyat</th><th>Trend<br>Durumu</th>
 <th>Matris Teyit</th><th>Piyasa &<br>Dominans</th><th>Matris<br>Puanı</th><th>Günlük<br>Oran</th><th>Önerilen<br>Oran</th>
 <th>Yatırım<br>Tutarı</th><th>Kar Al<br>Hedefi</th><th>Stop<br>Seviyesi</th>
 <th>Risk / Hedef</th>
 </tr>
 </thead><tbody>
"""
for v in islenen_veriler:
    fiyat_str = f"{v['Fiyat']:,.4f}&nbsp;$" if v['Basamak'] == 4 else f"{v['Fiyat']:,.2f}&nbsp;$"
    kar_al_str = f"{v['Kar_Al']:,.4f}&nbsp;$" if v['Basamak'] == 4 else f"{v['Kar_Al']:,.2f}&nbsp;$"
    stopla_str = f"{v['Stopla']:,.4f}&nbsp;$" if v['Basamak'] == 4 else f"{v['Stopla']:,.2f}&nbsp;$"
    sepet_val = v['Sepet_Orani']
    val_str = f"%{sepet_val:.1f}" if sepet_val != int(sepet_val) else f"%{int(sepet_val)}"
    
    if v['Notr']: 
        oran_html = '<div style="background-color: rgba(255, 235, 59, 0.3); padding: 5px; font-weight: bold;">%0<br>(Beklemede)</div>'
    else:
        t_bg = "#00FF00" if "Long" in v["Ham_Yon"] else "#FF0000"
        t_tip = "Güçlü Trend" if "Güçlü Trend" in v['Ham_Yon'] else "Onaylı"
        oran_html = f'<div style="background-color: {t_bg}; color: white; padding: 5px; font-weight: bold;">{val_str}<br>({t_tip})</div>'

    table_html += f"<tr><td>{v['Logo']}</td><td>{v['Coin']}</td><td style='font-weight: bold; color: #0d6efd; background-color: rgba(13, 110, 253, 0.05);'>{fiyat_str}</td><td>{v['Yon']}</td><td>{v['Teyit_Sunumu']}</td><td>{v['Dom_Sunumu']}</td><td style='background-color: rgba(0,0,0,0.02);'>{v['Matris_Puan_Sunumu']}</td><td>{v['Gunluk_Oran']}</td><td>{oran_html}</td><td>{v['Yatırım_Bedeli']}</td><td>{kar_al_str}</td><td>{stopla_str}</td><td style='font-weight: bold; color: #d63384;'>{v['Risk_Hedef_Metin']}</td></tr>"
table_html += "</tbody></table>"
st.markdown(f'<div class="table-container">{table_html}</div>', unsafe_allow_html=True)

# --- İKİ SÜTUNLU YAPI: SOL (HIZLI İŞLEM) & SAĞ (TOTAL MARKET ÇİZGİ GRAFİK VE MATRİS LEDLERİ) ---
col_sol_panel, col_sag_panel = st.columns([1, 1])

with col_sol_panel:
    st.markdown("### 🚀 Hızlı İşlem Emri Ver (Senkronize Giriş)")
    df_gosterge = pd.DataFrame(islenen_veriler)
    df_islem_yapilabilir = df_gosterge[df_gosterge['Notr'] == False]
    coin_listesi = df_islem_yapilabilir['Coin'].tolist() if not df_islem_yapilabilir.empty else []

    if coin_listesi:
        secilen_coin = st.selectbox("İşleme Girmek İstediğiniz Coini Seçin:", coin_listesi, key="hizli_coin_secim")
    else:
        st.warning("Şu an işlem açmaya uygun coin bulunmuyor.")
        secilen_coin = None

    onerilen_oran_val, anlik_matris_puani, anlik_risk_hedef_metin, coin_verisii = 0.0, 0.0, "1 / 2,0", None
    if secilen_coin:
        coin_verisii = df_gosterge[df_gosterge['Coin'] == secilen_coin].iloc[0]
        onerilen_oran_val = float(coin_verisii['Sepet_Orani'])
        anlik_matris_puani = float(coin_verisii['Skor'])
        anlik_risk_hedef_metin = coin_verisii['Risk_Hedef_Metin']

    if 'last_selected_coin' not in st.session_state or st.session_state['last_selected_coin'] != secilen_coin:
        st.session_state['last_selected_coin'] = secilen_coin
        st.session_state['hizli_oran_slider'] = onerilen_oran_val
        st.session_state['hizli_manuel_tutar_input'] = round(mevcut_bakiye * (onerilen_oran_val / 100.0), 2)

    c_s1, c_s2 = st.columns(2)
    with c_s1:
        secilen_oran = st.slider("Yatırım Oranı (%):", 0.0, 100.0, 0.5, key="hizli_oran_slider", on_change=lambda: st.session_state.update({'hizli_manuel_tutar_input': round(mevcut_bakiye * (st.session_state['hizli_oran_slider'] / 100.0), 2)}))
    with c_s2:
        manuel_girilen_tutar = st.number_input("Yatırım Tutarı ($):", 0.0, float(max(100.0, mevcut_bakiye)), 10.0, key="hizli_manuel_tutar_input")

    st.markdown(f"💼 **Tutar:** `{manuel_girilen_tutar:,.2f} $` | **Boş Nakit:** `{mevcut_bakiye:,.2f} $`")

    if st.button("🚀 İşlemi Başlat ve Emri Al", use_container_width=True, key="hizli_islem_btn"):
        if coin_verisii is not None and coin_verisii['Notr']:
            st.error("⚠️ Nötr konumdaki coine işlem açılamaz!")
        elif coin_verisii is not None:
            basari, mesaj = yeni_islem_ekle(secilen_coin, coin_verisii['Aktif_Yon'], coin_verisii['Fiyat'], manuel_girilen_tutar, coin_verisii['Stopla'], coin_verisii['Kar_Al'], "Matris Kurgusu", anlik_matris_puani, anlik_risk_hedef_metin)
            if basari: st.success(mesaj); st.balloons(); time.sleep(1); st.rerun()
            else: st.error(mesaj)

with col_sag_panel:
    st.markdown("### 🌐 Total Market (5 Dakikalık Akış)")
    t_data = total_ham_veri
    t_df = t_data["df_market"]
    
    fig_total = go.Figure(data=[go.Scatter(
        x=t_df['timestamp'], y=t_df['Close'], mode='lines',
        line=dict(color='#2962FF', width=2)
    )])
    fig_total.update_layout(
        template="plotly_white", margin=dict(t=10, b=10, l=10, r=10), height=240,
        xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
    )
    st.plotly_chart(fig_total, use_container_width=True)

    t_puan = t_data["nihai_puan"]
    t_yon = t_data["aktif_yon"]
    t_fiyat = t_data["anlik_fiyat"]
    t_y_yuzde = t_data["y_yuzde"]
    t_k_yuzde = 100.0 - t_y_yuzde
    
    t_y_gorsel = max(0, min(10, int(round(t_y_yuzde / 10.0))))
    t_k_gorsel = 10 - t_y_gorsel
    t_detay_matris_html = '<div style="text-align: center; line-height: 1.2; margin-bottom: 6px;"><div style="font-size: 15px; margin-bottom: 2px; letter-spacing: 1px;">' + ("🟢" * t_y_gorsel) + ("🔴" * t_k_gorsel) + '</div><div style="font-size: 11px; color: #495057; font-weight: 600;"><span style="color: #00FF00; display: inline-block; vertical-align: middle; width: 10px; height: 10px; background-color: #00FF00; border-radius: 50%; margin-right: 2px;"></span>%' + f"{t_y_yuzde:.1f}" + ' | <span style="color: #FF0000; display: inline-block; vertical-align: middle; width: 10px; height: 10px; background-color: #FF0000; border-radius: 50%; margin-left: 4px; margin-right: 2px;"></span>%' + f"{t_k_yuzde:.1f}" + '</div></div>'
    
    t_renk = "#00FF00" if t_yon == "Long" else ("#FF0000" if t_yon == "Short" else "#ffc107")
    
    def periyot_degisim_hesapla(df, bar_sayisi):
        if df is None or len(df) < bar_sayisi:
            return 0.0
        ilk_f = float(df.iloc[-bar_sayisi]['Open'])
        son_f = float(df.iloc[-1]['Close'])
        return ((son_f - ilk_f) / ilk_f) * 100.0

    d_24 = periyot_degisim_hesapla(t_df, 288)
    d_16 = periyot_degisim_hesapla(t_df, 192)
    d_12 = periyot_degisim_hesapla(t_df, 144)
    d_4  = periyot_degisim_hesapla(t_df, 48)
    d_1  = periyot_degisim_hesapla(t_df, 12)

    def renkli_format(deger, etiket):
        renk = "#00FF00" if deger >= 0 else "#FF0000"
        return f'<span style="color: #212529 !important; font-weight: 600;">{etiket}:</span> <span style="color: {renk} !important; font-weight: bold;">{deger:+,.2f}%</span>'

    str_24 = renkli_format(d_24, "24 S")
    str_16 = renkli_format(d_16, "16 S")
    str_12 = renkli_format(d_12, "12 S")
    str_4  = renkli_format(d_4, "4 S")
    str_1  = renkli_format(d_1, "1 S")

    st.markdown(t_detay_matris_html, unsafe_allow_html=True)
    st.markdown(f"""
        <div style="background-color: #e9ecef; padding: 10px; border-radius: 6px; text-align: center; font-weight: bold; line-height: 1.6;">
        <span style="color: #212529 !important;">Piyasa Değeri:</span> <span style="color: #0d6efd !important;">${t_fiyat:,.0f}</span> | 
        <span style="color: #212529 !important;">Matris Puanı:</span> <span style="color: {t_renk} !important;">{t_puan:.1f} / 200 ({t_yon})</span><br>
        {str_24} &nbsp;|&nbsp; {str_16} &nbsp;|&nbsp; {str_12} &nbsp;|&nbsp; {str_4} &nbsp;|&nbsp; {str_1}
        </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# --- SANAL PORTFÖY VE AÇIK POZİSYONLAR ---
df_gecmis = islem_gecmisi_getir(sheet_guncelle=False)
if not df_gecmis.empty and 'Durum' in df_gecmis.columns:
    kapali_mask = df_gecmis['Durum'].astype(str).str.contains('kapandi|kar|zarar', case=False, na=False)
    acik_islem_listesi = df_gecmis[~kapali_mask]['Islem_ID'].tolist()
    
    col_pbas1, col_pbas2 = st.columns([2, 2])
    with col_pbas1: st.markdown("### 🛑 Pozisyon Kapat")
    with col_pbas2: pass

    with st.form(key="pozisyon_kapat_form"):
        col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns([1.2, 2.2, 1.5, 1.5, 1.5])
        with col_f1: kapatilacak_id = st.selectbox("ID:", acik_islem_listesi if acik_islem_listesi else [0], key="k_id")
        with col_f2: onay_verildi = st.checkbox(f"ID #{kapatilacak_id} onay", key="onay_chk")
        with col_f3: st.write(""); submit_kapat = st.form_submit_button("🔒 Kapat", use_container_width=True)
        with col_f4: st.write(""); submit_aktif = st.form_submit_button("Aktifler", use_container_width=True)
        with col_f5: st.write(""); submit_tum = st.form_submit_button("Tümü", use_container_width=True)
            
        if submit_aktif: st.session_state['sadece_aktifleri_goster'] = True; st.rerun()
        if submit_tum: st.session_state['sadece_aktifleri_goster'] = False; st.rerun()
            
        if submit_kapat:
            if acik_islem_listesi and kapatilacak_id in acik_islem_listesi:
                if onay_verildi:
                    kapanacak_coin = df_gecmis[df_gecmis['Islem_ID'] == kapatilacak_id]['Coin'].iloc[0]
                    kapatma_fiyati = ortak_fiyat_havuzu.get(kapanacak_coin, baz_fiyatlar.get(kapanacak_coin, 100.0))
                    b_durum, b_mesaj = manuel_islem_kapat(kapatilacak_id, kapatma_fiyati)
                    if b_durum: st.success(b_mesaj); time.sleep(1); st.rerun()
                    else: st.error(b_mesaj)
                else: st.warning("Onay kutusunu işaretleyin!")
            else: st.info("Kapatılacak açık işlem yok.")

    st.markdown("---")
    df_gosterilecek = df_gecmis.copy()
    if st.session_state['sadece_aktifleri_goster']:
        kapali_mask = df_gecmis['Durum'].astype(str).str.contains('kapandi|kar|zarar', case=False, na=False)
        df_gosterilecek = df_gecmis[~kapali_mask]
        st.info("ℹ️ Sadece Aktif pozisyonlar gösteriliyor.")

    anlik_fiyat_sozluk, anlik_kz_sozluk, hedef_kar_sozluk, olasi_stop_sozluk = {}, {}, {}, {}
    for idx, row in df_gecmis.iterrows():
        islem_id = row['Islem_ID']
        coin = row['Coin']
        giris_f = float(row['Giris_Fiyat'])
        miktar = float(row['Islem_Miktari'])
        kar_al_f = float(row['Kar_Al'])
        stop_f = float(row['Stop'])
        yon = row['Yon']
        
        anl_f = ortak_fiyat_havuzu.get(coin, baz_fiyatlar.get(coin, 100.0))
        anlik_fiyat_sozluk[islem_id] = anl_f
        
        if giris_f > 0 and kar_al_f > 0 and stop_f > 0:
            hedef_kar_sozluk[islem_id] = round(miktar * KALDIRAC * (((kar_al_f - giris_f) / giris_f) if 'Long' in yon else ((giris_f - kar_al_f) / giris_f)), 2)
            olasi_stop_sozluk[islem_id] = round(miktar * KALDIRAC * (((stop_f - giris_f) / giris_f) if 'Long' in yon else ((giris_f - stop_f) / giris_f)), 2)
        else:
            hedef_kar_sozluk[islem_id], olasi_stop_sozluk[islem_id] = 0.0, 0.0

        durum_str = str(row['Durum']).lower()
        if not ('kapandi' in durum_str or 'kar' in durum_str or 'zarar' in durum_str):
            fark_y = ((anl_f - giris_f) / giris_f) if 'Long' in yon else ((giris_f - anl_f) / giris_f)
            anlik_kz_sozluk[islem_id] = round(miktar * KALDIRAC * fark_y, 2)
        else:
            anlik_kz_sozluk[islem_id] = float(row['Net_Kar_Zarar'])

    df_gecmis_copy = df_gosterilecek.copy()
    df_gecmis_copy['Anlik_Fiyat_Deger'] = df_gecmis_copy['Islem_ID'].map(anlik_fiyat_sozluk)
    df_gecmis_copy['Canli_Beklenen_Kar'] = df_gecmis_copy['Islem_ID'].map(hedef_kar_sozluk)
    df_gecmis_copy['Canli_Olasi_Stop'] = df_gecmis_copy['Islem_ID'].map(olasi_stop_sozluk)
    df_gecmis_copy['Anlik_KZ_Deger'] = df_gecmis_copy['Islem_ID'].map(anlik_kz_sozluk)
    
    df_gecmis_copy['Yatırım_Bedeli'] = df_gecmis_copy['Islem_Miktari'].apply(lambda x: f"{float(x):,.2f}&nbsp;$")
    df_gecmis_copy['Beklenen_Kar_Str'] = df_gecmis_copy['Canli_Beklenen_Kar'].apply(lambda x: f"{float(x):,.2f}&nbsp;$")
    df_gecmis_copy['Olasi_Stop_Str'] = df_gecmis_copy['Canli_Olasi_Stop'].apply(lambda x: f"{float(x):,.2f}&nbsp;$")
    df_gecmis_copy['Kasa_Str'] = df_gecmis_copy['Guncel_Kasa'].apply(lambda x: f"{float(x):,.2f}&nbsp;$")

    def format_fiyat(fiyat_degeri, coin_adi):
        basamak = 4 if coin_adi == 'XRP/USDT' else 2
        return f"{float(fiyat_degeri):,.{basamak}f}&nbsp;$"

    df_gecmis_copy['Giris_Fiyat_Str'] = df_gecmis_copy.apply(lambda r: format_fiyat(r['Giris_Fiyat'], r['Coin']), axis=1)
    df_gecmis_copy['Stop_Str'] = df_gecmis_copy.apply(lambda r: format_fiyat(r['Stop'], r['Coin']), axis=1)
    df_gecmis_copy['Kar_Al_Str'] = df_gecmis_copy.apply(lambda r: format_fiyat(r['Kar_Al'], r['Coin']), axis=1)

    portfoy_html = """
    <table class="custom-table">
     <thead class="custom-table-header">
     <tr>
     <th>ID</th><th>Açılış</th><th>Logo</th><th>Coin</th><th>Yön</th>
     <th>Giriş</th><th>Anlık</th><th>Kapanış</th><th>Yatırım</th>
     <th>Stop</th><th>Hedef</th><th>Beklenen Kâr</th><th>Matris Puanı</th><th>Olası Stop</th>
     <th>Durum</th><th>Anlık K/Z</th><th>Kapanış Zamanı</th><th>Güncel Kasa</th>
     </tr>
     </thead><tbody>
    """

    for _, row in df_gecmis_copy.iterrows():
        l_url = logo_urls.get(row['Coin'], "")
        logo_h = f'<img src="{l_url}" width="24" height="24">'
        y_val = row['Yon']
        k_renk = "#00FF00" if "Long" in y_val else "#FF0000"
        yon_h = f'<div style="background-color: {k_renk}; padding: 6px; border-radius: 6px; color: white; font-weight: bold;">{y_val}</div>'
        
        fiyat_stil = "#00FF00" if row['Anlik_Fiyat_Deger'] > float(row['Giris_Fiyat']) else "#FF0000"
        anlik_fiyat_h = f'<div style="background-color: {fiyat_stil}; color: white; padding: 5px; font-weight: bold;">{format_fiyat(row["Anlik_Fiyat_Deger"], row["Coin"])}</div>'
        
        d_val = str(row['Durum']).lower()
        if not ('kapandi' in d_val or 'kar' in d_val or 'zarar' in d_val):
            kapanis_fiyat_h = '<div style="padding: 5px; color: #6c757d;">-</div>'
            durum_h = '<div style="background-color: #0000FF; color: white; padding: 4px; border-radius: 4px; font-weight: bold;">Aktif</div>'
        else:
            net_kz_degeri = float(row['Net_Kar_Zarar'])
            is_kar = net_kz_degeri >= 0
            k_stil = "#00FF00" if is_kar else "#FF0000"
            k_fiyat_val = float(row.get('Kapanis_Fiyati', 0.0) or row['Giris_Fiyat'])
            kapanis_fiyat_h = f'<div style="background-color: {k_stil}; color: white; padding: 5px; font-weight: bold;">{format_fiyat(k_fiyat_val, row["Coin"])}</div>'
            durum_h = f'<div style="background-color: {k_stil}; color: white; padding: 4px; border-radius: 4px; font-weight: bold;">{"Kâr" if is_kar else "Zarar"}</div>'

        kz_val = row['Anlik_KZ_Deger']
        kz_stil = "#00FF00" if kz_val >= 0 else "#FF0000"
        kz_h = f'<div style="background-color: {kz_stil}; color: white; padding: 5px; font-weight: bold; white-space: nowrap;">{kz_val:+,.2f}&nbsp;$</div>'

        matris_rh_hucre = str(row.get('Matris_Puan_RH', '145.2 (1 / 2.5)'))

        portfoy_html += f"<tr><td>{row['Islem_ID']}</td><td>{row['Acilis_Zamani']}</td><td>{logo_h}</td><td>{row['Coin']}</td><td>{yon_h}</td><td>{row['Giris_Fiyat_Str']}</td><td>{anlik_fiyat_h}</td><td>{kapanis_fiyat_h}</td><td>{row['Yatırım_Bedeli']}</td><td>{row['Stop_Str']}</td><td>{row['Kar_Al_Str']}</td><td>{row['Beklenen_Kar_Str']}</td><td style='font-weight: bold; color: #495057;'>{matris_rh_hucre}</td><td>{row['Olasi_Stop_Str']}</td><td>{durum_h}</td><td>{kz_h}</td><td>{row['Kapanis_Zamani']}</td><td>{row['Kasa_Str']}</td></tr>"
    portfoy_html += "</tbody></table>"
    st.markdown(f'<div class="table-container">{portfoy_html}</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("📊 Kapanan İşlemler Pasta Grafik & Para Akışı Analizi")
    
    kapananlar_df = df_gecmis[df_gecmis['Durum'].astype(str).str.contains('Kapandi|Kar|Zarar', case=False, na=False)]
    if not kapananlar_df.empty:
        karli_sayisi, zararli_sayisi = 0, 0
        toplam_kazanc_dolar, toplam_kayip_dolar = 0.0, 0.0
        for idx, r in kapananlar_df.iterrows():
            val = float(pd.to_numeric(r['Net_Kar_Zarar'], errors='coerce') or 0.0)
            if val >= 0: karli_sayisi += 1; toplam_kazanc_dolar += val
            else: zararli_sayisi += 1; toplam_kayip_dolar += abs(val)
            
        toplam_kapanan = len(kapananlar_df)
        karli_oran = (karli_sayisi / toplam_kapanan) * 100 if toplam_kapanan > 0 else 0
        zararli_oran = (zararli_sayisi / toplam_kapanan) * 100 if toplam_kapanan > 0 else 0
        net_fark_dolar = toplam_kazanc_dolar - toplam_kayip_dolar
        
        col_p1, col_p2, col_p3 = st.columns([1.5, 1, 1])
        with col_p1:
            df_pie = pd.DataFrame({'Durum': ['Kârlı İşlemler', 'Zararlı İşlemler'], 'Adet': [karli_sayisi, zararli_sayisi]})
            fig = px.pie(df_pie, names='Durum', values='Adet', hole=0.35, color='Durum', color_discrete_map={'Kârlı İşlemler': '#00FF00', 'Zararlı İşlemler': '#FF0000'})
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#212529', margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
            st.plotly_chart(fig, use_container_width=True)
            
        with col_p2:
            st.markdown("#### 📈 Strateji Metrikleri")
            st.metric("Toplam Kapanan İşlem", f"{toplam_kapanan} Adet")
            st.metric("🟢 Kârlı Kapanma", f"{karli_sayisi} Adet (%{karli_oran:.1f})")
            st.metric("🔴 Zararlı Kapanma", f"{zararli_sayisi} Adet (%{zararli_oran:.1f})")
            
        with col_p3:
            st.markdown("#### 💰 Para Değerleri Bloku")
            net_fark_renk = "#00FF00" if net_fark_dolar >= 0 else "#FF0000"
            st.markdown(
                '<div class="para-blogu">'
                '<p style="color: #00FF00; margin: 0px; font-size: 15px; font-weight: bold;">Toplam Kâr:</p>'
                f'<h3 style="color: #00FF00; margin: 0px 0px 10px 0px;">+{toplam_kazanc_dolar:,.2f} $</h3>'
                '<p style="color: #FF0000; margin: 0px; font-size: 15px; font-weight: bold;">Toplam Zarar:</p>'
                f'<h3 style="color: #FF0000; margin: 0px 0px 10px 0px;">-{toplam_kayip_dolar:,.2f} $</h3>'
                '<hr style="border-color: #ced4da; margin: 8px 0px;">'
                '<p style="color: #212529; margin: 0px; font-size: 14px;">Net Fark:</p>'
                f'<h3 style="color: {net_fark_renk}; margin: 0px;">{net_fark_dolar:+,.2f} $</h3>'
                '</div>',
                unsafe_allow_html=True
            )
            
    st.markdown("---")
    st.markdown("### 📁 50'şerli İşlem Arşivleri (Analiz Klasörü)")
    if os.path.exists(ARSIV_KLASORU):
        try:
            arsiv_dosyalari = os.listdir(ARSIV_KLASORU)
            if arsiv_dosyalari:
                arsiv_dosyalari.sort()
                secilen_arsiv = st.selectbox("Geçmiş 50'li Blok Dönemini Seçin:", arsiv_dosyalari, key="arsiv_select_50")
                if secilen_arsiv:
                    df_arsiv = pd.read_csv(os.path.join(ARSIV_KLASORU, secilen_arsiv), delimiter=';')
                    st.write(df_arsiv.to_html(escape=False, index=False), unsafe_allow_html=True)
            else: st.info("Henüz 50 işleme ulaşılmadı.")
        except: st.info("Arşiv yüklenirken bilgi alınamadı.")
    else: st.info("Arşiv klasörü henüz oluşturulmadı.")
