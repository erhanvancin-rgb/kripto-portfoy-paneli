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
# Sizin oluşturduğunuz Kripto Analiz Raporu Tablosunun ID'si
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
    print("     SABİT BULUT TABLOSU ENTEGRASYONLU KRİPTO ANALİZ VE OPTİMİZASYON MOTORU")
    print("=" * 115)
    print("Ana tablodan güncel veriler çekiliyor...\n")

    try:
        gcp_json_str = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
        if not gcp_json_str:
            print("[HATA] GCP_SERVICE_ACCOUNT_JSON ortam değişkeni bulunamadı!")
            return False
            
        service_account_info = json.loads(gcp_json_str)
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
                df_fiyat["Fiyat"] = pd.to_numeric(df_fiyat["Fiyat"])

                # İşlem süresince görülen Maksimum ve Minimum noktalar
                max_fiyat = df_fiyat["Fiyat"].max()
                min_fiyat = df_fiyat["Fiyat"].min()

                # Optimizasyon Hesaplamaları (Matematiksel Gerçeklik)
                if yon == "long":
                    # Long için terste kalma: Giriş - Min Fiyat
                    sl_yuzde = ((giriş_fiyatı - min_fiyat) / giriş_fiyatı) * 100
                    # Long için Kâr: Max Fiyat - Giriş
                    tp_yuzde = ((max_fiyat - giriş_fiyatı) / giriş_fiyatı) * 100
                else:
                    # Short için terste kalma: Max Fiyat - Giriş
                    sl_yuzde = ((max_fiyat - giriş_fiyatı) / giriş_fiyatı) * 100
                    # Short için Kâr: Giriş - Min Fiyat
                    tp_yuzde = ((giriş_fiyatı - min_fiyat) / giriş_fiyatı) * 100

                # Negatif kâr ihtimalini yönet (hiç kâra geçemediyse)
                if tp_yuzde < 0:
                    tp_str = "Ulasilamaz"
                else:
                    tp_str = f"{tp_yuzde:.2f}"
                
                # Sadece pozitif terste kalma değerini (zarar oranını) al
                sl_str = f"{max(0, sl_yuzde):.2f}"
                
                optimum_matris = f"67.42 ({sl_str} / {tp_str})"

                # --- 1. KISIM: REEL DURUM ---
                satir_verisi = {
                    "Reel_Durum_Islem_ID": row.get('Islem_ID', ''),
                    "Reel_Durum_Acilis_Zamani": row.get('Acilis_Zamani', ''),
                    "Reel_Durum_Coin": row.get('Coin', ''),
                    "Reel_Durum_Yon": row.get('Yon', ''),
                    "Reel_Durum_Zaman_Dilimi": row.get('Zaman_Dilimi', ''),
                    "Reel_Durum_Giris_Fiyat": row.get('Giris_Fiyat', ''),
                    "Reel_Durum_Islem_Miktari": row.get('Islem_Miktari', ''),
                    "Reel_Durum_Stop": row.get('Stop', ''),
                    "Reel_Durum_Kar_Al": row.get('Kar_Al', ''),
                    "Reel_Durum_Beklenen_Kar": row.get('Beklenen_Kar', ''),
                    "Reel_Durum_Matris_Puan_RH": row.get('Matris_Puan_RH', ''),
                    "Reel_Durum_Olasi_Stop": row.get('Olasi_Stop', ''),
                    "Reel_Durum_Durum": row.get('Durum', ''),
                    "Reel_Durum_Net_Kar_Zarar": row.get('Net_Kar_Zarar', ''),
                    "Reel_Durum_Guncel_Kasa": row.get('Guncel_Kasa', ''),
                    "Reel_Durum_Kapanis_Zamani": row.get('Kapanis_Zamani', ''),
                    "Reel_Durum_Kapanis_Fiyati": row.get('Kapanis_Fiyati', ''),
                    "Reel_Durum_Kaldirac": row.get('Kaldirac', '')
                }

                # --- 2. KISIM: OLMASI GEREKEN (OPTİMİZASYON) ---
                satir_verisi.update({
                    "Optimizasyon_Giris_Fiyat": row.get('Giris_Fiyat', ''),
                    "Optimizasyon_Islem_Miktari": row.get('Islem_Miktari', ''),
                    "Optimizasyon_Stop": "xxx",
                    "Optimizasyon_Kar_Al": "xxx",
                    "Optimizasyon_Beklenen_Kar": "xxx",
                    "Optimizasyon_Matris_Puan_RH": optimum_matris,
                    "Optimizasyon_Olasi_Stop": "xxx",
                    "Optimizasyon_Durum": "xxx",
                    "Optimizasyon_Net_Kar_Zarar": "xxx",
                    "Optimizasyon_Guncel_Kasa": row.get('Guncel_Kasa', ''),
                    "Optimizasyon_Kapanis_Zamani": "xxx",
                    "Optimizasyon_Kapanis_Fiyati": "xxx",
                    "Optimizasyon_Kaldirac": row.get('Kaldirac', '')
                })

                sonuclar.append(satir_verisi)
                print(f"[İŞLENDİ] {parite} analizi ve optimizasyon hesaplaması tamamlandı.")
                time.sleep(1.2)

            except Exception as e:
                print(f"Satır atlandı: {e}")

        if sonuclar:
            df_yeni = pd.DataFrame(sonuclar).fillna("-")
            
            # Sütun başlıklarını tabloya uygun şekilde iki satır haline getiriyoruz
            ana_basliklar = ["Reel Durum Gerçekleşen İşlemler"] * 18 + ["Olması Gereken Risk Hedef Oranları"] * 13
            alt_basliklar = [
                "Islem_ID", "Acilis_Zamani", "Coin", "Yon", "Zaman_Dilimi", "Giris_Fiyat", "Islem_Miktari", "Stop", 
                "Kar_Al", "Beklenen_Kar", "Matris_Puan_RH", "Olasi_Stop", "Durum", "Net_Kar_Zarar", "Guncel_Kasa", 
                "Kapanis_Zamani", "Kapanis_Fiyati", "Kaldirac",
                "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Beklenen_Kar", "Matris_Puan_RH", "Olasi_Stop", 
                "Durum", "Net_Kar_Zarar", "Guncel_Kasa", "Kapanis_Zamani", "Kapanis_Fiyati", "Kaldirac"
            ]
            
            veri_listesi = [ana_basliklar, alt_basliklar] + df_yeni.values.tolist()
            
            try:
                rapor_gspread = client.open_by_key(RAPOR_TABLO_ID)
                rapor_sheet = rapor_gspread.get_worksheet(0)
                
                rapor_sheet.clear()
                rapor_sheet.update(veri_listesi)
                rapor_sheet.update_title("Optimizasyon_Analizi")
                
                print(f"\n[BAŞARILI] Rapor bulutta yeni Optimizasyon kurgusuyla güncellendi!")
                return True
            except Exception as e:
                print(f"Drive rapor yazma hatası: {e}")
                return False
    except Exception as e:
        print(f"Sistem Hatası: {e}")
        return False

if __name__ == "__main__":
    tabloyu_analiz_et()
