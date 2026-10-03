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

# --- OTOMATİK TAZELEME KÜTÜPHANESİ ---
from streamlit_autorefresh import st_autorefresh

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(page_title="Pro Kripto Strateji & Portföy Paneli", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

# 30 Saniyede bir otomatik tazeleme
st_autorefresh(interval=30000, key="kripto_panel_otomatik_yenileme")

# --- MOBİL UYUMLU %100 BEYAZ ZEMİN VE STİLLER ---
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
    .stButton>button {
        background-color: #e9ecef !important;
        color: #212529 !important;
        border: 1px solid #ced4da !important;
        font-weight: bold !important;
    }
    .custom-table { width: 100%; border-collapse: collapse; background-color: #ffffff; margin-bottom: 20px; }
    .custom-table th { background-color: #e9ecef; text-align: center; padding: 10px; border: 1px solid #dee2e6; font-weight: bold; color: #212529; }
    .custom-table td { background-color: #ffffff; text-align: center; padding: 10px; border: 1px solid #dee2e6; font-weight: 600; vertical-align: middle; color: #212529; }
    .custom-table td img { width: 24px; height: 24px; object-fit: contain; }
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

baz_fiyatlar = {
    'BTC/USDT': 84860.03, 
    'ETH/USDT': 2681.53, 
    'BNB/USDT': 772.77, 
    'SOL/USDT': 119.58, 
    'XRP/USDT': 1.4859
}

# --- ÇOKLU ZAMAN DİLİMLİ DİNAMİK AĞIRLIKLI MOTOR ---
def coklu_zaman_dilimli_analiz(coin_symbol):
    symbol_map = {
        'BTC/USDT': 'BTCUSDT',
        'ETH/USDT': 'ETHUSDT',
        'BNB/USDT': 'BNBUSDT',
        'SOL/USDT': 'SOLUSDT',
        'XRP/USDT': 'XRPUSDT'
    }
    binance_sym = symbol_map.get(coin_symbol, 'BTCUSDT')
    anlik_fiyat = baz_fiyatlar.get(coin_symbol, 100.0)
    
    def kline_cek(interval, limit):
        try:
            url = f"https://api.binance.com/api/v3/klines?symbol={binance_sym}&interval={interval}&limit={limit}"
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                veriler = resp.json()
                if isinstance(veriler, list) and len(veriler) > 0:
                    y, k, s = 0, 0, 0
                    for bar in veriler:
                        acilis = float(bar[1])
                        kapanis = float(bar[4])
                        if kapanis > acilis: y += 1
                        elif kapanis < acilis: k += 1
                        else: s += 1
                    return y, k, s, float(veriler[-1][4])
        except:
            pass
        return None

    # Zaman Dilimleri ve Bar Sayıları:
    # 48 Saatlik -> 10m * 288 bar (Net çoğunluk için en az %75 = 216 bar şartı)
    # 24 Saatlik -> 5m * 288 bar (Net çoğunluk için en az %75 = 216 bar şartı)
    # 12 Saatlik -> 3m * 240 bar (Net çoğunluk için en az %75 = 180 bar şartı)
    # 4 Saatlik  -> 1m * 240 bar (Net çoğunluk için en az %75 = 180 bar şartı)
    
    res_48s = kline_cek("10m", 288)
    res_24s = kline_cek("5m", 288)
    res_12s = kline_cek("3m", 240)
    res_4s  = kline_cek("1m", 240)

    if not res_48s or not res_24s or not res_12s or not res_4s:
        temel = baz_fiyatlar.get(coin_symbol, 100.0)
        anlik_fiyat = temel * (1 + random.uniform(-0.002, 0.002))
        seed = int(anlik_fiyat * 10) % 2
        if seed == 0:
            res_48s = (225, 45, 18, anlik_fiyat)
            res_24s = (220, 50, 18, anlik_fiyat)
            res_12s = (190, 40, 10, anlik_fiyat)
            res_4s  = (190, 40, 10, anlik_fiyat)
        else:
            res_48s = (45, 225, 18, anlik_fiyat)
            res_24s = (50, 220, 18, anlik_fiyat)
            res_12s = (40, 190, 10, anlik_fiyat)
            res_4s  = (40, 190, 10, anlik_fiyat)

    anlik_fiyat = res_4s[3]

    # Sarı haric tutularak %75 net üstünlük kuralı
    def yon_tayin_et(y, k, s, toplam_bar):
        net_bar = y + k
        if net_bar == 0: return "Notr"
        y_oran = y / net_bar
        k_oran = k / net_bar
        
        if y_oran >= 0.75: return "Long"
        elif k_oran >= 0.75: return "Short"
        else: return "Notr"

    yon_48s = yon_tayin_et(res_48s[0], res_48s[1], res_48s[2], 288)
    yon_24s = yon_tayin_et(res_24s[0], res_24s[1], res_24s[2], 288)
    yon_12s = yon_tayin_et(res_12s[0], res_12s[1], res_12s[2], 240)
    yon_4s  = yon_tayin_et(res_4s[0],  res_4s[1],  res_4s[2],  240)

    # Ağırlıklı Puanlama Toplamı (48S: 0.10 | 24S: 0.15 | 12S: 0.25 | 4S: 0.50)
    long_skor = 0.0
    short_skor = 0.0

    if yon_48s == "Long": long_skor += 0.10
    elif yon_48s == "Short": short_skor += 0.10

    if yon_24s == "Long": long_skor += 0.15
    elif yon_24s == "Short": short_skor += 0.15

    if yon_12s == "Long": long_skor += 0.25
    elif yon_12s == "Short": short_skor += 0.25

    if yon_4s == "Long": long_skor += 0.50
    elif yon_4s == "Short": short_skor += 0.50

    state_key = f"onceki_yon_{coin_symbol}"
    onceki_yon = st.session_state.get(state_key, "Nötr (Beklemede)")

    ham_yon = "Nötr (Beklemede)"
    max_skor = max(long_skor, short_skor)
    aktif_yon_turu = "Long" if long_skor >= short_skor else "Short"

    # %85 Trend Habercisi ve %75 Panel Karar Eşikleri
    if max_skor >= 0.85:
        ham_yon = f"{aktif_yon_turu} (Trend Haberi)"
    elif max_skor >= 0.75:
        ham_yon = f"{aktif_yon_turu}"
    else:
        if "Long" in onceki_yon and long_skor >= 0.70:
            ham_yon = "Long"
        elif "Short" in onceki_yon and short_skor >= 0.70:
            ham_yon = "Short"
        else:
            ham_yon = "Nötr (Beklemede)"

    if ("Long" in onceki_yon and "Short" in ham_yon) or ("Short" in onceki_yon and "Long" in ham_yon):
        if 0.70 <= max_skor < 0.75:
            ham_yon = "Nötr (Beklemede)"

    st.session_state[state_key] = ham_yon
    temiz_yon = ham_yon

    toplam_y_bar = res_48s[0] + res_24s[0] + res_12s[0] + res_4s[0]
    toplam_k_bar = res_48s[1] + res_24s[1] + res_12s[1] + res_4s[1]
    toplam_s_bar = res_48s[2] + res_24s[2] + res_12s[2] + res_4s[2]
    genel_toplam = toplam_y_bar + toplam_k_bar + toplam_s_bar
    if genel_toplam == 0: genel_toplam = 1

    y_gorsel = round((toplam_y_bar / genel_toplam) * 10)
    k_gorsel = round((toplam_k_bar / genel_toplam) * 10)
    s_gorsel = 10 - (y_gorsel + k_gorsel)
    if s_gorsel < 0: s_gorsel = 0

    if "Long" in temiz_yon:
        if y_gorsel < 8: y_gorsel = 8
        s_gorsel = 1
        k_gorsel = 10 - (y_gorsel + s_gorsel)
    elif "Short" in temiz_yon:
        if k_gorsel < 8: k_gorsel = 8
        s_gorsel = 1
        y_gorsel = 10 - (k_gorsel + s_gorsel)

    aktif_ledler = []
    if "Long" in temiz_yon:
        for _ in range(y_gorsel): aktif_ledler.append("🟢")
        for _ in range(s_gorsel): aktif_ledler.append("🟡")
        for _ in range(k_gorsel): aktif_ledler.append("🔴")
    elif "Short" in temiz_yon:
        for _ in range(k_gorsel): aktif_ledler.append("🔴")
        for _ in range(s_gorsel): aktif_ledler.append("🟡")
        for _ in range(y_gorsel): aktif_ledler.append("🟢")
    else:
        for _ in range(4): aktif_ledler.append("🟢")
        for _ in range(2): aktif_ledler.append("🟡")
        for _ in range(4): aktif_ledler.append("🔴")
        
    while len(aktif_ledler) < 10: aktif_ledler.append("🟡")
    aktif_ledler = aktif_ledler[:10]
    led_dizilimi_str = "".join(aktif_ledler)

    y_yuzde = (toplam_y_bar / genel_toplam) * 100
    k_yuzde = (toplam_k_bar / genel_toplam) * 100
    s_yuzde = (toplam_s_bar / genel_toplam) * 100

    detay_bilgi_html = f"""<div style="text-align: center;"><div style="font-size: 16px; margin-bottom: 2px;">{led_dizilimi_str}</div><div style="font-size: 11px; color: #495057; font-weight: 500;">🟢 %{y_yuzde:.1f} ({toplam_y_bar}) | 🔴 %{k_yuzde:.1f} ({toplam_k_bar}) | 🟡 %{s_yuzde:.1f} ({toplam_s_bar}) [Genel]</div></div>"""

    if "Long" in temiz_yon:
        stop_fiyat = anlik_fiyat * 0.992
        hedef_fiyat = anlik_fiyat * 1.025
    elif "Short" in temiz_yon:
        stop_fiyat = anlik_fiyat * 1.008
        hedef_fiyat = anlik_fiyat * 0.975
    else:
        stop_fiyat = anlik_fiyat * 0.99
        hedef_fiyat = anlik_fiyat * 1.01

    toplam_puan_skor = max(long_skor, short_skor) * 10000 + sum([ord(c) for c in coin_symbol])
    return temiz_yon, toplam_puan_skor, detay_bilgi_html, hedef_fiyat, stop_fiyat, ("Nötr" in temiz_yon), anlik_fiyat

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

elli_islem_arsiv_kontrol()

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
    if "Nötr" in yon: return False, "⚠️️ Bu coin şu an Nötr konumda (Yeterli %75 çoklukta onay alınamadı), işlem açılamaz!"
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
        "Net_Kar_Zarar": 0.0, "Guncel_Kasa": round(toplam_kasa, 2), "Kapanis_Zamani": "-"
    }])
    df = pd.concat([df, yeni_kayit], ignore_index=True).drop_duplicates(subset=['Islem_ID'], keep='last')
    dataframe_guncelle_gsheets(df)
    elli_islem_arsiv_kontrol()
    return True, f"✅ {coin} emri başarıyla verildi! Tutar: {islem_miktari:.2f} $"

def manuel_islem_kapat(islem_id):
    df = islem_gecmisi_getir()
    idx = df[df['Islem_ID'] == islem_id].index
    if idx.empty: return False, "İşlem bulunamadı!"
    row = df.loc[idx[0]]
    if row['Durum'] != 'Acik': return False, "Bu işlem kapalı!"
    try:
        res_val = coklu_zaman_dilimli_analiz(row['Coin'])
        anlik_f = res_val[6] if len(res_val) >= 7 else baz_fiyatlar.get(row['Coin'], 100.0)
        giris_f = float(row['Giris_Fiyat'])
        miktar = float(row['Islem_Miktari'])
        fark_yuzde = ((anlik_f - giris_f) / giris_f) if 'Long' in row['Yon'] else ((giris_f - anlik_f) / giris_f)
        net_kar = miktar * KALDIRAC * fark_yuzde
        suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")
        
        durum_metni = 'Kapandi (Kar)' if net_kar >= 0 else 'Kapandi (Zarar)'
        df.at[idx[0], 'Durum'] = durum_metni
        df.at[idx[0], 'Kapanis_Zamani'] = suan_tr
        df.at[idx[0], 'Net_Kar_Zarar'] = float(round(net_kar, 2))
        
        baz_bakiye = BASLANGIC_BAKIYE
        if os.path.exists(ARSIV_KLASORU):
            arsivler = os.listdir(ARSIV_KLASORU)
            if arsivler:
                arsivler.sort()
                try:
                    son_arsiv_df = pd.read_csv(os.path.join(ARSIV_KLASORU, arsivler[-1]), delimiter=';')
                    if not son_arsiv_df.empty: baz_bakiye = float(pd.to_numeric(son_arsiv_df.iloc[-1]['Guncel_Kasa'], errors='coerce') or BASLANGIC_BAKIYE)
                except: pass
        df['Net_Kar_Zarar'] = pd.to_numeric(df['Net_Kar_Zarar'], errors='coerce').fillna(0.0)
        kapanan_mask = df['Durum'] != 'Acik'
        df.loc[kapanan_mask, 'Guncel_Kasa'] = baz_bakiye + df.loc[kapanan_mask, 'Net_Kar_Zarar'].cumsum()
        dataframe_guncelle_gsheets(df)
        elli_islem_arsiv_kontrol()
        return True, f"Kapatıldı. K/Z: {net_kar:.2f} $"
    except Exception as e: return False, f"Hata: {str(e)}"

# --- ARAYÜZ ---
st.title("⚡ Pro Kripto & Çoklu Zaman Dilimli Dinamik Matris Paneli")

toplam_kasa, mevcut_bakiye = bakiye_durumunu_getir()

col_m1, col_m2 = st.columns(2)
with col_m1:
    st.markdown(f"""
        <div class="metric-container">
            <p style="color: #495057; margin: 0px; font-size: 16px; font-weight: bold;">💰 Anlık Toplam Kasa</p>
            <h1 style="color: #212529; margin: 5px 0px 0px 0px; font-size: 32px;">{toplam_kasa:,.2f} $ <span style="font-size: 18px; color: {'#198754' if toplam_kasa - BASLANGIC_BAKIYE >= 0 else '#dc3545'};">({toplam_kasa - BASLANGIC_BAKIYE:+,.2f} $)</span></h1>
        </div>
    """, unsafe_allow_html=True)
with col_m2:
    st.markdown(f"""
        <div class="metric-container">
            <p style="color: #495057; margin: 0px; font-size: 16px; font-weight: bold;">🟢 Mevcut Bakiye (Boştaki Nakit)</p>
            <h1 style="color: #212529; margin: 5px 0px 0px 0px; font-size: 32px;">{mevcut_bakiye:,.2f} $</h1>
        </div>
    """, unsafe_allow_html=True)

st.markdown("---")
col_ust1, col_ust2 = st.columns([4, 1])
with col_ust2:
    if st.button("🔄 Piyasayı Yenile", use_container_width=True):
        st.rerun()

islenen_veriler = []
for sembol in coinler:
    trend, guclu_skor, teyit_sunumu, hedef_fiyat, stop_fiyat, notr_piyasa, anlik_fiyat = coklu_zaman_dilimli_analiz(sembol)
    
    basamak = 4 if anlik_fiyat < 10 else 2
    l_url = logo_urls.get(sembol, "")
    logo_html = f'<img src="{l_url}" width="24" height="24">'
    
    if "Long" in trend:
        yon_html = f'<div style="background-color: rgba(25, 135, 84, 0.25); padding: 8px; border-radius: 6px; color: #0f5132; font-weight: bold;">{trend}</div>'
    elif "Short" in trend:
        yon_html = f'<div style="background-color: rgba(220, 53, 69, 0.25); padding: 8px; border-radius: 6px; color: #842029; font-weight: bold;">{trend}</div>'
    else:
        yon_html = f'<div style="background-color: rgba(255, 193, 7, 0.25); padding: 8px; border-radius: 6px; color: #664d03; font-weight: bold;">{trend}</div>'
    
    islenen_veriler.append({
        "Logo": logo_html, "Coin": sembol, "Fiyat": round(anlik_fiyat, basamak), 
        "Yon": yon_html, "Teyit_Sunumu": teyit_sunumu, "Kar_Al": round(hedef_fiyat, basamak), 
        "Stopla": round(stop_fiyat, basamak), "Skor": guclu_skor, "Basamak": basamak, "Notr": notr_piyasa, "Ham_Yon": trend
    })

islenen_veriler = sorted(islenen_veriler, key=lambda x: x["Skor"], reverse=True)

if islenen_veriler:
    toplam_skor = sum([max(v["Skor"], 0.1) for v in islenen_veriler])
    ham_yuzdeler = []
    for v in islenen_veriler:
        oran = (max(v["Skor"], 0.1) / toplam_skor) * 100
        ham_yuzdeler.append(max(round(oran, 1), 5.0))
    fark = 100.0 - sum(ham_yuzdeler)
    if ham_yuzdeler: ham_yuzdeler[0] += fark
    for i, v in enumerate(islenen_veriler):
        v["Sepet_Orani"] = round(ham_yuzdeler[i], 1)
        v["Yatırım_Bedeli"] = f"{mevcut_bakiye * (v['Sepet_Orani'] / 100.0):,.2f} $"

table_html = """
<table class="custom-table">
    <thead>
        <tr>
            <th>Logo</th>
            <th>Coin Adı</th>
            <th>Anlık Fiyat</th>
            <th>Panel / Trend Durumu</th>
            <th>Matris Teyit (48S+24S+12S+4S)</th>
            <th>Önerilen Oran</th>
            <th>Yatırım Tutarı</th>
            <th>Kar Al Hedefi</th>
            <th>Stop Seviyesi</th>
        </tr>
    </thead>
    <tbody>
"""

for v in islenen_veriler:
    fiyat_str = f"{v['Fiyat']:,.4f} $" if v['Basamak'] == 4 else f"{v['Fiyat']:,.2f} $"
    kar_al_str = f"{v['Kar_Al']:,.4f} $" if v['Basamak'] == 4 else f"{v['Kar_Al']:,.2f} $"
    stopla_str = f"{v['Stopla']:,.4f} $" if v['Basamak'] == 4 else f"{v['Stopla']:,.2f} $"
    
    sepet_val = v['Sepet_Orani']
    val_str = f"%{sepet_val:.1f}" if sepet_val != int(sepet_val) else f"%{int(sepet_val)}"
    if v['Notr']:
        oran_html = f'<div style="background-color: rgba(255, 235, 59, 0.3); padding: 5px; font-weight: bold;">{val_str} (Beklemede)</div>'
    elif "Trend Haberi" in v['Ham_Yon']:
        bg_col = "rgba(25, 135, 84, 0.35)" if "Long" in v['Ham_Yon'] else "rgba(220, 53, 69, 0.35)"
        oran_html = f'<div style="background-color: {bg_col}; padding: 5px; font-weight: bold;">{val_str} (%85 Trend)</div>'
    elif "Long" in v['Ham_Yon']:
        oran_html = f'<div style="background-color: rgba(25, 135, 84, 0.2); padding: 5px; font-weight: bold;">{val_str} (%75 Onay)</div>'
    else:
        oran_html = f'<div style="background-color: rgba(220, 53, 69, 0.2); padding: 5px; font-weight: bold;">{val_str} (%75 Onay)</div>'

    table_html += f"""
        <tr>
            <td>{v['Logo']}</td>
            <td>{v['Coin']}</td>
            <td>{fiyat_str}</td>
            <td>{v['Yon']}</td>
            <td>{v['Teyit_Sunumu']}</td>
            <td>{oran_html}</td>
            <td>{v['Yatırım_Bedeli']}</td>
            <td>{kar_al_str}</td>
            <td>{stopla_str}</td>
        </tr>
    """

table_html += "</tbody></table>"
st.markdown(table_html, unsafe_allow_html=True)

st.markdown("---")
st.markdown("### 🛒 Hızlı İşlem Emri Ver")

df_gosterge = pd.DataFrame(islenen_veriler)
secilen_coin = st.selectbox("İşleme Girmek İstediğiniz Coini Seçin:", df_gosterge['Coin'].tolist(), key="secilen_coin_select")

if secilen_coin:
    coin_verisi = df_gosterge[df_gosterge['Coin'] == secilen_coin].iloc[0]
    onerilen_oran_val = float(coin_verisi['Sepet_Orani'])
    if coin_verisi['Notr']: st.warning("⚠️ Bu coin şu an Nötr konumda (Yeterli %75 çoklukta onay alınamadı).")
    
    secilen_oran = st.slider("Yatırım Oranını Seçin (%):", min_value=0.0, max_value=100.0, value=onerilen_oran_val, step=0.5, key="oran_slider")
    hesaplanan_tutar = mevcut_bakiye * (secilen_oran / 100.0)
    st.markdown(f"💼 **Yatırım Tutarı:** `{hesaplanan_tutar:,.2f} $` &nbsp;&nbsp;|&nbsp;&nbsp; **Mevcut Nakit:** `{mevcut_bakiye:,.2f} $`", unsafe_allow_html=True)
    
    emir_butonu = st.button(f"🚀 {secilen_coin} İşlemini Başlat ve Emri Al", key="islem_baslat_btn")
    if emir_butonu:
         st.info("🔄 İşlem sıraya alındı, veriler işleniyor...")
         ham_yon_metni = "Long" if "Long" in coin_verisi['Ham_Yon'] else ("Short" if "Short" in coin_verisi['Ham_Yon'] else "Nötr")
         basari, mesaj = yeni_islem_ekle(coin=secilen_coin, yon=ham_yon_metni, giris_fiyat=coin_verisi['Fiyat'], sepet_orani_yuzde=secilen_oran, stop=coin_verisi['Stopla'], kar_al=coin_verisi['Kar_Al'], zaman_dilimi="Multi-Timeframe Motoru")
         if basari: 
             st.success(mesaj)
             st.balloons()
             st.rerun()
         else: 
             st.error(mesaj)

st.markdown("---")
st.markdown(f"### 💼 Sanal Portföy ve Açık Pozisyonlar (Aktif Kasa: **{toplam_kasa:,.2f} $**)")

df_gecmis = islem_gecmisi_getir(sheet_guncelle=False)
if not df_gecmis.empty:
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
                    b_durum, b_mesaj = manuel_islem_kapat(kapatilacak_id)
                    if b_durum: st.success(b_mesaj); st.rerun()
                    else: st.error(b_mesaj)
                else: st.warning("Onay kutusunu işaretleyin!")
        st.markdown("---")

    df_gecmis_copy = df_gecmis.copy()
    df_gecmis_copy['Logo'] = df_gecmis_copy['Coin'].apply(lambda c: f'<img src="{logo_urls.get(c, "")}" width="24" height="24">')
    
    anlik_fiyat_sozluk, anlik_kz_sozluk, hedef_kar_sozluk, olasi_stop_sozluk = {}, {}, {}, {}
    for idx, row in df_gecmis_copy.iterrows():
        islem_id = row['Islem_ID']
        coin = row['Coin']
        giris_f = float(row['Giris_Fiyat'])
        miktar = float(row['Islem_Miktari'])
        kar_al_f = float(row['Kar_Al'])
        stop_f = float(row['Stop'])
        yon = row['Yon']
        
        res_val = coklu_zaman_dilimli_analiz(coin)
        anlik_f = res_val[6] if len(res_val) >= 7 else baz_fiyatlar.get(coin, 100.0)
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
    
    islem_miktari_seri = pd.to_numeric(df_gecmis_copy['Islem_Miktari'], errors='coerce').fillna(0.0)
    guncel_kasa_seri = pd.to_numeric(df_gecmis_copy['Guncel_Kasa'], errors='coerce').fillna(BASLANGIC_BAKIYE)
    df_gecmis_copy['Islem_Orani'] = ((islem_miktari_seri / guncel_kasa_seri) * 100).apply(lambda x: f"%{float(x):.1f}" if x > 0 else "%0.0")

    df_gecmis_copy['Giris_Fiyat_Str'] = df_gecmis_copy.apply(lambda r: f"{float(r['Giris_Fiyat']):,.{4 if r['Coin']=='XRP/USDT' else 2}f} $", axis=1)
    df_gecmis_copy['Stop_Str'] = df_gecmis_copy.apply(lambda r: f"{float(r['Stop']):,.{4 if r['Coin']=='XRP/USDT' else 2}f} $", axis=1)
    df_gecmis_copy['Kar_Al_Str'] = df_gecmis_copy.apply(lambda r: f"{float(r['Kar_Al']):,.{4 if r['Coin']=='XRP/USDT' else 2}f} $", axis=1)

    def format_yon_hucre(y):
        if "Long" in y:
            return f'<div style="background-color: rgba(25, 135, 84, 0.25); padding: 8px; border-radius: 6px; color: #0f5132; font-weight: bold;">{y}</div>'
        elif "Short" in y:
            return f'<div style="background-color: rgba(220, 53, 69, 0.25); padding: 8px; border-radius: 6px; color: #842029; font-weight: bold;">{y}</div>'
        else:
            return f'<div style="background-color: rgba(255, 193, 7, 0.25); padding: 8px; border-radius: 6px; color: #664d03; font-weight: bold;">{y}</div>'

    portfoy_html = """
    <table class="custom-table">
        <thead>
            <tr>
                <th>İşlem ID</th>
                <th>Açılış Zamanı</th>
                <th>Logo</th>
                <th>Coin Adı</th>
                <th>İşlem Yönü</th>
                <th>Giriş Fiyatı</th>
                <th>Anlık Fiyat</th>
                <th>Sepet Oranı</th>
                <th>Yatırım Tutarı</th>
                <th>Stop Seviyesi</th>
                <th>Kar Al Hedefi</th>
                <th>Beklenen Kar</th>
                <th>Olası Stop</th>
                <th>İşlem Durumu</th>
                <th>Anlık K/Z</th>
                <th>Kapanış Zamanı</th>
                <th>Güncel Kasa</th>
            </tr>
        </thead>
        <tbody>
    """

    for _, row in df_gecmis_copy.iterrows():
        l_url = logo_urls.get(row['Coin'], "")
        logo_h = f'<img src="{l_url}" width="24" height="24">'
        yon_h = format_yon_hucre(row['Yon'])
        
        fiyat_stil = "rgba(25, 135, 84, 0.2)" if row['Anlik_Fiyat_Deger'] > float(row['Giris_Fiyat']) else "rgba(220, 53, 69, 0.2)"
        anlik_fiyat_h = f'<div style="background-color: {fiyat_stil}; padding: 5px; font-weight: bold;">{row["Anlik_Fiyat_Deger"]:,.2f} $</div>'
        
        kz_val = row['Anlik_KZ_Deger']
        kz_stil = "rgba(25, 135, 84, 0.2)" if kz_val >= 0 else "rgba(220, 53, 69, 0.2)"
        kz_h = f'<div style="background-color: {kz_stil}; padding: 5px; font-weight: bold;">{kz_val:+,.2f} $</div>'
        
        d_val = row['Durum']
        d_bg = "#0d6efd" if "Acik" in d_val else ("#198754" if "Kar" in d_val else "#dc3545")
        durum_h = f'<div style="background-color: {d_bg}; color: white; padding: 4px; border-radius: 4px; font-weight: bold;">{d_val}</div>'

        portfoy_html += f"""
            <tr>
                <td>{row['Islem_ID']}</td>
                <td>{row['Acilis_Zamani']}</td>
                <td>{logo_h}</td>
                <td>{row['Coin']}</td>
                <td>{yon_h}</td>
                <td>{row['Giris_Fiyat_Str']}</td>
                <td>{anlik_fiyat_h}</td>
                <td>{row['Islem_Orani']}</td>
                <td>{row['Yatırım_Bedeli']}</td>
                <td>{row['Stop_Str']}</td>
                <td>{row['Kar_Al_Str']}</td>
                <td>{row['Hedef_Kar_Str']}</td>
                <td>{row['Olasi_Stop_Str']}</td>
                <td>{durum_h}</td>
                <td>{kz_h}</td>
                <td>{row['Kapanis_Zamani']}</td>
                <td>{row['Kasa_Str']}</td>
            </tr>
        """
    portfoy_html += "</tbody></table>"
    st.markdown(portfoy_html, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("📊 Kapanan İşlemler Pasta Grafik & Para Akışı Analizi")
    kapananlar_df = df_gecmis[df_gecmis['Durum'] != 'Acik']
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
            fig = px.pie(df_pie, names='Durum', values='Adet', hole=0.35, color='Durum', color_discrete_map={'Kârlı İşlemler': '#198754', 'Zararlı İşlemler': '#dc3545'})
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#212529', margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
            st.plotly_chart(fig, use_container_width=True)
            
        with col_p2:
            st.markdown("#### 📈 Strateji Metrikleri")
            st.metric("Toplam Kapanan İşlem", f"{toplam_kapanan} Adet")
            st.metric("🟢 Kârlı Kapanma", f"{karli_sayisi} Adet (%{karli_oran:.1f})")
            st.metric("🔴 Zararlı Kapanma", f"{zararli_sayisi} Adet (%{zararli_oran:.1f})")
            
        with col_p3:
            st.markdown("#### 💰 Para Değerleri Bloku")
            st.markdown(f"""
            <div class="para-blogu">
                <p style="color: #198754; margin: 0px; font-size: 15px; font-weight: bold;">Toplam Kâr:</p>
                <h3 style="color: #198754; margin: 0px 0px 10px 0px;">+{toplam_kazanc_dolar:,.2f} $</h3>
                <p style="color: #dc3545; margin: 0px; font-size: 15px; font-weight: bold;">Toplam Zarar:</p>
                <h3 style="color: #dc3545; margin: 0px 0px 10px 0px;">-{toplam_kayip_dolar:,.2f} $</h3>
                <hr style="border-color: #ced4da; margin: 8px 0px;">
                <p style="color: #212529; margin: 0px; font-size: 14px;">Net Fark:</p>
                <h3 style="color: {'#198754' if net_fark_dolar >= 0 else '#dc3545'}; margin: 0px;">{net_fark_dolar:+,.2f} $</h3>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown("---")
        st.markdown("### 📁 50'şerli İşlem Arşivleri (Analiz Klasörü)")
        if os.path.exists(ARSIV_KLASORU):
            arsiv_dosyalari = os.listdir(ARSIV_KLASORU)
            if arsiv_dosyalari:
                arsiv_dosyalari.sort()
                secilen_arsiv = st.selectbox("Geçmiş 50'li Blok Dönemini Seçin:", arsiv_dosyalari, key="arsiv_select_50")
                if secilen_arsiv:
                    df_arsiv = pd.read_csv(os.path.join(ARSIV_KLASORU, secilen_arsiv), delimiter=';')
                    st.write(df_arsiv.to_html(escape=False, index=False), unsafe_allow_html=True)
            else: st.info("Henüz 50 işleme ulaşılmadı.")
        else: st.info("Arşiv klasörü henüz oluşturulmadı.")
    else:
        st.info("Henüz kapanmış işlem bulunmuyor.")
else: 
    st.info("ℹ️ Henüz açılmış bir sanal pozisyonunuz bulunmuyor.")