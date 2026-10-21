import os
import json
import time
from datetime import datetime
import pytz
import requests
import pandas as pd
import gspread
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import numpy as np

TR_TZ = pytz.timezone("Europe/Istanbul")
GOOGLE_SHEET_DOSYA = "KriptoPortfoyVeritabani"
HAFIZA_DOSYASI = "sinyal_hafizasi.json"
MAIL_LOG_DOSYASI = "mail_log.txt"
KALDIRAC = 3

baz_fiyatlar = {
    "BTC/USDT": 83750.0,
    "ETH/USDT": 2511.0,
    "BNB/USDT": 745.0,
    "SOL/USDT": 107.6,
    "XRP/USDT": 1.373,
    "TOTAL": 2.77e12,
}

def tr_zaman():
    return datetime.now(TR_TZ)

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
        hata = "GMAIL_PASSWORD tanımlı değil."
        print(hata)
        mail_log_yaz(f"HATA ({konu}): {hata}")
        return False, hata

    server = None
    try:
        msg = MIMEMultipart()
        msg["From"] = gonderici_mail
        msg["To"] = alici_mail
        msg["Subject"] = konu
        msg.attach(MIMEText(icerik_html, "html", "utf-8"))

        server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15)
        server.login(gonderici_mail, uygulama_sifresi)
        server.sendmail(gonderici_mail, [alici_mail], msg.as_string())
        mail_log_yaz(f"BAŞARILI: {konu}")
        print(f"E-posta başarıyla gönderildi: {konu}")
        return True, "Başarılı"
    except Exception as e:
        hata_detayi = f"HATA ({konu}): {type(e).__name__}: {e}"
        print(hata_detayi)
        mail_log_yaz(hata_detayi)
        return False, hata_detayi
    finally:
        if server is not None:
            try:
                server.quit()
            except:
                pass

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

def fiyat_cek_binance(coin_symbol):
    if coin_symbol == "TOTAL":
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

def google_sheets_baglan(sayfa_adi):
    try:
        if "GCP_SERVICE_ACCOUNT_JSON" in os.environ:
            sec_dict = json.loads(os.environ["GCP_SERVICE_ACCOUNT_JSON"])
            if "private_key" in sec_dict:
                sec_dict["private_key"] = sec_dict["private_key"].replace(r"\n", "\n")
            client = gspread.service_account_from_dict(sec_dict)
        else:
            client = gspread.service_account(filename="credentials.json")
        return client.open(GOOGLE_SHEET_DOSYA).worksheet(sayfa_adi)
    except Exception as e:
        print(f"GSheets bağlantı hatası: {e}")
        return None

def islem_gecmisi_getir():
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
    except:
        return pd.DataFrame(columns=beklenen_kolonlar)

    if not ham_veriler or len(ham_veriler) == 0:
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
        df = df[df["Islem_ID"].notna() & (df["Islem_ID"] != "") & (df["Islem_ID"].astype(str) != "Islem_ID")]
    df["Islem_ID"] = pd.to_numeric(df["Islem_ID"], errors="coerce").fillna(0).astype(int)
    sayisal_kolonlar = [
        "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Beklenen_Kar",
        "Olasi_Stop", "Net_Kar_Zarar", "Guncel_Kasa", "Kapanis_Fiyati"
    ]
    for col in sayisal_kolonlar:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ".").str.strip(), errors="coerce").fillna(0.0).astype(float)
    return df

def dataframe_guncelle_gsheets(df):
    sheet = google_sheets_baglan("KriptoPortfoyVeritabani")
    if sheet is not None:
        try:
            df["Islem_ID"] = df["Islem_ID"].astype(int)
            df = df.sort_values(by="Islem_ID").reset_index(drop=True)
            veri_listesi = [df.columns.tolist()] + df.values.tolist()
            sheet.clear()
            sheet.update(veri_listesi)
        except Exception as e:
            print(f"GSheets Güncelleme Hatası: {e}")

def kasa_islem_ekle_deftere(islem_turu, tutar, aciklama):
    sheet = google_sheets_baglan("KasaDefteri")
    if sheet is not None:
        try:
            ham = sheet.get_all_values()
            if not ham or len(ham) == 0:
                yeni_id = 1
            else:
                yeni_id = len(ham[1:]) + 1
            suan_tr = tr_zaman().strftime("%d.%m.%Y %H:%M")
            sheet.append_row([yeni_id, suan_tr, islem_turu, round(tutar, 2), aciklama])
        except Exception as e:
            print(f"Kasa Defteri Kayıt Hatası: {e}")

def bakiye_hesapla():
    df_trade = islem_gecmisi_getir()
    baslangic = 500.0
    if not df_trade.empty:
        kap_trades = df_trade[df_trade["Durum"].astype(str).str.contains("Kapandi|Kar|Zarar|Kismi", case=False, na=False)]
        if not kap_trades.empty:
            baslangic += pd.to_numeric(kap_trades["Net_Kar_Zarar"], errors="coerce").fillna(0.0).sum()
    return baslangic

def motoru_calistir():
    print("Bağımsız Trade Kontrol Motoru Başlatıldı...")
    df = islem_gecmisi_getir()
    if df.empty or "Durum" not in df.columns:
        print("Kontrol edilecek işlem bulunamadı.")
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

                guncel_toplam_kasa = bakiye_hesapla() + net_kar
                df.at[idx, "Guncel_Kasa"] = float(round(guncel_toplam_kasa, 2))

                islem_turu_etiket = "Hedef Kâr" if hedefe_ulasti else "Otomatik Stop"
                kasa_islem_ekle_deftere("Trade_Sonuc", float(round(net_kar, 2)), f"{islem_turu_etiket}: #{islem_id} {coin}")

                hafiza = hafizayi_oku()
                islem_mail_anahtari = f"otomatik_kapanma_{islem_id}"
                if not hafiza.get(islem_mail_anahtari, False):
                    hafiza[islem_mail_anahtari] = True
                    hafizayi_kaydet(hafiza)

                    konu_mail = f"⚡ {islem_turu_etiket}: #{islem_id} {coin} ({durum_metni})"
                    icerik_mail = f"<h3>İşlem Otomatik Kapatıldı</h3><p><b>Coin:</b> {coin}</p><p><b>Yön:</b> {yon}</p><p><b>Sebep:</b> {islem_turu_etiket}</p><p><b>Net K/Z:</b> {net_kar:,.2f} $</p><p><b>Güncel Kasa:</b> {guncel_toplam_kasa:,.2f} $</p>"
                    gmail_bildirim_gonder(konu_mail, icerik_mail)

                degisiklik_oldu = True

    if degisiklik_oldu:
        dataframe_guncelle_gsheets(df)
        print("Değişiklikler Google Sheets ve veri tabanına işlendi.")
    else:
        print("Kapatılması gereken yeni bir işlem bulunamadı.")

if __name__ == "__main__":
    motoru_calistir()
