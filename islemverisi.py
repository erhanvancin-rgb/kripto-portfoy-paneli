import datetime
import time
import json
import pandas as pd
from pycoingecko import CoinGeckoAPI
import gspread
from google.oauth2.service_account import Credentials

cg = CoinGeckoAPI()

# Google Cloud Service Account Bot Kimlik Bilgileri (API Bağlantı Adresleri Onarıldı)
service_account_info = {
  "type": "service_account",
  "project_id": "western-avatar-442315-t7",
  "private_key_id": "0a61ae2ee745efae2cece2cf0bb96cd8dc8f23d9",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDWZx+lZBNeaOPJ\nYMxQtqtdygNZd3t5c1BjtY5TO7/xKpjcvdyiSAA2PVMtS5djOsHCNCAeEZBvnKRn\nnIVTVfWiBf0fcKROvFZHFBceX+TNp08/gljP+KRE7dcEM2eiRAHJiysDjgmKHWJN\nt1Z9zo560rnr2+QbfDQSih4zekOKxc9lsZXSD/RXyFl04RNbNLPYyAK1OnEa8nCe\nbvgvGCb5jLgsJJ9zmVGtKgj6/ufM2tsdrwEUQ+S7YhPNfI9bsv92dd7fAfwewr81\n7l6beQqw8puOxMLDPY9zH0QFeU+BQzfKxOHWEE31Z7ZTTq4TsD1fR4xtkqXu1XZP\nN3DXi2kfAgMBAAECggEAAaxFKXhepQ6Sx5iISbMLnBtQ5Q8UxNOEQRBkVjkVIRCb\n0FFV4ovAObmX7nMtzzkJTcrVsstq0RkvKwJTVKDR0Mme9vKTHF84DEgJ9HUI/Q9I\n76W3Cm1w+rEhPkRpQfgi7fXECF3OGDKi6zOwtKh+DPUv+ZCihEfBFVCU5W4keuFX\nHkAE032KARszmqz/tAbD30Ych9IpsE7aYil5peFobQsMhQ8q0lc8bm3gFwOMpr8D\nR+sTX6BPxfLp3NY1lSiBzh8rPbvHSVPoUq+8hweesFAVnDXAuv7gPleLGT47EBrU\nivpQ8ARjOYVeoCXLGqauhw0GIQAAv9DBdMlef7kRYQKBgQD1nF8XGw6Ofc2IPABB\nG2dRZ3b/XkHL7xZEj4Gk66xi1iifACH6LQRohWRQ3Gy+0oEaS2vtAN1G+bBg3QLc\npSqRiwptfWgfhkXTrDr2FkMEK+d6MSB1sjr6cBoR1vxUfBcerWUHGDO1N2caLhzc\nqLozkd1YflIuKXf8bph4qIYzVQKBgQDfeM/0KGI+X/aP4xo6mic69BCcPxGa+dff\nkrTYEKwqgz7ZkNFGnY4K5AJS6xvdoccVxsD0yqBbLQJrSqfp8IHIFbjAZVvoKX2s\nsI+m5f5cV+rCrkUv6174oYhtVcRIr2INJLDWulpJ5rPqbjutkom8hmTDoEyONIoN\nmrN1DgnSowKBgEx4nG7AQN8CslypedbLnaFBVrrSQcq8L72A4KK0kiPr2QaEXoo\nTAgTCDHY/47GUeYS9456R2sS0OTHy11Rm5hnNx7x/dpa3yDRriXytnj1BoRYCWg7\nzvssriFB05ymajhl+l+kHG1ey54uH1RgwGDQGJ+17PZseOxCrvxaVDZlAoGBAKoG\nmnoS68S3cLpDOSaTOPvyzFyE49k89JFZtZELBmMGHqCcPY3zvCnvFxGNjlMPjpCz\n+wWE0YLteOS3FZC5i5T3ae0AcW/veY4VfAapAOGzhot+2mc+NrEG/ezqD4CZ6AlF\n/EIz4RRPMl5QZpmGX8OPoUTyRqz/rnXxWU7bUn/vAoGAX96LjM+E8GoUHFBjxU9H\nlTXTYxR1Y6rzOQlKs0Vp3Vc0+LLzV7Eedg1kc5bVoVes9Et3zHEn48Gsv/R/qO+2\nLThEQZGyDrRhDdUcG1Wb0bqpSOz26vaN1Z5w+MP6iZQNslUG4ZfCQvInnbpTYVvo\n+UHxldGSsWzkpMuWR3r6WSE=\n-----END PRIVATE KEY-----\n",
  "client_email": "kripto-bot@://gserviceaccount.com",
  "client_id": "116674981434745196964",
  "auth_uri": "https://google.com",
  "token_uri": "https://googleapis.com",
  "auth_provider_x509_cert_url": "https://googleapis.com",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/kripto-bot%40://gserviceaccount.com",
  "universe_domain": "googleapis.com"
}

ANA_TABLO_ID = "1likk2RqtqxPxj7nSNDroxT6GQGrQXJmfx-SoyHswgyo"
RAPOR_TABLO_ADI = "Kripto_Analiz_Raporu"

symbols = {
    "BTC/USDT": "bitcoin",
    "ETH/USDT": "ethereum",
    "BNB/USDT": "binancecoin",
    "XRP/USDT": "ripple",
    "SOL/USDT": "solana"
}

def tabloyu_analiz_et():
    print("=" * 115)
    print("     SABİT BULUT TABLOSU ENTEGRASYONLU KRİPTO ANALİZ MOTORU")
    print("=" * 115)
    print("Ana tablodan güncel veriler çekiliyor...\n")

    try:
        # Doğru ve standart Google oAuth API kapsamları tanımlandı
        scopes = [
            "https://googleapis.com",
            "https://googleapis.com"
        ]
        creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
        client = gspread.authorize(creds)
        
        ana_sheet = client.open_by_key(ANA_TABLO_ID).worksheet("KriptoPortfoyVeritabani")
        records = ana_sheet.get_all_records()
        
        if not records:
            print("[HATA] Veritabanında işlenecek veri bulunamadı!")
            return False

        sonuclar = []

        for index, row in enumerate(records):
            try:
                parite = str(row.get('Coin', '')).strip()
                yon = str(row.get('Yon', '')).lower().strip()
                giriş_fiyatı = float(row.get('Giris_Fiyat', 0))
                tp_fiyatı = float(row.get('Kar_Al', 0))
                sl_fiyatı = float(row.get('Stop', 0))
                giriş_dt_ham = str(row.get('Acilis_Zamani', '')).strip()

                if not giriş_dt_ham or parite == "" or parite == "nan":
                    continue

                if ".2026" in giriş_dt_ham or ".202" in giriş_dt_ham:
                    if len(giriş_dt_ham) > 16: giriş_dt_ham = giriş_dt_ham[:16]
                    giriş_dt = datetime.datetime.strptime(giriş_dt_ham, "%d.%m.%Y %H:%M")
                else:
                    if len(giriş_dt_ham) > 16: giriş_dt_ham = giriş_dt_ham[:16]
                    giriş_dt = datetime.datetime.strptime(giriş_dt_ham, "%Y-%m-%d %H:%M")

                start_timestamp = int(time.mktime(giriş_dt.timetuple()))
                end_timestamp = int(time.time())
                
                coin_id = symbols.get(parite)
                if not coin_id:
                    continue

                data = cg.get_coin_market_chart_range_by_id(
                    id=coin_id, vs_currency="usd", from_timestamp=start_timestamp, to_timestamp=end_timestamp
                )
                prices = data.get("prices", [])

                if not prices:
                    continue

                df_fiyat = pd.DataFrame(prices, columns=["Zaman_Ms", "Fiyat"])
                df_fiyat["Zaman"] = pd.to_datetime(df_fiyat["Zaman_Ms"], unit="ms") + pd.Timedelta(hours=3)
                df_fiyat["Fiyat"] = pd.to_numeric(df_fiyat["Fiyat"])

                if yon == "long":
                    en_iyi = df_fiyat.loc[df_fiyat["Fiyat"].idxmax()]
                    en_kötü = df_fiyat.loc[df_fiyat["Fiyat"].idxmin()]
                    durum = "Kapandı (Kar)" if df_fiyat["Fiyat"].max() >= tp_fiyatı else ("Kapandı (Zarar)" if df_fiyat["Fiyat"].min() <= sl_fiyatı else "Açık")
                else:
                    en_iyi = df_fiyat.loc[df_fiyat["Fiyat"].idxmin()]
                    en_kötü = df_fiyat.loc[df_fiyat["Fiyat"].idxmax()]
                    durum = "Kapandı (Kar)" if df_fiyat["Fiyat"].min() <= tp_fiyatı else ("Kapandı (Zarar)" if df_fiyat["Fiyat"].max() >= sl_fiyatı else "Açık")

                yeni_satir = dict(row)
                yeni_satir.update({
                    "Reel_Durum": durum,
                    "Max_Kar_Zamani": en_iyi["Zaman"].strftime("%d.%m.%Y %H:%M"),
                    "Max_Kar_Fiyati": round(en_iyi["Fiyat"], 4),
                    "Max_Terste_Zamani": en_kötü["Zaman"].strftime("%d.%m.%Y %H:%M"),
                    "Max_Terste_Fiyati": round(en_kötü["Fiyat"], 4)
                })
                sonuclar.append(yeni_satir)
                print(f"[İŞLENDİ] {parite} analizi tamamlandı.")
                time.sleep(1.2)

            except Exception as e:
                print(f"Satır atlandı: {e}")

        # Raporlama ve Drive üzerine geri basma aşaması
        if sonuclar:
            df_yeni = pd.DataFrame(sonuclar).fillna("-")
            veri_listesi = [df_yeni.columns.values.tolist()] + df_yeni.values.tolist()
            
            try:
                try:
                    rapor_gspread = client.open(RAPOR_TABLO_ADI)
                    rapor_sheet = rapor_gspread.get_worksheet(0)
                    rapor_sheet.clear()
                    print(f"Mevcut '{RAPOR_TABLO_ADI}' bulundu, eski veriler temizleniyor...")
                except gspread.exceptions.SpreadsheetNotFound:
                    print(f"'{RAPOR_TABLO_ADI}' bulunamadı, sıfırdan oluşturuluyor...")
                    rapor_gspread = client.create(RAPOR_TABLO_ADI)
                    rapor_gspread.share("erhanvancin@gmail.com", perm_type="user", role="writer")
                    rapor_sheet = rapor_gspread.get_worksheet(0)
                    rapor_sheet.update_title("Analiz_Sonuclari")

                rapor_sheet.update(veri_listesi)
                print(f"\n[BAŞARILI] Rapor bulutta güncellendi! Tablo Adı: {RAPOR_TABLO_ADI}")
                return True

            except Exception as e:
                print(f"Drive rapor yazma hatası: {e}")
                return False
    except Exception as e:
        print(f"Sistem Hatası: {e}")
        return False

if __name__ == "__main__":
    tabloyu_analiz_et()
