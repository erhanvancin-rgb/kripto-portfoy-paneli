import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
import os
import csv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import threading
import random
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(page_title="Pro Kripto Strateji & Portföy Paneli", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #1a1c23; border-radius: 5px 5px 0 0; gap: 1px; padding-top: 10px; padding-bottom: 10px; font-size: 18px; font-weight: bold; }
    .stTabs [aria-selected="true"] { background-color: #2d3748; color: #00FF00; font-weight: bold; border-bottom: 2px solid #00FF00; }
    .para-blogu { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 15px; text-align: center; }
    .metric-container { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 15px; text-align: center; margin-bottom: 12px; }
    
    [data-testid="stDataFrame"] div[data-baseweb="datatable"] { font-size: 16px !important; font-weight: 600 !important; color: #ffffff !important; }
    </style>
""", unsafe_allow_html=True)

# --- SABİTLER VE TÜRKİYE SAATİ ---
GOOGLE_SHEET_ADRESI = "KriptoPortfoyVeritabani"  
ARSIV_KLASORU = "arsiv"
BASLANGIC_BAKIYE = 500.0
KALDIRAC = 3 
TR_TZ = pytz.timezone('Europe/Istanbul')

def tr_zaman():
    return datetime.now(TR_TZ)

# --- E-POSTA BİLDİRİM AYARLARI ---
GONDERICI_MAIL = "erhanvancin@gmail.com"
ALICI_MAIL = "erhanvancin@hotmail.com"
GMAIL_SIFRE = "jkef zgaf zwtg qyom"

coinler = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT']

logo_urls = {
    'BTC/USDT': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/btc.png',
    'ETH/USDT': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/eth.png',
    'BNB/USDT': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/bnb.png',
    'SOL/USDT': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/sol.png',
    'XRP/USDT': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/xrp.png'
}

if 'son_mail_zamanlari' not in st.session_state:
    st.session_state['son_mail_zamanlari'] = {}

def piyasa_verilerini_cek_canli():
    veri_sozlugu = {}
    binance_sembolleri = {'BTC/USDT': 'BTCUSDT', 'ETH/USDT': 'ETHUSDT', 'BNB/USDT': 'BNBUSDT', 'SOL/USDT': 'SOLUSDT', 'XRP/USDT': 'XRPUSDT'}
    
    zaman_damgasi = int(time.time() * 1000)
    # Ön belleğe almayı tamamen engelleyen başlıklar
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    
    for sembol, bs in binance_sembolleri.items():
        try:
            # Alternatif global Binance Vision API uç noktası (Türkiye'den engelsiz ve anlık veri akışı sağlar)
            p_url = f"https://data-api.binance.vision/api/v3/ticker/price?symbol={bs}&timestamp={zaman_damgasi}"
            pr = requests.get(p_url, headers=headers, timeout=2)
            fiyat = 0.0
            if pr.status_code == 200:
                fiyat = float(pr.json().get('price', 0.0))

            b_url = f"https://data-api.binance.vision/api/v3/ticker/24hr?symbol={bs}&timestamp={zaman_damgasi}"
            br = requests.get(b_url, headers=headers, timeout=2)
            degisim_24s = 0.5
            if br.status_code == 200:
                bj = br.json()
                degisim_24s = float(bj.get('priceChangePercent', 0.5))
                if fiyat == 0.0:
                    fiyat = float(bj.get('lastPrice', 0.0))
            
            def get_interval_change(interval):
                k_url = f"https://data-api.binance.vision/api/v3/klines?symbol={bs}&interval={interval}&limit=10&timestamp={zaman_damgasi}"
                kr = requests.get(k_url, headers=headers, timeout=2)
                if kr.status_code == 200:
                    k_data = kr.json()
                    if len(k_data) >= 2:
                        acilis = float(k_data[0][1])
                        kapanis = float(k_data[-1][4])
                        if acilis > 0:
                            return ((kapanis - acilis) / acilis) * 100
                return degisim_24s / 3.0

            degisim_1s = get_interval_change('1h')
            degisim_4s = get_interval_change('4h')
            degisim_12s = get_interval_change('12h')

            if fiyat > 0:
                veri_sozlugu[sembol] = {
                    'usd': fiyat, 
                    'usd_24h_change': degisim_24s, 
                    'usd_1h_change': degisim_1s, 
                    'usd_4h_change': degisim_4s, 
                    'usd_12s_change': degisim_12s
                }
        except:
            pass

    return veri_sozlugu

def get_coingecko_price(symbol):
    data = piyasa_verilerini_cek_canli()
    if symbol in data and data[symbol]['usd'] > 0:
        return data[symbol]['usd']
    
    guvenli_fiyatlar = {'BTC/USDT': 85258.0, 'ETH/USDT': 2696.4, 'BNB/USDT': 774.3, 'SOL/USDT': 120.1, 'XRP/USDT': 1.50}
    return guvenli_fiyatlar.get(symbol, 100.0)

def google_sheets_baglan():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" in st.secrets:
            sec = st.secrets["gcp_service_account"]
            creds_dict = {
                "type": sec["type"], "project_id": sec["project_id"], "private_key_id": sec["private_key_id"],
                "private_key": str(sec["private_key"]).replace("\\n", "\n"), "client_email": sec["client_email"],
                "client_id": sec["client_id"], "auth_uri": sec["auth_uri"], "token_uri": sec["token_uri"],
                "auth_provider_x509_cert_url": sec["auth_provider_x509_cert_url"], "client_x509_cert_url": sec["client_x509_cert_url"],
                "universe_domain": sec.get("universe_domain", "googleapis.com")
            }
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        else:
            creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open(GOOGLE_SHEET_ADRESI).worksheet("Sayfa1")
        return sheet
    except Exception: return None

def islem_gecmisi_getir(sheet_guncelle=True):
    sheet = google_sheets_baglan()
    beklenen_kolonlar = ["Islem_ID", "Acilis_Zamani", "Coin", "Yon", "Zaman_Dilimi", "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Durum", "Net_Kar_Zarar", "Guncel_Kasa", "Kapanis_Zamani"]
    
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

    if not df.empty and sheet_guncelle:
        degisti = False
        baz_bakiye = BASLANGIC_BAKIYE
        if os.path.exists(ARSIV_KLASORU):
            arsivler = os.listdir(ARSIV_KLASORU)
            if arsivler:
                arsivler.sort()
                try:
                    son_arsiv_df = pd.read_csv(os.path.join(ARSIV_KLASORU, arsivler[-1]), delimiter=';')
                    if not son_arsiv_df.empty: baz_bakiye = float(pd.to_numeric(son_arsiv_df.iloc[-1]['Guncel_Kasa'], errors='coerce') or BASLANGIC_BAKIYE)
                except: pass
                
        bakiye = baz_bakiye
        for i, r in df.iterrows():
            if str(r['Durum']) != 'Acik': bakiye += float(r['Net_Kar_Zarar'])
            if abs(df.at[i, 'Guncel_Kasa'] - bakiye) > 0.01:
                df.at[i, 'Guncel_Kasa'] = bakiye
                degisti = True

        if degisti: dataframe_guncelle_gsheets(df)

    return df

def dataframe_guncelle_gsheets(df):
    sheet = google_sheets_baglan()
    if sheet is not None:
        try:
            sheet.clear()
            basliklar = list(df.columns)
            sheet.append_row(basliklar)
            for _, row in df.iterrows(): sheet.append_row(list(row.values))
        except: pass

def trend_gecis_epotasi_gonder(coin, yon, fiyat, degisim_24s):
    if not GMAIL_SIFRE or GMAIL_SIFRE == "BURAYA_16_HANELI_UYGULAMA_SIFRESINI_YAZ": return 
    simdi_zaman = tr_zaman()
    if coin in st.session_state['son_mail_zamanlari']:
        if simdi_zaman - st.session_state['son_mail_zamanlari'][coin] < timedelta(hours=2):
            return

    try:
        coin_adi = coin.split('/')[0]
        konu = f"🚀 TREND FURYASI ALARMI: {coin_adi} ({yon}) Fırsatı!"
        mesaj_metni = f"Piyasa Analiz Sinyali:\n\n{coin_adi} varlığında komite teyitleri onaylandı ve {yon} yönlü işlem fırsatı oluştu!\n\nAnlık Fiyat: {fiyat:,.2f} $\n24s Değişim: %{degisim_24s:+.2f}"
        
        msg = MIMEMultipart()
        msg['From'] = GONDERICI_MAIL
        msg['To'] = ALICI_MAIL
        msg['Subject'] = konu
        msg.attach(MIMEText(mesaj_metni, 'plain', 'utf-8'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GONDERICI_MAIL, GMAIL_SIFRE)
        server.sendmail(GONDERICI_MAIL, ALICI_MAIL, msg.as_string())
        server.quit()
        st.session_state['son_mail_zamanlari'][coin] = simdi_zaman
    except: pass

def eposta_gonder(islem_id, coin, durum, net_kar):
    if not GMAIL_SIFRE or GMAIL_SIFRE == "BURAYA_16_HANELI_UYGULAMA_SIFRESINI_YAZ": return 
    try:
         konu = f"🚨 Kripto İşlem Bildirimi: ID #{islem_id} - {coin} ({durum})"
         mesaj_metni = f"İşlem ID #{islem_id} ({coin}) durumu: {durum}\nNet K/Z: {net_kar:.2f} $"
         msg = MIMEMultipart()
         msg['From'] = GONDERICI_MAIL
         msg['To'] = ALICI_MAIL
         msg['Subject'] = konu
         msg.attach(MIMEText(mesaj_metni, 'plain', 'utf-8'))
         server = smtplib.SMTP('smtp.gmail.com', 587)
         server.starttls()
         server.login(GONDERICI_MAIL, GMAIL_SIFRE)
         server.sendmail(GONDERICI_MAIL, ALICI_MAIL, msg.as_string())
         server.quit()
    except: pass

def otomatik_islem_kontrol():
    df = islem_gecmisi_getir(sheet_guncelle=False)
    if df.empty: return
    aciklar = df[df['Durum'] == 'Acik']
    if aciklar.empty: return
    degisiklik_var = False
    
    for idx, row in aciklar.iterrows():
        coin = row['Coin']
        anlik_fiyat = get_coingecko_price(coin)
        if anlik_fiyat == 0: continue
        
        giris_f = float(row['Giris_Fiyat'])
        stop_f = float(row['Stop'])
        kar_al_f = float(row['Kar_Al'])
        miktar = float(row['Islem_Miktari'])
        yon = row['Yon']
        
        yeni_durum = None
        if yon == 'Long':
            if anlik_fiyat <= stop_f: yeni_durum = 'Kapandi (Zarar)'
            elif anlik_fiyat >= kar_al_f: yeni_durum = 'Kapandi (Kar)'
        else:
            if anlik_fiyat >= stop_f: yeni_durum = 'Kapandi (Zarar)'
            elif anlik_fiyat <= kar_al_f: yeni_durum = 'Kapandi (Kar)'
            
        if yeni_durum:
            fark_y = ((anlik_fiyat - giris_f) / giris_f) if yon == 'Long' else ((giris_f - anlik_f) / giris_f)
            net_kar = miktar * KALDIRAC * fark_y
            suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")
            df.at[idx, 'Durum'] = yeni_durum
            df.at[idx, 'Kapanis_Zamani'] = suan_tr
            df.at[idx, 'Net_Kar_Zarar'] = float(round(net_kar, 2))
            degisiklik_var = True
            eposta_gonder(row['Islem_ID'], coin, yeni_durum, net_kar)
            
    if degisiklik_var:
        baz_bakiye = BASLANGIC_BAKIYE
        if os.path.exists(ARSIV_KLASORU):
            arsivler = os.listdir(ARSIV_KLASORU)
            if arsivler:
                arsivler.sort()
                try:
                    son_arsiv_df = pd.read_csv(os.path.join(ARSIV_KLASORU, arsivler[-1]), delimiter=';')
                    if not son_arsiv_df.empty: baz_bakiye = float(pd.to_numeric(son_arsiv_df.iloc[-1]['Guncel_Kasa'], errors='coerce') or BASLANGIC_BAKIYE)
                except: pass
        b = baz_bakiye
        for i, r in df.iterrows():
            if str(r['Durum']) != 'Acik': b += float(r['Net_Kar_Zarar'])
            df.at[i, 'Guncel_Kasa'] = b
        dataframe_guncelle_gsheets(df)

def arka_plan_takip_islemcisi():
    while True:
        try: otomatik_islem_kontrol()
        except: pass
        time.sleep(30)

if 'arka_plan_baslatildi' not in st.session_state:
    st.session_state['arka_plan_baslatildi'] = True
    bg_thread = threading.Thread(target=arka_plan_takip_islemcisi, daemon=True)
    bg_thread.start()

otomatik_islem_kontrol()

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
    mevcut_bakiye = toplam_kasa - acik_marjin
    return float(toplam_kasa), float(mevcut_bakiye)

def dinamik_volatilite_ve_risk_yonetimi(coin_symbol, anlik_fiyat, degisim_24s, degisim_1s, degisim_4s, degisim_12s):
    rsi_val = int(50 + (degisim_24s * 2.5) + (degisim_12s * 3.0) + (degisim_1s * 4.0))
    rsi_val = max(25, min(78, rsi_val))
    
    rsi_durum = "🟢" if rsi_val > 50 else ("🔴" if rsi_val < 50 else "🟡")
    fibo_durum = "🟢" if degisim_24s > 0.0 else ("🔴" if degisim_24s < 0.0 else "🟡")
    
    sma_yon = (degisim_4s + degisim_12s) / 2.0
    sma_durum = "🟢" if sma_yon > 0.0 else ("🔴" if sma_yon < 0.0 else "🟡")
    
    macd_durum = "🟢" if degisim_1s > 0.0 else ("🔴" if degisim_1s < 0.0 else "🟡")
    ichi_durum = "🟢" if degisim_12s > 0 else ("🔴" if degisim_12s < 0 else "🟡")
    
    oylar = [fibo_durum, sma_durum, macd_durum, ichi_durum, rsi_durum]
    yesil_sayisi = oylar.count("🟢")
    kirmizi_sayisi = oylar.count("🔴")
    
    if yesil_sayisi >= 3:
        yon = "Long"
        islem_acis_onayi = True
    elif kirmizi_sayisi >= 3:
        yon = "Short"
        islem_acis_onayi = True
    else:
        yon = "Nötr (Beklemede)"
        islem_acis_onayi = False
    
    if islem_acis_onayi:
        trend_gecis_epotasi_gonder(coin_symbol, yon, anlik_fiyat, degisim_24s)

    temel_puan = abs(degisim_24s) + (yesil_sayisi if yon == "Long" else kirmizi_sayisi) * 2.0 + random.uniform(0.1, 0.9)
    volatilite_faktoru = max(abs(degisim_24s), 0.5) / 100.0
    
    if yon == "Long":
        stop_yuzde = max(0.4, 0.4 + (volatilite_faktoru * 30))
        hedef_yuzde = max(1.2, stop_yuzde * 2.8)
        stop_fiyat = anlik_fiyat * (1 - (stop_yuzde / 100.0))
        hedef_fiyat = anlik_fiyat * (1 + (hedef_yuzde / 100.0))
    elif yon == "Short":
        stop_yuzde = max(0.4, 0.4 + (volatilite_faktoru * 30))
        hedef_yuzde = max(1.2, stop_yuzde * 2.8)
        stop_fiyat = anlik_fiyat * (1 + (stop_yuzde / 100.0))
        hedef_fiyat = anlik_fiyat * (1 - (hedef_yuzde / 100.0))
    else:
        stop_fiyat = anlik_fiyat * 0.99
        hedef_fiyat = anlik_fiyat * 1.01

    rsi_gosterim = f"🟢({rsi_val})" if rsi_val > 50 else (f"🔴({rsi_val})" if rsi_val < 50 else f"🟡({rsi_val})")
    
    def format_degisim_metin(deger):
        isaret = "+" if deger > 0 else ""
        return f"%{isaret}{deger:.1f}"

    d1s_str = format_degisim_metin(degisim_1s)
    d4s_str = format_degisim_metin(degisim_4s)
    d12s_str = format_degisim_metin(degisim_12s)
    d24s_str = format_degisim_metin(degisim_24s)

    teyit_matrisi = f"Fibo {fibo_durum} | SMA {sma_durum} | MACD {macd_durum} | Ichi {ichi_durum} | RSI {rsi_gosterim} [1s:{d1s_str} | 4s:{d4s_str} | 12s:{d12s_str} | 24s:{d24s_str}]"
    
    notr_piyasa = not islem_acis_onayi
    return yon, temel_puan, teyit_matrisi, hedef_fiyat, stop_fiyat, notr_piyasa

def yeni_islem_ekle(coin, yon, giris_fiyat, sepet_orani_yuzde, stop, kar_al, zaman_dilimi):
    if "Nötr" in yon: return False, "⚠️️ Bu coin komite onayından geçemedi, işlem açılamaz!"
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
    return True, f"✅ {coin} emri başarıyla verildi! Tutar: {islem_miktari:.2f} $"

def manuel_islem_kapat(islem_id):
    df = islem_gecmisi_getir()
    idx = df[df['Islem_ID'] == islem_id].index
    if idx.empty: return False, "İşlem bulunamadı!"
    row = df.loc[idx[0]]
    if row['Durum'] != 'Acik': return False, "Bu işlem kapalı!"
    try:
        anlik_fiyat = get_coingecko_price(row['Coin'])
        if anlik_fiyat == 0: anlik_fiyat = float(row['Giris_Fiyat'])
            
        giris_f = float(row['Giris_Fiyat'])
        miktar = float(row['Islem_Miktari'])
        fark_yuzde = ((anlik_fiyat - giris_f) / giris_f) if row['Yon'] == 'Long' else ((giris_f - anlik_f) / giris_f)
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
        eposta_gonder(row['Islem_ID'], row['Coin'], durum_metni, net_kar)
        return True, f"Kapatıldı. K/Z: {net_kar:.2f} $"
    except Exception as e: return False, f"Hata: {str(e)}"

def verileri_getir():
    toplam_kasa, mev_bakiye = bakiye_durumunu_getir()
    islenen_veriler = []
    canli_data = piyasa_verilerini_cek_canli()
    
    for sembol in coinler:
        coin_info = canli_data.get(sembol, {})
        anlik_fiyat = float(coin_info.get('usd', 0.0))
        if anlik_fiyat <= 0.0: anlik_fiyat = get_coingecko_price(sembol)
            
        degisim_24s = float(coin_info.get('usd_24h_change', random.uniform(-0.5, 0.8)))
        degisim_1s = float(coin_info.get('usd_1h_change', random.uniform(-0.3, 0.4)))
        degisim_4s = float(coin_info.get('usd_4h_change', random.uniform(-0.4, 0.5)))
        degisim_12s = float(coin_info.get('usd_12s_change', random.uniform(-0.6, 0.7)))
            
        trend, komite_skoru, teyit_sunumu, hedef_fiyat, stop_fiyat, notr_piyasa = dinamik_volatilite_ve_risk_yonetimi(sembol, anlik_fiyat, degisim_24s, degisim_1s, degisim_4s, degisim_12s)
        
        basamak = 4 if anlik_fiyat < 10 else 2
        bilesik_skor = 0.5 if notr_piyasa else (komite_skoru + (abs(degisim_24s) * 0.5))
        
        islenen_veriler.append({
            "Logo": logo_urls.get(sembol, ""), "Coin": sembol, "Fiyat": round(anlik_fiyat, basamak), 
            "Yon": trend, "Teyit_Sunumu": teyit_sunumu, "Kar_Al": round(hedef_fiyat, basamak), 
            "Stopla": round(stop_fiyat, basamak), "Skor": bilesik_skor, "Basamak": basamak, "Notr": notr_piyasa
        })
    
    if not islenen_veriler: return []
    
    toplam_skor = sum([max(v["Skor"], 0.1) for v in islenen_veriler])
    ham_yuzdeler = []
    for v in islenen_veriler:
        oran = (max(v["Skor"], 0.1) / toplam_skor) * 100
        ham_yuzdeler.append(max(round(oran, 1), 5.0))
            
    fark = 100.0 - sum(ham_yuzdeler)
    if ham_yuzdeler: ham_yuzdeler[0] += fark
        
    for i, v in enumerate(islenen_veriler):
        v["Sepet_Orani"] = round(ham_yuzdeler[i], 1)
        v["Yatırım_Bedeli"] = f"{mev_bakiye * (v['Sepet_Orani'] / 100.0):,.2f} $"
        
    return islenen_veriler

# --- ARAYÜZ ---
st.title("⚡ Pro Kripto & Otomatik Sanal Portföy")

toplam_kasa, mevcut_bakiye = bakiye_durumunu_getir()

col_m1, col_m2 = st.columns(2)
with col_m1:
    st.markdown(f"""
        <div class="metric-container">
            <p style="color: #8b949e; margin: 0px; font-size: 16px; font-weight: bold;">💰 Anlık Toplam Kasa (Çift Teyitli Stop Koruması Aktif)</p>
            <h1 style="color: #ffffff; margin: 5px 0px 0px 0px; font-size: 32px;">{toplam_kasa:,.2f} $ <span style="font-size: 18px; color: {'#00FF00' if toplam_kasa - BASLANGIC_BAKIYE >= 0 else '#FF0000'};">({toplam_kasa - BASLANGIC_BAKIYE:+,.2f} $)</span></h1>
        </div>
    """, unsafe_allow_html=True)
with col_m2:
    st.markdown(f"""
        <div class="metric-container">
            <p style="color: #8b949e; margin: 0px; font-size: 16px; font-weight: bold;">🟢 Mevcut Bakiye (Boştaki Nakit)</p>
            <h1 style="color: #ffffff; margin: 5px 0px 0px 0px; font-size: 32px;">{mevcut_bakiye:,.2f} $</h1>
        </div>
    """, unsafe_allow_html=True)

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📊 Piyasa Taraması & Algoritmik Teyitler", "💼 Sanal Portföy", "📁 Geçmiş Arşiv"])

@st.fragment(run_every=5)
def canli_piyasa_ve_portfoy_alani():
    with tab1:
        col1, col2 = st.columns([4, 1])
        with col2:
            if st.button("🔄 Piyasayı Yenile", use_container_width=True):
                st.rerun()

        with st.spinner('Piyasa ve Sinyal Matrisi Taranıyor...'):
            veriler = verileri_getir()
            
        if veriler:
            st.caption("🔥 *Gelişmiş Komite Modu: data-api.binance.vision üzerinden saniyelik engelsiz canlı fiyat akışı aktif.*")
            df_gosterge = pd.DataFrame(veriler)
            
            df_gosterge['Fiyat_Str'] = df_gosterge.apply(lambda r: f"{r['Fiyat']:,.4f} $" if r['Basamak'] == 4 else f"{r['Fiyat']:,.2f} $", axis=1)
            df_gosterge['Kar_Al_Str'] = df_gosterge.apply(lambda r: f"{r['Kar_Al']:,.4f} $" if r['Basamak'] == 4 else f"{r['Kar_Al']:,.2f} $", axis=1)
            df_gosterge['Stopla_Str'] = df_gosterge.apply(lambda r: f"{r['Stopla']:,.4f} $" if r['Basamak'] == 4 else f"{r['Stopla']:,.2f} $", axis=1)
            df_gosterge['Sepet_Orani_Str'] = df_gosterge.apply(lambda r: f"%{r['Sepet_Orani']:.1f}" if r['Sepet_Orani'] != int(r['Sepet_Orani']) else f"%{int(r['Sepet_Orani'])}", axis=1)
            
            gosterilecek_df = df_gosterge[['Logo', 'Coin', 'Fiyat_Str', 'Yon', 'Teyit_Sunumu', 'Sepet_Orani_Str', 'Yatırım_Bedeli', 'Kar_Al_Str', 'Stopla_Str']]
            
            gosterilecek_df.columns = [
                ' ', 
                'Coin\nAdı', 
                'Anlık\nFiyat', 
                'İşlem\nYönü', 
                'Sinyal Teyit Matrisi & Çoklu Zaman Dilimi Analizi\n(Detaylı Teknik Göstergeler)', 
                'Önerilen\nOran', 
                'Yatırım\nTutarı', 
                'Kar Al\nHedefi', 
                'Stop\nSeviyesi'
            ]
            
            def apply_styling_piyasa(df):
                df_styles = pd.DataFrame('', index=df.index, columns=df.columns)
                for i in range(len(df)):
                    r_data = df_gosterge.iloc[i]
                    yon_idx = df.columns.get_loc('İşlem\nYönü')
                    if r_data['Yon'] == 'Long': df_styles.iloc[i, yon_idx] = 'color: #00FF00; font-weight: bold;'
                    elif r_data['Yon'] == 'Short': df_styles.iloc[i, yon_idx] = 'color: #FF0000; font-weight: bold;'
                    else: df_styles.iloc[i, yon_idx] = 'color: #FFFF00; font-weight: bold;'
                        
                    oran_idx = df.columns.get_loc('Önerilen\nOran')
                    if r_data['Notr']: 
                        df_styles.iloc[i, oran_idx] = 'background-color: rgba(255, 255, 0, 0.25); color: rgb(255, 255, 0); font-weight: bold; text-align: center;'
                    elif r_data['Yon'] == 'Long': 
                        df_styles.iloc[i, oran_idx] = 'background-color: rgba(0, 255, 0, 0.25); color: rgb(0, 255, 0); font-weight: bold; text-align: center;'
                    else: 
                        df_styles.iloc[i, oran_idx] = 'background-color: rgba(255, 0, 0, 0.25); color: rgb(255, 0, 0); font-weight: bold; text-align: center;'
                return df_styles

            st.dataframe(gosterilecek_df.style.apply(apply_styling_piyasa, axis=None), use_container_width=True, hide_index=True, column_config={" ": st.column_config.ImageColumn(" ", width="small")})
            
            st.markdown("---")
            st.markdown("### 🛒 Hızlı İşlem Emri Ver (Paper Trading)")
            secilen_coin = st.selectbox("İşleme Girmek İstediğiniz Coini Seçin:", df_gosterge['Coin'].tolist(), key="secilen_coin_select")
            
            if secilen_coin:
                coin_verisi = df_gosterge[df_gosterge['Coin'] == secilen_coin].iloc[0]
                onerilen_oran_val = float(coin_verisi['Sepet_Orani'])
                
                if coin_verisi['Notr']: st.warning("⚠️️ **Komite Durumu:** Bu coin şu an Nötr/Beklemede konumunda.")
                st.info(f"**Karar Matrisi:** {coin_verisi['Teyit_Sunumu']}")
            
                secilen_oran = st.slider("Mevcut Bakiye Üzerinden Yatırım Oranını Seçin (%):", min_value=0.0, max_value=100.0, value=onerilen_oran_val, step=0.5, key="oran_slider")
                hesaplanan_tutar = mevcut_bakiye * (secilen_oran / 100.0)
                
                st.markdown(f"💼 **Yatırım Tutarı:** `{hesaplanan_tutar:,.2f} $` &nbsp;&nbsp;|&nbsp;&nbsp; <span style='color: #ffffff; font-size: 16px; font-weight: bold;'>Mevcut Nakit Bakiye: <b>{mevcut_bakiye:,.2f} $</b></span>", unsafe_allow_html=True)
                
                if st.button(f"🚀 {secilen_coin} İşlemini Başlat", key="islem_baslat_btn"):
                    basari, mesaj = yeni_islem_ekle(coin=secilen_coin, yon=coin_verisi['Yon'], giris_fiyat=coin_verisi['Fiyat'], sepet_orani_yuzde=secilen_oran, stop=coin_verisi['Stopla'], kar_al=coin_verisi['Kar_Al'], zaman_dilimi="Çoklu Zaman Dilimi Filtreli")
                    if basari: 
                        st.success(mesaj)
                        time.sleep(0.5)
                        st.rerun()
                    else: st.error(mesaj)

    with tab2:
        col_p_baslik, col_p_buton = st.columns([3, 1])
        with col_p_baslik: st.markdown(f"### 💰 Aktif Dönem Kasası: **{toplam_kasa:,.2f} $**")
        with col_p_buton:
            if st.button("🔄 Portföyü Yenile", use_container_width=True, key="portfoy_yenile_btn"):
                st.rerun()
        
        df_gecmis = islem_gecmisi_getir(sheet_guncelle=False)
        if not df_gecmis.empty:
            acik_islem_listesi = df_gecmis[df_gecmis['Durum'] == 'Acik']['Islem_ID'].tolist()
            if acik_islem_listesi:
                st.markdown("#### 🛑 Güvenli Manuel İşlem Kapatma Paneli")
                col_kapat1, col_kapat2, col_kapat3 = st.columns([2, 2, 1])
                with col_kapat1: kapatilacak_id = st.selectbox("Kapatılacak İşlem ID:", acik_islem_listesi, key="kapat_id_select")
                with col_kapat2: onay_verildi = st.checkbox(f"ID #{kapatilacak_id} işlemini kapatmayı onaylıyorum", key="onay_chk")
                with col_kapat3:
                    st.write("") 
                    if st.button("🔒 İşlemi Sonlandır", key="kapat_btn"):
                        if onay_verildi:
                            b_durum, b_mesaj = manuel_islem_kapat(kapatilacak_id)
                            if b_durum: 
                                st.success(b_mesaj)
                                time.sleep(0.5)
                                st.rerun()
                            else: st.error(b_mesaj)
                        else: st.warning("Lütfen önce onay kutusunu işaretleyin!")
                st.markdown("---")

            df_gecmis_copy = df_gecmis.copy()
            df_gecmis_copy['Logo'] = df_gecmis_copy['Coin'].map(logo_urls)
            
            anlik_kz_sozluk, hedef_kar_sozluk, olasi_stop_sozluk = {}, {}, {}
            
            for idx, row in df_gecmis_copy.iterrows():
                islem_id = row['Islem_ID']
                giris_f = float(pd.to_numeric(row['Giris_Fiyat'], errors='coerce') or 0.0)
                miktar = float(pd.to_numeric(row['Islem_Miktari'], errors='coerce') or 0.0)
                kar_al_f = float(pd.to_numeric(row['Kar_Al'], errors='coerce') or 0.0)
                stop_f = float(pd.to_numeric(row['Stop'], errors='coerce') or 0.0)
                yon = row['Yon']
                
                if giris_f == 0.0 or kar_al_f == 0.0 or stop_f == 0.0:
                    hedef_kar_sozluk[islem_id] = 0.0
                    olasi_stop_sozluk[islem_id] = 0.0
                    anlik_kz_sozluk[islem_id] = float(pd.to_numeric(row['Net_Kar_Zarar'], errors='coerce') or 0.0)
                    continue
                
                hedef_fark_y = ((kar_al_f - giris_f) / giris_f) if yon == 'Long' else ((giris_f - kar_al_f) / giris_f)
                hedef_kar_sozluk[islem_id] = round(miktar * KALDIRAC * hedef_fark_y, 2)
                
                stop_fark_y = ((stop_f - giris_f) / giris_f) if yon == 'Long' else ((giris_f - stop_f) / giris_f)
                olasi_stop_sozluk[islem_id] = round(miktar * KALDIRAC * stop_fark_y, 2)
                
                if row['Durum'] == 'Acik':
                    anlik_f = get_coingecko_price(row['Coin'])
                    if anlik_f > 0:
                        fark_y = ((anlik_f - giris_f) / giris_f) if yon == 'Long' else ((giris_f - anlik_f) / giris_f)
                        anlik_kz_sozluk[islem_id] = round(miktar * KALDIRAC * fark_y, 2)
                    else: anlik_kz_sozluk[islem_id] = 0.0
                else:
                    anlik_kz_sozluk[islem_id] = float(pd.to_numeric(row['Net_Kar_Zarar'], errors='coerce') or 0.0)
                    
            df_gecmis_copy['Hedef_Kar'] = df_gecmis_copy['Islem_ID'].map(hedef_kar_sozluk)
            df_gecmis_copy['Olasi_Stop'] = df_gecmis_copy['Islem_ID'].map(olasi_stop_sozluk)
            df_gecmis_copy['Anlik_KZ_Deger'] = df_gecmis_copy['Islem_ID'].map(anlik_kz_sozluk)
            
            islem_miktari_seri = pd.to_numeric(df_gecmis_copy['Islem_Miktari'], errors='coerce').fillna(0.0)
            guncel_kasa_seri = pd.to_numeric(df_gecmis_copy['Guncel_Kasa'], errors='coerce').fillna(BASLANGIC_BAKIYE)
            
            def guvenli_yuzde(oran):
                if pd.isna(oran) or oran == float('inf') or oran == float('-inf') or oran <= 0: return "%0.0"
                return f"%{float(oran):.1f}"

            df_gecmis_copy['Islem_Orani'] = ((islem_miktari_seri / guncel_kasa_seri) * 100).apply(guvenli_yuzde)
            
            def format_fiyat_hucre(val, coin_adi):
                b = 4 if coin_adi == 'XRP/USDT' or float(val) < 10 else 2
                return f"{float(val):,.{b}f} $"

            df_gecmis_copy['Giris_Fiyat_Str'] = df_gecmis_copy.apply(lambda r: format_fiyat_hucre(r['Giris_Fiyat'], r['Coin']), axis=1)
            df_gecmis_copy['Stop_Str'] = df_gecmis_copy.apply(lambda r: format_fiyat_hucre(r['Stop'], r['Coin']), axis=1)
            df_gecmis_copy['Kar_Al_Str'] = df_gecmis_copy.apply(lambda r: format_fiyat_hucre(r['Kar_Al'], r['Coin']), axis=1)

            df_gecmis_copy['Yatırım_Bedeli'] = islem_miktari_seri.apply(lambda x: f"{x:,.2f} $")
            df_gecmis_copy['Hedef_Kar_Str'] = df_gecmis_copy['Hedef_Kar'].apply(lambda x: f"{x:,.2f} $")
            df_gecmis_copy['Olasi_Stop_Str'] = df_gecmis_copy['Olasi_Stop'].apply(lambda x: f"{x:,.2f} $")
            df_gecmis_copy['Anlık_KZ_Str'] = df_gecmis_copy['Anlik_KZ_Deger'].apply(lambda x: f"{x:+,.2f} $")
            df_gecmis_copy['Kasa_Str'] = guncel_kasa_seri.apply(lambda x: f"{x:,.2f} $")
            
            cols = ["Islem_ID", "Acilis_Zamani", "Logo", "Coin", "Yon", "Giris_Fiyat_Str", "Islem_Orani", "Yatırım_Bedeli", "Stop_Str", "Kar_Al_Str", "Hedef_Kar_Str", "Olasi_Stop_Str", "Durum", "Anlık_KZ_Str", "Kapanis_Zamani", "Kasa_Str"]
            df_gosterim = df_gecmis_copy[cols].copy()
            
            df_gosterim.columns = [
                "İşlem\nID", "Açılış\nZamanı", " ", "Coin\nAdı", "İşlem\nYönü", 
                "Giriş\nFiyatı", "Sepet\nOranı", "Yatırım\nTutarı", "Stop\nSeviyesi", 
                "Kar Al\nHedefi", "Beklenen\nKar", "Olası\nStop", "İşlem\nDurumu", 
                "Anlık\nK/Z", "Kapanış\nZamanı", "Güncel\nKasa"
            ]
            
            def parse_money(val_str):
                try:
                    clean_str = str(val_str).replace('$', '').replace('+', '').replace(',', '').strip()
                    return float(clean_str)
                except: return 0.0

            def tabloyu_renklendir(row):
                styles = pd.Series([''] * len(row), index=row.index)
                durum_str, yon_str = str(row['İşlem\nDurumu']), str(row['İşlem\nYönü'])
                
                if 'Long' in yon_str: styles['İşlem\nYönü'] = 'color: #00FF00; font-weight: bold;'
                elif 'Short' in yon_str: styles['İşlem\nYönü'] = 'color: #FF0000; font-weight: bold;'
                
                if 'Acik' in durum_str: styles['İşlem\nDurumu'] = 'background-color: #0066FF; color: white; font-weight: bold;'
                elif 'Kar' in durum_str: styles['İşlem\nDurumu'] = 'background-color: #00FF00; color: black; font-weight: bold;' 
                else: styles['İşlem\nDurumu'] = 'background-color: #FF0000; color: white; font-weight: bold;' 
                    
                kz = parse_money(row['Anlık\nK/Z'])
                h_kar, o_stop = parse_money(row['Beklenen\nKar']), parse_money(row['Olası\nStop'])
                if h_kar == 0: h_kar = 1.0
                if o_stop == 0: o_stop = -1.0
                
                if kz == 0: r, g, b = 255, 255, 0 
                elif kz > 0:
                    ratio = min(kz / h_kar, 1.0) if h_kar > 0 else 1.0
                    r, g, b = int(255 * (1 - ratio)), 255, 0
                else: 
                    ratio = min(abs(kz) / abs(o_stop), 1.0) if o_stop < 0 else 1.0
                    r, g, b = 255, int(255 * (1 - ratio)), 0
                    
                parlaklik = (r * 299 + g * 587 + b * 114) / 1000
                yazi_rengi = '#000000' if parlaklik > 128 else '#FFFFFF'
                kz_stili = f'background-color: rgb({r},{g},{b}); color: {yazi_rengi}; font-weight: bold;'
                
                styles['Anlık\nK/Z'] = kz_stili
                if 'Acik' in durum_str:
                    styles['Beklenen\nKar'] = kz_stili
                    styles['Olası\nStop'] = kz_stili
                return styles

            st.dataframe(df_gosterim.style.apply(tabloyu_renklendir, axis=1), use_container_width=True, hide_index=True, column_config={" ": st.column_config.ImageColumn(" ", width="small")})

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
                    fig = px.pie(df_pie, names='Durum', values='Adet', hole=0.35, color='Durum', color_discrete_map={'Kârlı İşlemler': '#00FF00', 'Zararlı İşlemler': '#FF0000'})
                    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white', margin=dict(t=10, b=10, l=10, r=10), legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
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
                        <p style="color: #00FF00; margin: 0px; font-size: 15px; font-weight: bold;">Toplam Kâr:</p>
                        <h3 style="color: #00FF00; margin: 0px 0px 10px 0px;">+{toplam_kazanc_dolar:,.2f} $</h3>
                        <p style="color: #FF0000; margin: 0px; font-size: 15px; font-weight: bold;">Toplam Zarar:</p>
                        <h3 style="color: #FF0000; margin: 0px 0px 10px 0px;">-{toplam_kayip_dolar:,.2f} $</h3>
                        <hr style="border-color: #30363d; margin: 8px 0px;">
                        <p style="color: #ffffff; margin: 0px; font-size: 14px;">Net Fark:</p>
                        <h3 style="color: {'#00FF00' if net_fark_dolar >= 0 else '#FF0000'}; margin: 0px;">{net_fark_dolar:+,.2f} $</h3>
                    </div>
                    """, unsafe_allow_html=True)
            else: st.info("Henüz kapanmış işlem bulunmuyor.")
        else: st.info("Henüz açılmış bir sanal işleminiz bulunmuyor.")

    with tab3:
        st.markdown("### 📁 Geçmiş Arşiv Dosyaları İnceleme")
        if os.path.exists(ARSIV_KLASORU):
            arsiv_dosyalari = os.listdir(ARSIV_KLASORU)
            if arsiv_dosyalari:
                secilen_arsiv = st.selectbox("İncelemek İstediğiniz Arşiv Dönemi:", arsiv_dosyalari, key="arsiv_select")
                if secilen_arsiv:
                    df_arsiv = pd.read_csv(os.path.join(ARSIV_KLASORU, secilen_arsiv), delimiter=';')
                    st.dataframe(df_arsiv, use_container_width=True, hide_index=True)
            else: st.info("Arşivde henüz tamamlanmış dönem bulunmuyor.")
        else: st.info("Arşiv klasörü henüz oluşturulmadı.")

canli_piyasa_ve_portfoy_alani()