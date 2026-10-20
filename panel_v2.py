import os, json, time, smtplib, traceback
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import gspread
from google.oauth2.service_account import Credentials
import numpy as np
import pandas as pd
import pytz
import requests

# --- SABİTLER ---
GOOGLE_SHEET_DOSYA = "KriptoPortfoyVeritabani"
ARSIV_KLASORU = "arsiv"
BASLANGIC_BAKIYE = 500.0
KALDIRAC = 3
TR_TZ = pytz.timezone("Europe/Istanbul")
HAFIZA_DOSYASI = "sinyal_hafizasi.json"
MAIL_LOG_DOSYASI = "mail_log.txt"

def tr_zaman():
    return datetime.now(TR_TZ)

def hafta_sonu_mu():
    simdi = tr_zaman()
    haftanin_gunu = simdi.weekday()
    saat = simdi.hour
    if (haftanin_gunu == 4 and saat >= 23) or (haftanin_gunu in [5, 6]) or (haftanin_gunu == 0 and saat < 3):
        return True
    return False

def aktif_min_puan_esigi_getir():
    return 60.0 if hafta_sonu_mu() else 55.0

def hafizayi_oku():
    if os.path.exists(HAFIZA_DOSYASI):
        try:
            with open(HAFIZA_DOSYASI, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def hafizayi_kaydet(hafiza):
    try:
        with open(HAFIZA_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(hafiza, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Hafıza kayıt hatası: {e}")

coinler = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"]
logo_urls = {
    "BTC/USDT": "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/btc.png",
    "ETH/USDT": "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/eth.png",
    "BNB/USDT": "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/bnb.png",
    "SOL/USDT": "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/sol.png",
    "XRP/USDT": "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/xrp.png",
    "TOTAL": "https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/usdt.png",
}
baz_fiyatlar = {
    "BTC/USDT": 83750.0,
    "ETH/USDT": 2511.0,
    "BNB/USDT": 745.0,
    "SOL/USDT": 107.6,
    "XRP/USDT": 1.373,
    "TOTAL": 2.77e12,
}

def mail_log_yaz(mesaj):
    try:
        zamanli_mesaj = f"[{tr_zaman().strftime('%d.%m.%Y %H:%M:%S')}] {mesaj}\n"
        with open(MAIL_LOG_DOSYASI, "a", encoding="utf-8") as f:
            f.write(zamanli_mesaj)
    except:
        pass

def gmail_bildirim_gonder(konu, icerik_html):
    gonderici_mail = "erhanvancin@gmail.com"
    uygulama_sifresi = os.environ.get("GMAIL_PASSWORD", "").strip()
    alici_mail = "erhanvancin@gmail.com"

    if not uygulama_sifresi:
        hata = (
            "GMAIL_PASSWORD tanımlı değil. "
            "GitHub Actions Secrets veya ortam değişkenine ekleyin."
        )
        print(hata)
        mail_log_yaz(
            f"HATA ({konu}): GMAIL_PASSWORD tanımlı değil."
        )
        return False, hata

    try:
        msg = MIMEMultipart()
        msg["From"] = gonderici_mail
        msg["To"] = alici_mail
        msg["Subject"] = konu
        msg.attach(MIMEText(icerik_html, "html"))

        server = smtplib.SMTP_SSL(
            "smtp.gmail.com", 465, timeout=10
        )
        server.login(gonderici_mail, uygulama_sifresi)
        server.sendmail(
            gonderici_mail, alici_mail, msg.as_string()
        )
        server.quit()

        mail_log_yaz(f"BAŞARILI: {konu}")
        return True, "E-posta başarıyla gönderildi."

    except Exception as e:
        hata_detayi = f"HATA ({konu}): {str(e)}"
        print(hata_detayi)
        mail_log_yaz(hata_detayi)
        return False, str(e)

# --- BİNANCE API ENTEGRASYONU ---
def fiyat_cek_binance(coin_symbol):
    if coin_symbol == "TOTAL":
        try:
            btc = fiyat_cek_binance("BTC/USDT")
            eth = fiyat_cek_binance("ETH/USDT")
            bnb = fiyat_cek_binance("BNB/USDT")
            sol = fiyat_cek_binance("SOL/USDT")
            xrp = fiyat_cek_binance("XRP/USDT")

            tahmini_total = (
                (btc * 19700000)
                + (eth * 120000000)
                + (bnb * 145000000)
                + (sol * 470000000)
                + (xrp * 5700000000)
            )
            if tahmini_total > 0:
                return float(tahmini_total)
        except:
            pass
        return baz_fiyatlar["TOTAL"]

    sym = coin_symbol.replace("/", "")
    endpoints = [
        f"https://data-api.binance.vision/api/v3/ticker/price?symbol={sym}",
        f"https://api.binance.com/api/v3/ticker/price?symbol={sym}",
    ]
    for ep in endpoints:
        try:
            r = requests.get(ep, timeout=3)
            if r.status_code == 200:
                val = float(r.json()["price"])
                if val > 0:
                    return val
        except:
            continue
    return baz_fiyatlar.get(coin_symbol, 100.0)

def kline_cek_binance(coin_symbol, interval, limit):
    sym = coin_symbol.replace("/", "")
    endpoints = [
        f"https://data-api.binance.vision/api/v3/klines?symbol={sym}&interval={interval}&limit={limit}",
        f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={interval}&limit={limit}",
    ]
    for ep in endpoints:
        try:
            r = requests.get(ep, timeout=5)
            if r.status_code == 200:
                data = r.json()
                df = pd.DataFrame(
                    data,
                    columns=[
                        "timestamp", "Open", "High", "Low", "Close", "Volume",
                        "Close_Time", "QAV", "Num_Trades", "Taker_BBAV", "Taker_BQAV", "Ignore"
                    ],
                )
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.tz_convert(TR_TZ)
                for col in ["Open", "High", "Low", "Close"]:
                    df[col] = df[col].astype(float)
                return df[["timestamp", "Open", "High", "Low", "Close"]]
        except:
            continue
    return pd.DataFrame()

def load_15min_market_data(coin_symbol: str):
    limit = 192
    if coin_symbol == "TOTAL":
        anlik_total = fiyat_cek_binance("TOTAL")
        df_btc = kline_cek_binance("BTC/USDT", "5m", limit)
        if not df_btc.empty:
            current_btc = float(df_btc["Close"].iloc[-1])
            if current_btc > 0:
                carpan = anlik_total / current_btc
                df_btc["Open"] = df_btc["Open"] * carpan
                df_btc["High"] = df_btc["High"] * carpan
                df_btc["Low"] = df_btc["Low"] * carpan
                df_btc["Close"] = df_btc["Close"] * carpan
        return df_btc

    if coin_symbol != "TOTAL":
        df = kline_cek_binance(coin_symbol, "5m", limit)
        if not df.empty:
            return df

    dates = pd.date_range(end=datetime.now(TR_TZ), periods=limit, freq="5min")
    base_p = baz_fiyatlar.get(coin_symbol, 2.77e12 if coin_symbol == "TOTAL" else 100.0)
    return pd.DataFrame({
        "timestamp": dates,
        "Open": [base_p] * limit,
        "High": [base_p] * limit,
        "Low": [base_p] * limit,
        "Close": [base_p] * limit,
    })

# --- LOGARİTMİK RİSK / HEDEF HESAPLAMA MİMARİSİ ---
def calculate_coin_metrics_by_score(matris_puani):
    hsonu = hafta_sonu_mu()
    min_esik = 60.0 if hsonu else 55.0

    if matris_puani < min_esik:
        return 0.90, 1.0, "Nötr"

    x_puanlar = np.array([55.0, 59.0, 63.0, 67.0, 71.0, 75.0])
    
    # 1. RISK HESAPLAMA (0.70 -> 0.50)
    y_risk = np.array([0.70, 0.62, 0.58, 0.55, 0.52, 0.50])
    risk_katsayilar = np.polyfit(np.log(x_puanlar), y_risk, 1)
    
    # 2. HEDEF HESAPLAMA (0.70 -> 2.00)
    y_hedef = np.array([0.70, 1.20, 1.50, 1.70, 1.87, 2.00])
    hedef_katsayilar = np.polyfit(np.log(x_puanlar), y_hedef, 1)

    puan = max(min_esik, min(100.0, matris_puani))

    stop_uzde = risk_katsayilar[0] * np.log(puan) + risk_katsayilar[1]
    hedef_uzde = hedef_katsayilar[0] * np.log(puan) + hedef_katsayilar[1]

    stop_uzde = max(0.40, min(0.70, stop_uzde))
    hedef_uzde = max(0.60, min(2.50, hedef_uzde))

    hedef_carpan = hedef_uzde / stop_uzde if stop_uzde > 0 else 1.5

    str_stop = f"{stop_uzde:.2f}".replace(".", ",")
    str_hedef = f"{hedef_uzde:.2f}".replace(".", ",")
    risk_hedef_metin = f"{str_stop} / {str_hedef}"

    return stop_uzde, hedef_carpan, risk_hedef_metin

def oransal_matris_ve_teknik_faktorler_hesapla(df, max_puan):
    if df.empty or len(df) < 10:
        return max_puan / 2.0, max_puan / 2.0, 0, 0

    df["Body"] = df["Close"] - df["Open"]
    toplam_yesil_boy = df[df["Body"] > 0]["Body"].sum()
    toplam_kirmizi_boy = abs(df[df["Body"] < 0]["Body"].sum())
    toplam_boy = toplam_yesil_boy + toplam_kirmizi_boy

    if toplam_boy > 0:
        yesil_oran = toplam_yesil_boy / toplam_boy
        kirmizi_oran = toplam_kirmizi_boy / toplam_boy
    else:
        yesil_oran, kirmizi_oran = 0.5, 0.5

    baz_long_puan = max_puan * yesil_oran
    baz_short_puan = max_puan * kirmizi_oran

    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
    anlik_fiyat = float(df["Close"].iloc[-1])
    anlik_ema = float(df["EMA20"].iloc[-1])
    fark_yuzde = (abs(anlik_fiyat - anlik_ema) / anlik_ema) * 100.0
    ema_log_carpan = min(1.0, np.log1p(fark_yuzde) / np.log1p(1.5))
    max_ema_bonus = max_puan * 0.04
    ema_l = max_ema_bonus * ema_log_carpan if anlik_fiyat > anlik_ema else 0.0
    ema_s = max_ema_bonus * ema_log_carpan if anlik_fiyat < anlik_ema else 0.0

    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi_serisi = 100 - (100 / (1 + rs))
    rsi_anlik = float(rsi_serisi.iloc[-1]) if not rsi_serisi.isna().all() else 50.0
    fark_rsi = abs(rsi_anlik - 50.0)
    rsi_log_carpan = min(1.0, np.log1p(fark_rsi) / np.log1p(20.0))
    max_rsi_bonus = max_puan * 0.03
    rsi_l = max_rsi_bonus * rsi_log_carpan if rsi_anlik > 50 else 0.0
    rsi_s = max_rsi_bonus * rsi_log_carpan if rsi_anlik < 50 else 0.0

    max_f = float(df["High"].max())
    min_f = float(df["Low"].min())
    fiyat_fark = max_f - min_f
    fib_l, fib_s = 0.0, 0.0
    if fiyat_fark > 0:
        fib_050 = min_f + (fiyat_fark * 0.5)
        fib_618 = min_f + (fiyat_fark * 0.618)
        mesafe_050 = abs(anlik_fiyat - fib_050) / fiyat_fark
        mesafe_618 = abs(anlik_fiyat - fib_618) / fiyat_fark
        min_mesafe = min(mesafe_050, mesafe_618)
        if min_mesafe < 0.05:
            yaklasim = (0.05 - min_mesafe) / 0.05
            fib_log_carpan = np.log1p(yaklasim * 10) / np.log1p(10)
            max_fib_bonus = max_puan * 0.03
            if anlik_fiyat >= anlik_ema:
                fib_l = max_fib_bonus * fib_log_carpan
            else:
                fib_s = max_fib_bonus * fib_log_carpan

    final_long = baz_long_puan + ema_l + rsi_l + fib_l
    final_short = baz_short_puan + ema_s + rsi_s + fib_s

    grup_toplam = final_long + final_short
    if grup_toplam > 0 and grup_toplam > max_puan:
        final_long = (final_long / grup_toplam) * max_puan
        final_short = (final_short / grup_toplam) * max_puan

    y_adet = len(df[df["Body"] > 0])
    k_adet = len(df[df["Body"] < 0])
    return round(final_long, 2), round(final_short, 2), y_adet, k_adet

def kurgusal_matris_hesapla(coin_symbol):
    anlik_fiyat = fiyat_cek_binance(coin_symbol)
    sembol_istek = coin_symbol if coin_symbol != "TOTAL" else "BTC/USDT"

    df_16s = kline_cek_binance(sembol_istek, "15m", 64)
    df_8s = kline_cek_binance(sembol_istek, "5m", 96)
    df_4s = kline_cek_binance(sembol_istek, "5m", 48)
    df_2s = kline_cek_binance(sembol_istek, "1m", 120)
    df_1s = kline_cek_binance(sembol_istek, "1m", 60)

    dilimler = [
        (df_16s, 9.5, "16 S"),
        (df_8s, 15.5, "8 S"),
        (df_4s, 50.0, "4 S"),
        (df_2s, 15.5, "2 S"),
        (df_1s, 9.5, "1 S"),
    ]

    toplam_long_puan = 0.0
    toplam_short_puan = 0.0
    zaman_katkilari = {}

    for df_zaman, max_puan, isim in dilimler:
        sl, ss, y_ad, k_ad = oransal_matris_ve_teknik_faktorler_hesapla(df_zaman, max_puan)
        toplam_long_puan += sl
        toplam_short_puan += ss
        zaman_katkilari[isim] = {
            "sl": sl,
            "ss": ss,
            "y_adet": y_ad,
            "k_adet": k_ad,
        }

    nihai_long = round(toplam_long_puan, 2)
    nihai_short = round(toplam_short_puan, 2)
    min_esik_degeri = aktif_min_puan_esigi_getir()

    if nihai_long >= min_esik_degeri:
        nihai_puan = nihai_long
        aktif_yon = "Long"
    elif nihai_short >= min_esik_degeri:
        nihai_puan = nihai_short
        aktif_yon = "Short"
    else:
        nihai_puan = round(max(nihai_long, nihai_short), 2)
        aktif_yon = "Long" if nihai_long >= nihai_short else "Short"

    return anlik_fiyat, nihai_puan, aktif_yon, nihai_long, nihai_short, zaman_katkilari

def google_sheets_baglan(sayfa_adi):
    try:
        raw = os.environ.get("GCP_SERVICE_ACCOUNT_JSON", "").strip()
        if raw:
            sec_dict = json.loads(raw)
            if "private_key" in sec_dict:
                sec_dict["private_key"] = sec_dict["private_key"].replace(r"\n", "\n")
            client = gspread.service_account_from_dict(sec_dict)
        elif os.path.exists("credentials.json"):
            client = gspread.service_account(filename="credentials.json")
        else:
            print("Google Sheets kimlik bilgisi yok: GCP_SERVICE_ACCOUNT_JSON veya credentials.json gerekli.")
            return None
        return client.open(GOOGLE_SHEET_DOSYA).worksheet(sayfa_adi)
    except Exception as e:
        print(f"Google Sheets bağlantı hatası: {e}")
        return None

def islem_gecmisi_getir(sheet_guncelle=True):
    beklenen_kolonlar = [
        "Islem_ID", "Acilis_Zamani", "Coin", "Yon", "Zaman_Dilimi",
        "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Beklenen_Kar",
        "Matris_Puan_RH", "Olasi_Stop", "Durum", "Net_Kar_Zarar",
        "Guncel_Kasa", "Kapanis_Zamani", "Kapanis_Fiyati"
    ]
    sheet = google_sheets_baglan("KriptoPortfoyVeritabani")
    if sheet is None:
        return pd.DataFrame(columns=beklenen_kolonlar)
    try:
        ham_veriler = sheet.get_all_values()
    except Exception:
        return pd.DataFrame(columns=beklenen_kolonlar)

    if not ham_veriler or len(ham_veriler) == 0:
        if sheet_guncelle:
            try:
                sheet.append_row(beklenen_kolonlar)
            except:
                pass
        return pd.DataFrame(columns=beklenen_kolonlar)

    satirlar = ham_veriler[1:] if len(ham_veriler) > 1 else []
    duzeltilmis_satirlar = []
    for satir in satirlar:
        if len(satir) < len(beklenen_kolonlar):
            satir.extend([""] * (len(beklenen_kolonlar) - len(satir)))
        elif len(satir) > len(beklenen_kolonlar):
            satir = satir[: len(beklenen_kolonlar)]
        duzeltilmis_satirlar.append(satir)

    df = pd.DataFrame(duzeltilmis_satirlar, columns=beklenen_kolonlar)
    if not df.empty and "Islem_ID" in df.columns:
        df = df[
            df["Islem_ID"].notna()
            & (df["Islem_ID"] != "")
            & (df["Islem_ID"].astype(str) != "Islem_ID")
        ]
    df["Islem_ID"] = pd.to_numeric(df["Islem_ID"], errors="coerce").fillna(0).astype(int)
    df = df.drop_duplicates(subset=["Islem_ID"], keep="last").sort_values(by="Islem_ID").reset_index(drop=True)
    sayisal_kolonlar = [
        "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Beklenen_Kar",
        "Olasi_Stop", "Net_Kar_Zarar", "Guncel_Kasa", "Kapanis_Fiyati"
    ]
    for col in sayisal_kolonlar:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", ".").str.strip(),
                errors="coerce",
            ).fillna(0.0).astype(float)
    return df

# --- GOOGLE SHEETS HIZLI GÜNCELLEME (TOPLU UPDATE) ---
def dataframe_guncelle_gsheets(df):
    sheet = google_sheets_baglan("KriptoPortfoyVeritabani")
    if sheet is not None:
        try:
            # Tek tek append_row yapmak yerine tüm tabloyu tek seferde güncelliyoruz (Hızlı & Güvenli)[cite: 1]
            df["Islem_ID"] = df["Islem_ID"].astype(int)
            df = df.sort_values(by="Islem_ID").reset_index(drop=True)
            veri_listesi = [df.columns.tolist()] + df.values.tolist()
            sheet.clear()
            sheet.update(veri_listesi)
        except Exception as e:
            print(f"GSheets Güncelleme Hatası: {e}")

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
        try:
            sheet.append_row(kolonlar)
        except:
            pass
        return pd.DataFrame(columns=kolonlar)

    satirlar = ham[1:] if len(ham) > 1 else []
    duz_satirlar = []
    for s in satirlar:
        if len(s) < len(kolonlar):
            s.extend([""] * (len(kolonlar) - len(s)))
        elif len(s) > len(kolonlar):
            s = s[: len(kolonlar)]
        duz_satirlar.append(s)

    df = pd.DataFrame(duz_satirlar, columns=kolonlar)
    if not df.empty and "Islem_ID" in df.columns:
        df = df[
            df["Islem_ID"].notna()
            & (df["Islem_ID"] != "")
            & (df["Islem_ID"].astype(str) != "Islem_ID")
        ]
    df["Islem_ID"] = pd.to_numeric(df["Islem_ID"], errors="coerce").fillna(0).astype(int)
    df["Tutar"] = pd.to_numeric(
        df["Tutar"].astype(str).str.replace(",", ".").str.strip(),
        errors="coerce",
    ).fillna(0.0).astype(float)
    return df

def kasa_defteri_guncelle_gsheets(df):
    sheet = google_sheets_baglan("KasaDefteri")
    if sheet is not None:
        try:
            df["Islem_ID"] = df["Islem_ID"].astype(int)
            df = df.sort_values(by="Islem_ID").reset_index(drop=True)
            veri_listesi = [df.columns.tolist()] + df.values.tolist()
            sheet.clear()
            sheet.update(veri_listesi)
        except Exception as e:
            print(f"Kasa Defteri Güncelleme Hatası: {e}")

def kasa_islem_ekle(islem_turu, tutar, aciklama):
    df_kasa = kasa_defteri_getir()
    yeni_id = 1 if df_kasa.empty else int(pd.to_numeric(df_kasa["Islem_ID"], errors="coerce").max() or 0) + 1
    suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")

    islem_carpan = 1.0 if islem_turu == "Para_Yatir" else -1.0
    net_tutar = float(tutar) * islem_carpan

    yeni_kayit = pd.DataFrame([{
        "Islem_ID": yeni_id,
        "Zaman": suan_tr,
        "Islem_Turu": islem_turu,
        "Tutar": round(net_tutar, 2),
        "Aciklama": aciklama,
    }])
    df_kasa = pd.concat([df_kasa, yeni_kayit], ignore_index=True).drop_duplicates(subset=["Islem_ID"], keep="last")
    kasa_defteri_guncelle_gsheets(df_kasa)
    return True, f"Kasa işlemi başarılı: {islem_turu} -> {net_tutar:.2f} $"

def kasa_islem_ekle_deftere(islem_turu, tutar, aciklama):
    df_kasa = kasa_defteri_getir()
    yeni_id = 1 if df_kasa.empty else int(pd.to_numeric(df_kasa["Islem_ID"], errors="coerce").max() or 0) + 1
    suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")
    yeni_kayit = pd.DataFrame([{
        "Islem_ID": yeni_id,
        "Zaman": suan_tr,
        "Islem_Turu": islem_turu,
        "Tutar": round(tutar, 2),
        "Aciklama": aciklama,
    }])
    df_kasa = pd.concat([df_kasa, yeni_kayit], ignore_index=True).drop_duplicates(subset=["Islem_ID"], keep="last")
    kasa_defteri_guncelle_gsheets(df_kasa)

def elli_islem_arsiv_kontrol():
    try:
        df = islem_gecmisi_getir(sheet_guncelle=False)
        if df.empty:
            return
        toplam_islem = len(df)
        if toplam_islem >= 50:
            if not os.path.exists(ARSIV_KLASORU):
                os.makedirs(ARSIV_KLASORU)
            blok_sayisi = toplam_islem // 50
            for b in range(blok_sayisi):
                bas_i, bit_i = b * 50, (b + 1) * 50
                blok_df = df.iloc[bas_i:bit_i]
                yol = os.path.join(ARSIV_KLASORU, f"islem_arsivi_{bas_i+1}_{bit_i}.csv")
                if not os.path.exists(yol):
                    blok_df.to_csv(yol, sep=";", index=False)
    except:
        pass

# --- BAKİYE VE ORTAK FİYAT HAVUZU ---
def bakiye_durumunu_getir(ortak_fiyat_havuzu={}):
    df_trade = islem_gecmisi_getir(sheet_guncelle=False)
    df_kasa = kasa_defteri_getir()
    net_kasa_hareketleri = BASLANGIC_BAKIYE

    if not df_kasa.empty:
        net_kasa_hareketleri += pd.to_numeric(df_kasa["Tutar"], errors="coerce").fillna(0.0).sum()

    if not df_trade.empty:
        kap_trades = df_trade[df_trade["Durum"].astype(str).str.contains("Kapandi|Kar|Zarar|Kismi", case=False, na=False)]
        if not kap_trades.empty:
            trade_sonuc_defterde = 0.0
            if not df_kasa.empty and "Islem_Turu" in df_kasa.columns:
                ts_df = df_kasa[df_kasa["Islem_Turu"] == "Trade_Sonuc"]
                if not ts_df.empty:
                    trade_sonuc_defterde = pd.to_numeric(ts_df["Tutar"], errors="coerce").fillna(0.0).sum()
            gercek_trade_toplam = pd.to_numeric(kap_trades["Net_Kar_Zarar"], errors="coerce").fillna(0.0).sum()
            if gercek_trade_toplam != trade_sonuc_defterde:
                net_kasa_hareketleri += gercek_trade_toplam - trade_sonuc_defterde

    toplam_kasa = net_kasa_hareketleri
    acik_df = pd.DataFrame()
    if not df_trade.empty and "Durum" in df_trade.columns:
        kapali_mask = df_trade["Durum"].astype(str).str.contains("kapandi|kar|zarar|kısmi", case=False, na=False)
        acik_df = df_trade[~kapali_mask]

    aktif_marjin_toplami = 0.0
    acik_kz_toplam = 0.0

    if not acik_df.empty:
        aktif_marjin_toplami = pd.to_numeric(acik_df["Islem_Miktari"], errors="coerce").fillna(0.0).sum()
        for _, rw in acik_df.iterrows():
            c_SYM = rw["Coin"]
            g_F = float(rw["Giris_Fiyat"])
            m_M = float(rw["Islem_Miktari"])
            y_Y = rw["Yon"]
            if not ortak_fiyat_havuzu:
                anl_F = fiyat_cek_binance(c_SYM)
            else:
                anl_F = ortak_fiyat_havuzu.get(c_SYM, baz_fiyatlar.get(c_SYM, 100.0))
            f_y = ((anl_F - g_F) / g_F) if "Long" in y_Y else ((g_F - anl_F) / g_F)
            acik_kz_toplam += m_M * KALDIRAC * f_y

    efektif_kasa = toplam_kasa + acik_kz_toplam
    bos_bakiye = toplam_kasa - aktif_marjin_toplami
    return float(toplam_kasa), float(efektif_kasa), float(bos_bakiye), float(aktif_marjin_toplami), float(acik_kz_toplam)

def yeni_islem_ekle(coin, yon, giris_fiyat, islem_miktari, stop, kar_al, zaman_dilimi, matris_puan, risk_hedef_metin):
    df = islem_gecmisi_getir()
    _, _, mevcut_bakiye, _, _ = bakiye_durumunu_getir()
    if round(islem_miktari, 2) > round(mevcut_bakiye, 2):
        return False, f"Bakiye yetersiz! Mevcut Bakiye: {mevcut_bakiye:.2f} $, Girilen: {islem_miktari:.2f} $"
    if islem_miktari <= 0:
        return False, "İşlem miktarı 0 $'dan büyük olmalıdır!"

    suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")
    acik_islem_idx = None
    if not df.empty and "Durum" in df.columns:
        acik_mask = ~df["Durum"].astype(str).str.contains("kapandi|kar|zarar|kısmi", case=False, na=False)
        acik_df = df[acik_mask]
        if not acik_df.empty and coin in acik_df["Coin"].values:
            acik_islem_idx = acik_df[acik_df["Coin"] == coin].index[0]

    if acik_islem_idx is not None:
        eski_giris = float(df.loc[acik_islem_idx, "Giris_Fiyat"])
        eski_miktar = float(df.loc[acik_islem_idx, "Islem_Miktari"])
        eski_yon = str(df.loc[acik_islem_idx, "Yon"])

        eski_matris_rh = str(df.loc[acik_islem_idx, "Matris_Puan_RH"])
        try:
            eski_puan = float(eski_matris_rh.split()[0].replace(",", "."))
        except:
            eski_puan = matris_puan

        yeni_toplam_miktar = eski_miktar + islem_miktari
        yeni_agirlikli_ortalama = ((eski_miktar * eski_giris) + (islem_miktari * giris_fiyat)) / yeni_toplam_miktar
        yeni_agirlikli_puan = ((eski_miktar * eski_puan) + (islem_miktari * matris_puan)) / yeni_toplam_miktar

        if eski_giris > 0:
            stop_oran = abs(stop - giris_fiyat) / giris_fiyat
            kar_al_oran = abs(kar_al - giris_fiyat) / giris_fiyat
        else:
            stop_oran, kar_al_oran = 0.01, 0.02

        if "Long" in eski_yon:
            yeni_stop = yeni_agirlikli_ortalama * (1.0 - stop_oran)
            yeni_kar_al = yeni_agirlikli_ortalama * (1.0 + kar_al_oran)
            beklenen_kar = yeni_toplam_miktar * KALDIRAC * ((yeni_kar_al - yeni_agirlikli_ortalama) / yeni_agirlikli_ortalama)
            olasi_stop = yeni_toplam_miktar * KALDIRAC * ((yeni_stop - yeni_agirlikli_ortalama) / yeni_agirlikli_ortalama)
        else:
            yeni_stop = yeni_agirlikli_ortalama * (1.0 + stop_oran)
            yeni_kar_al = yeni_agirlikli_ortalama * (1.0 - kar_al_oran)
            beklenen_kar = yeni_toplam_miktar * KALDIRAC * ((yeni_agirlikli_ortalama - yeni_kar_al) / yeni_agirlikli_ortalama)
            olasi_stop = yeni_toplam_miktar * KALDIRAC * ((yeni_agirlikli_ortalama - yeni_stop) / yeni_agirlikli_ortalama)

        basamak = 4 if yeni_agirlikli_ortalama < 10 else 2
        matris_rh_metin = f"{yeni_agirlikli_puan:.2f} ({risk_hedef_metin})"
        toplam_kasa, _, _, _, _ = bakiye_durumunu_getir()

        df.at[acik_islem_idx, "Giris_Fiyat"] = round(yeni_agirlikli_ortalama, basamak)
        df.at[acik_islem_idx, "Islem_Miktari"] = round(yeni_toplam_miktar, 2)
        df.at[acik_islem_idx, "Stop"] = round(yeni_stop, basamak)
        df.at[acik_islem_idx, "Kar_Al"] = round(yeni_kar_al, basamak)
        df.at[acik_islem_idx, "Acilis_Zamani"] = suan_tr
        df.at[acik_islem_idx, "Beklenen_Kar"] = round(beklenen_kar, 2)
        df.at[acik_islem_idx, "Olasi_Stop"] = round(olasi_stop, 2)
        df.at[acik_islem_idx, "Matris_Puan_RH"] = matris_rh_metin
        df.at[acik_islem_idx, "Guncel_Kasa"] = round(toplam_kasa, 2)

        dataframe_guncelle_gsheets(df)
        elli_islem_arsiv_kontrol()
        return True, f"🔄 {coin} pozisyonuna ekleme yapıldı! Yeni Ort. Maliyet: {yeni_agirlikli_ortalama:,.{basamak}f} $"
    else:
        min_esik_kontrol = aktif_min_puan_esigi_getir()
        if matris_puan < min_esik_kontrol or "Nötr" in yon or "Beklemede" in yon:
            return False, f"⚠️ Nötr veya Min. Eşik ({min_esik_kontrol}) altındaki yeni işlemler engellenmiştir!"

        yeni_id = 1 if df.empty else int(pd.to_numeric(df["Islem_ID"], errors="coerce").max() or 0) + 1

        if "Long" in yon:
            beklenen_kar = islem_miktari * KALDIRAC * ((kar_al - giris_fiyat) / giris_fiyat)
            olasi_stop = islem_miktari * KALDIRAC * ((stop - giris_fiyat) / giris_fiyat)
        else:
            beklenen_kar = islem_miktari * KALDIRAC * ((giris_fiyat - kar_al) / giris_fiyat)
            olasi_stop = islem_miktari * KALDIRAC * ((giris_fiyat - stop) / giris_fiyat)

        basamak = 4 if giris_fiyat < 10 else 2
        matris_rh_metin = f"{matris_puan} ({risk_hedef_metin})"
        toplam_kasa, _, _, _, _ = bakiye_durumunu_getir()
        yeni_kayit = pd.DataFrame([{
            "Islem_ID": yeni_id,
            "Acilis_Zamani": suan_tr,
            "Coin": coin,
            "Yon": yon,
            "Zaman_Dilimi": zaman_dilimi,
            "Giris_Fiyat": round(giris_fiyat, basamak),
            "Islem_Miktari": round(islem_miktari, 2),
            "Stop": round(stop, basamak),
            "Kar_Al": round(kar_al, basamak),
            "Beklenen_Kar": round(beklenen_kar, 2),
            "Matris_Puan_RH": matris_rh_metin,
            "Olasi_Stop": round(olasi_stop, 2),
            "Durum": "Acik",
            "Net_Kar_Zarar": 0.0,
            "Guncel_Kasa": round(toplam_kasa, 2),
            "Kapanis_Zamani": "-",
            "Kapanis_Fiyati": 0.0,
        }])
        df = pd.concat([df, yeni_kayit], ignore_index=True).drop_duplicates(subset=["Islem_ID"], keep="last")
        dataframe_guncelle_gsheets(df)
        elli_islem_arsiv_kontrol()
        return True, f"✅ {coin} emri başarıyla verildi!"

def manuel_islem_kapat(islem_id, anlik_kapatma_fiyati, kapatilacak_miktar=None):
    df = islem_gecmisi_getir()
    idx = df[df["Islem_ID"] == islem_id].index
    if idx.empty:
        return False, "İşlem bulunamadı!"
    row = df.loc[idx[0]]
    try:
        giris_fiyat = float(row["Giris_Fiyat"])
        mevcut_miktar = float(row["Islem_Miktari"])
        suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")

        if kapatilacak_miktar is not None and kapatilacak_miktar < mevcut_miktar:
            fark_yuzde = ((anlik_kapatma_fiyati - giris_fiyat) / giris_fiyat) if "Long" in row["Yon"] else ((giris_fiyat - anlik_kapatma_fiyati) / giris_fiyat)
            kismi_kar = kapatilacak_miktar * KALDIRAC * fark_yuzde
            
            yeni_id = int(pd.to_numeric(df["Islem_ID"], errors="coerce").max() or 0) + 1
            durum_metni = "Kısmi Kapandı (Zarar)" if kismi_kar < 0 else "Kısmi Kapandı (Kâr)"
            
            toplam_kasa, _, _, _, _ = bakiye_durumunu_getir()
            yeni_kapali_kayit = pd.DataFrame([{
                "Islem_ID": yeni_id,
                "Acilis_Zamani": row["Acilis_Zamani"],
                "Coin": row["Coin"],
                "Yon": row["Yon"],
                "Zaman_Dilimi": row["Zaman_Dilimi"],
                "Giris_Fiyat": giris_fiyat,
                "Islem_Miktari": round(kapatilacak_miktar, 2),
                "Stop": float(row["Stop"]),
                "Kar_Al": float(row["Kar_Al"]),
                "Beklenen_Kar": float(row["Beklenen_Kar"]),
                "Matris_Puan_RH": row["Matris_Puan_RH"],
                "Olasi_Stop": float(row["Olasi_Stop"]),
                "Durum": durum_metni,
                "Net_Kar_Zarar": float(round(kismi_kar, 2)),
                "Guncel_Kasa": float(round(toplam_kasa + kismi_kar, 2)),
                "Kapanis_Zamani": suan_tr,
                "Kapanis_Fiyati": float(round(anlik_kapatma_fiyati, 4)),
            }])
            
            kalan_miktar = mevcut_miktar - kapatilacak_miktar
            df.at[idx[0], "Islem_Miktari"] = round(kalan_miktar, 2)
            
            if "Long" in row["Yon"]:
                bek_kar_yeni = kalan_miktar * KALDIRAC * ((float(row["Kar_Al"]) - giris_fiyat) / giris_fiyat)
                olasi_stop_yeni = kalan_miktar * KALDIRAC * ((float(row["Stop"]) - giris_fiyat) / giris_fiyat)
            else:
                bek_kar_yeni = kalan_miktar * KALDIRAC * ((giris_fiyat - float(row["Kar_Al"])) / giris_fiyat)
                olasi_stop_yeni = kalan_miktar * KALDIRAC * ((giris_fiyat - float(row["Stop"])) / giris_fiyat)
            
            df.at[idx[0], "Beklenen_Kar"] = round(bek_kar_yeni, 2)
            df.at[idx[0], "Olasi_Stop"] = round(olasi_stop_yeni, 2)
            
            df = pd.concat([df, yeni_kapali_kayit], ignore_index=True).sort_values(by="Islem_ID").reset_index(drop=True)
            dataframe_guncelle_gsheets(df)
            
            kasa_islem_ekle_deftere(
                "Trade_Sonuc",
                float(round(kismi_kar, 2)),
                f"Kısmi K/Z: #{islem_id} {row['Coin']} ({kapatilacak_miktar}$ kapatıldı)",
            )
            elli_islem_arsiv_kontrol()
            return True, f"Kısmi kapama başarılı! Realize Edilen K/Z: {kismi_kar:,.2f} $"
        else:
            fark_yuzde = ((anlik_kapatma_fiyati - giris_fiyat) / giris_fiyat) if "Long" in row["Yon"] else ((giris_fiyat - anlik_kapatma_fiyati) / giris_fiyat)
            net_kar = mevcut_miktar * KALDIRAC * fark_yuzde

            durum_metni = "Kapandi (Zarar)" if net_kar < 0 else "Kapandi (Kar)"
            df.at[idx[0], "Durum"] = durum_metni
            df.at[idx[0], "Kapanis_Zamani"] = suan_tr
            df.at[idx[0], "Net_Kar_Zarar"] = float(round(net_kar, 2))
            df.at[idx[0], "Kapanis_Fiyati"] = float(round(anlik_kapatma_fiyati, 4))

            toplam_kasa, _, _, _, _ = bakiye_durumunu_getir()
            df.at[idx[0], "Guncel_Kasa"] = float(round(toplam_kasa + net_kar, 2))
            dataframe_guncelle_gsheets(df)
            kasa_islem_ekle_deftere(
                "Trade_Sonuc",
                float(round(net_kar, 2)),
                f"Trade K/Z: #{islem_id} {row['Coin']} ({durum_metni})",
            )
            elli_islem_arsiv_kontrol()
            return True, f"İşlem tamamen kapatıldı. K/Z: {net_kar:.2f} $"
    except Exception as e:
        return False, f"Hata: {str(e)}"

def otomatik_stop_kar_kontrolu(ortak_fiyat_havuzu=None):
    df = islem_gecmisi_getir(sheet_guncelle=False)
    if df.empty or "Durum" not in df.columns:
        return

    degisiklik_oldu = False
    suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")

    for idx, row in df.iterrows():
        durum_str = str(row["Durum"]).lower()
        if not ("kapandi" in durum_str or "kar" in durum_str or "zarar" in durum_str or "kısmi" in durum_str):
            islem_id = int(row["Islem_ID"])
            coin = row["Coin"]
            yon = row["Yon"]
            giris_fiyat = float(row["Giris_Fiyat"])
            stop_f = float(row["Stop"])
            kar_al_f = float(row["Kar_Al"])
            miktar = float(row["Islem_Miktari"])

            if ortak_fiyat_havuzu is not None and coin in ortak_fiyat_havuzu:
                anl_f = ortak_fiyat_havuzu[coin]
            else:
                anl_f = fiyat_cek_binance(coin)

            islem_kapatilacak = False
            hedefe_ulasti = False
            kapanis_fiyat_degeri = 0.0

            if "Long" in yon:
                if anl_f <= stop_f:
                    islem_kapatilacak, hedefe_ulasti, kapanis_fiyat_degeri = True, False, stop_f
                elif anl_f >= kar_al_f:
                    islem_kapatilacak, hedefe_ulasti, kapanis_fiyat_degeri = True, True, kar_al_f
            elif "Short" in yon:
                if anl_f >= stop_f:
                    islem_kapatilacak, hedefe_ulasti, kapanis_fiyat_degeri = True, False, stop_f
                elif anl_f <= kar_al_f:
                    islem_kapatilacak, hedefe_ulasti, kapanis_fiyat_degeri = True, True, kar_al_f

            if islem_kapatilacak:
                fark_yuzde = ((kapanis_fiyat_degeri - giris_fiyat) / giris_fiyat) if "Long" in yon else ((giris_fiyat - kapanis_fiyat_degeri) / giris_fiyat)
                net_kar = miktar * KALDIRAC * fark_yuzde
                durum_metni = "Kapandi (Kar)" if hedefe_ulasti else "Kapandi (Zarar)"

                df.at[idx, "Durum"] = durum_metni
                df.at[idx, "Kapanis_Zamani"] = suan_tr
                df.at[idx, "Net_Kar_Zarar"] = float(round(net_kar, 2))
                df.at[idx, "Kapanis_Fiyati"] = float(round(kapanis_fiyat_degeri, 4))

                toplam_kasa, _, _, _, _ = bakiye_durumunu_getir({} if ortak_fiyat_havuzu is None else ortak_fiyat_havuzu)
                df.at[idx, "Guncel_Kasa"] = float(round(toplam_kasa + net_kar, 2))

                islem_turu_etiket = "Hedef Kâr" if hedefe_ulasti else "Otomatik Stop"
                kasa_islem_ekle_deftere(
                    "Trade_Sonuc",
                    float(round(net_kar, 2)),
                    f"{islem_turu_etiket}: #{islem_id} {coin} ({'Kar' if hedefe_ulasti else 'Zarar'})",
                )
                
                hafiza = hafizayi_oku()
                islem_mail_anahtari = f"otomatik_kapanma_{islem_id}"
                if not hafiza.get(islem_mail_anahtari, False):
                    hafiza[islem_mail_anahtari] = True
                    hafizayi_kaydet(hafiza)

                    konu_mail = f"⚡ {islem_turu_etiket}: #{islem_id} {coin} ({durum_metni})"
                    icerik_mail = f"<h3>Otomatik İşlem Kapatıldı</h3><p><b>Coin:</b> {coin}</p><p><b>Yön:</b> {yon}</p><p><b>Sebep:</b> {islem_turu_etiket}</p><p><b>Net K/Z:</b> {net_kar:,.2f} $</p><p><b>Güncel Kasa:</b> {toplam_kasa + net_kar:,.2f} $</p>"
                    gmail_bildirim_gonder(konu_mail, icerik_mail)

                degisiklik_oldu = True

    if degisiklik_oldu:
        dataframe_guncelle_gsheets(df)
        elli_islem_arsiv_kontrol()

def trend_asamasini_ve_ikon_belirle(puan, aktif_yon):
    hsonu = hafta_sonu_mu()
    min_esik = 60.0 if hsonu else 55.0

    if puan < min_esik:
        return "Nötr (Beklemede)", 1.0, False, False

    if not hsonu:
        if 55.0 <= puan < 58.75:
            return "⭐ 1. Aşama (Zayıf Trend)", 3.0, False, False
        elif 58.75 <= puan < 62.50:
            return "⭐⭐ 2. Aşama (Orta Trend)", 3.0, False, False
        elif 62.50 <= puan < 66.25:
            return "⭐⭐⭐ 3. Aşama (Güvenli Trend)", 3.0, False, False
        elif 66.25 <= puan < 70.00:
            return "🔥 4. Aşama (Güçlü Trend)", 3.0, False, False
        elif 70.00 <= puan < 73.75:
            return "🔥 🔥 5. Aşama (Çok Güçlü Trend)", 4.0, True, False
        else:
            return "🔥🔥🔥 6. Aşama (Boğa Vuruşu / Ayı Pençesi)", 5.0, False, True
    else:
        if 60.0 <= puan < 63.75:
            return "⭐ 1. Aşama (Zayıf Trend)", 3.0, False, False
        elif 63.75 <= puan < 67.50:
            return "⭐⭐ 2. Aşama (Orta Trend)", 3.0, False, False
        elif 67.50 <= puan < 71.25:
            return "⭐⭐⭐ 3. Aşama (Güvenli Trend)", 3.0, False, False
        elif 71.25 <= puan < 75.00:
            return "🔥 4. Aşama (Güçlü Trend)", 3.0, False, False
        elif 75.00 <= puan < 78.75:
            return "🔥 🔥 5. Aşama (Çok Güçlü Trend)", 4.0, True, False
        else:
            return "🔥🔥🔥 6. Aşama (Boğa Vuruşu / Ayı Pençesi)", 5.0, False, True

def sinyal_ve_trend_mail_kontrolu(sembol, nihai_puan, aktif_yon, trend_metni, coin_mi=True):
    hafiza = hafizayi_oku()
    if sembol not in hafiza:
        hafiza[sembol] = {"asama_5_tetiklendi": False, "asama_6_tetiklendi": False}

    hsonu = hafta_sonu_mu()
    asama_5_sart = False
    asama_6_sart = False

    if not hsonu:
        if 70.00 <= nihai_puan < 73.75:
            asama_5_sart = True
        elif nihai_puan >= 73.75:
            asama_6_sart = True
    else:
        if 75.00 <= nihai_puan < 78.75:
            asama_5_sart = True
        elif nihai_puan >= 78.75:
            asama_6_sart = True

    if coin_mi and asama_5_sart and not hafiza[sembol]["asama_5_tetiklendi"]:
        konu = f"🔥🔥 Çok Güçlü Trend Sinyali (5. Aşama): {sembol} (Puan: {nihai_puan:.1f})"
        icerik = f"<h3>Coin 5. Aşama Çok Güçlü Trende Ulaştı!</h3><p><b>Coin:</b> {sembol}</p><p><b>Matris Puanı:</b> {nihai_puan:.1f} / 100</p><p><b>Yön:</b> {aktif_yon}</p>"
        ok, _ = gmail_bildirim_gonder(konu, icerik)
        if ok:
            hafiza[sembol]["asama_5_tetiklendi"] = True
            hafizayi_kaydet(hafiza)
    elif coin_mi and not asama_5_sart and hafiza[sembol]["asama_5_tetiklendi"]:
        hafiza[sembol]["asama_5_tetiklendi"] = False
        hafizayi_kaydet(hafiza)

    if not coin_mi and asama_6_sart and not hafiza[sembol]["asama_6_tetiklendi"]:
        konu = f"🔥🔥🔥 Top 5 Endeks Zirvede (6. Aşama - Boğa/Ayı Vuruşu): Puan {nihai_puan:.1f}"
        icerik = f"<h3>Top 5 Endeks 6. Aşama Zirveye Ulaştı!</h3><p><b>Matris Puanı:</b> {nihai_puan:.1f} / 100</p><p><b>Durum:</b> Boğa Vuruşu / Ayı Pençesi</p>"
        ok, _ = gmail_bildirim_gonder(konu, icerik)
        if ok:
            hafiza[sembol]["asama_6_tetiklendi"] = True
            hafizayi_kaydet(hafiza)
    elif not coin_mi and not asama_6_sart and hafiza[sembol]["asama_6_tetiklendi"]:
        hafiza[sembol]["asama_6_tetiklendi"] = False
        hafizayi_kaydet(hafiza)

# --- ARKA PLAN DİNLEYİCİSİ (TOPLU FİYAT HAVUZU İLE) ---
def main():
    print(f"Bot kontrolü başladı: {tr_zaman().isoformat()}")
    symbols = coinler + ["TOTAL"]
    prices = {}
    errors = 0
    for symbol in symbols:
        try:
            prices[symbol] = fiyat_cek_binance(symbol)
            _, score, direction, _, _, _ = kurgusal_matris_hesapla(symbol)
            trend_text, _, _, _ = trend_asamasini_ve_ikon_belirle(score, direction)
            print(f"{symbol}: fiyat={prices[symbol]} puan={score} yön={direction} trend={trend_text}")
            sinyal_ve_trend_mail_kontrolu(symbol, score, direction, trend_text, coin_mi=(symbol != "TOTAL"))
        except Exception as exc:
            errors += 1
            print(f"{symbol} kontrol hatası: {exc}")
            traceback.print_exc()
    try:
        otomatik_stop_kar_kontrolu(prices)
    except Exception as exc:
        errors += 1
        print(f"Otomatik stop/kâr kontrol hatası: {exc}")
        traceback.print_exc()
    print(f"Bot kontrolü tamamlandı; hata sayısı={errors}; saat={tr_zaman().isoformat()}")
    if errors:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
