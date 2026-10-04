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
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(page_title="Pro Kripto Canlı Akış Paneli", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

# --- CSS STİLLERİ VE GRADYAN SLIDER KİLİT KIRICI ---
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
    
    /* SLIDER (POTANS) ÇUBUĞUNU KALIN GRADYAN YAPMAK İÇİN AGRESİF CSS */
    div[data-baseweb="slider"] div[data-testid="stSliderTickBar"] { display: none !important; }
    div[data-baseweb="slider"] > div:first-child > div:first-child {
        background: linear-gradient(90deg, #198754 0%, #ffc107 50%, #dc3545 100%) !important;
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
    div[data-baseweb="slider"] div[data-testid="stThumbValue"] {
        color: #212529 !important;
        font-weight: bold !important;
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
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={binance_sym}"
        resp = requests.get(url, headers=headers, timeout=2.5)
        if resp.status_code == 200:
            val = float(resp.json().get('price', 0))
            if val > 0: return val
    except: pass
    return baz_fiyatlar.get(coin_symbol, 100.0)

def kline_cek_guvenli(coin_symbol, period_type):
    symbol_map = {'BTC/USDT': 'BTCUSDT', 'ETH/USDT': 'ETHUSDT', 'BNB/USDT': 'BNBUSDT', 'SOL/USDT': 'SOLUSDT', 'XRP/USDT': 'XRPUSDT'}
    binance_sym = symbol_map.get(coin_symbol, 'BTCUSDT')
    kucoin_sym = coin_symbol.replace('/', '-')
    headers = {'User-Agent': 'Mozilla/5.0'}
    ts = int(time.time() * 1000)
    
    if period_type == "48s":
        b_int, b_lim, k_int = "15m", 192, "15min"
    elif period_type == "24s":
        b_int, b_lim, k_int = "5m", 288, "5min"
    elif period_type == "12s":
        b_int, b_lim, k_int = "3m", 240, "3min"
    else: 
        b_int, b_lim, k_int = "1m", 240, "1min"

    def hesabla(veriler, o_idx, c_idx):
        y, k, s = 0, 0, 0
        for bar in veriler:
            try:
                o, c = float(bar[o_idx]), float(bar[c_idx])
                if c > o: y += 1
                elif c < o: k += 1
                else: s += 1
            except: pass
        return y, k, s

    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={binance_sym}&interval={b_int}&limit={b_lim}&_t={ts}"
        r = requests.get(url, headers=headers, timeout=2.5)
        if r.status_code == 200:
            data = r.json()
            if len(data) > int(b_lim * 0.5): return hesabla(data, 1, 4)
    except: pass

    try:
        url = f"https://api.kucoin.com/api/v1/market/candles?type={k_int}&symbol={kucoin_sym}"
        r = requests.get(url, headers=headers, timeout=2.5)
        if r.status_code == 200:
            data = r.json().get('data', [])
            if len(data) > int(b_lim * 0.5): return hesabla(data[:b_lim], 1, 2)
    except: pass

    random.seed(int(time.time() / 300) + sum([ord(c) for c in coin_symbol])) 
    y_sabit = int(b_lim * random.uniform(0.45, 0.55))
    k_sabit = int(b_lim * random.uniform(0.45, 0.55))
    if y_sabit + k_sabit > b_lim: k_sabit = b_lim - y_sabit
    return y_sabit, k_sabit, b_lim - (y_sabit + k_sabit)

def ham_verileri_getir(coin_symbol, risk_yuzdesi):
    anlik_fiyat = fiyat_cek_guvenli(coin_symbol)
    res_48s = kline_cek_guvenli(coin_symbol, "48s")
    res_24s = kline_cek_guvenli(coin_symbol, "24s")
    res_12s = kline_cek_guvenli(coin_symbol, "12s")
    res_4s  = kline_cek_guvenli(coin_symbol, "4s")

    def calc_ratio(rez):
        toplam = rez[0] + rez[1]
        return (rez[0] / toplam * 100.0) if toplam > 0 else 50.0

    # 4 Zaman dilimi ağırlıklı HAM yüzde hesabı
    raw_y_net = (calc_ratio(res_48s) * 0.10) + (calc_ratio(res_24s) * 0.15) + (calc_ratio(res_12s) * 0.25) + (calc_ratio(res_4s) * 0.50)
    
    # V2'DEN GELEN ÖZELLİK: Slider'ın Matris Üzerindeki Katsayı Çarpan Etkisi
    # Yüzde 50 barajından ne kadar uzaklaştığını potansa göre katlayarak görselleştiriyoruz
    fark = raw_y_net - 50.0
    risk_katsayisi = 0.5 + (risk_yuzdesi / 100.0) * 1.5 
    y_net_scaled = min(100.0, max(0.0, 50.0 + (fark * risk_katsayisi)))
    
    return anlik_fiyat, round(y_net_scaled, 1)

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
    if "Nötr" in yon: return False, "⚠️ Bu coin şu an Nötr konumda (Eşik Aşılmadı), işlem açılamaz!"
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
        coin_isim = str(row['Coin'])
        fark_yuzde = ((anlik_kapatma_fiyati - giris_f) / giris_f) if 'Long' in row['Yon'] else ((giris_f - anlik_kapatma_fiyati) / giris_f)
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
st.title("⚡ Pro Kripto & Canlı Piyasa Paneli")
elli_islem_arsiv_kontrol()

@st.fragment(run_every=60.0)
def tam_ekran_canli_yayin_dongusu():
    toplam_kasa, mevcut_bakiye = bakiye_durumunu_getir()

    col_ust1, col_ust2 = st.columns([4, 1])
    with col_ust2:
        if st.button("🔄 Piyasayı Şimdi Yenile", use_container_width=True):
            st.rerun()

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

    # --- SLIDER VE MATRİS EŞİĞİ ---
    risk_yuzdesi = st.slider("🎛️ Panel Güvenli Bölge Risk Oranı (%0 - %100):", min_value=0.0, max_value=100.0, value=50.0, step=1.0, key="risk_yuzde_potansi")

    if risk_yuzdesi <= 50:
        oran = risk_yuzdesi / 50.0
        r, g, b = 25 + int((255 - 25) * oran), 135 + int((193 - 135) * oran), 84 + int((7 - 84) * oran)
    else:
        oran = (risk_yuzdesi - 50.0) / 50.0
        r, g, b = 255 + int((220 - 255) * oran), 193 + int((53 - 193) * oran), 7 + int((69 - 7) * oran)

    rgba_bg = f"rgba({r}, {g}, {b}, 0.22)"
    border_col = f"rgb({r}, {g}, {b})"

    # FORMÜL: Risk %0 -> Eşik %75 | Risk %100 -> Eşik %25
    dinamik_matris_esigi = 75.0 - (risk_yuzdesi * 0.50)

    st.markdown(f"""
        <div style="background-color: {rgba_bg}; border: 2px solid {border_col}; padding: 12px; border-radius: 8px; text-align: center; margin-bottom: 15px;">
            <span style="font-size: 16px; font-weight: bold; color: #212529;">Aktif Risk ve Güvenli Bölge Seviyesi: %{risk_yuzdesi:.0f} (Dinamik Matris Eşiği: %{dinamik_matris_esigi:.1f})</span>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    islenen_ham_veriler = []
    ortak_fiyat_havuzu = {} 
    
    # 1. Aşama: Tüm Coinlerin 4 Zaman Dilimli Ağırlıklı Verilerini Topla (V2 katsayı mantığıyla)
    for sembol in coinler:
        anlik_fiyat, y_net_yuzde = ham_verileri_getir(sembol, risk_yuzdesi)
        ortak_fiyat_havuzu[sembol] = anlik_fiyat 
        islenen_ham_veriler.append({
            "sembol": sembol, "anlik_fiyat": anlik_fiyat, "y_net": y_net_yuzde
        })

    # 2. Aşama: U Ledi (USDT Piyasa Ortalaması) İçin Tüm Coinlerin Ağırlıklı Ortalamasını Al
    usdt_genel_yuzde = sum([d["y_net"] for d in islenen_ham_veriler]) / len(islenen_ham_veriler)

    # 3. Aşama: Şartlı Matris ve LED Yapılandırması
    islenen_veriler = []
    for data in islenen_ham_veriler:
        sembol = data["sembol"]
        y_net = data["y_net"]
        k_net = 100.0 - y_net
        anlik_fiyat = data["anlik_fiyat"]
        
        # C (Coin) ve U (USDT) 4 Zaman Dilimli Doğrulama Durumları
        c_long_mu = (y_net >= 50.0)
        u_long_mu = (usdt_genel_yuzde >= 50.0)
        
        # Matrisin Slider Eşiğini Aşıp Aşmadığının Kontrolü
        is_long_esik_met = (y_net >= dinamik_matris_esigi)
        is_short_esik_met = (k_net >= dinamik_matris_esigi)

        # V2 MANTIĞI: Matris alanı 10'lu LED Bar'ı daima yüzdeleri yeşil/kırmızı oranda göstersin.
        y_gorsel = int(y_net / 10)
        y_gorsel = max(0, min(10, y_gorsel))
        k_gorsel = 10 - y_gorsel
        led_str = ("🟢" * y_gorsel) + ("🔴" * k_gorsel)

        # Matris Durum LED'i (Nötr İse SARI Yanacak)[cite: 27]
        m_durum = "🟡"
        if is_long_esik_met:
            m_durum = "🟢"
        elif is_short_esik_met:
            m_durum = "🔴"

        # C ve U Durum LED'leri
        c_durum = "🟢" if c_long_mu else "🔴"
        u_durum = "🟢" if u_long_mu else "🔴"

        # TREND KURALI: Eşik Aşılmalı (M_Durum Sarı Olmamalı) VE (C veya U ledi Matris ile Aynı Renkte Yanmalı)
        is_notr = True
        trend = "Nötr (Beklemede)"
        aktif_matris_orani = 0.0
        aktif_yon_turu = "Nötr"
        
        piyasa_cift_onay = (c_durum == m_durum) or (u_durum == m_durum)

        if m_durum != "🟡" and piyasa_cift_onay:
            is_notr = False
            if m_durum == "🟢":
                aktif_yon_turu = "Long"
                aktif_matris_orani = y_net
                trend = "Long (Trend Haberi)" if y_net >= 85.0 else "Long (Onaylı)"
            elif m_durum == "🔴":
                aktif_yon_turu = "Short"
                aktif_matris_orani = k_net
                trend = "Short (Trend Haberi)" if k_net >= 85.0 else "Short (Onaylı)"

        # Stop & Hedef Belirleme
        if aktif_yon_turu == "Long":
            stop_fiyat, hedef_fiyat = anlik_fiyat * 0.992, anlik_fiyat * 1.025
        elif aktif_yon_turu == "Short":
            stop_fiyat, hedef_fiyat = anlik_fiyat * 1.008, anlik_fiyat * 0.975
        else: # Nötr iken varsayılan
            stop_fiyat, hedef_fiyat = anlik_fiyat * 0.992, anlik_fiyat * 1.025
        
        dom_html = f"""
        <div style="text-align: center;">
            <div style="font-size: 16px; margin-bottom: 2px; letter-spacing: 2px;">{c_durum}{u_durum}{m_durum}</div>
            <div style="font-size: 10px; color: #495057; font-weight: 500;">C:%{y_net if y_net >= 50 else k_net:.0f} | U:%{usdt_genel_yuzde if usdt_genel_yuzde >= 50 else (100.0 - usdt_genel_yuzde):.0f} | M:{m_durum}</div>
        </div>
        """
        
        detay_bilgi_html = f"""<div style="text-align: center;"><div style="font-size: 15px; margin-bottom: 2px; letter-spacing: 1px;">{led_str}</div><div style="font-size: 11px; color: #495057; font-weight: 500;">🟢 %{y_net:.1f} | 🔴 %{k_net:.1f}</div></div>"""

        basamak = 4 if anlik_fiyat < 10 else 2
        logo_html = f'<img src="{logo_urls.get(sembol, "")}" width="24" height="24">'
        
        if "Trend Haberi" in trend: yon_html = f'<div style="background-color: rgba(25, 135, 84, 0.35); padding: 6px; border-radius: 6px; color: #0f5132; font-weight: bold;">{trend}</div>' if "Long" in trend else f'<div style="background-color: rgba(220, 53, 69, 0.35); padding: 6px; border-radius: 6px; color: #842029; font-weight: bold;">{trend}</div>'
        elif "Long" in trend: yon_html = f'<div style="background-color: rgba(25, 135, 84, 0.2); padding: 6px; border-radius: 6px; color: #0f5132; font-weight: bold;">{trend}</div>'
        elif "Short" in trend: yon_html = f'<div style="background-color: rgba(220, 53, 69, 0.2); padding: 6px; border-radius: 6px; color: #842029; font-weight: bold;">{trend}</div>'
        else: yon_html = f'<div style="background-color: rgba(255, 193, 7, 0.25); padding: 6px; border-radius: 6px; color: #664d03; font-weight: bold;">{trend}</div>'
        
        islenen_veriler.append({
            "Logo": logo_html, "Coin": sembol, "Fiyat": round(anlik_fiyat, basamak), 
            "Yon": yon_html, "Teyit_Sunumu": detay_bilgi_html, "Dom_Sunumu": dom_html, 
            "Kar_Al": round(hedef_fiyat, basamak), "Stopla": round(stop_fiyat, basamak), 
            "Skor": aktif_matris_orani * 10000 + sum([ord(c) for c in sembol]) if not is_notr else 0, 
            "Basamak": basamak, "Notr": is_notr, "Ham_Yon": trend, "Matris_Orani": aktif_matris_orani, "Aktif_Yon": aktif_yon_turu
        })

    # OTOMATİK KAPATMA
    df_gecmis = islem_gecmisi_getir(sheet_guncelle=False)
    kapanan_islem_oldu_mu = False
    if not df_gecmis.empty:
        acik_islemler = df_gecmis[df_gecmis['Durum'] == 'Acik']
        for _, row in acik_islemler.iterrows():
            i_id, c, yon = row['Islem_ID'], row['Coin'], row['Yon']
            stop, kar_al = float(row['Stop']), float(row['Kar_Al'])
            a_fiyat = ortak_fiyat_havuzu.get(c, 0)
            
            if a_fiyat > 0:
                if 'Long' in yon and (a_fiyat <= stop or a_fiyat >= kar_al):
                    manuel_islem_kapat(i_id, a_fiyat); kapanan_islem_oldu_mu = True
                elif 'Short' in yon and (a_fiyat >= stop or a_fiyat <= kar_al):
                    manuel_islem_kapat(i_id, a_fiyat); kapanan_islem_oldu_mu = True
                        
    if kapanan_islem_oldu_mu: st.rerun() 

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

    table_html = """
    <table class="custom-table">
        <thead>
            <tr>
                <th>Logo</th><th>Coin<br>Adı</th><th>Güncel<br>Fiyat</th><th>Trend<br>Durumu</th>
                <th>Matris Teyit<br>(48+24+12+4)</th><th>Piyasa &<br>Dominans</th><th>Önerilen<br>Oran</th>
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
        
        if v['Notr']: oran_html = f'<div style="background-color: rgba(255, 235, 59, 0.3); padding: 5px; font-weight: bold;">%0<br>(Beklemede)</div>'
        elif "Trend Haberi" in v['Ham_Yon']: oran_html = f'<div style="background-color: {"rgba(25, 135, 84, 0.35)" if "Long" in v["Ham_Yon"] else "rgba(220, 53, 69, 0.35)"}; padding: 5px; font-weight: bold;">{val_str}<br>(%85 Trend)</div>'
        else: oran_html = f'<div style="background-color: {"rgba(25, 135, 84, 0.2)" if "Long" in v["Ham_Yon"] else "rgba(220, 53, 69, 0.2)"}; padding: 5px; font-weight: bold;">{val_str}<br>(Onaylı)</div>'

        table_html += f"<tr><td>{v['Logo']}</td><td>{v['Coin']}</td><td style='font-weight: bold; color: #0d6efd; background-color: rgba(13, 110, 253, 0.05);'>{fiyat_str}</td><td>{v['Yon']}</td><td>{v['Teyit_Sunumu']}</td><td>{v['Dom_Sunumu']}</td><td>{oran_html}</td><td>{v['Yatırım_Bedeli']}</td><td>{kar_al_str}</td><td>{stopla_str}</td></tr>"
    table_html += "</tbody></table>"
    st.html(table_html)

    st.markdown("### 🛒 Hızlı İşlem Emri Ver")
    df_gosterge = pd.DataFrame(islenen_veriler)
    secilen_coin = st.selectbox("İşleme Girmek İstediğiniz Coini Seçin:", df_gosterge['Coin'].tolist(), key="secilen_coin_select_frag")

    if secilen_coin:
        coin_verisi = df_gosterge[df_gosterge['Coin'] == secilen_coin].iloc[0]
        onerilen_oran_val = float(coin_verisi['Sepet_Orani'])
        if coin_verisi['Notr']: st.warning("⚠️ Bu coin şu an Nötr konumda (Eşiği Aşamadı).")
        
        secilen_oran = st.slider("Yatırım Oranını Seçin (%):", min_value=0.0, max_value=100.0, value=onerilen_oran_val, step=0.5, key="oran_slider_frag")
        hesaplanan_tutar = mevcut_bakiye * (secilen_oran / 100.0)
        st.markdown(f"💼 **Yatırım Tutarı:** `{hesaplanan_tutar:,.2f} $` &nbsp;&nbsp;|&nbsp;&nbsp; **Mevcut Nakit:** `{mevcut_bakiye:,.2f} $`", unsafe_allow_html=True)
        
        if st.button(f"🚀 {secilen_coin} İşlemini Başlat ve Emri Al", key="islem_baslat_btn_frag"):
             st.info("🔄 İşlem sıraya alındı, veriler işleniyor...")
             basari, mesaj = yeni_islem_ekle(coin=secilen_coin, yon=coin_verisi['Aktif_Yon'], giris_fiyat=coin_verisi['Fiyat'], sepet_orani_yuzde=secilen_oran, stop=coin_verisi['Stopla'], kar_al=coin_verisi['Kar_Al'], zaman_dilimi="Multi-Timeframe Motoru")
             if basari: 
                 st.success(mesaj); st.balloons(); st.rerun()
             else: st.error(mesaj)

    st.markdown("---")
    st.markdown(f"### 💼 Sanal Portföy ve Açık Pozisyonlar")

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
                        kapanacak_coin = df_gecmis[df_gecmis['Islem_ID'] == kapatilacak_id]['Coin'].iloc[0]
                        kapatma_fiyati = ortak_fiyat_havuzu.get(kapanacak_coin, baz_fiyatlar.get(kapanacak_coin, 100.0))
                        b_durum, b_mesaj = manuel_islem_kapat(kapatilacak_id, kapatma_fiyati)
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
        
        islem_miktari_seri = pd.to_numeric(df_gecmis_copy['Islem_Miktari'], errors='coerce').fillna(0.0)
        guncel_kasa_seri = pd.to_numeric(df_gecmis_copy['Guncel_Kasa'], errors='coerce').fillna(BASLANGIC_BAKIYE)
        df_gecmis_copy['Islem_Orani'] = ((islem_miktari_seri / guncel_kasa_seri) * 100).apply(lambda x: f"%{float(x):.1f}" if x > 0 else "%0.0")

        df_gecmis_copy['Yatırım_Bedeli'] = df_gecmis_copy['Islem_Miktari'].apply(lambda x: f"{float(x):,.2f}&nbsp;$")
        df_gecmis_copy['Hedef_Kar_Str'] = df_gecmis_copy['Hedef_Kar'].apply(lambda x: f"{float(x):,.2f}&nbsp;$")
        df_gecmis_copy['Olasi_Stop_Str'] = df_gecmis_copy['Olasi_Stop'].apply(lambda x: f"{float(x):,.2f}&nbsp;$")
        df_gecmis_copy['Kasa_Str'] = df_gecmis_copy['Guncel_Kasa'].apply(lambda x: f"{float(x):,.2f}&nbsp;$")

        df_gecmis_copy['Giris_Fiyat_Str'] = df_gecmis_copy.apply(lambda r: f"{float(r['Giris_Fiyat']):,.{4 if r['Coin']=='XRP/USDT' else 2}f}&nbsp;$", axis=1)
        df_gecmis_copy['Stop_Str'] = df_gecmis_copy.apply(lambda r: f"{float(r['Stop']):,.{4 if r['Coin']=='XRP/USDT' else 2}f}&nbsp;$", axis=1)
        df_gecmis_copy['Kar_Al_Str'] = df_gecmis_copy.apply(lambda r: f"{float(r['Kar_Al']):,.{4 if r['Coin']=='XRP/USDT' else 2}f}&nbsp;$", axis=1)

        def format_yon_hucre(y):
            if "Trend Haberi" in y: return f'<div style="background-color: rgba(25, 135, 84, 0.35); padding: 6px; border-radius: 6px; color: #0f5132; font-weight: bold;">{y}</div>' if "Long" in y else f'<div style="background-color: rgba(220, 53, 69, 0.35); padding: 6px; border-radius: 6px; color: #842029; font-weight: bold;">{y}</div>'
            elif "Long" in y: return f'<div style="background-color: rgba(25, 135, 84, 0.25); padding: 6px; border-radius: 6px; color: #0f5132; font-weight: bold;">{y}</div>'
            elif "Short" in y: return f'<div style="background-color: rgba(220, 53, 69, 0.25); padding: 6px; border-radius: 6px; color: #842029; font-weight: bold;">{y}</div>'
            else: return f'<div style="background-color: rgba(255, 193, 7, 0.25); padding: 6px; border-radius: 6px; color: #664d03; font-weight: bold;">{y}</div>'

        portfoy_html = """
        <table class="custom-table">
            <thead>
                <tr>
                    <th>ID</th><th>Açılış<br>Zamanı</th><th>Logo</th><th>Coin</th><th>İşlem<br>Yönü</th>
                    <th>Giriş<br>Fiyatı</th><th>Anlık<br>Fiyat</th><th>Sepet<br>Oranı</th><th>Yatırım<br>Tutarı</th>
                    <th>Stop<br>Seviyesi</th><th>Kar Al<br>Hedefi</th><th>Beklenen<br>Kar</th><th>Olası<br>Stop</th>
                    <th>İşlem<br>Durumu</th><th>Anlık<br>K/Z</th><th>Kapanış<br>Zamanı</th><th>Güncel<br>Kasa</th>
                </tr>
            </thead><tbody>
        """

        for _, row in df_gecmis_copy.iterrows():
            l_url = logo_urls.get(row['Coin'], "")
            logo_h = f'<img src="{l_url}" width="24" height="24">'
            yon_h = format_yon_hucre(row['Yon'])
            
            fiyat_stil = "rgba(25, 135, 84, 0.2)" if row['Anlik_Fiyat_Deger'] > float(row['Giris_Fiyat']) else "rgba(220, 53, 69, 0.2)"
            anlik_fiyat_str = f"{row['Anlik_Fiyat_Deger']:,.4f}&nbsp;$" if row['Coin'] == 'XRP/USDT' else f"{row['Anlik_Fiyat_Deger']:,.2f}&nbsp;$"
            anlik_fiyat_h = f'<div style="background-color: {fiyat_stil}; padding: 5px; font-weight: bold;">{anlik_fiyat_str}</div>'
            
            kz_val = row['Anlik_KZ_Deger']
            kz_stil = "rgba(25, 135, 84, 0.2)" if kz_val >= 0 else "rgba(220, 53, 69, 0.2)"
            kz_h = f'<div style="background-color: {kz_stil}; padding: 5px; font-weight: bold; white-space: nowrap;">{kz_val:+,.2f}&nbsp;$</div>'
            
            d_val = row['Durum']
            d_bg = "#0d6efd" if "Acik" in d_val else ("#198754" if "Kar" in d_val else "#dc3545")
            durum_h = f'<div style="background-color: {d_bg}; color: white; padding: 4px; border-radius: 4px; font-weight: bold;">{d_val}</div>'

            portfoy_html += f"<tr><td>{row['Islem_ID']}</td><td>{row['Acilis_Zamani']}</td><td>{logo_h}</td><td>{row['Coin']}</td><td>{yon_h}</td><td>{row['Giris_Fiyat_Str']}</td><td>{anlik_fiyat_h}</td><td>{row['Islem_Orani']}</td><td>{row['Yatırım_Bedeli']}</td><td>{row['Stop_Str']}</td><td>{row['Kar_Al_Str']}</td><td>{row['Hedef_Kar_Str']}</td><td>{row['Olasi_Stop_Str']}</td><td>{durum_h}</td><td>{kz_h}</td><td>{row['Kapanis_Zamani']}</td><td>{row['Kasa_Str']}</td></tr>"
        portfoy_html += "</tbody></table>"
        st.html(portfoy_html)

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

# CANLI DÖNGÜYÜ BAŞLAT
tam_ekran_canli_yayin_dongusu()
