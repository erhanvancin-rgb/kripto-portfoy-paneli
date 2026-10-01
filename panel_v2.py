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

# --- OTOMATİK TAZELEME (60 saniye) ---
st_autorefresh(interval=60000, key="datarefresh")

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

coingecko_ids = {
    'BTC/USDT': 'bitcoin',
    'ETH/USDT': 'ethereum',
    'BNB/USDT': 'binancecoin',
    'SOL/USDT': 'solana',
    'XRP/USDT': 'ripple'
}

logo_urls = {
    'BTC/USDT': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/btc.png',
    'ETH/USDT': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/eth.png',
    'BNB/USDT': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/bnb.png',
    'SOL/USDT': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/sol.png',
    'XRP/USDT': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/xrp.png'
}

# --- COINGECKO CANLI FİYAT MOTORU ---
@st.cache_data(ttl=30)
def coingecko_verilerini_cek():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,binancecoin,solana,ripple&vs_currencies=usd&include_24hr_change=true"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json()
        return {}
    except:
        return {}

def get_coingecko_price(symbol):
    data = coingecko_verilerini_cek()
    cg_id = coingecko_ids.get(symbol)
    if cg_id and cg_id in data:
        return float(data[cg_id].get('usd', 0.0))
    return 0.0

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

    if not df.empty:
        degisti = False
        baz_bakiye = BASLANGIC_BAKIYE
        if os.path.exists(ARSIV_KLASORU):
            arsivler = os.listdir(ARSIV_KLASORU)
            if arsivler:
                arsivler.sort()
                try:
                    son_arsiv_df = pd.read_csv(os.path.join(ARSIV_KLASORU, arsivler[-1]), delimiter=';')
                    if not son_arsiv_df.empty:
                        baz_bakiye = float(pd.to_numeric(son_arsiv_df.iloc[-1]['Guncel_Kasa'], errors='coerce') or BASLANGIC_BAKIYE)
                except: pass
                
        bakiye = baz_bakiye
        for i, r in df.iterrows():
            if str(r['Durum']) != 'Acik':
                bakiye += float(r['Net_Kar_Zarar'])
            if abs(df.at[i, 'Guncel_Kasa'] - bakiye) > 0.01:
                df.at[i, 'Guncel_Kasa'] = bakiye
                degisti = True

        if degisti:
            dataframe_guncelle_gsheets(df)

    if len(df) >= 50:
        if not os.path.exists(ARSIV_KLASORU):
            os.makedirs(ARSIV_KLASORU)
        zaman_etiketi = datetime.now().strftime("%Y%m%d_%H%M%S")
        arsiv_dosya_adi = os.path.join(ARSIV_KLASORU, f"Portfoy_Arsiv_{zaman_etiketi}.csv")
        df.to_csv(arsiv_dosya_adi, index=False, sep=';')
        
        sheet.clear()
        sheet.append_row(beklenen_kolonlar)
        df = pd.DataFrame(columns=beklenen_kolonlar)

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
        
    baz_bakiye = BASLANGIC_BAKIYE
    if os.path.exists(ARSIV_KLASORU):
        arsivler = os.listdir(ARSIV_KLASORU)
        if arsivler:
            arsivler.sort()
            try:
                son_arsiv_df = pd.read_csv(os.path.join(ARSIV_KLASORU, arsivler[-1]), delimiter=';')
                if not son_arsiv_df.empty:
                    baz_bakiye = float(pd.to_numeric(son_arsiv_df.iloc[-1]['Guncel_Kasa'], errors='coerce') or BASLANGIC_BAKIYE)
            except: pass

    toplam_kasa = baz_bakiye + kapanan_kar
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

def yeni_islem_ekle(coin, yon, giris_fiyat, sepet_orani_yuzde, stop, kar_al, zaman_dilimi):
    toplam_kasa, mevcut_bakiye = bakiye_durumunu_getir()
    islem_miktari = mevcut_bakiye * (sepet_orani_yuzde / 100.0)
    
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
    return True, f"✅ {coin} emri başarıyla verildi! İşlem Tutarı: {islem_miktari:.2f} $"

def manuel_islem_kapat(islem_id):
    df = islem_gecmisi_getir()
    idx = df[df['Islem_ID'] == islem_id].index
    if idx.empty: return False, "İşlem bulunamadı!"
    row = df.loc[idx[0]]
    if row['Durum'] != 'Acik': return False, "Bu işlem zaten kapalı!"
    try:
        anlik_fiyat = get_coingecko_price(row['Coin'])
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
        
        baz_bakiye = BASLANGIC_BAKIYE
        if os.path.exists(ARSIV_KLASORU):
            arsivler = os.listdir(ARSIV_KLASORU)
            if arsivler:
                arsivler.sort()
                try:
                    son_arsiv_df = pd.read_csv(os.path.join(ARSIV_KLASORU, arsivler[-1]), delimiter=';')
                    if not son_arsiv_df.empty:
                        baz_bakiye = float(pd.to_numeric(son_arsiv_df.iloc[-1]['Guncel_Kasa'], errors='coerce') or BASLANGIC_BAKIYE)
                except: pass

        df['Net_Kar_Zarar'] = pd.to_numeric(df['Net_Kar_Zarar'], errors='coerce').fillna(0.0)
        kapanan_mask = df['Durum'] != 'Acik'
        df.loc[kapanan_mask, 'Guncel_Kasa'] = baz_bakiye + df.loc[kapanan_mask, 'Net_Kar_Zarar'].cumsum()

        dataframe_guncelle_gsheets(df)
        eposta_gonder(row['Islem_ID'], row['Coin'], durum_metni, net_kar)
        return True, f"İşlem kapatıldı. Kar/Zarar: {net_kar:.2f} $"
    except Exception as e:
        return False, f"Hata: {str(e)}"

@st.cache_data(ttl=30)
def verileri_getir():
    toplam_kasa, mevcut_bakiye = bakiye_durumunu_getir()
    islenen_veriler = []
    cg_data = coingecko_verilerini_cek()
    
    for sembol in coinler:
        cg_id = coingecko_ids.get(sembol)
        coin_info = cg_data.get(cg_id, {})
        anlik_fiyat = float(coin_info.get('usd', 0.0))
        degisim_24s = float(coin_info.get('usd_24h_change', 0.0))
        
        if anlik_fiyat == 0.0:
            continue
            
        trend = "Long" if degisim_24s >= 0 else "Short"
        basamak = 4 if anlik_fiyat < 10 else 2
        
        stop_oran = BAZ_RISK_YUZDE / 100
        hedef_oran = GUNLUK_HEDEF_YUZDE / 100
        
        stop_fiyat = anlik_fiyat * (1 - stop_oran) if trend == "Long" else anlik_fiyat * (1 + stop_oran)
        hedef_fiyat = anlik_fiyat * (1 + hedef_oran) if trend == "Long" else anlik_fiyat * (1 - hedef_oran)
        
        zaman_dilimi = "2 Saatlik (Scalp)" if abs(degisim_24s) > 3 else "8 Saatlik"
        skor = abs(degisim_24s) * 1.5 + 1.0
        
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
    
    if not islenen_veriler:
        return []

    islenen_veriler = sorted(islenen_veriler, key=lambda x: x["Skor"], reverse=True)
    toplam_skor = sum([v["Skor"] for v in islenen_veriler]) or 1.0
    
    yuzdeler = []
    for v in islenen_veriler:
        saf_oran = (v["Skor"] / toplam_skor) * 100
        yuzdeler.append(max(round(saf_oran / 5) * 5, 10))
        
    fark = 100 - sum(yuzdeler)
    if yuzdeler: yuzdeler[0] += fark 
        
    for i, v in enumerate(islenen_veriler):
        v["Sepet_Orani"] = int(yuzdeler[i])
        v["Yatırım_Bedeli"] = f"{mevcut_bakiye * (yuzdeler[i] / 100):,.2f} $"
        
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
            <p style="color: #8b949e; margin: 0px; font-size: 14px;">🟢 Mevcut Bakiye (Boştaki Para)</p>
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
        
        df_gosterge['Fiyat_Str'] = df_gosterge['Fiyat'].apply(lambda x: f"{x:,.2f} $")
        df_gosterge['Kar_Al_Str'] = df_gosterge['Kar_Al'].apply(lambda x: f"{x:,.2f} $")
        df_gosterge['Stopla_Str'] = df_gosterge['Stopla'].apply(lambda x: f"{x:,.2f} $")
        df_gosterge['Sepet_Orani_Str'] = df_gosterge['Sepet_Orani'].apply(lambda x: f"%{x}")
        
        gosterilecek_df = df_gosterge[['Logo', 'Coin', 'Fiyat_Str', 'Yon', 'Sepet_Orani_Str', 'Yatırım_Bedeli', 'Kar_Al_Str', 'Stopla_Str']]
        gosterilecek_df.columns = [' ', 'Coin\nAdı', 'Anlık\nFiyat', 'İşlem\nYönü', 'Önerilen\nOran', 'Yatırım\nTutarı', 'Kar Al\nHedefi', 'Stop\nSeviyesi']
        
        # Piyasa Taramasındaki renk mantığı da nokta atışı hücre bazlı hale getirildi
        def piyasa_yon_renk(val):
            val_str = str(val)
            if 'Long' in val_str: return 'color: #00FF66; font-weight: bold;'
            if 'Short' in val_str: return 'color: #FF3333; font-weight: bold;'
            return ''
            
        g_style = gosterilecek_df.style
        if hasattr(g_style, 'map'):
            g_style = g_style.map(piyasa_yon_renk, subset=['İşlem\nYönü'])
        else:
            g_style = g_style.applymap(piyasa_yon_renk, subset=['İşlem\nYönü'])

        st.dataframe(
            g_style,
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
            onerilen_yuzde = int(coin_verisi['Sepet_Orani'])
            
            st.info(f"**Toplam Kasa:** {toplam_kasa:,.2f} $ | 🟢 **Mevcut Bakiye (Boşta):** {mevcut_bakiye:,.2f} $ | **Önerilen Oran:** %{onerilen_yuzde}")
            
            secilen_oran = st.slider("Mevcut Bakiye Üzerinden Yatırım Oranını Seçin (%):", min_value=5, max_value=100, value=onerilen_yuzde, step=5)
            hesaplanan_tutar = mevcut_bakiye * (secilen_oran / 100.0)
            st.write(f"💼 **Seçilen Oranla Yatırım Tutarı:** `{hesaplanan_tutar:,.2f} $`")
            
            if st.button(f"🚀 {secilen_coin} İşlemini Otomatik Başlat"):
                basari, mesaj = yeni_islem_ekle(
                    coin=secilen_coin, yon=coin_verisi['Yon'], giris_fiyat=coin_verisi['Fiyat'], 
                    sepet_orani_yuzde=secilen_oran, stop=coin_verisi['Stopla'], kar_al=coin_verisi['Kar_Al'], 
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
    col_p_baslik, col_p_buton = st.columns([3, 1])
    with col_p_baslik:
        st.markdown(f"### 💰 Aktif Dönem Kasası: **{toplam_kasa:,.2f} $** | 🟢 Mevcut Bakiye: **{mevcut_bakiye:,.2f} $**")
    with col_p_buton:
        if st.button("🔄 Portföyü Yenile", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    df_gecmis = islem_gecmisi_getir()
    if not df_gecmis.empty:
        acik_islem_listesi = df_gecmis[df_gecmis['Durum'] == 'Acik']['Islem_ID'].tolist()
        
        if acik_islem_listesi:
            st.markdown("#### 🛑 Güvenli Manuel İşlem Kapatma Paneli")
            col_kapat1, col_kapat2, col_kapat3 = st.columns([2, 2, 1])
            with col_kapat1: kapatilacak_id = st.selectbox("Kapatılacak İşlem ID:", acik_islem_listesi)
            with col_kapat2: onay_verildi = st.checkbox(f"ID #{kapatilacak_id} işlemini kapatmayı onaylıyorum")
            with col_kapat3:
                st.write("") 
                if st.button("🔒 İşlemi Sonlandır"):
                    if onay_verildi:
                        b_durum, b_mesaj = manuel_islem_kapat(kapatilacak_id)
                        if b_durum: 
                            st.success(b_mesaj)
                            st.cache_data.clear()
                            time.sleep(0.5)
                            st.rerun()
                        else: st.error(b_mesaj)
                    else: st.warning("Lütfen önce onay kutusunu işaretleyin!")
            st.markdown("---")

        df_gosterim = df_gecmis.copy()
        df_gosterim['Logo'] = df_gosterim['Coin'].map(logo_urls)
        
        anlik_kz_sozluk = {}
        hedef_kar_listesi = []
        
        for idx, row in df_gosterim.iterrows():
            islem_id = row['Islem_ID']
            giris_f = float(pd.to_numeric(row['Giris_Fiyat'], errors='coerce') or 0.0)
            miktar = float(pd.to_numeric(row['Islem_Miktari'], errors='coerce') or 0.0)
            kar_al_f = float(pd.to_numeric(row['Kar_Al'], errors='coerce') or 0.0)
            
            if giris_f == 0.0 or kar_al_f == 0.0:
                hedef_kar_listesi.append(0.0)
                anlik_kz_sozluk[islem_id] = float(pd.to_numeric(row['Net_Kar_Zarar'], errors='coerce') or 0.0)
                continue
            
            hedef_fark_yuzde = ((kar_al_f - giris_f) / giris_f) if row['Yon'] == 'Long' else ((giris_f - kar_al_f) / giris_f)
            hedef_kar_dolar = (miktar * KALDIRAC) * hedef_fark_yuzde
            hedef_kar_listesi.append(round(hedef_kar_dolar, 2))
            
            if row['Durum'] == 'Acik':
                anlik_f = get_coingecko_price(row['Coin'])
                if anlik_f > 0:
                    fark_y = ((anlik_f - giris_f) / giris_f) if row['Yon'] == 'Long' else ((giris_f - anlik_f) / giris_f)
                    anlik_kar = (miktar * KALDIRAC) * fark_y
                    anlik_kz_sozluk[islem_id] = round(anlik_kar, 2)
                else:
                    anlik_kz_sozluk[islem_id] = 0.0
            else:
                anlik_kz_sozluk[islem_id] = float(pd.to_numeric(row['Net_Kar_Zarar'], errors='coerce') or 0.0)
                
        df_gosterim['Hedef_Kar'] = hedef_kar_listesi
        df_gosterim['Anlik_KZ_Deger'] = df_gosterim['Islem_ID'].map(anlik_kz_sozluk)
        
        df_gosterim['Giris_Fiyat'] = pd.to_numeric(df_gosterim['Giris_Fiyat'], errors='coerce').fillna(0.0)
        df_gosterim['Stop'] = pd.to_numeric(df_gosterim['Stop'], errors='coerce').fillna(0.0)
        df_gosterim['Kar_Al'] = pd.to_numeric(df_gosterim['Kar_Al'], errors='coerce').fillna(0.0)

        islem_miktari_seri = pd.to_numeric(df_gosterim['Islem_Miktari'], errors='coerce').fillna(0.0)
        guncel_kasa_seri = pd.to_numeric(df_gosterim['Guncel_Kasa'], errors='coerce').fillna(BASLANGIC_BAKIYE)
        
        def guvenli_yuzde_cevir(oran):
            if pd.isna(oran) or oran == float('inf') or oran == float('-inf') or oran <= 0: return "%10"
            return f"%{int(oran)}"

        df_gosterim['Islem_Orani'] = ((islem_miktari_seri / guncel_kasa_seri) * 100).apply(guvenli_yuzde_cevir)
        
        df_gosterim['Giris_Fiyat_Str'] = df_gosterim['Giris_Fiyat'].apply(lambda x: f"{x:,.2f} $")
        df_gosterim['Stop_Str'] = df_gosterim['Stop'].apply(lambda x: f"{x:,.2f} $")
        df_gosterim['Kar_Al_Str'] = df_gosterim['Kar_Al'].apply(lambda x: f"{x:,.2f} $")
        df_gosterim['Yatırım_Bedeli'] = islem_miktari_seri.apply(lambda x: f"{x:,.2f} $")
        df_gosterim['Hedef_Kar_Str'] = df_gosterim['Hedef_Kar'].apply(lambda x: f"{x:,.2f} $")
        df_gosterim['Anlık_KZ_Str'] = df_gosterim['Anlik_KZ_Deger'].apply(lambda x: f"{x:+,.2f} $")
        df_gosterim['Kasa_Str'] = guncel_kasa_seri.apply(lambda x: f"{x:,.2f} $")
        
        cols = ["Islem_ID", "Tarih", "Saat", "Logo", "Coin", "Yon", "Giris_Fiyat_Str", "Islem_Orani", "Yatırım_Bedeli", "Stop_Str", "Kar_Al_Str", "Hedef_Kar_Str", "Durum", "Anlık_KZ_Str", "Kasa_Str"]
        df_gosterim = df_gosterim[cols]
        df_gosterim.columns = ["İşlem\nID", "Açılış\nTarihi", "Açılış\nSaati", " ", "Coin\nAdı", "İşlem\nYönü", "Giriş\nFiyatı", "Sepet\nOranı", "Yatırım\nTutarı", "Stop\nSeviyesi", "Kar Al\nHedefi", "Beklenen\nKar", "İşlem\nDurumu", "Anlık\nK/Z", "Güncel\nKasa"]
        
        # --- YENİ GARANTİLİ HÜCRE BAZLI RENKLENDİRME MANTIĞI ---
        
        def yon_renk_sec(val):
            val_str = str(val)
            if 'Long' in val_str: return 'color: #00FF66; font-weight: bold;'
            elif 'Short' in val_str: return 'color: #FF3333; font-weight: bold;'
            return ''
            
        def durum_renk_sec(val):
            val_str = str(val)
            if 'Acik' in val_str: return 'background-color: #0066FF; color: white; font-weight: bold;'
            elif 'Kar' in val_str: return 'background-color: #008751; color: white; font-weight: bold;' 
            elif 'Zarar' in val_str: return 'background-color: #A30036; color: white; font-weight: bold;' 
            return ''
            
        def kz_renk_sec(val):
            try:
                # Örn: "+0.26 $" veya "-0.13 $" yazısından rakamı saf olarak çekiyoruz
                num = float(str(val).replace('$', '').replace('+', '').replace(',', '').strip())
            except:
                num = 0.0
                
            # Rakama göre kusursuz tonlama (degrade)
            if num <= -20.0: renk = '#57001A'
            elif num <= -10.0: renk = '#7A0028'  
            elif num < -5.0: renk = '#91002F'  
            elif num < -2.0: renk = '#B8003C'  
            elif num < 0.0: renk = '#C7852B'  
            elif num == 0.0: renk = '#2d3748'  
            elif num <= 2.0: renk = '#2d5a3c'  
            elif num <= 5.0: renk = '#2E8B57'  
            elif num <= 10.0: renk = '#008751'  
            elif num <= 20.0: renk = '#00B36B'
            else: renk = '#00FF66'  
            
            return f'background-color: {renk}; color: #FFFFFF; font-weight: bold;'

        styled_df = df_gosterim.style
        
        # Pandas versiyonuna göre en doğru metodu dinamik seçiyoruz
        if hasattr(styled_df, 'map'):
            styled_df = styled_df.map(yon_renk_sec, subset=['İşlem\nYönü']) \
                                 .map(durum_renk_sec, subset=['İşlem\nDurumu']) \
                                 .map(kz_renk_sec, subset=['Anlık\nK/Z'])
        else:
            styled_df = styled_df.applymap(yon_renk_sec, subset=['İşlem\nYönü']) \
                                 .applymap(durum_renk_sec, subset=['İşlem\nDurumu']) \
                                 .applymap(kz_renk_sec, subset=['Anlık\nK/Z'])

        st.dataframe(
            styled_df,
            use_container_width=True, hide_index=True,
            column_config={
                " ": st.column_config.ImageColumn(" ", width="small")
            }
        )

        st.markdown("---")
        st.subheader("📊 Kapanan İşlemler Pasta Grafik & Para Akışı Analizi")
        
        kapananlar_df = df_gecmis[df_gecmis['Durum'] != 'Acik']
        if not kapananlar_df.empty:
            karli_sayisi = 0
            zararli_sayisi = 0
            toplam_kazanc_dolar = 0.0
            toplam_kayip_dolar = 0.0
            
            for idx, r in kapananlar_df.iterrows():
                val = float(pd.to_numeric(r['Net_Kar_Zarar'], errors='coerce') or 0.0)
                if val >= 0:
                    karli_sayisi += 1
                    toplam_kazanc_dolar += val
                else:
                    zararli_sayisi += 1
                    toplam_kayip_dolar += abs(val)
                    
            toplam_kapanan = len(kapananlar_df)
            karli_oran = (karli_sayisi / toplam_kapanan) * 100 if toplam_kapanan > 0 else 0
            zararli_oran = (zararli_sayisi / toplam_kapanan) * 100 if toplam_kapanan > 0 else 0
            net_fark_dolar = toplam_kazanc_dolar - toplam_kayip_dolar
            
            col_p1, col_p2, col_p3 = st.columns([1.5, 1, 1])
            
            with col_p1:
                df_pie = pd.DataFrame({'Durum': ['Kârlı İşlemler', 'Zararlı İşlemler'], 'Adet': [karli_sayisi, zararli_sayisi]})
                fig = px.pie(df_pie, names='Durum', values='Adet', hole=0.35, color='Durum', color_discrete_map={'Kârlı İşlemler': '#008751', 'Zararlı İşlemler': '#A30036'})
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
                    <p style="color: #00FF66; margin: 0px; font-size: 14px; font-weight: bold;">Toplam Kâr:</p>
                    <h3 style="color: #00FF66; margin: 0px 0px 10px 0px;">+{toplam_kazanc_dolar:,.2f} $</h3>
                    <p style="color: #FF3333; margin: 0px; font-size: 14px; font-weight: bold;">Toplam Zarar:</p>
                    <h3 style="color: #FF3333; margin: 0px 0px 10px 0px;">-{toplam_kayip_dolar:,.2f} $</h3>
                    <hr style="border-color: #30363d; margin: 8px 0px;">
                    <p style="color: #ffffff; margin: 0px; font-size: 13px;">Net Fark:</p>
                    <h3 style="color: {'#00FF66' if net_fark_dolar >= 0 else '#FF3333'}; margin: 0px;">{net_fark_dolar:+,.2f} $</h3>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Henüz kapanmış işlem bulunmuyor.")
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