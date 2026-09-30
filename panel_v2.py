import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import os
import csv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

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
    </style>
""", unsafe_allow_html=True)

# --- SABİTLER VE VERİ DOSYALARI ---
DOSYA_PORTFOY = "Sanal_Portfoy_Gecmisi.csv"
ARSIV_KLASORU = "arsiv"
BASLANGIC_BAKIYE = 500.0
KALDIRAC = 3 
GUNLUK_HEDEF_YUZDE = 1.25  
BAZ_RISK_YUZDE = 0.5       

# --- E-POSTA BİLDİRİM AYARLARI ---
GONDERICI_MAIL = "erhanvancin@gmail.com"
ALICI_MAIL = "erhanvancin@hotmail.com"
GMAIL_SIFRE = "jkef zgaf zwtg qyom"

coinler = {'BTC/USDT': 'BTC-USD', 'ETH/USDT': 'ETH-USD', 'BNB/USDT': 'BNB-USD', 'SOL/USDT': 'SOL-USD', 'XRP/USDT': 'XRP-USD'}

logo_urls = {
    'BTC/USDT': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/btc.png',
    'ETH/USDT': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/eth.png',
    'BNB/USDT': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/bnb.png',
    'SOL/USDT': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/sol.png',
    'XRP/USDT': 'https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/xrp.png'
}

# --- E-POSTA GÖNDERME MOTORU ---
def eposta_gonder(islem_id, coin, durum, net_kar):
    if not GMAIL_SIFRE or GMAIL_SIFRE == "BURAYA_16_HANELI_UYGULAMA_SIFRESINI_YAZ":
        return 
    try:
         konu = f"🚨 Kripto İşlem Bildirimi: ID #{islem_id} - {coin} ({durum})"
         if net_kar >= 0:
             mesaj_metni = f"Tebrikler!\n\nİşlem ID #{islem_id} ({coin}) başarıyla kapatıldı.\nDurum: Kapandi (Kar)\nNet Kâr/Zarar: +{net_kar:.2f} $"
         else:
             mesaj_metni = f"Bilgilendirme:\n\nİşlem ID #{islem_id} ({coin}) kapatıldı.\nDurum: Kapandi (Zarar)\nNet Kâr/Zarar: {net_kar:.2f} $"
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
         print(f"E-posta gönderme hatası: {e}")

# --- ARŞİVLEME VE PORTFÖY YÖNETİMİ ---
def portfoy_dosyasi_olustur():
    beklenen_kolonlar = ["Islem_ID", "Tarih", "Saat", "Coin", "Yon", "Zaman_Dilimi", "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Durum", "Kapanis_Tarih", "Kapanis_Saat", "Net_Kar_Zarar", "Guncel_Kasa"]
    
    if not os.path.exists(DOSYA_PORTFOY):
        with open(DOSYA_PORTFOY, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(beklenen_kolonlar)

def islem_gecmisi_getir():
    portfoy_dosyasi_olustur()
    try:
        df = pd.read_csv(DOSYA_PORTFOY, delimiter=';')
        
        if not df.empty and 'Islem_ID' in df.columns:
            df = df[df['Islem_ID'].notna() & (df['Islem_ID'] != "")]
        
        if len(df) >= 50:
            if not os.path.exists(ARSIV_KLASORU):
                os.makedirs(ARSIV_KLASORU)
            
            zaman_etiketi = datetime.now().strftime("%Y%m%d_%H%M%S")
            arsiv_dosya_adi = os.path.join(ARSIV_KLASORU, f"Portfoy_Arsiv_{zaman_etiketi}.csv")
            
            df.to_csv(arsiv_dosya_adi, index=False, sep=';')
            
            with open(DOSYA_PORTFOY, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(["Islem_ID", "Tarih", "Saat", "Coin", "Yon", "Zaman_Dilimi", "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Durum", "Kapanis_Tarih", "Kapanis_Saat", "Net_Kar_Zarar", "Guncel_Kasa"])
            
            df = pd.read_csv(DOSYA_PORTFOY, delimiter=';')
            
        return df
    except:
        return pd.DataFrame(columns=["Islem_ID", "Tarih", "Saat", "Coin", "Yon", "Zaman_Dilimi", "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Durum", "Kapanis_Tarih", "Kapanis_Saat", "Net_Kar_Zarar", "Guncel_Kasa"])

def bakiye_durumunu_getir():
    df = islem_gecmisi_getir()
    if df.empty: return BASLANGIC_BAKIYE, BASLANGIC_BAKIYE
    
    kapanan_df = df[df['Durum'] != 'Acik']
    kapanan_kar = 0.0
    if not kapanan_df.empty:
        temizlenmis_kar = pd.to_numeric(kapanan_df['Net_Kar_Zarar'], errors='coerce').fillna(0.0)
        kapanan_kar = temizlenmis_kar.sum()
        
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
    acik_marjin = 0.0
    if not acik_df.empty:
        temizlenmis_marjin = pd.to_numeric(acik_df['Islem_Miktari'], errors='coerce').fillna(0.0)
        acik_marjin = temizlenmis_marjin.sum()
        
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
    yeni_kayit.to_csv(DOSYA_PORTFOY, mode='a', header=not os.path.exists(DOSYA_PORTFOY), index=False, sep=';')
    return True, f"✅ {coin} ({zaman_dilimi}) emri başarıyla verildi. Portföye eklendi!"

def manuel_islem_kapat(islem_id):
    df = islem_gecmisi_getir()
    idx = df[df['Islem_ID'] == islem_id].index
    if idx.empty: return False, "İşlem bulunamadı!"
    row = df.loc[idx[0]]
    if row['Durum'] != 'Acik': return False, "Bu işlem zaten kapalı!"
    try:
        ticker = coinler.get(row['Coin'], row['Coin'].replace('/', '-'))
        gecmis = yf.download(ticker, period='1d', interval='1m', progress=False)
        if isinstance(gecmis.columns, pd.MultiIndex):
            gecmis.columns = gecmis.columns.get_level_values(0)
        anlik_fiyat = float(gecmis.iloc[-1]['Close'])
        
        giris_f = float(pd.to_numeric(row['Giris_Fiyat'], errors='coerce') or 0.0)
        miktar = float(pd.to_numeric(row['Islem_Miktari'], errors='coerce') or 0.0)
        
        fark_yuzde = ((anlik_fiyat - giris_f) / giris_f) if row['Yon'] == 'Long' else ((giris_f - anlik_f) / giris_f)
        net_kar = (miktar * KALDIRAC) * fark_yuzde
        suan = datetime.now()
        
        durum_metni = 'Kapandi (Kar)' if net_kar >= 0 else 'Kapandi (Zarar)'
        
        df.at[idx[0], 'Durum'] = durum_metni
        df.at[idx[0], 'Kapanis_Tarih'] = suan.strftime("%d.%m.%Y")
        df.at[idx[0], 'Kapanis_Saat'] = suan.strftime("%H:%M")
        df.at[idx[0], 'Net_Kar_Zarar'] = round(net_kar, 2)
        
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
        for i in df.index:
            if df.at[i, 'Durum'] != 'Acik':
                bakiye += float(pd.to_numeric(df.at[i, 'Net_Kar_Zarar'], errors='coerce') or 0.0)
            df.at[i, 'Guncel_Kasa'] = round(bakiye, 2)
            
        df.to_csv(DOSYA_PORTFOY, index=False, sep=';')
        eposta_gonder(row['Islem_ID'], row['Coin'], durum_metni, net_kar)
        return True, f"İşlem ID {islem_id} başarıyla kapatıldı. Kar/Zarar: {net_kar:.2f} $"
    except Exception as e:
        return False, f"Hata oluştu: {str(e)}"

def acik_islemleri_denetle():
    df = islem_gecmisi_getir()
    if df.empty: return []
    acik_mask = df['Durum'] == 'Acik'
    if not acik_mask.any(): return []
    kapananlar = []
    degisim_oldu = False
    for idx, row in df[acik_mask].iterrows():
        try:
            ticker = coinler.get(row['Coin'], row['Coin'].replace('/', '-'))
            gecmis = yf.download(ticker, period='5d', interval='5m', progress=False)
            if isinstance(gecmis.columns, pd.MultiIndex):
                gecmis.columns = gecmis.columns.get_level_values(0)
            if gecmis.empty: continue
            
            suan = datetime.now()
            giris_f = float(pd.to_numeric(row['Giris_Fiyat'], errors='coerce') or 0.0)
            stop_f = float(pd.to_numeric(row['Stop'], errors='coerce') or 0.0)
            hedef_f = float(pd.to_numeric(row['Kar_Al'], errors='coerce') or 0.0)
            miktar = float(pd.to_numeric(row['Islem_Miktari'], errors='coerce') or 0.0)
            
            if giris_f == 0.0 or stop_f == 0.0 or hedef_f == 0.0:
                continue
            
            kapanis_turu = None
            kapanis_fiyati = None
            anlik_fiyat = float(gecmis.iloc[-1]['Close'])
            
            if row['Yon'] == 'Long':
                if anlik_fiyat >= hedef_f: kapanis_turu, kapanis_fiyati = 'Kapandi (Kar)', hedef_f
                elif anlik_fiyat <= stop_f: kapanis_turu, kapanis_fiyati = 'Kapandi (Zarar)', stop_f
            elif row['Yon'] == 'Short':
                if anlik_fiyat <= hedef_f: kapanis_turu, kapanis_fiyati = 'Kapandi (Kar)', hedef_f
                elif anlik_fiyat >= stop_f: kapanis_turu, kapanis_fiyati = 'Kapandi (Zarar)', stop_f
                    
            if kapanis_turu:
                fark_yuzde = ((kapanis_fiyati - giris_f) / giris_f) if row['Yon'] == 'Long' else ((giris_f - kapanis_fiyati) / giris_f)
                net_kar = (miktar * KALDIRAC) * fark_yuzde
                df.at[idx, 'Durum'] = kapanis_turu
                df.at[idx, 'Kapanis_Tarih'] = suan.strftime("%d.%m.%Y")
                df.at[idx, 'Kapanis_Saat'] = suan.strftime("%H:%M")
                df.at[idx, 'Net_Kar_Zarar'] = round(net_kar, 2)
                
                eposta_gonder(row['Islem_ID'], row['Coin'], kapanis_turu, net_kar)
                kapananlar.append({
                    "ID": row['Islem_ID'],
                    "Coin": row['Coin'],
                    "Durum": kapanis_turu,
                    "Kar_Zarar": round(net_kar, 2)
                })
                degisim_oldu = True
        except: continue
            
    if degisim_oldu:
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
        for idx in df.index:
            if df.at[idx, 'Durum'] != 'Acik':
                bakiye += float(pd.to_numeric(df.at[idx, 'Net_Kar_Zarar'], errors='coerce') or 0.0)
            df.at[idx, 'Guncel_Kasa'] = round(bakiye, 2)
        df.to_csv(DOSYA_PORTFOY, index=False, sep=';')
    return kapananlar

def hesapla_rsi(df, periyot=14):
    delta = df['Close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    rs = up.ewm(com=periyot-1, adjust=False).mean() / down.ewm(com=periyot-1, adjust=False).mean()
    return round(float((100 - (100 / (1 + rs))).iloc[-1]), 2)

@st.cache_data(ttl=60)
def verileri_getir():
    toplam_kasa, _ = bakiye_durumunu_getir()
    islenen_veriler = []
    for sembol, ticker in coinler.items():
        try:
            df = yf.download(ticker, period='60d', interval='1h', progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if df.empty: continue
            
            anlik_fiyat = float(df.iloc[-1]['Close'])
            onceki_fiyat = float(df.iloc[-2]['Close'])
            trend = "Long" if onceki_fiyat < anlik_fiyat else ("Short" if onceki_fiyat > anlik_fiyat else "Notr")
            basamak = 4 if anlik_fiyat < 10 else 2
            
            stop_oran = BAZ_RISK_YUZDE / 100
            hedef_oran = GUNLUK_HEDEF_YUZDE / 100
            
            stop_fiyat = anlik_fiyat * (1 - stop_oran) if trend == "Long" else anlik_fiyat * (1 + stop_oran)
            hedef_fiyat = anlik_fiyat * (1 + hedef_oran) if trend == "Long" else anlik_fiyat * (1 - hedef_oran)
            
            rsi_deger = hesapla_rsi(df)
            
            if rsi_deger < 35 or rsi_deger > 65:
                zaman_dilimi = "2 Saatlik (Scalp)"
            elif 40 <= rsi_deger <= 60:
                zaman_dilimi = "8 Saatlik"
            else:
                zaman_dilimi = "4 Saatlik"
                
            skor = abs(rsi_deger - 50) * 1.5
            islenen_veriler.append({
                "Logo": logo_urls.get(sembol, ""),
                "Coin": sembol, 
                "Fiyat": round(anlik_fiyat, basamak), 
                "Yon": trend,
                "Zaman_Dilimi": zaman_dilimi, 
                "Kar_Al": round(hedef_fiyat, basamak), 
                "Stopla": round(stop_fiyat, basamak), 
                "Skor": skor if trend != "Notr" else 0.1
            })
        except: continue
    
    if not islenen_veriler:
        return []

    islenen_veriler = sorted(islenen_veriler, key=lambda x: x["Skor"], reverse=True)
    toplam_skor = sum([v["Skor"] for v in islenen_veriler])
    
    yuzdeler = []
    for v in islenen_veriler:
        saf_oran = (v["Skor"] / toplam_skor) * 100
        yuvarlanmis = max(round(saf_oran / 5) * 5, 10)
        yuzdeler.append(yuvarlanmis)
        
    fark = 100 - sum(yuzdeler)
    if yuzdeler:
        yuzdeler[0] += fark 
        
    for i, v in enumerate(islenen_veriler):
        v["Sepet_Orani"] = f"%{int(yuzdeler[i])}"
        v["Yatırım_Bedeli"] = f"{toplam_kasa * (yuzdeler[i] / 100):.2f} $"
        
    return islenen_veriler

# --- ARAYÜZ ---
st.title("⚡ Pro Kripto & Otomatik Sanal Portföy")

kapanan_islem_bildirimleri = acik_islemleri_denetle()
if kapanan_islem_bildirimleri:
    for islem in kapanan_islem_bildirimleri:
        if "Kar" in islem["Durum"]:
            st.success(f"🎯 **Tebrikler!** İşlem ID #{islem['ID']} ({islem['Coin']}) hedef fiyata ulaşarak **Kârla** kapandı! | Net K/Z: **{islem['Kar_Zarar']:.2f} $**")
        else:
            st.error(f"🛑 **Uyarı:** İşlem ID #{islem['ID']} ({islem['Coin']}) stop seviyesine ulaşarak kapandı. | Net K/Z: **{islem['Kar_Zarar']:.2f} $**")

toplam_kasa, mevcut_bakiye = bakiye_durumunu_getir()
gunluk_kar = gunluk_kazanc_hesapla()

# --- ÜST ÖZET METRİK ALANI ---
col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("💰 Anlık Toplam Kasa", f"{toplam_kasa:.2f} $", delta=f"{toplam_kasa - BASLANGIC_BAKIYE:.2f} $")
col_m2.metric("📊 24 Saatlik Kâr / Zarar", f"{gunluk_kar:.2f} $", delta_color="normal" if gunluk_kar >= 0 else "inverse")
col_m3.metric("🟢 Mevcut Bakiye", f"{mevcut_bakiye:.2f} $")

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
        st.caption("🔥 *Liste kârlılık potansiyeli en yüksek (en verimli) coinden başlayacak şekilde sıralanmıştır.*")
        df_gosterge = pd.DataFrame(veriler)
        gosterilecek_df = df_gosterge[['Logo', 'Coin', 'Fiyat', 'Yon', 'Zaman_Dilimi', 'Sepet_Orani', 'Yatırım_Bedeli', 'Kar_Al', 'Stopla']]
        gosterilecek_df.columns = [' ', 'Coin', 'Fiyat', 'Yön', 'İşlem Süresi', 'Yatırım Oranı (%)', 'Yatırım Tutarı', 'Kar Al', 'Stopla']
        
        st.dataframe(
            gosterilecek_df.style.map(
                lambda x: 'color: #00FF66; font-weight: bold;' if x == 'Long' else ('color: #FF3333; font-weight: bold;' if x == 'Short' else ''),
                subset=['Yön']
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
            st.info(f"**Toplam Kasa:** {toplam_kasa:.2f} $ | 🟢 **Mevcut Bakiye:** {mevcut_bakiye:.2f} $ | **Önerilen Oran:** {coin_verisi['Sepet_Orani']} | **Otomatik Süre:** {coin_verisi['Zaman_Dilimi']} | **İşlem Bedeli:** {coin_verisi['Yatırım_Bedeli']}")
            
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
                else: 
                    st.error(mesaj)

with tab2:
    col_p_baslik, col_p_buton = st.columns([3, 1])
    with col_p_baslik:
        st.markdown(f"### 💰 Aktif Dönem Kasası: **{toplam_kasa:.2f} $** | 🟢 Mevcut Bakiye: **{mevcut_bakiye:.2f} $**")
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
            with col_kapat1:
                kapatilacak_id = st.selectbox("Kapatılacak İşlem ID:", acik_islem_listesi)
            with col_kapat2:
                onay_verildi = st.checkbox(f"ID #{kapatilacak_id} işlemini kapatmayı onaylıyorum")
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
                        else: 
                            st.error(b_mesaj)
                    else:
                        st.warning("Lütfen önce onay kutusunu işaretleyin!")
            st.markdown("---")

        df_gecmis = islem_gecmisi_getir()
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
                try:
                    ticker = coinler.get(row['Coin'], row['Coin'].replace('/', '-'))
                    gecmis = yf.download(ticker, period='1d', interval='1m', progress=False)
                    if isinstance(gecmis.columns, pd.MultiIndex):
                        gecmis.columns = gecmis.columns.get_level_values(0)
                    anlik_f = float(gecmis.iloc[-1]['Close'])
                    
                    fark_y = ((anlik_f - giris_f) / giris_f) if row['Yon'] == 'Long' else ((giris_f - anlik_f) / giris_f)
                    anlik_kar = (miktar * KALDIRAC) * fark_y
                    anlik_kz_sozluk[islem_id] = round(anlik_kar, 2)
                except:
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
            if pd.isna(oran) or oran == float('inf') or oran == float('-inf'):
                return "%0"
            return f"%{int(oran)}"

        df_gosterim['Islem_Orani'] = ((islem_miktari_seri / guncel_kasa_seri) * 100).apply(guvenli_yuzde_cevir)
        
        df_gosterim['Yatırım_Bedeli'] = islem_miktari_seri.apply(lambda x: f"{x:.2f} $")
        df_gosterim['Hedef_Kar_Str'] = df_gosterim['Hedef_Kar'].apply(lambda x: f"{x:.2f} $")
        df_gosterim['Anlık_KZ_Str'] = df_gosterim['Anlik_KZ_Deger'].apply(lambda x: f"{x:.2f} $")
        df_gosterim['Kasa_Str'] = guncel_kasa_seri.apply(lambda x: f"{x:.2f} $")
        
        cols = ["Islem_ID", "Tarih", "Saat", "Logo", "Coin", "Yon", "Zaman_Dilimi", "Giris_Fiyat", "Islem_Orani", "Yatırım_Bedeli", "Stop", "Kar_Al", "Hedef_Kar_Str", "Durum", "Anlık_KZ_Str", "Kasa_Str"]
        df_gosterim = df_gosterim[cols]
        df_gosterim.columns = ["ID", "Tarih", "Saat", " ", "Coin", "Yön", "İşlem Süresi", "Giriş Fiyatı", "Yatırım Oranı (%)", "Yatırım Tutarı", "Stop", "Kar Al", "Hedeflenen Kar", "Durum", "Anlık K/Z", "Kasa"]
        
        def isi_haritasi_boya(row):
            styles = [''] * len(row.index)
            durum_idx = row.index.get_loc('Durum')
            islem_id = int(row['ID'])
            orijinal_kz = float(anlik_kz_sozluk.get(islem_id, 0.0))
            durum_str = str(row['Durum'])
            
            if 'Acik' in durum_str:
                styles[durum_idx] = 'background-color: #0066FF; color: white; font-weight: bold;'
            elif orijinal_kz >= 0:
                styles[durum_idx] = 'background-color: #008751; color: white; font-weight: bold;' 
            else:
                styles[durum_idx] = 'background-color: #A30036; color: white; font-weight: bold;' 
                
            kz_idx = row.index.get_loc('Anlık K/Z')
            
            if orijinal_kz <= -10.0: renk = '#7A0028'  
            elif orijinal_kz < -5.0: renk = '#91002F'  
            elif orijinal_kz < -2.0: renk = '#A30036'  
            elif orijinal_kz < 0.0: renk = '#C7852B'  
            elif orijinal_kz == 0.0: renk = '#FFD700'  
            elif orijinal_kz <= 2.0: renk = '#85BB65'  
            elif orijinal_kz <= 5.0: renk = '#2E8B57'  
            elif orijinal_kz <= 10.0: renk = '#008751'  
            else: renk = '#006138'  
                
            yazi_rengi = '#000000' if orijinal_kz == 0.0 else '#FFFFFF'
            styles[kz_idx] = f'background-color: {renk}; color: {yazi_rengi}; font-weight: bold;'
            return styles

        st.dataframe(
            df_gosterim.style
            .apply(isi_haritasi_boya, axis=1)
            .format({
                'Giriş Fiyatı': '{:.4f}',
                'Stop': '{:.4f}',
                'Kar Al': '{:.4f}'
            }),
            use_container_width=True, hide_index=True,
            column_config={
                " ": st.column_config.ImageColumn(" ", width="small")
            }
        )

        # --- PASTA GRAFİK VE ÖZEL YAN BLOK METRİKLERİ ---
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
                df_pie = pd.DataFrame({
                    'Durum': ['Kârlı İşlemler', 'Zararlı İşlemler'],
                    'Adet': [karli_sayisi, zararli_sayisi]
                })
                fig = px.pie(
                    df_pie, names='Durum', values='Adet', hole=0.35,
                    color='Durum',
                    color_discrete_map={'Kârlı İşlemler': '#008751', 'Zararlı İşlemler': '#A30036'}
                )
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font_color='white',
                    margin=dict(t=10, b=10, l=10, r=10),
                    legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
                )
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
                    <h3 style="color: #00FF66; margin: 0px 0px 10px 0px;">+{toplam_kazanc_dolar:.2f} $</h3>
                    <p style="color: #FF3333; margin: 0px; font-size: 14px; font-weight: bold;">Toplam Zarar:</p>
                    <h3 style="color: #FF3333; margin: 0px 0px 10px 0px;">-{toplam_kayip_dolar:.2f} $</h3>
                    <hr style="border-color: #30363d; margin: 8px 0px;">
                    <p style="color: #ffffff; margin: 0px; font-size: 13px;">Net Fark:</p>
                    <h3 style="color: {'#00FF66' if net_fark_dolar >= 0 else '#FF3333'}; margin: 0px;">{net_fark_dolar:.2f} $</h3>
                </div>
                """, unsafe_allow_html=True)
                
        else:
            st.info("Henüz kapanmış işlem bulunmuyor.")

    else:
        st.warning("Henüz açılmış bir sanal işleminiz bulunmuyor.")

with tab3:
    st.markdown("### 📁 Geçmiş Arşiv Dosyaları İnceleme")
    if os.path.exists(ARSIV_KLASORU):
        arsiv_dosyalari = os.listdir(ARSIV_KLASORU)
        if arsiv_dosyalari:
            secilen_arsiv = st.selectbox("İncelemek İstediğiniz Arşiv Dönemini Seçin:", arsiv_dosyalari)
            if secilen_arsiv:
                arsiv_yolu = os.path.join(ARSIV_KLASORU, secilen_arsiv)
                df_arsiv = pd.read_csv(arsiv_yolu, delimiter=';')
                st.success(f"📂 {secilen_arsiv} arşiv dosyası başarıyla yüklendi. (Toplam {len(df_arsiv)} işlem)")
                
                # --- ARŞİV İÇİN ÖZET GÖRSEL ANALİZ (PASTA GRAFİK + METRİKLER) ---
                kapanan_arsiv_df = df_arsiv[df_arsiv['Durum'] != 'Acik']
                if not kapanan_arsiv_df.empty:
                    a_karli = 0
                    a_zararli = 0
                    a_toplam_kazanc = 0.0
                    a_toplam_kayip = 0.0
                    
                    for idx, r in kapanan_arsiv_df.iterrows():
                        val = float(pd.to_numeric(r['Net_Kar_Zarar'], errors='coerce') or 0.0)
                        if val >= 0:
                            a_karli += 1
                            a_toplam_kazanc += val
                        else:
                            a_zararli += 1
                            a_toplam_kayip += abs(val)
                            
                    a_toplam_kapanan = len(kapanan_arsiv_df)
                    a_karli_oran = (a_karli / a_toplam_kapanan) * 100 if a_toplam_kapanan > 0 else 0
                    a_zararli_oran = (a_zararli / a_toplam_kapanan) * 100 if a_toplam_kapanan > 0 else 0
                    a_net_fark = a_toplam_kazanc - a_toplam_kayip
                    
                    st.markdown("---")
                    st.markdown(f"#### 📊 {secilen_arsiv} Dönemi Özet Analiz ve Grafiği")
                    col_ap1, col_ap2, col_ap3 = st.columns([1.5, 1, 1])
                    
                    with col_ap1:
                        df_apie = pd.DataFrame({
                            'Durum': ['Kârlı İşlemler', 'Zararlı İşlemler'],
                            'Adet': [a_karli, a_zararli]
                        })
                        fig_a = px.pie(
                            df_apie, names='Durum', values='Adet', hole=0.35,
                            color='Durum',
                            color_discrete_map={'Kârlı İşlemler': '#008751', 'Zararlı İşlemler': '#A30036'}
                        )
                        fig_a.update_layout(
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            font_color='white',
                            margin=dict(t=10, b=10, l=10, r=10),
                            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
                        )
                        st.plotly_chart(fig_a, use_container_width=True)
                        
                    with col_ap2:
                        st.markdown("#### 📈 Strateji Metrikleri")
                        st.metric("Toplam Kapanan İşlem", f"{a_toplam_kapanan} Adet")
                        st.metric("🟢 Kârlı Kapanma", f"{a_karli} Adet (%{a_karli_oran:.1f})")
                        st.metric("🔴 Zararlı Kapanma", f"{a_zararli} Adet (%{a_zararli_oran:.1f})")
                        
                    with col_ap3:
                        st.markdown("#### 💰 Para Değerleri Bloku")
                        st.markdown(f"""
                        <div class="para-blogu">
                            <p style="color: #00FF66; margin: 0px; font-size: 14px; font-weight: bold;">Toplam Kâr:</p>
                            <h3 style="color: #00FF66; margin: 0px 0px 10px 0px;">+{a_toplam_kazanc:.2f} $</h3>
                            <p style="color: #FF3333; margin: 0px; font-size: 14px; font-weight: bold;">Toplam Zarar:</p>
                            <h3 style="color: #FF3333; margin: 0px 0px 10px 0px;">-{a_toplam_kayip:.2f} $</h3>
                            <hr style="border-color: #30363d; margin: 8px 0px;">
                            <p style="color: #ffffff; margin: 0px; font-size: 13px;">Net Fark:</p>
                            <h3 style="color: {'#00FF66' if a_net_fark >= 0 else '#FF3333'}; margin: 0px;">{a_net_fark:.2f} $</h3>
                        </div>
                        """, unsafe_allow_html=True)
                    st.markdown("---")
                
                st.markdown("#### 📋 Dönem İşlem Tablosu")
                st.dataframe(df_arsiv, use_container_width=True, hide_index=True)
        else:
            st.info("Arşiv klasöründe henüz tamamlanmış 50'şerli işlem dönemi bulunmuyor.")
    else:
        st.info("Arşiv klasörü henüz oluşturulmadı (İlk 50 işlem tamamlandığında otomatik oluşacaktır).")