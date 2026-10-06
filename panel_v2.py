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

def makro_kline_analiz(symbol_or_type, interval_str="1h", limit_adet=1200):
    headers = {'User-Agent': 'Mozilla/5.0'}
    ts = int(time.time() * 1000)
    # Eğer symbol_or_type 'TOTAL' veya 'USDT.D' ise simüle edelim ya da Binance genel proxy verisi kullanalım
    try:
        # Gerçek Binance sembolleri üzerinden simüle veya doğrudan kline çekme
        url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval={interval_str}&limit={limit_adet}&_t={ts}"
        r = requests.get(url, headers=headers, timeout=2.0)
        if r.status_code == 200:
            data = r.json()
            yesil, kirmizi = 0, 0
            for bar in data:
                o, c = float(bar[1]), float(bar[4])
                if symbol_or_type == 'USDT.D':
                    # USDT.D için ters mantık (düşüş yeşil sayılır)
                    if c < o: yesil += 1
                    elif c > o: kirmizi += 1
                else:
                    if c > o: yesil += 1
                    elif c < o: kirmizi += 1
            toplam = yesil + kirmizi
            puan = (yesil / toplam * 100.0) if toplam > 0 else 50.0
            return puan
    except: pass
    return 76.0 # Varsayılan güvenli skor

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
    beklenen_kolonlar = ["Islem_ID", "Acilis_Zamani", "Coin", "Yon", "Zaman_Dilimi", "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Durum", "Net_Kar_Zarar", "Guncel_Kasa", "Kapanis_Zamani", "Kapanis_Fiyati"]
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
        sayisal_kolonlar = ['Giris_Fiyat', 'Islem_Miktari', 'Stop', 'Kar_Al', 'Net_Kar_Zarar', 'Guncel_Kasa', 'Kapanis_Fiyati']
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
    
    acik_df = df_trade[df_trade['Durum'] == 'Acik'] if not df_trade.empty else pd.DataFrame()
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

def yeni_islem_ekle(coin, yon, giris_fiyat, sepet_orani_yuzde, stop, kar_al, zaman_dilimi):
    if "Nötr" in yon or "Beklemede" in yon: return False, "⚠️ Bu coin şu an Nötr konumda, işlem açılamaz!"
    _, _, mevcut_bakiye, _ = bakiye_durumunu_getir()
    islem_miktari = mevcut_bakiye * (sepet_orani_yuzde / 100.0)
    if islem_miktari > mevcut_bakiye: return False, f"Bakiye yetersiz! Gereken: {islem_miktari:.2f} $"
    if islem_miktari < 10: return False, "İşlem miktarı 10 $'dan küçük olamaz!"
        
    df = islem_gecmisi_getir()
    yeni_id = 1 if df.empty else int(pd.to_numeric(df['Islem_ID'], errors='coerce').max() or 0) + 1
    suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")
    
    toplam_kasa, _, _, _ = bakiye_durumunu_getir()
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
        
        durum_metni = 'Kapandi (Kar)' if net_kar >= 0 else 'Kapandi (Zarar)'
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
        return True, f"Kapatıldı. K/Z: {net_kar:.2f} $"
    except Exception as e: return False, f"Hata: {str(e)}"

# --- OTOMATİK STOP VE KÂR AL (TP) KONTROL MEKANİZMASI ---
def otomatik_pozisyon_kontrolu(ortak_fiyat_havuzu):
    df = islem_gecmisi_getir(sheet_guncelle=False)
    if df.empty or 'Durum' not in df.columns: return
    
    acik_pozlar = df[df['Durum'] == 'Acik']
    if acik_pozlar.empty: return
    
    degisiklik_oldu = False
    for _, row in acik_pozlar.iterrows():
        is_id = int(row['Islem_ID'])
        coin = row['Coin']
        yon = row['Yon']
        stop_f = float(row['Stop'])
        kar_al_f = float(row['Kar_Al'])
        
        anlik_f = ortak_fiyat_havuzu.get(coin, baz_fiyatlar.get(coin, 0.0))
        if anlik_f <= 0: continue
        
        kapat_gerekli = False
        kapanis_fiyat_degeri = anlik_f
        
        if 'Long' in yon:
            if stop_f > 0 and anlik_f <= stop_f:
                kapat_gerekli = True
                kapanis_fiyat_degeri = stop_f
            elif kar_al_f > 0 and anlik_f >= kar_al_f:
                kapat_gerekli = True
                kapanis_fiyat_degeri = kar_al_f
        elif 'Short' in yon:
            if stop_f > 0 and anlik_f >= stop_f:
                kapat_gerekli = True
                kapanis_fiyat_degeri = stop_f
            elif kar_al_f > 0 and anlik_f <= kar_al_f:
                kapat_gerekli = True
                kapanis_fiyat_degeri = kar_al_f
                
        if kapat_gerekli:
            manuel_islem_kapat(is_id, kapanis_fiyat_degeri)
            degisiklik_oldu = True
            
    if degisiklik_oldu:
        st.toast("⚡ Otomatik Stop/TP Kontrolü: Hedefe ulaşan pozisyonlar otomatik kapatıldı!", icon="🚨")

# --- ARAYÜZ AKIŞI ---
st.title("⚡ Pro Kripto & Canlı Piyasa Paneli")
elli_islem_arsiv_kontrol()

if 'trend_gecmisleri' not in st.session_state:
    st.session_state['trend_gecmisleri'] = {c: [] for c in coinler}

if 'risk_yuzde_potansi' not in st.session_state:
    st.session_state['risk_yuzde_potansi'] = 75.0

if 'kasa_islem_acik' not in st.session_state:
    st.session_state['kasa_islem_acik'] = False

if 'kasa_islem_turu' not in st.session_state:
    st.session_state['kasa_islem_turu'] = "Para Yatır"

if 'sadece_aktifleri_goster' not in st.session_state:
    st.session_state['sadece_aktifleri_goster'] = False

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
        "sembol": sembol, "anlik_fiyat
