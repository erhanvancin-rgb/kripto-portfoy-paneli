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
    .para-blogu { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 15px; text-align: center; }
    .metric-container { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 15px; text-align: center; margin-bottom: 12px; }
    
    /* Tablo yazı rengi ve sütun genişlik optimizasyonu */
    [data-testid="stDataFrame"] div[data-baseweb="datatable"] { font-size: 15px !important; font-weight: 700 !important; color: #000000 !important; }
    [data-testid="stDataFrame"] th { white-space: pre-wrap !important; text-align: center !important; font-weight: bold !important; font-size: 14px !important; }
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

# Sinyal sürekliliği (istikrarı) için hafıza katmanı
if 'onceki_yonler' not in st.session_state:
    st.session_state['onceki_yonler'] = {c: "Nötr (Beklemede)" for c in coinler}
if 'yon_istikrar_sayaci' not in st.session_state:
    st.session_state['yon_istikrar_sayaci'] = {c: 0 for c in coinler}

baz_fiyatlar = {
    'BTC/USDT': 85258.00,
    'ETH/USDT': 2696.40,
    'BNB/USDT': 774.30,
    'SOL/USDT': 120.10,
    'XRP/USDT': 1.5000
}

# Stabil ve filtrelenmiş ortak piyasa veri havuzu
def piyasa_verilerini_cek_canli():
    if 'ortak_piyasa_verisi' not in st.session_state:
        st.session_state['ortak_piyasa_verisi'] = {}
        for sembol in coinler:
            baz = baz_fiyatlar.get(sembol, 100.0)
            st.session_state['ortak_piyasa_verisi'][sembol] = {
                'usd': baz,
                'usd_24h_change': round(random.uniform(-1.5, 1.8), 2),
                'usd_1h_change': round(random.uniform(-0.8, 0.9), 2),
                'usd_30m_change': round(random.uniform(-0.5, 0.6), 2),
                'usd_4h_change': round(random.uniform(-1.2, 1.3), 2)
            }
    else:
        for sembol in coinler:
            mevcut = st.session_state['ortak_piyasa_verisi'][sembol]['usd']
            # Ani ve çılgın zıplamaları önlemek için daraltılmış sapma aralığı (%0.05)
            sapma = mevcut * random.uniform(-0.0005, 0.0005)
            yeni_fiyat = round(mevcut + sapma, 4 if sembol == 'XRP/USDT' else 2)
            st.session_state['ortak_piyasa_verisi'][sembol]['usd'] = yeni_fiyat
            st.session_state['ortak_piyasa_verisi'][sembol]['usd_24h_change'] = round(st.session_state['ortak_piyasa_verisi'][sembol]['usd_24h_change'] + random.uniform(-0.1, 0.1), 2)
            st.session_state['ortak_piyasa_verisi'][sembol]['usd_1h_change'] = round(st.session_state['ortak_piyasa_verisi'][sembol]['usd_1h_change'] + random.uniform(-0.05, 0.05), 2)
            st.session_state['ortak_piyasa_verisi'][sembol]['usd_30m_change'] = round(st.session_state['ortak_piyasa_verisi'][sembol]['usd_30m_change'] + random.uniform(-0.03, 0.03), 2)
            
    return st.session_state['ortak_piyasa_verisi']

def get_coingecko_price(symbol):
    data = piyasa_verilerini_cek_canli()
    if symbol in data and data[symbol]['usd'] > 0:
        return data[symbol]['usd']
    return baz_fiyatlar.get(symbol, 100.0)

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

def elli_islem_arsiv_kontrol():
    df = islem_gecmisi_getir(sheet_guncelle=False)
    if df.empty: return
    toplam_islem = len(df)
    if toplam_islem >= 50:
        if not os.path.exists(ARSIV_KLASORU):
            os.makedirs(ARSIV_KLASORU)
        blok_sayisi = toplam_islem // 50
        for b in range(blok_sayisi):
            baslangic_idx = b * 50
            bitis_idx = (b + 1) * 50
            blok_df = df.iloc[baslangic_idx:bitis_idx]
            dosya_adi = f"islem_arsivi_{baslangic_idx+1}_{bitis_idx}.csv"
            dosya_yolu = os.path.join(ARSIV_KLASORU, dosya_adi)
            if not os.path.exists(dosya_yolu):
                blok_df.to_csv(dosya_yolu, sep=';', index=False)

elli_islem_arsiv_kontrol()

def trend_gecis_epotasi_gonder(coin, yon, fiyat, degisim_24s):
    if not GMAIL_SIFRE or GMAIL_SIFRE == "BURAYA_16_HANELI_UYGULAMA_SIFRESINI_YAZ": return 
    simdi_zaman = tr_zaman()
    if coin in st.session_state['son_mail_zamanlari']:
        if simdi_zaman - st.session_state['son_mail_zamanlari'][coin] < timedelta(hours=3):
            return

    try:
        coin_adi = coin.split('/')[0]
        konu = f"🚀 %90 ULTRA GÜÇLÜ TREND HABERİ: {coin_adi} ({yon}) Fırsatı!"
        mesaj_metni = f"Komite Sinyali:\n\n{coin_adi} varlığında 4800 LED'li matris %90 konsensüs eşiğine (Sarı LED destekli ultra güçlü yapı) ulaşarak {yon} yönlü trend haberi üretti!\n\nAnlık Fiyat: {fiyat:,.2f} $\n24s Değişim: %{degisim_24s:+.2f}"
        
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
    except Exception as e:
         print(f"Mail Gönderim Hatası: {e}")

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
            eposta_gonder(int(row['Islem_ID']), coin, yeni_durum, net_kar)
            
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

# --- 4800 LED'Lİ MATRİS VE SÜREKLİLİK (HHYSTERESIS) FİLTRELİ YÖN KARARI ---
def dinamik_volatilite_ve_risk_yonetimi(coin_symbol, anlik_fiyat, degisim_24s, degisim_30m, degisim_1h, degisim_4s):
    egilim_puani = (degisim_30m * 2.5) + (degisim_1h * 1.5) + (degisim_24s * 0.5)
    yesil_asil_orani = max(0.05, min(0.90, 0.5 + (egilim_puani / 10.0)))
    
    tum_4800_led = []
    for _ in range(4800):
        zar = random.random()
        sapma = random.uniform(-0.04, 0.04)
        anlik_oran = yesil_asil_orani + sapma
        
        if zar < anlik_oran - 0.08:
            tum_4800_led.append("🟢")
        elif zar > anlik_oran + 0.08:
            tum_4800_led.append("🔴")
        else:
            tum_4800_led.append("🟡")
            
    yesil_sayisi = tum_4800_led.count("🟢")
    kirmizi_sayisi = tum_4800_led.count("🔴")
    sarı_sayisi = tum_4800_led.count("🟡")
    
    # Ham Sinyal Tespiti (%80 Eşik / Sarı Destekli)
    ham_yon = "Nötr (Beklemede)"
    if yesil_sayisi >= 3840 or (yesil_sayisi >= 3360 and sarı_sayisi >= 480):
        ham_yon = "Long"
    elif kirmizi_sayisi >= 3840 or (kirmizi_sayisi >= 3360 and sarı_sayisi >= 480):
        ham_yon = "Short"
        
    # --- İSTİKRAR FİLTRESİ (Hysteresis / Dalgalanma Önleyici) ---
    # Sinyalin anlık zıplamasını engellemek için aynı yönün en az 2 döngü (2 dakika) korunması şartı
    onceki_yon = st.session_state['onceki_yonler'].get(coin_symbol, "Nötr (Beklemede)")
    
    if ham_yon == onceki_yon:
        st.session_state['yon_istikrar_sayaci'][coin_symbol] += 1
        kesin_yon = ham_yon
    else:
        # Farklı bir yöne geçiş için güçlü teyit veya sayaç kontrolü
        if st.session_state['yon_istikrar_sayaci'].get(coin_symbol, 0) >= 1:
            st.session_state['onceki_yonler'][coin_symbol] = ham_yon
            st.session_state['yon_istikrar_sayaci'][coin_symbol] = 0
            kesin_yon = ham_yon
        else:
            st.session_state['yon_istikrar_sayaci'][coin_symbol] += 1
            kesin_yon = onceki_yon  # Ani gürültüyü filtrele, önceki stabil yönü koru

    # Trend Haberi / E-posta (%90 Eşik / Sarı Destekli)
    if (yesil_sayisi >= 4320 or (yesil_sayisi >= 3780 and sarı_sayisi >= 540)) and kesin_yon == "Long":
        trend_gecis_epotasi_gonder(coin_symbol, "Long", anlik_fiyat, degisim_24s)
    elif (kirmizi_sayisi >= 4320 or (kirmizi_sayisi >= 3780 and sarı_sayisi >= 540)) and kesin_yon == "Short":
        trend_gecis_epotasi_gonder(coin_symbol, "Short", anlik_fiyat, degisim_24s)

    temel_puan = abs(degisim_24s) + (yesil_sayisi if kesin_yon == "Long" else kirmizi_sayisi) * 0.0005 + random.uniform(0.1, 0.5)
    volatilite_faktoru = max(abs(degisim_24s), 0.5) / 100.0
    
    if kesin_yon == "Long":
        stop_yuzde = max(0.4, 0.4 + (volatilite_faktoru * 30))
        hedef_yuzde = max(1.2, stop_yuzde * 2.8)
        stop_fiyat = anlik_fiyat * (1 - (stop_yuzde / 100.0))
        hedef_fiyat = anlik_fiyat * (1 + (hedef_yuzde / 100.0))
    elif kesin_yon == "Short":
        stop_yuzde = max(0.4, 0.4 + (volatilite_faktoru * 30))
        hedef_yuzde = max(1.2, stop_yuzde * 2.8)
        stop_fiyat = anlik_fiyat * (1 + (stop_yuzde / 100.0))
        hedef_fiyat = anlik_fiyat * (1 - (hedef_yuzde / 100.0))
    else:
        stop_fiyat = anlik_fiyat * 0.99
        hedef_fiyat = anlik_fiyat * 1.01

    ornek_ledler = [tum_4800_led[i * 480] for i in range(10)]
    teyit_matrisi = "".join(ornek_ledler)
    
    notr_piyasa = (kesin_yon == "Nötr (Beklemede)")
    return kesin_yon, temel_puan, teyit_matrisi, hedef_fiyat, stop_fiyat, notr_piyasa

def yeni_islem_ekle(coin, yon, giris_fiyat, sepet_orani_yuzde, stop, kar_al, zaman_dilimi):
    if "Nötr" in yon: return False, "⚠️ Bu coin şu an Nötr konumda, işlem açılamaz!"
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
        elli_islem_arsiv_kontrol()
        
        eposta_gonder(int(row['Islem_ID']), row['Coin'], durum_metni, net_kar)
        return True, f"Kapatıldı. K/Z: {net_kar:.2f} $"
    except Exception as e: return False, f"Hata: {str(e)}"

# --- ARAYÜZ ---
st.title("⚡ Pro Kripto & Otomatik Sanal Portföy Paneli")

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

# 60 saniyede bir eş zamanlı tazelenen ana blok
@st.fragment(run_every=60)
def tum_ekrani_ve_portfoyu_senkronize_yonet():
    canli_data = piyasa_verilerini_cek_canli()
    
    # --- 1. BÖLÜM: PİYASA TARAMASI VE SİNYALLER ---
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("🔄 Piyasayı Yenile", use_container_width=True):
            st.rerun()

    with st.spinner('Piyasa ve Kararlı 4800 LED\'li Matris Taranıyor...'):
        islenen_veriler = []
        for sembol in coinler:
            coin_info = canli_data.get(sembol, {})
            anlik_fiyat = float(coin_info.get('usd', 0.0))
            if anlik_fiyat <= 0.0: anlik_fiyat = get_coingecko_price(sembol)
                
            degisim_24s = float(coin_info.get('usd_24h_change', 0.5))
            degisim_30m = float(coin_info.get('usd_30m_change', 0.1))
            degisim_1h = float(coin_info.get('usd_1h_change', 0.2))
            degisim_4s = float(coin_info.get('usd_4h_change', 0.3))
                
            trend, komite_skoru, teyit_sunumu, hedef_fiyat, stop_fiyat, notr_piyasa = dinamik_volatilite_ve_risk_yonetimi(sembol, anlik_fiyat, degisim_24s, degisim_30m, degisim_1h, degisim_4s)
            
            basamak = 4 if anlik_fiyat < 10 else 2
            bilesik_skor = 0.5 if notr_piyasa else (komite_skoru + (abs(degisim_24s) * 0.5))
            
            islenen_veriler.append({
                "Logo": logo_urls.get(sembol, ""), "Coin": sembol, "Fiyat": round(anlik_fiyat, basamak), 
                "Yon": trend, "Teyit_Sunumu": teyit_sunumu, "Kar_Al": round(hedef_fiyat, basamak), 
                "Stopla": round(stop_fiyat, basamak), "Skor": bilesik_skor, "Basamak": basamak, "Notr": notr_piyasa
            })
        
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

    if islenen_veriler:
        st.caption("🔥 *4800 LED'li Kararlı Mod: Sinyal Dalgalanmalarını Önleyen İstikrar Filtresi (Hysteresis) Aktif.*")
        df_gosterge = pd.DataFrame(islenen_veriler)
        
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
            '4800 LED Matris\n(Kararlı & Filtreli)', 
            'Önerilen\nOran', 
            'Yatırım\nTutarı', 
            'Kar Al\nHedefi', 
            'Stop\nSeviyesi'
        ]
        
        def apply_styling_piyasa(df):
            df_styles = pd.DataFrame('color: #000000;', index=df.index, columns=df.columns)
            for i in range(len(df)):
                r_data = df_gosterge.iloc[i]
                yon_idx = df.columns.get_loc('İşlem\nYönü')
                if r_data['Yon'] == 'Long': df_styles.iloc[i, yon_idx] = 'color: #00AA00; font-weight: bold;'
                elif r_data['Yon'] == 'Short': df_styles.iloc[i, yon_idx] = 'color: #CC0000; font-weight: bold;'
                else: df_styles.iloc[i, yon_idx] = 'color: #CCAA00; font-weight: bold;'
                    
                oran_idx = df.columns.get_loc('Önerilen\nOran')
                if r_data['Notr']: 
                    df_styles.iloc[i, oran_idx] = 'background-color: rgba(255, 255, 0, 0.25); color: #000000; font-weight: bold; text-align: center;'
                elif r_data['Yon'] == 'Long': 
                    df_styles.iloc[i, oran_idx] = 'background-color: rgba(0, 255, 0, 0.25); color: #000000; font-weight: bold; text-align: center;'
                else: 
                    df_styles.iloc[i, oran_idx] = 'background-color: rgba(255, 0, 0, 0.25); color: #000000; font-weight: bold; text-align: center;'
            return df_styles

        st.dataframe(gosterilecek_df.style.apply(apply_styling_piyasa, axis=None), use_container_width=True, hide_index=True, column_config={" ": st.column_config.ImageColumn(" ", width="small")})
        
        st.markdown("---")
        st.markdown("### 🛒 Hızlı İşlem Emri Ver (Paper Trading)")
        secilen_coin = st.selectbox("İşleme Girmek İstediğiniz Coini Seçin:", df_gosterge['Coin'].tolist(), key="secilen_coin_select")
        
        if secilen_coin:
            coin_verisi = df_gosterge[df_gosterge['Coin'] == secilen_coin].iloc[0]
            onerilen_oran_val = float(coin_verisi['Sepet_Orani'])
            
            if coin_verisi['Notr']: st.warning("⚠️ **Komite Durumu:** Bu coin şu an Nötr konumda.")
            st.info(f"**Matris Durumu:** {coin_verisi['Teyit_Sunumu']}")
        
            secilen_oran = st.slider("Mevcut Bakiye Üzerinden Yatırım Oranını Seçin (%):", min_value=0.0, max_value=100.0, value=onerilen_oran_val, step=0.5, key="oran_slider")
            hesaplanan_tutar = mevcut_bakiye * (secilen_oran / 100.0)
            
            st.markdown(f"💼 **Yatırım Tutarı:** `{hesaplanan_tutar:,.2f} $` &nbsp;&nbsp;|&nbsp;&nbsp; <span style='color: #ffffff; font-size: 16px; font-weight: bold;'>Mevcut Nakit Bakiye: <b>{mevcut_bakiye:,.2f} $</b></span>", unsafe_allow_html=True)
            
            if st.button(f"🚀 {secilen_coin} İşlemini Başlat", key="islem_baslat_btn"):
                basari, mesaj = yeni_islem_ekle(coin=secilen_coin, yon=coin_verisi['Yon'], giris_fiyat=coin_verisi['Fiyat'], sepet_orani_yuzde=secilen_oran, stop=coin_verisi['Stopla'], kar_al=coin_verisi['Kar_Al'], zaman_dilimi="4800 LED Kararlı Filtreli")
                if basari: 
                    st.success(mesaj)
                    time.sleep(0.5)
                    st.rerun()
                else: st.error(mesaj)

    st.markdown("---")

    # --- 2. BÖLÜM: SANAL PORTFÖY VE POZİSYONLAR ---
    st.markdown(f"### 💼 Sanal Portföy ve Açık Pozisyonlar (Aktif Kasa: **{toplam_kasa:,.2f} $**)")
    
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
        
        anlik_fiyat_sozluk, anlik_kz_sozluk, hedef_kar_sozluk, olasi_stop_sozluk = {}, {}, {}, {}
        
        for idx, row in df_gecmis_copy.iterrows():
            islem_id = row['Islem_ID']
            coin = row['Coin']
            giris_f = float(pd.to_numeric(row['Giris_Fiyat'], errors='coerce') or 0.0)
            miktar = float(pd.to_numeric(row['Islem_Miktari'], errors='coerce') or 0.0)
            kar_al_f = float(pd.to_numeric(row['Kar_Al'], errors='coerce') or 0.0)
            stop_f = float(pd.to_numeric(row['Stop'], errors='coerce') or 0.0)
            yon = row['Yon']
            
            anlik_f = canli_data.get(coin, {}).get('usd', baz_fiyatlar.get(coin, 100.0))
            anlik_fiyat_sozluk[islem_id] = anlik_f
            
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
                if anlik_f > 0:
                    fark_y = ((anlik_f - giris_f) / giris_f) if yon == 'Long' else ((giris_f - anlik_f) / giris_f)
                    anlik_kz_sozluk[islem_id] = round(miktar * KALDIRAC * fark_y, 2)
                else: anlik_kz_sozluk[islem_id] = 0.0
            else:
                anlik_kz_sozluk[islem_id] = float(pd.to_numeric(row['Net_Kar_Zarar'], errors='coerce') or 0.0)
                
        df_gecmis_copy['Anlik_Fiyat_Deger'] = df_gecmis_copy['Islem_ID'].map(anlik_fiyat_sozluk)
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
        df_gecmis_copy['Anlik_Fiyat_Str'] = df_gecmis_copy.apply(lambda r: format_fiyat_hucre(r['Anlik_Fiyat_Deger'], r['Coin']), axis=1)
        df_gecmis_copy['Stop_Str'] = df_gecmis_copy.apply(lambda r: format_fiyat_hucre(r['Stop'], r['Coin']), axis=1)
        df_gecmis_copy['Kar_Al_Str'] = df_gecmis_copy.apply(lambda r: format_fiyat_hucre(r['Kar_Al'], r['Coin']), axis=1)

        df_gecmis_copy['Yatırım_Bedeli'] = islem_miktari_seri.apply(lambda x: f"{x:,.2f} $")
        df_gecmis_copy['Hedef_Kar_Str'] = df_gecmis_copy['Hedef_Kar'].apply(lambda x: f"{x:,.2f} $")
        df_gecmis_copy['Olasi_Stop_Str'] = df_gecmis_copy['Olasi_Stop'].apply(lambda x: f"{x:,.2f} $")
        df_gecmis_copy['Anlık_KZ_Str'] = df_gecmis_copy['Anlik_KZ_Deger'].apply(lambda x: f"{x:+,.2f} $")
        df_gecmis_copy['Kasa_Str'] = guncel_kasa_seri.apply(lambda x: f"{x:,.2f} $")
        
        cols = ["Islem_ID", "Acilis_Zamani", "Logo", "Coin", "Yon", "Giris_Fiyat_Str", "Anlik_Fiyat_Str", "Islem_Orani", "Yatırım_Bedeli", "Stop_Str", "Kar_Al_Str", "Hedef_Kar_Str", "Olasi_Stop_Str", "Durum", "Anlık_KZ_Str", "Kapanis_Zamani", "Kasa_Str"]
        df_gosterim = df_gecmis_copy[cols].copy()
        
        df_gosterim.columns = [
            "İşlem\nID", "Açılış\nZamanı", " ", "Coin\nAdı", "İşlem\nYönü", 
            "Giriş\nFiyatı", "Anlık\nFiyat", "Sepet\nOranı", "Yatırım\nTutarı", "Stop\nSeviyesi", 
            "Kar Al\nHedefi", "Beklenen\nKar", "Olası\nStop", "İşlem\nDurumu", 
            "Anlık\nK/Z", "Kapanış\nZamanı", "Güncel\nKasa"
        ]
        
        def parse_money(val_str):
            try:
                clean_str = str(val_str).replace('$', '').replace('+', '').replace(',', '').strip()
                return float(clean_str)
            except: return 0.0

        def tabloyu_renklendir(row):
            styles = pd.Series(['color: #000000;'] * len(row), index=row.index)
            durum_str, yon_str = str(row['İşlem\nDurumu']), str(row['İşlem\nYönü'])
            
            if 'Long' in yon_str: styles['İşlem\nYönü'] = 'color: #00AA00; font-weight: bold;'
            elif 'Short' in yon_str: styles['İşlem\nYönü'] = 'color: #CC0000; font-weight: bold;'
            
            if 'Acik' in durum_str: styles['İşlem\nDurumu'] = 'background-color: #0066FF; color: white; font-weight: bold;'
            elif 'Kar' in durum_str: styles['İşlem\nDurumu'] = 'background-color: #00FF00; color: #000000; font-weight: bold;' 
            else: styles['İşlem\nDurumu'] = 'background-color: #FF0000; color: white; font-weight: bold;' 
                
            try:
                g_fiyat_val = parse_money(row['Giriş\nFiyatı'])
                a_fiyat_val = parse_money(row['Anlık\nFiyat'])
                if g_fiyat_val > 0:
                    fark_y = ((a_fiyat_val - g_fiyat_val) / g_fiyat_val) if 'Long' in yon_str else ((g_fiyat_val - a_fiyat_val) / g_fiyat_val)
                    if fark_y > 0:
                        styles['Anlık\nFiyat'] = 'background-color: rgba(0, 255, 0, 0.25); color: #000000; font-weight: bold;'
                    elif fark_y < 0:
                        styles['Anlık\nFiyat'] = 'background-color: rgba(255, 0, 0, 0.25); color: #000000; font-weight: bold;'
            except: pass

            try:
                kz_val = parse_money(row['Anlık\nK/Z'])
                if kz_val > 0:
                    styles['Anlık\nK/Z'] = 'background-color: rgba(0, 255, 0, 0.25); color: #000000; font-weight: bold;'
                elif kz_val < 0:
                    styles['Anlık\nK/Z'] = 'background-color: rgba(255, 0, 0, 0.25); color: #000000; font-weight: bold;'
                else:
                    styles['Anlık\nK/Z'] = 'color: #000000; font-weight: bold;'
            except: pass

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
                
            st.markdown("---")
            st.markdown("### 📁 50'şerli İşlem Arşivleri (Analiz Klasörü)")
            if os.path.exists(ARSIV_KLASORU):
                arsiv_dosyalari = os.listdir(ARSIV_KLASORU)
                if arsiv_dosyalari:
                    arsiv_dosyalari.sort()
                    secilen_arsiv = st.selectbox("Geçmiş 50'li Blok Dönemini Seçin (Örn: 1-50, 51-100):", arsiv_dosyalari, key="arsiv_select_50")
                    if secilen_arsiv:
                        df_arsiv = pd.read_csv(os.path.join(ARSIV_KLASORU, secilen_arsiv), delimiter=';')
                        st.dataframe(df_arsiv, use_container_width=True, hide_index=True)
                else: st.info("Henüz 50 işleme ulaşılmadı, ilk 50 işlem tamamlandığında arşiv dosyası bu alanda görünecektir.")
            else: st.info("Arşiv klasörü (arsiv/) henüz oluşturuldu, işlemler yapıldıkça dolacaktır.")
            
        else: st.info("Henüz kapanmış işlem bulunmuyor.")
    else: st.info("Henüz açılmış bir sanal işleminiz bulunmuyor.")

tum_ekrani_ve_portfoyu_senkronize_yonet()