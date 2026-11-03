import datetime
import time
import json
import os
import pandas as pd
from pycoingecko import CoinGeckoAPI
import gspread
from google.oauth2.service_account import Credentials

cg = CoinGeckoAPI()

ANA_TABLO_ID = "1likk2RqtqxPxj7nSNDroxT6GQGrQXJmfx-SoyHswgyo"
# Yeni oluşturduğunuz rapor tablosunun ID'si eklendi
RAPOR_TABLO_ID = "1BCTDr3SXSZDHgYjVZObAsALQdem5BCIaKMzb157ntsY"

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
        # 1. GitHub Secrets üzerinden gelen JSON verisini okuma
        gcp_json_str = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
        if not gcp_json_str:
            print("[HATA] GCP_SERVICE_ACCOUNT_JSON ortam değişkeni bulunamadı!")
            return False
            
        service_account_info = json.loads(gcp_json_str)

        # 2. Hatalı olan scopes tanımlarını standart gspread yetkileriyle değiştirme
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
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

        if sonuclar:
            df_yeni = pd.DataFrame(sonuclar).fillna("-")
            veri_listesi = [df_yeni.columns.values.tolist()] + df_yeni.values.tolist()
            
            try:
                # 3. Create mantığı kaldırıldı, tabloyu doğrudan yeni ID ile açıyoruz
                rapor_gspread = client.open_by_key(RAPOR_TABLO_ID)
                rapor_sheet = rapor_gspread.get_worksheet(0)
                
                rapor_sheet.clear()
                rapor_sheet.update(veri_listesi)
                rapor_sheet.update_title("Analiz_Sonuclari")
                
                print(f"\n[BAŞARILI] Rapor bulutta güncellendi!")
                return True
            except Exception as e:
                print(f"Drive rapor yazma hatası: {e}")
                return False
    except Exception as e:
        print(f"Sistem Hatası: {e}")
        return False

if __name__ == "__main__":
    tabloyu_analiz_et()
