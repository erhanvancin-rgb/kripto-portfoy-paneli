import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import os
import csv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import gspread
from google.oauth2.service_account import Credentials

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(page_title="Pro Kripto Strateji & Portföy Paneli", page_icon="📈", layout="wide")

# --- OTOMATİK TAZELEME ---
st_autorefresh(interval=30000, key="datarefresh")

st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #1a1c23; border-radius: 5px 5px 0 0; gap: 1px; padding-top: 10px; padding-bottom: 10px; }
    .stTabs [aria-selected="true"] { background-color: #2d3748; color: #00A933; font-weight: bold; border-bottom: 2px solid #00A933; }
    .para-blogu { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 15px; text-align: center; }
    .metric-container { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px; text-align: center; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- SABİTLER VE GOOGLE SHEETS BAĞLANTISI ---
GOOGLE_SHEET_ADRESI = "KriptoPortfoyVeritabani"  
ARSIV_KLASORU = "arsiv"
BASLANGIC_BAKIYE = 500.0
KALDIRAC = 3 
GUNLUK_HEDEF_YUZDE = 1.25  
BAZ_RISK_YUZDE = 0.5       

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

# --- BINANCE PUBLIC REST API MOTORU ---
def get_binance_price(symbol):
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        r = requests.get(url, timeout=3)
        if r.status_code == 200:
            return float(r.json()['price'])
        return 0.0
    except:
        return 0.0

def get_binance_klines(symbol, interval='1h', limit=50):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data, columns=['Open time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close time', 'Quote asset volume', 'Number of trades', 'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'])
                df['Close'] = df['Close'].astype(float)
                return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

# --- GOOGLE SHEETS BAĞLANTI MOTORU ---
def google_sheets_baglan():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" in st.secrets:
            sec = st.secrets["gcp_service_account"]
            creds_dict = {
                "type": sec["type"],
                "project_id": sec["project_id"],
                "private_key_id": sec["private_key_id"],
                "private_key": str(sec["private_key"]).replace("\\n", "\n"),
                "client_email": sec["client_email"],
                "client_id": sec["client_id"],
                "auth_uri": sec["auth_uri"],
                "token_uri": sec["token_uri"],
                "auth_provider_x509_cert_url": sec["auth_provider_x509_cert_url"],
                "client_x509_cert_url": sec["client_x509_cert_url"],
                "universe_domain": sec.get("universe_domain", "googleapis.com")
            }
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        else:
            creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
            
        client = gspread.authorize(creds)
        sheet = client.open(GOOGLE_SHEET_ADRESI).worksheet("Sayfa1")
        return sheet
    except Exception as e:
        return None

def islem_gecmisi_getir():
    sheet = google_sheets_baglan()
    beklenen_kolonlar = ["Islem_ID", "Tarih", "Saat", "Coin", "Yon", "Zaman_Dilimi", "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Durum", "Kapanis_Tarih", "Kapanis_Saat", "Net_Kar_Zarar", "Guncel_Kasa"]
    
    if sheet is None:
        return pd.DataFrame(columns=beklenen_kolonlar)
    
    try:
        ham_veriler = sheet.get_all_values()
    except Exception:
        return pd.DataFrame(columns=beklenen_kolonlar)
        
    if not ham_veriler or len(ham_veriler) == 0:
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
            basliklar = list(df.columns)
            sheet.append_row(basliklar)
            for _, row in df.iterrows():
                sheet.append_row(list(row.values))
        except: pass

def eposta_gonder(islem_id, coin, durum, net_kar):
    if not GMAIL_SIFRE or GMAIL_SIFRE == "BURAYA_16_HANELI_UYGULAMA_SIFRESINI_YAZ":
        return 
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

def bakiye_durumunu_getir():
    df = islem_gecmisi_getir()
    if df.empty: return BASLANGIC_BAKIYE, BASLANGIC_BAKIYE
    
    kapanan_df = df[df['Durum'] != 'Acik']
    kapanan_kar = 0.0
    if not kapanan_df.empty:
        kapanan_kar = pd.to_numeric(kapanan_df['Net_Kar_Zarar'], errors='coerce').fillna(0.0).sum()
        
    toplam_kasa = BASLANGIC_BAKIYE + kapanan_kar
    acik_df = df[df['Durum'] == 'Acik']
    acik_marjin = pd.to_numeric(acik_df['Islem_Miktari'], errors='coerce').fillna(0.0).sum() if not acik_df.empty else 0.0
    mevcut_bakiye = toplam_kasa - acik_marjin
    return float(toplam_kasa), float(mevcut_bakiye)

def gunluk_kazanc_hesapla():
    df = islem_gecmisi_getir()
    if df.empty: return 0.0
    simdi = datetime.now()
    gun_once = simdi - timedelta(hours=24)
    toplam_24s = 0.0
    for idx, row in df.iterrows():
        if row['Durum'] != 'Acik' and str(row['Kapanis_Tarih']) != '-' and str(row['Kapanis_Saat']) != '-':
            try:
                kapanis_zamani = datetime.strptime(f"{row['Kapanis_Tarih']} {row['Kapanis_Saat']}", "%d.%m.%Y %H:%M")
                if kapanis_zamani >= gun_once:
                    toplam_24s += float(pd.to_numeric(row['Net_Kar_Zarar'], errors='coerce') or 0.0)
            except: pass
    return round(toplam_24s, 2)

def yeni_islem_ekle(coin, yon, giris_fiyat, sepet_orani, stop, kar_al, zaman_dilimi):
    toplam_kasa, mevcut_bakiye = bakiye_durumunu_getir()
    oran = float(sepet_orani.replace('%', '')) / 100
    islem_miktari = toplam_kasa * oran
    
    if islem_miktari > mevcut_bakiye: 
        return False, f"Mevcut bakiyeniz yetersiz! Gereken: {islem_miktari:.2f} $ | Mevcut Bakiye: {mevcut_bakiye:.2f} $"
    if islem_miktari < 10: 
        return False, "İşlem miktarı 10 $'dan küçük olamaz!"
        
    df = islem_gecmisi_getir()
    yeni_id = 1 if df.empty else int(pd.to_numeric(df['Islem_ID'], errors='coerce').max() or 0) + 1
    suan = datetime.now()
    
    yeni_kayit = pd.DataFrame([{
        "Islem_ID": yeni_id, "Tarih": suan.strftime("%d.%m.%Y"), "Saat": suan.strftime("%H:%M"),
        "Coin": coin, "Yon": yon, "Zaman_Dilimi": zaman_dilimi, "Giris_Fiyat": giris_fiyat, 
        "Islem_Miktari": round(islem_miktari, 2), "Stop": stop, "Kar_Al": kar_al, "Durum": "Acik", 
        "Kapanis_Tarih": "-", "Kapanis_Saat": "-", "Net_Kar_Zarar": 0.0, "Guncel_Kasa": round(toplam_kasa, 2)
    }])
    
    df = pd.concat([df, yeni_kayit], ignore_index=True)
    dataframe_guncelle_gsheets(df)
    return True, f"✅ {coin} ({zaman_dilimi}) emri başarıyla verildi!"

def manuel_islem_kapat(islem_id):
    df = islem_gecmisi_getir()
    idx = df[df['Islem_ID'] == islem_id].index
    if idx.empty: return False, "İşlem bulunamadı!"
    row = df.loc[idx[0]]
    if row['Durum'] != 'Acik': return False, "Bu işlem zaten kapalı!"
    try:
        binance_symbol = row['Coin'].replace('/', '')
        anlik_fiyat = get_binance_price(binance_symbol)
        if anlik_fiyat == 0.0: return False, "Borsa fiyatı alınamadı!"
            
        giris_f = float(row['Giris_Fiyat'])
        miktar = float(row['Islem_Miktari'])
        fark_yuzde = ((anlik_fiyat - giris_f) / giris_f) if row['Yon'] == 'Long' else ((giris_f - anlik_fiyat) / giris_f)
        net_kar = (miktar * KALDIRAC) * fark_yuzde
        suan = datetime.now()
        
        durum_metni = 'Kapandi (Kar)' if net_kar >= 0 else 'Kapandi (Zarar)'
        df.at[idx[0], 'Durum'] = durum_metni
        df.at[idx[0], 'Kapanis_Tarih'] = suan.strftime("%d.%m.%Y")
        df.at[idx[0], 'Kapanis_Saat'] = suan.strftime("%H:%M")
        df.at[idx[0], 'Net_Kar_Zarar'] = float(round(net_kar, 2))
        
        dataframe_guncelle_gsheets(df)
        eposta_gonder(row['Islem_ID'], row['Coin'], durum_metni, net_kar)
        return True, f"İşlem kapatıldı. Kar/Zarar: {net_kar:.2f} $"
    except Exception as e:
        return False, f"Hata: {str(e)}"

def hesapla_rsi(df, periyot=14):
    try:
        delta = df['Close'].diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        rs = up.ewm(com=periyot-1, adjust=False).mean() / down.ewm(com=periyot-1, adjust=False).mean()
        return round(float((100 - (100 / (1 + rs))).iloc[-1]), 2)
    except:
        return 50.0

@st.cache_data(ttl=30)
def verileri_getir():
    toplam_kasa, _ = bakiye_durumunu_getir()
    islenen_veriler = []
    
    for sembol in coinler:
        binance_symbol = sembol.replace('/', '')
        anlik_fiyat = get_binance_price(binance_symbol)
        
        if anlik_fiyat == 0.0:
            # Yedek sabit fiyatlar (Binance API yanıt vermezse panel çökmesin diye)
            yedekler = {'BTC/USDT': 65000.0, 'ETH/USDT': 3500.0, 'BNB/USDT': 600.0, 'SOL/USDT': 150.0, 'XRP/USDT': 1.5}
            anlik_fiyat = yedekler.get(sembol, 100.0)

        df = get_binance_klines(binance_symbol, interval='1h', limit=30)
        onceki_fiyat = float(df.iloc[-2]['Close']) if not df.empty and len(df) > 1 else anlik_fiyat * 0.99
        
        trend = "Long" if onceki_fiyat < anlik_fiyat else "Short"
        basamak = 4 if anlik_fiyat < 10 else 2
        
        stop_oran = BAZ_RISK_YUZDE / 100
        hedef_oran = GUNLUK_HEDEF_YUZDE / 100
        
        stop_fiyat = anlik_fiyat * (1 - stop_oran) if trend == "Long" else anlik_fiyat * (1 + stop_oran)
        hedef_fiyat = anlik_fiyat * (1 + hedef_oran) if trend == "Long" else anlik_fiyat * (1 - hedef_oran)
        
        rsi_deger = hesapla_rsi(df) if not df.empty else 50.0
        zaman_dilimi = "2 Saatlik (Scalp)" if (rsi_deger < 35 or rsi_deger > 65) else "8 Saatlik"
        skor = abs(rsi_deger - 50) * 1.5
        
        islenen_veriler.append({
            "Logo": logo_urls.get(sembol, ""),
            "Coin": sembol, 
            "Fiyat": round(anlik_fiyat, basamak), 
            "Yon": trend,
            "Zaman_Dilimi": zaman_dilimi, 
            "Kar_Al": round(hedef_fiyat, basamak), 
            "Stopla": round(stop_fiyat, basamak), 
            "Skor": skor
        })
    
    islenen_veriler = sorted(islenen_veriler, key=lambda x: x["Skor"], reverse=True)
    toplam_skor = sum([v["Skor"] for v in islenen_veriler]) or 1.0
    
    yuzdeler = []
    for v in islenen_veriler:
        saf_oran = (v["Skor"] / toplam_skor) * 100
        yuzdeler.append(max(round(saf_oran / 5) * 5, 10))
        
    fark = 100 - sum(yuzdeler)
    if yuzdeler: yuzdeler[0] += fark 
        
    for i, v in enumerate(islenen_veriler):
        v["Sepet_Orani"] = f"%{int(yuzdeler[i])}"
        v["Yatırım_Bedeli"] = f"{toplam_kasa * (yuzdeler[i] / 100):,.2f} $"
        
    return islenen_veriler

# --- ARAYÜZ ---
st.title("⚡ Pro Kripto & Otomatik Sanal Portföy")

toplam_kasa, mevcut_bakiye = bakiye_durumunu_getir()
gunluk_kar = gunluk_kazanc_hesapla()

col_m1, col_m2 = st.columns(2)
with col_m1:
    st.markdown(f"""
        <div class="metric-container">
            <p style="color: #8b949e; margin: 0px; font-size: 14px;">💰 Anlık Toplam Kasa</p>
            <h2 style="color: #ffffff; margin: 0px;">{toplam_kasa:,.2f} $ <span style="font-size: 14px; color: {'#00FF66' if toplam_kasa - BASLANGIC_BAKIYE >= 0 else '#FF3333'};">({toplam_kasa - BASLANGIC_BAKIYE:+,.2f} $)</span></h2>
        </div>
    """, unsafe_allow_html=True)
with col_m2:
    st.markdown(f"""
        <div class="metric-container">
            <p style="color: #8b949e; margin: 0px; font-size: 14px;">🟢 Mevcut Bakiye</p>
            <h2 style="color: #ffffff; margin: 0px;">{mevcut_bakiye:,.2f} $</h2>
        </div>
    """, unsafe_allow_html=True)

col_m3, col_m4 = st.columns(2)
with col_m3:
    st.markdown(f"""
        <div class="metric-container">
            <p style="color: #8b949e; margin: 0px; font-size: 14px;">📊 24 Saatlik Kâr / Zarar</p>
            <h2 style="color: {'#00FF66' if gunluk_kar >= 0 else '#FF3333'}; margin: 0px;">{gunluk_kar:+,.2f} $</h2>
        </div>
    """, unsafe_allow_html=True)
with col_m4:
    st.markdown(f"""
        <div class="metric-container">
            <p style="color: #8b949e; margin: 0px; font-size: 14px;">🚀 Başlangıç Sermayesi</p>
            <h2 style="color: #ffffff; margin: 0px;">{BASLANGIC_BAKIYE:,.2f} $</h2>
        </div>
    """, unsafe_allow_html=True)

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📊 Piyasa Taraması & Sinyaller", "💼 Sanal Portföy & İşlemler", "📁 Geçmiş Arşiv İnceleme"])

with tab1:
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("🔄 Piyasayı Yenile", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    with st.spinner('Piyasa taranıyor...'):
        veriler = verileri_getir()
        
    if veriler:
        st.caption("🔥 *Liste kârlılık potansiyeli en yüksek coinden başlayarak sıralanmıştır.*")
        df_gosterge = pd.DataFrame(veriler)
        
        df_gosterge['Fiyat_Str'] = df_gosterge['Fiyat'].apply(lambda x: f"{x:,.4f} $")
        df_gosterge['Kar_Al_Str'] = df_gosterge['Kar_Al'].apply(lambda x: f"{x:,.4f} $")
        df_gosterge['Stopla_Str'] = df_gosterge['Stopla'].apply(lambda x: f"{x:,.4f} $")
        
        gosterilecek_df = df_gosterge[['Logo', 'Coin', 'Fiyat_Str', 'Yon', 'Zaman_Dilimi', 'Sepet_Orani', 'Yatırım_Bedeli', 'Kar_Al_Str', 'Stopla_Str']]
        gosterilecek_df.columns = [' ', 'Coin\nAdı', 'Anlık\nFiyat', 'İşlem\nYönü', 'Zaman\nDilimi', 'Sepet\nOranı', 'Yatırım\nTutarı', 'Kar Al\nHedefi', 'Stop\nSeviyesi']
        
        st.dataframe(
            gosterilecek_df.style.map(
                lambda x: 'color: #00FF66; font-weight: bold;' if x == 'Long' else ('color: #FF3333; font-weight: bold;' if x == 'Short' else ''),
                subset=['İşlem\nYönü']
            ),
            use_container_width=True, hide_index=True,
            column_config={
                " ": st.column_config.ImageColumn(" ", width="small")
            }
        )
        
        st.markdown("---")
        st.markdown("### 🛒 Hızlı İşlem Emri Ver (Paper Trading)")
        secilen_coin = st.selectbox("İşleme Girmek İstediğiniz Coini Seçin:", df_gosterge['Coin'].tolist())
        
        if secilen_coin:
            coin_verisi = df_gosterge[df_gosterge['Coin'] == secilen_coin].iloc[0]
            st.info(f"**Toplam Kasa:** {toplam_kasa:,.2f} $ | 🟢 **Mevcut Bakiye:** {mevcut_bakiye:,.2f} $ | **Önerilen Oran:** {coin_verisi['Sepet_Orani']} | **İşlem Bedeli:** {coin_verisi['Yatırım_Bedeli']}")
            
            if st.button(f"🚀 {secilen_coin} İşlemini Otomatik Başlat"):
                basari, mesaj = yeni_islem_ekle(
                    coin=secilen_coin, yon=coin_verisi['Yon'], giris_fiyat=coin_verisi['Fiyat'], 
                    sepet_orani=coin_verisi['Sepet_Orani'], stop=coin_verisi['Stopla'], kar_al=coin_verisi['Kar_Al'], 
                    zaman_dilimi=coin_verisi['Zaman_Dilimi']
                )
                if basari: 
                    st.success(mesaj)
                    st.cache_data.clear()
                    time.sleep(0.5)
                    st.rerun()
                else: st.error(mesaj)
    else:
        st.warning("Piyasa verileri yüklenemedi. Lütfen 'Piyasayı Yenile' butonuna basın.")

with tab2:
    st.markdown(f"### 💰 Aktif Dönem Kasası: **{toplam_kasa:,.2f} $** | 🟢 Mevcut Bakiye: **{mevcut_bakiye:,.2f} $**")
    df_gecmis = islem_gecmisi_getir()
    if not df_gecmis.empty:
        st.dataframe(df_gecmis, use_container_width=True, hide_index=True)
    else:
        st.info("Henüz açılmış bir sanal işleminiz bulunmuyor.")

with tab3:
    st.markdown("### 📁 Geçmiş Arşiv Dosyaları İnceleme")
    if os.path.exists(ARSIV_KLASORU):
        arsiv_dosyalari = os.listdir(ARSIV_KLASORU)
        if arsiv_dosyalari:
            secilen_arsiv = st.selectbox("İncelemek İstediğiniz Arşiv Dönemi:", arsiv_dosyalari)
            if secilen_arsiv:
                df_arsiv = pd.read_csv(os.path.join(ARSIV_KLASORU, secilen_arsiv), delimiter=';')
                st.dataframe(df_arsiv, use_container_width=True, hide_index=True)
        else: st.info("Arşivde henüz tamamlanmış dönem bulunmuyor.")
    else: st.info("Arşiv klasörü henüz oluşturulmadı.")