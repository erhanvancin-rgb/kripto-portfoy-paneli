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
from streamlit_autorefresh import st_autorefresh

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(page_title="Pro Kripto Canlı Akış Paneli", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

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
        if "gcp_service_account" in st.secrets:
            sec_dict = dict(st.secrets["gcp_service_account"])
            if "private_key" in sec_dict:
                sec_dict["private_key"] = sec_dict["private_key"].replace("\\n", "\n")
            client = gspread.service_account_from_dict(sec_dict)
        else:
            client = gspread.service_account(filename="credentials.json")
        return client.open(GOOGLE_SHEET_ADRESI).worksheet("Sayfa1")
    except Exception:
        return None

def islem_gecmisi_getir(sheet_guncelle=True):
    beklenen_kolonlar = ["Islem_ID", "Acilis_Zamani", "Coin", "Yon", "Zaman_Dilimi", "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Durum", "Net_Kar_Zarar", "Guncel_Kasa", "Kapanis_Zamani", "Kapanis_Fiyati"]
    sheet = google_sheets_baglan()
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
        sayisal_kolonlar = ['Giris_Fiyat', 'Islem_Miktari', 'Stop', 'Kar_Al', 'Net_Kar_Zarar', 'Guncel_Kasa', 'Kapanis_Fiyati']
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

def bakiye_durumunu_getir():
    df = islem_gecmisi_getir(sheet_guncelle=False)
    if df.empty: return BASLANGIC_BAKIYE, BASLANGIC_BAKIYE
    
    kapanan_df = df[df['Durum'].isin(['Kar', 'Zarar', 'Para_Yatir', 'Para_Cek'])]
    toplam_hareketler = pd.to_numeric(kapanan_df['Net_Kar_Zarar'], errors='coerce').fillna(0.0).sum() if not kapanan_df.empty else 0.0
    
    baz_bakiye = BASLANGIC_BAKIYE
    if os.path.exists(ARSIV_KLASORU):
        try:
            arsivler = os.listdir(ARSIV_KLASORU)
            if arsivler:
                arsivler.sort()
                son_arsiv_df = pd.read_csv(os.path.join(ARSIV_KLASORU, arsivler[-1]), delimiter=';')
                if not son_arsiv_df.empty: 
                    baz_bakiye = float(pd.to_numeric(son_arsiv_df.iloc[-1]['Guncel_Kasa'], errors='coerce') or BASLANGIC_BAKIYE)
        except: pass
    
    toplam_kasa = baz_bakiye + toplam_hareketler
    acik_df = df[df['Durum'] == 'Acik']
    acik_marjin = pd.to_numeric(acik_df['Islem_Miktari'], errors='coerce').fillna(0.0).sum() if not acik_df.empty else 0.0
    return float(toplam_kasa), float(toplam_kasa - acik_marjin)

def kasa_islem_ekle(islem_tipi, miktar, aciklama):
    toplam_kasa, mevcut_bakiye = bakiye_durumunu_getir()
    if islem_tipi == "Para_Cek" and miktar > mevcut_bakiye:
        return False, f"⚠️ Çekilmek istenen tutar ({miktar} $) boştaki nakit bakiyenizden ({mevcut_bakiye:.2f} $) büyük olamaz!"
    if miktar <= 0:
        return False, "⚠️ Tutar 0'dan büyük olmalıdır!"
        
    df = islem_gecmisi_getir()
    yeni_id = 1 if df.empty else int(pd.to_numeric(df['Islem_ID'], errors='coerce').max() or 0) + 1
    suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")
    
    net_tutar = miktar if islem_tipi == "Para_Yatir" else -miktar
    durum_etiketi = "Para_Yatir" if islem_tipi == "Para_Yatir" else "Para_Cek"
    
    yeni_kayit = pd.DataFrame([{
        "Islem_ID": yeni_id, "Acilis_Zamani": suan_tr,
        "Coin": f"KASA: {aciklama}", "Yon": durum_etiketi, "Zaman_Dilimi": "Sermaye İşlemi", "Giris_Fiyat": 0.0, 
        "Islem_Miktari": 0.0, "Stop": 0.0, "Kar_Al": 0.0, "Durum": durum_etiketi, 
        "Net_Kar_Zarar": round(net_tutar, 2), "Guncel_Kasa": round(toplam_kasa + net_tutar, 2), "Kapanis_Zamani": suan_tr, "Kapanis_Fiyati": 0.0
    }])
    df = pd.concat([df, yeni_kayit], ignore_index=True).drop_duplicates(subset=['Islem_ID'], keep='last')
    dataframe_guncelle_gsheets(df)
    elli_islem_arsiv_kontrol()
    return True, f"✅ Kasa başarıyla güncellendi! İşlem Tutarı: {miktar:,.2f} $"

def yeni_islem_ekle(coin, yon, giris_fiyat, sepet_orani_yuzde, stop, kar_al, zaman_dilimi):
    if "Nötr" in yon or "Beklemede" in yon: return False, "⚠️ Bu coin şu an Nötr konumda (Yeterli onay yok), işlem açılamaz!"
    toplam_kasa, mevcut_bakiye = bakiye_durumunu_getir()
    islem_miktari = mevcut_bakiye * (sepet_orani_yuzde / 100.0)
    if islem_miktari > mevcut_bakiye: return False, f"Bakiye yetersiz! Gereken: {islem_miktari:.2f} $"
    if islem_miktari < 10: return False, "İşlem miktarı 10 $'dan küçük olamaz!"
        
    df = islem_gecmisi_getir()
    yeni_id = 1 if df.empty else int(pd.to_numeric(df['Islem_ID'], errors='coerce').max() or 0) + 1
    suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")
    
    yeni_kayit = pd.DataFrame([{
        "Islem_ID": yeni_id, "Acilis_Zamani": suan_tr,
        "Coin": coin, "Yon": yon, "Zaman_Dilimi": zaman_dilimi, "Giris_Fiyat": giris_fiyat, 
        "Islem_Miktari": round(islem_miktari, 2), "Stop": stop, "Kar_Al": kar_al, "Durum": "Acik", 
        "Net_Kar_Zarar": 0.0, "Guncel_Kasa": round(toplam_kasa, 2), "Kapanis_Zamani": "-", "Kapanis_Fiyati": 0.0
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
    if row['Durum'] != 'Acik': return False, "Bu işlem kapalı!"
    try:
        giris_f = float(row['Giris_Fiyat'])
        miktar = float(row['Islem_Miktari'])
        fark_yuzde = ((anlik_kapatma_fiyati - giris_f) / giris_f) if 'Long' in row['Yon'] else ((giris_f - anlik_kapatma_fiyati) / giris_f)
        net_kar = miktar * KALDIRAC * fark_yuzde
        suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")
        
        durum_metni = 'Kar' if net_kar >= 0 else 'Zarar'
        df.at[idx[0], 'Durum'] = durum_metni
        df.at[idx[0], 'Kapanis_Zamani'] = suan_tr
        df.at[idx[0], 'Net_Kar_Zarar'] = float(round(net_kar, 2))
        df.at[idx[0], 'Kapanis_Fiyati'] = float(round(anlik_kapatma_fiyati, 4))
        
        baz_bakiye = BASLANGIC_BAKIYE
        if os.path.exists(ARSIV_KLASORU):
            try:
                arsivler = os.listdir(ARSIV_KLASORU)
                if arsivler:
                    arsivler.sort()
                    son_arsiv_df = pd.read_csv(os.path.join(ARSIV_KLASORU, arsivler[-1]), delimiter=';')
                    if not son_arsiv_df.empty: baz_bakiye = float(pd.to_numeric(son_arsiv_df.iloc[-1]['Guncel_Kasa'], errors='coerce') or BASLANGIC_BAKIYE)
            except: pass
        df['Net_Kar_Zarar'] = pd.to_numeric(df['Net_Kar_Zarar'], errors='coerce').fillna(0.0)
        kapanan_mask = df['Durum'].isin(['Kar', 'Zarar', 'Para_Yatir', 'Para_Cek'])
        df.loc[kapanan_mask, 'Guncel_Kasa'] = baz_bakiye + df.loc[kapanan_mask, 'Net_Kar_Zarar'].cumsum()
        dataframe_guncelle_gsheets(df)
        elli_islem_arsiv_kontrol()
        return True, f"Kapatıldı. K/Z: {net_kar:.2f} $"
    except Exception as e: return False, f"Hata: {str(e)}"

# --- ARAYÜZ AKIŞI ---
st.title("⚡ Pro Kripto & Canlı Piyasa Paneli")
elli_islem_arsiv_kontrol()

toplam_kasa, mevcut_bakiye = bakiye_durumunu_getir()

if 'trend_gecmisleri' not in st.session_state:
    st.session_state['trend_gecmisleri'] = {c: [] for c in coinler}

if 'risk_yuzde_potansi' not in st.session_state:
    st.session_state['risk_yuzde_potansi'] = 75.0

if 'kasa_islem_acik' not in st.session_state:
    st.session_state['kasa_islem_acik'] = False

if 'kasa_islem_turu' not in st.session_state:
    st.session_state['kasa_islem_turu'] = "Para Yatır"

islenen_ham_veriler = []
ortak_fiyat_havuzu = {} 

for sembol in coinler:
    anlik_fiyat, net_puan, baraj, m_yon, y_yuzde = detayli_matris_hesapla(sembol, st.session_state['risk_yuzde_potansi'])
    ortak_fiyat_havuzu[sembol] = anlik_fiyat 

    gecmis_liste = st.session_state['trend_gecmisleri'][sembol]
    gecmis_liste.append(m_yon)
    if len(gecmis_liste) > 20:
        gecmis_liste.pop(0)

    long_sayisi = gecmis_liste.count("Long")
    short_sayisi = gecmis_liste.count("Short")

    mevcut_uzunluk = len(gecmis_liste)
    gereken_onay = max(1, int(mevcut_uzunluk * 0.7))
    
    suanki_filtrelenmis_yon = "Notr"
    if long_sayisi >= gereken_onay:
        suanki_filtrelenmis_yon = "Long"
    elif short_sayisi >= gereken_onay:
        suanki_filtrelenmis_yon = "Short"

    islenen_ham_veriler.append({
        "sembol": sembol, "anlik_fiyat": anlik_fiyat, "net_puan": net_puan,
        "baraj": baraj, "m_yon": suanki_filtrelenmis_yon, "y_yuzde": y_yuzde
    })

usdt_net_puan_ort = sum([d["net_puan"] for d in islenen_ham_veriler]) / len(islenen_ham_veriler)

islenen_veriler = []
for data in islenen_ham_veriler:
    sembol = data["sembol"]
    net_puan = data["net_puan"]
    baraj = data["baraj"]
    y_yuzde = data["y_yuzde"]
    k_yuzde = 100.0 - y_yuzde
    anlik_fiyat = data["anlik_fiyat"]
    filtrelenmis_yon = data["m_yon"]
    
    c_durum_led = "🟢" if (net_puan >= baraj and net_puan >= 50.0) else ("🔴" if (net_puan <= -baraj and net_puan <= -50.0) else "🟡")
    u_durum_led = "🟢" if (usdt_net_puan_ort >= baraj and usdt_net_puan_ort >= 50.0) else ("🔴" if (usdt_net_puan_ort <= -baraj and usdt_net_puan_ort <= -50.0) else "🟡")

    y_gorsel = max(0, min(10, int(round(y_yuzde / 10.0))))
    k_gorsel = 10 - y_gorsel
    
    yesil_top = "🟢" * y_gorsel
    kirmizi_top = "🔴" * k_gorsel
    detay_matris_html = '<div style="text-align: center; line-height: 1.2;"><div style="font-size: 15px; margin-bottom: 2px; letter-spacing: 1px;">' + yesil_top + kirmizi_top + '</div><div style="font-size: 11px; color: #495057; font-weight: 600;"><span style="color: #00FF00; display: inline-block; vertical-align: middle; width: 10px; height: 10px; background-color: #00FF00; border-radius: 50%; margin-right: 2px;"></span>%' + f"{y_yuzde:.1f}" + ' | <span style="color: #FF0000; display: inline-block; vertical-align: middle; width: 10px; height: 10px; background-color: #FF0000; border-radius: 50%; margin-left: 4px; margin-right: 2px;"></span>%' + f"{k_yuzde:.1f}" + '</div></div>'

    is_notr = True
    trend = "Nötr (Beklemede)"
    aktif_yon_turu = "Nötr"

    if filtrelenmis_yon != "Notr" and abs(net_puan) >= baraj and abs(net_puan) >= 50.0:
        is_notr = False
        aktif_yon_turu = filtrelenmis_yon
        trend = f"Güçlü Trend {aktif_yon_turu}" if abs(net_puan) > 100.0 else f"{aktif_yon_turu} (Onaylı)"

    if aktif_yon_turu == "Long":
        stop_fiyat, hedef_fiyat = anlik_fiyat * 0.992, anlik_fiyat * 1.025
    elif aktif_yon_turu == "Short":
        stop_fiyat, hedef_fiyat = anlik_fiyat * 1.008, anlik_fiyat * 0.975
    else:
        stop_fiyat, hedef_fiyat = anlik_fiyat * 0.992, anlik_fiyat * 1.025
    
    dom_html = '<div style="text-align: center;"><div style="font-size: 16px; margin-bottom: 2px; letter-spacing: 2px;">' + c_durum_led + u_durum_led + c_durum_led + '</div><div style="font-size: 10px; color: #495057; font-weight: 500;">C:' + c_durum_led + ' | U:' + u_durum_led + '</div></div>'

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
    
    islenen_veriler.append({
        "Logo": logo_html, "Coin": sembol, "Fiyat": round(anlik_fiyat, basamak), 
        "Yon": yon_html, "Teyit_Sunumu": detay_matris_html, "Dom_Sunumu": dom_html, 
        "Kar_Al": round(hedef_fiyat, basamak), "Stopla": round(stop_fiyat, basamak), 
        "Skor": abs(net_puan) * 10000 + sum([ord(c) for c in sembol]) if not is_notr else 0, 
        "Basamak": basamak, "Notr": is_notr, "Ham_Yon": trend, "Matris_Orani": abs(net_puan), "Aktif_Yon": aktif_yon_turu
    })

islenen_veriler = sorted(islenen_veriler, key=lambda x: x["Skor"], reverse=True)
aktif_coinler = [v for v in islenen_veriler if not v["Notr"]]

if aktif_coinler:
    toplam_aktif_matris = sum([v["Matris_Orani"] for v in aktif_coinler])
    if toplam_aktif_matris <= 0: toplam_aktif_matris = 1.0
    for v in islenen_veriler:
        v["Sepet_Orani"] = round((v["Matris_Orani"] / toplam_aktif_matris) * 100.0, 1) if not v["Notr"] else 0.0
else:
    for v in islenen_veriler: v["Sepet_Orani"] = 0.0

for v in islenen_veriler:
    v["Yatırım_Bedeli"] = f"{mevcut_bakiye * (v['Sepet_Orani'] / 100.0):,.2f} $"

# --- EFEKTİF KASA HESAPLAMASI ---
df_gecmis_anlik = islem_gecmisi_getir(sheet_guncelle=False)
acik_islem_toplam_kz = 0.0
if not df_gecmis_anlik.empty and 'Durum' in df_gecmis_anlik.columns:
    acik_df_mask = df_gecmis_anlik['Durum'] == 'Acik'
    if acik_df_mask.any():
        for _, rw in df_gecmis_anlik[acik_df_mask].iterrows():
            c_SYM = rw['Coin']
            g_F = float(rw['Giris_Fiyat'])
            m_M = float(rw['Islem_Miktari'])
            y_Y = rw['Yon']
            anl_F = ortak_fiyat_havuzu.get(c_SYM, baz_fiyatlar.get(c_SYM, 100.0))
            f_y = ((anl_F - g_F) / g_F) if 'Long' in y_Y else ((g_F - anl_F) / g_F)
            acik_islem_toplam_kz += m_M * KALDIRAC * f_y
efektif_kasa = toplam_kasa + acik_islem_toplam_kz

# --- ÜST BİLGİ PANELİ ---
col_ust1, col_ust2, col_ust3, col_ust4, col_ust5 = st.columns([2, 2, 2, 2, 1.5])
with col_ust1:
    st.markdown(f"""
        <div class="metric-container">
            <p style="color: #495057; margin: 0px; font-size: 14px; font-weight: bold;">🟢 Mevcut Bakiye (Boş)</p>
            <h1 style="color: #212529; margin: 5px 0px 0px 0px; font-size: 24px;">{mevcut_bakiye:,.2f} $</h1>
        </div>
    """, unsafe_allow_html=True)
with col_ust2:
    efektif_renk = '#FF0000' if efektif_kasa - toplam_kasa < 0 else '#00FF00'
    st.markdown(f"""
        <div class="metric-container">
            <p style="color: #495057; margin: 0px; font-size: 14px; font-weight: bold;">💎 Efektif Kasa</p>
            <h1 style="color: #212529; margin: 5px 0px 0px 0px; font-size: 24px;">{efektif_kasa:,.2f} $</h1>
        </div>
    """, unsafe_allow_html=True)
with col_ust3:
    toplam_renk = '#FF0000' if toplam_kasa - BASLANGIC_BAKIYE < 0 else '#00FF00'
    st.markdown(f"""
        <div class="metric-container">
            <p style="color: #495057; margin: 0px; font-size: 14px; font-weight: bold;">💰 Toplam Kasa</p>
            <h1 style="color: #212529; margin: 5px 0px 0px 0px; font-size: 24px;">{toplam_kasa:,.2f} $</h1>
        </div>
    """, unsafe_allow_html=True)
with col_ust4:
    st.markdown("""
        <div class="metric-container" style="padding: 11px !important;">
            <p style="color: #495057; margin: 0px; font-size: 13px; font-weight: bold;">👝 Kasa Sermaye</p>
    """, unsafe_allow_html=True)
    if st.button("💸 Para Yatır / Çek", use_container_width=True):
        st.session_state['kasa_islem_acik'] = not st.session_state['kasa_islem_acik']
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
with col_ust5:
    st.write("")
    st.write("")
    if st.button("🔄 Yenile", use_container_width=True):
        st.rerun()

# --- KASA İŞLEMLERİ AÇILIR PANELİ ---
if st.session_state['kasa_islem_acik']:
    with st.container():
        st.markdown("""
            <div style="background-color: #ffffff; padding: 20px; border: 2px solid #0d6efd; border-radius: 10px; margin-bottom: 20px;">
                <h4 style="margin-top: 0px; color: #0d6efd;">👝 Kasa Sermaye Yönetimi (Para Yatırma / Çekme)</h4>
                <p style="font-weight: bold; margin-bottom: 8px;">İşlem Türünü Seçin:</p>
        """, unsafe_allow_html=True)
        
        col_sec1, col_sec2 = st.columns(2)
        with col_sec1:
            if st.button("🟢 Para Yatır (Kasaya Ekle)", use_container_width=True):
                st.session_state['kasa_islem_turu'] = "Para Yatır"
                st.rerun()
        with col_sec2:
            if st.button("🔴 Para Çek ( Kasadan Azalt )", use_container_width=True):
                st.session_state['kasa_islem_turu'] = "Para Çek"
                st.rerun()
                
        secili_tlik = st.session_state['kasa_islem_turu']
        if secili_tlik == "Para Yatır":
            st.markdown("<p style='color: #00FF00; font-weight: bold; margin-top: 5px;'>👉 Seçilen İşlem: 🟢 Para Yatır (Kasaya Ekle)</p>", unsafe_allow_html=True)
        else:
            st.markdown("<p style='color: #FF0000; font-weight: bold; margin-top: 5px;'>👉 Seçilen İşlem: 🔴 Para Çek ( Kasadan Azalt )</p>", unsafe_allow_html=True)
            
        col_k1, col_k2 = st.columns([1, 2])
        with col_k1:
            kasa_tutar = st.number_input("Tutar ($):", min_value=1.0, value=100.0, step=10.0, key="kasa_islem_tutar_input")
        with col_k2:
            kasa_aciklama = st.text_input("Açıklama / Not:", value="Ekstra sermaye", key="kasa_islem_aciklama_input")
            
        col_islem1, col_islem2 = st.columns([1, 4])
        with col_islem1:
            if st.button("💾 Onayla", use_container_width=True):
                tip_str = "Para_Yatir" if secili_tlik == "Para Yatır" else "Para_Cek"
                basarili, mesaj = kasa_islem_ekle(tip_str, kasa_tutar, kasa_aciklama)
                if basarili:
                    st.success(mesaj)
                    st.session_state['kasa_islem_acik'] = False
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(mesaj)
        with col_islem2:
            if st.button("❌ Kapat", use_container_width=True):
                st.session_state['kasa_islem_acik'] = False
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")

# --- HIZLI RİSK MODU SEÇİM BUTONLARI ---
st.markdown("<p style='font-weight: bold; margin-bottom: 5px;'>⚡ Hızlı Risk Modu Seçimi:</p>", unsafe_allow_html=True)
b_col1, b_col2, b_col3, b_col4, b_col5 = st.columns(5)

with b_col1:
    if st.button("%50 Esnek", use_container_width=True):
        st.session_state['risk_yuzde_potansi'] = 50.0
        st.rerun()
with b_col2:
    if st.button("%60 Dengeli", use_container_width=True):
        st.session_state['risk_yuzde_potansi'] = 60.0
        st.rerun()
with b_col3:
    if st.button("%75 Güvenli", use_container_width=True):
        st.session_state['risk_yuzde_potansi'] = 75.0
        st.rerun()
with b_col4:
    if st.button("%90 Güçlü", use_container_width=True):
        st.session_state['risk_yuzde_potansi'] = 90.0
        st.rerun()
with b_col5:
    if st.button("%100 Ultra", use_container_width=True):
        st.session_state['risk_yuzde_potansi'] = 100.0
        st.rerun()

risk_yuzdesi = st.slider("🎛️ Panel Güvenli Bölge Risk Oranı (%50 - %100):", min_value=50.0, max_value=100.0, step=1.0, key="risk_yuzde_potansi")

table_html = """
<table class="custom-table">
    <thead>
        <tr>
            <th>Logo</th><th>Coin<br>Adı</th><th>Güncel<br>Fiyat</th><th>Trend<br>Durumu</th>
            <th>Matris Teyit</th><th>Piyasa &<br>Dominans</th><th>Önerilen<br>Oran</th>
            <th>Yatırım<br>Tutarı</th><th>Kar Al<br>Hedefi</th><th>Stop<br>Seviyesi</th>
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

    table_html += f"<tr><td>{v['Logo']}</td><td>{v['Coin']}</td><td style='font-weight: bold; color: #0d6efd; background-color: rgba(13, 110, 253, 0.05);'>{fiyat_str}</td><td>{v['Yon']}</td><td>{v['Teyit_Sunumu']}</td><td>{v['Dom_Sunumu']}</td><td>{oran_html}</td><td>{v['Yatırım_Bedeli']}</td><td>{kar_al_str}</td><td>{stopla_str}</td></tr>"
table_html += "</tbody></table>"
st.markdown(table_html, unsafe_allow_html=True)

st.markdown("### 🛒 Hızlı İşlem Emri Ver")
df_gosterge = pd.DataFrame(islenen_veriler)

secilen_coin = st.selectbox("İşleme Girmek İstediğiniz Coini Seçin:", df_gosterge['Coin'].tolist(), key="secilen_coin_select")

if secilen_coin:
    coin_verisi = df_gosterge[df_gosterge['Coin'] == secilen_coin].iloc[0]
    onerilen_oran_val = float(coin_verisi['Sepet_Orani'])
    if coin_verisi['Notr']: st.warning("⚠️ Bu coin şu an Nötr konumda (Yeterli onay yok).")
    
    secilen_oran = st.slider("Yatırım Oranını Seçin (%):", min_value=0.0, max_value=100.0, value=onerilen_oran_val, step=0.5, key="oran_slider")
    hesaplanan_tutar = mevcut_bakiye * (secilen_oran / 100.0)
    st.markdown(f"💼 **Yatırım Tutarı:** `{hesaplanan_tutar:,.2f} $` &nbsp;&nbsp;|&nbsp;&nbsp; **Mevcut Nakit:** `{mevcut_bakiye:,.2f} $`", unsafe_allow_html=True)
    
    if st.button(f"🚀 {secilen_coin} İşlemini Başlat ve Emri Al", key="islem_baslat_btn"):
        st.info("🔄 İşlem sıraya alındı, veriler işleniyor...")
        basari, mesaj = yeni_islem_ekle(coin=secilen_coin, yon=coin_verisi['Aktif_Yon'], giris_fiyat=coin_verisi['Fiyat'], sepet_orani_yuzde=secilen_oran, stop=coin_verisi['Stopla'], kar_al=coin_verisi['Kar_Al'], zaman_dilimi="Multi-Timeframe Motoru")
        if basari: 
            st.success(mesaj)
            st.balloons()
        else: 
            st.error(mesaj)

st.markdown("---")
st.markdown("### 💼 Sanal Portföy ve Açık Pozisyonlar")

df_gecmis = islem_gecmisi_getir(sheet_guncelle=False)
if not df_gecmis.empty and 'Durum' in df_gecmis.columns:
    acik_islem_listesi = df_gecmis[df_gecmis['Durum'] == 'Acik']['Islem_ID'].tolist()
    if acik_islem_listesi:
        st.markdown("#### 🛑 İşlem Kapatma Paneli")
        col_kapat1, col_kapat2, col_kapat3 = st.columns([2, 2, 1])
        with col_kapat1: kapatilacak_id = st.selectbox("Kapatılacak İşlem ID:", acik_islem_listesi, key="kapat_id_select")
        with col_kapat2: onay_verildi = st.checkbox(f"ID #{kapatilacak_id} işlemini kapatmayı onaylıyorum", key="onay_chk")
        with col_kapat3:
            st.write("") 
            if st.button("🔒 İşlemi Sonlandır", key="kapat_btn"):
                if onay_verildi:
                    kapanacak_coin = df_gecmis[df_gecmis['Islem_ID'] == kapatilacak_id]['Coin'].iloc[0]
                    kapatma_fiyati = ortak_fiyat_havuzu.get(kapanacak_coin, baz_fiyatlar.get(kapanacak_coin, 100.0))
                    b_durum, b_mesaj = manuel_islem_kapat(kapatilacak_id, kapatma_fiyati)
                    if b_durum: st.success(b_mesaj)
                    else: st.error(b_mesaj)
                else: st.warning("Onay kutusunu işaretleyin!")
        st.markdown("---")

    df_gecmis_copy = df_gecmis.copy()
    anlik_fiyat_sozluk, anlik_kz_sozluk, hedef_kar_sozluk, olasi_stop_sozluk = {}, {}, {}, {}
    for idx, row in df_gecmis_copy.iterrows():
        islem_id = row['Islem_ID']
        coin = row['Coin']
        giris_f = float(row['Giris_Fiyat'])
        miktar = float(row['Islem_Miktari'])
        kar_al_f = float(row['Kar_Al'])
        stop_f = float(row['Stop'])
        yon = row['Yon']
        
        anlik_f = ortak_fiyat_havuzu.get(coin, baz_fiyatlar.get(coin, 100.0))
        anlik_fiyat_sozluk[islem_id] = anlik_f
        
        if giris_f > 0 and kar_al_f > 0 and stop_f > 0:
            hedef_kar_sozluk[islem_id] = round(miktar * KALDIRAC * (((kar_al_f - giris_f) / giris_f) if 'Long' in yon else ((giris_f - kar_al_f) / giris_f)), 2)
            olasi_stop_sozluk[islem_id] = round(miktar * KALDIRAC * (((stop_f - giris_f) / giris_f) if 'Long' in yon else ((giris_f - stop_f) / giris_f)), 2)
        else:
            hedef_kar_sozluk[islem_id], olasi_stop_sozluk[islem_id] = 0.0, 0.0

        if row['Durum'] == 'Acik':
            fark_y = ((anlik_f - giris_f) / giris_f) if 'Long' in yon else ((giris_f - anlik_f) / giris_f)
            anlik_kz_sozluk[islem_id] = round(miktar * KALDIRAC * fark_y, 2)
        else:
            anlik_kz_sozluk[islem_id] = float(row['Net_Kar_Zarar'])

    df_gecmis_copy['Anlik_Fiyat_Deger'] = df_gecmis_copy['Islem_ID'].map(anlik_fiyat_sozluk)
    df_gecmis_copy['Hedef_Kar'] = df_gecmis_copy['Islem_ID'].map(hedef_kar_sozluk)
    df_gecmis_copy['Olasi_Stop'] = df_gecmis_copy['Islem_ID'].map(olasi_stop_sozluk)
    df_gecmis_copy['Anlik_KZ_Deger'] = df_gecmis_copy['Islem_ID'].map(anlik_kz_sozluk)
    
    df_gecmis_copy['Yatırım_Bedeli'] = df_gecmis_copy['Islem_Miktari'].apply(lambda x: f"{float(x):,.2f}&nbsp;$")
    df_gecmis_copy['Hedef_Kar_Str'] = df_gecmis_copy['Hedef_Kar'].apply(lambda x: f"{float(x):,.2f}&nbsp;$")
    df_gecmis_copy['Olasi_Stop_Str'] = df_gecmis_copy['Olasi_Stop'].apply(lambda x: f"{float(x):,.2f}&nbsp;$")
    df_gecmis_copy['Kasa_Str'] = df_gecmis_copy['Guncel_Kasa'].apply(lambda x: f"{float(x):,.2f}&nbsp;$")

    def format_fiyat(fiyat_degeri, coin_adi):
        basamak = 4 if coin_adi == 'XRP/USDT' else 2
        return f"{float(fiyat_degeri):,.{basamak}f}&nbsp;$"

    df_gecmis_copy['Giris_Fiyat_Str'] = df_gecmis_copy.apply(lambda r: format_fiyat(r['Giris_Fiyat'], r['Coin']), axis=1)
    df_gecmis_copy['Stop_Str'] = df_gecmis_copy.apply(lambda r: format_fiyat(r['Stop'], r['Coin']), axis=1)
    df_gecmis_copy['Kar_Al_Str'] = df_gecmis_copy.apply(lambda r: format_fiyat(r['Kar_Al'], r['Coin']), axis=1)

    def format_yon_hucre(y):
        if "Güçlü Trend" in y:
            k_renk = "#00FF00" if "Long" in y else "#FF0000"
            return f'<div style="background-color: {k_renk}; padding: 6px; border-radius: 6px; color: white; font-weight: bold;">{y}</div>'
        elif "Long" in y:
            return '<div style="background-color: #00FF00; padding: 6px; border-radius: 6px; color: white; font-weight: bold;">' + y + '</div>'
        elif "Short" in y:
            return '<div style="background-color: #FF0000; padding: 6px; border-radius: 6px; color: white; font-weight: bold;">' + y + '</div>'
        else:
            return f'<div style="background-color: #ffc107; padding: 6px; border-radius: 6px; color: #212529; font-weight: bold;">{y}</div>'

    portfoy_html = """
    <table class="custom-table">
        <thead>
            <tr>
                <th>ID</th><th>Açılış<br>Zamanı</th><th>Logo</th><th>Coin</th><th>İşlem<br>Yönü</th>
                <th>Giriş<br>Fiyatı</th><th>Anlık<br>Fiyat</th><th>Kapanış<br>Fiyatı</th><th>Yatırım<br>Tutarı</th>
                <th>Stop<br>Seviyesi</th><th>Kar Al<br>Hedefi</th><th>Beklenen<br>Kar</th><th>Olası<br>Stop</th>
                <th>İşlem<br>Durumu</th><th>Anlık<br>K/Z</th><th>Kapanış<br>Zamanı</th><th>Güncel<br>Kasa</th>
            </tr>
        </thead><tbody>
    """

    for _, row in df_gecmis_copy.iterrows():
        l_url = logo_urls.get(row['Coin'], "")
        logo_h = f'<img src="{l_url}" width="24" height="24">'
        yon_h = format_yon_hucre(row['Yon'])
        
        fiyat_stil = "#00FF00" if row['Anlik_Fiyat_Deger'] > float(row['Giris_Fiyat']) else "#FF0000"
        anlik_fiyat_h = f'<div style="background-color: {fiyat_stil}; color: white; padding: 5px; font-weight: bold;">{format_fiyat(row["Anlik_Fiyat_Deger"], row["Coin"])}</div>'
        
        d_val = row['Durum']
        if d_val == 'Acik':
            kapanis_fiyat_h = '<div style="padding: 5px; color: #6c757d;">-</div>'
            durum_h = '<div style="background-color: #0000FF; color: white; padding: 4px; border-radius: 4px; font-weight: bold;">Aktif</div>'
        elif d_val in ['Para_Yatir', 'Para_Cek']:
            kapanis_fiyat_h = '<div style="padding: 5px; color: #6c757d;">-</div>'
            p_renk = "#00FF00" if d_val == 'Para_Yatir' else "#FF0000"
            p_etiket = "Para Yatırma" if d_val == 'Para_Yatir' else "Para Çekme"
            durum_h = f'<div style="background-color: {p_renk}; color: white; padding: 4px; border-radius: 4px; font-weight: bold;">{p_etiket}</div>'
        else:
            net_kz_degeri = float(row['Net_Kar_Zarar'])
            is_kar = net_kz_degeri >= 0
            k_stil = "#00FF00" if is_kar else "#FF0000"
            
            sheet_kapanis_f = float(row.get('Kapanis_Fiyati', 0.0) or 0.0)
            if sheet_kapanis_f > 0:
                k_fiyat_val = sheet_kapanis_f
            else:
                g_fiyat = float(row['Giris_Fiyat'])
                islem_mik = float(row['Islem_Miktari'])
                yon_str = str(row['Yon'])
                if islem_mik > 0 and g_fiyat > 0:
                    fark_yuzdesi = net_kz_degeri / (islem_mik * KALDIRAC)
                    if 'Long' in yon_str: k_fiyat_val = g_fiyat * (1 + fark_yuzdesi)
                    else: k_fiyat_val = g_fiyat * (1 - fark_yuzdesi)
                else: k_fiyat_val = g_fiyat

            k_fiyat_str = format_fiyat(k_fiyat_val, row['Coin'])
            kapanis_fiyat_h = f'<div style="background-color: {k_stil}; color: white; padding: 5px; font-weight: bold;">{k_fiyat_str}</div>'
            durum_etiketi = "Kâr" if is_kar else "Zarar"
            durum_h = f'<div style="background-color: {k_stil}; color: white; padding: 4px; border-radius: 4px; font-weight: bold;">{durum_etiketi}</div>'

        kz_val = row['Anlik_KZ_Deger']
        kz_stil = "#00FF00" if kz_val >= 0 else "#FF0000"
        kz_h = f'<div style="background-color: {kz_stil}; color: white; padding: 5px; font-weight: bold; white-space: nowrap;">{kz_val:+,.2f}&nbsp;$</div>'

        portfoy_html += f"<tr><td>{row['Islem_ID']}</td><td>{row['Acilis_Zamani']}</td><td>{logo_h}</td><td>{row['Coin']}</td><td>{yon_h}</td><td>{row['Giris_Fiyat_Str']}</td><td>{anlik_fiyat_h}</td><td>{kapanis_fiyat_h}</td><td>{row['Yatırım_Bedeli']}</td><td>{row['Stop_Str']}</td><td>{row['Kar_Al_Str']}</td><td>{row['Hedef_Kar_Str']}</td><td>{row['Olasi_Stop_Str']}</td><td>{durum_h}</td><td>{kz_h}</td><td>{row['Kapanis_Zamani']}</td><td>{row['Kasa_Str']}</td></tr>"
    portfoy_html += "</tbody></table>"
    st.markdown(portfoy_html, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("📊 Kapanan İşlemler Pasta Grafik & Para Akışı Analizi")
    kapananlar_df = df_gecmis[df_gecmis['Durum'].isin(['Kar', 'Zarar'])]
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
            st.markdown(f"""
            <div class="para-blogu">
                <p style="color: #00FF00; margin: 0px; font-size: 15px; font-weight: bold;">Toplam Kâr:</p>
                <h3 style="color: #00FF00; margin: 0px 0px 10px 0px;">+{toplam_kazanc_dolar:,.2f} $</h3>
                <p style="color: #FF0000; margin: 0px; font-size: 15px; font-weight: bold;">Toplam Zarar:</p>
                <h3 style="color: #FF0000; margin: 0px 0px 10px 0px;">-{toplam_kayip_dolar:,.2f} $</h3>
                <hr style="border-color: #ced4da; margin: 8px 0px;">
                <p style="color: #212529; margin: 0px; font-size: 14px;">Net Fark:</p>
                <h3 style="color: {net_fark_renk}; margin: 0px;">{net_fark_dolar:+,.2f} $</h3>
            </div>
            """, unsafe_allow_html=True)
            
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
    else:
        st.info("Henüz kapanmış işlem bulunmuyor.")
else: 
    st.info("ℹ️ Henüz açılmış bir sanal pozisyonunuz bulunmuyor.")
