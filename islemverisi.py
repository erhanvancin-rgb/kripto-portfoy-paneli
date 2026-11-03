import datetime
import time
import os
import pandas as pd
from pycoingecko import CoinGeckoAPI

cg = CoinGeckoAPI()

# Bilgisayarınızda hatasız çalışması için yerel dosyayı hedef alıyoruz
excel_adi = "TPSL Oranlari.xlsx"

symbols = {
    "BTC/USDT": "bitcoin",
    "ETH/USDT": "ethereum",
    "BNB/USDT": "binancecoin",
    "XRP/USDT": "ripple",
    "SOL/USDT": "solana"
}

print("=" * 115)
print("     YEREL DOSYA BAĞLANTILI KRİPTO İŞLEM ANALİZ MOTORU")
print("=" * 115)

if not os.path.exists(excel_adi):
    print(f"[HATA] Klasörde '{excel_adi}' adında bir dosya bulunamadı!")
    exit()

print(f"Klasördeki '{excel_adi}' dosyası okunuyor...\n")

try:
    df_original = pd.read_excel(excel_adi, sheet_name="KriptoPortfoyVeritabani")
    ek_veriler = []

    for index, row in df_original.iterrows():
        try:
            parite = str(row['Coin']).strip()
            yon = str(row['Yon']).lower().strip()
            giriş_fiyatı = float(row['Giris_Fiyat'])
            tp_fiyatı = float(row['Kar_Al'])
            sl_fiyatı = float(row['Stop'])
            
            giriş_dt_ham = str(row['Acilis_Zamani']).strip()
            if not giriş_dt_ham or parite == "nan":
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
                ek_veriler.append({"Reel_Durum": "Bilinmeyen Parite", "Max_Kar_Zamani": "-", "Max_Kar_Fiyati": "-", "Max_Terste_Zamani": "-", "Max_Terste_Fiyati": "-"})
                continue

            # CoinGecko internet bağlantısı kontrolü
            try:
                data = cg.get_coin_market_chart_range_by_id(
                    id=coin_id, vs_currency="usd", from_timestamp=start_timestamp, to_timestamp=end_timestamp
                )
                prices = data.get("prices", [])
            except Exception:
                prices = []

            if not prices:
                ek_veriler.append({"Reel_Durum": "Fiyat Alınamadı", "Max_Kar_Zamani": "-", "Max_Kar_Fiyati": "-", "Max_Terste_Zamani": "-", "Max_Terste_Fiyati": "-"})
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

            ek_veriler.append({
                "Reel_Durum": durum,
                "Max_Kar_Zamani": en_iyi["Zaman"].strftime("%d.%m.%Y %H:%M"),
                "Max_Kar_Fiyati": round(en_iyi["Fiyat"], 4),
                "Max_Terste_Zamani": en_kötü["Zaman"].strftime("%d.%m.%Y %H:%M"),
                "Max_Terste_Fiyati": round(en_kötü["Fiyat"], 4)
            })
            print(f"[BAŞARILI] Satır {index+2} ({parite}) işlendi.")
            time.sleep(1)

        except Exception as row_err:
            ek_veriler.append({"Reel_Durum": "Hata", "Max_Kar_Zamani": "-", "Max_Kar_Fiyati": "-", "Max_Terste_Zamani": "-", "Max_Terste_Fiyati": "-"})

    df_ek = pd.DataFrame(ek_veriler)
    df_final = pd.concat([df_original, df_ek], axis=1)
    df_final.to_excel("islem_analiz_raporu.xlsx", index=False)
    
    print("\n[TAMAMLANDI] Bilgisayarınızdaki yerel veriler başarıyla işlendi ve 'islem_analiz_raporu.xlsx' dosyası oluşturuldu!")

except Exception as e:
    print(f"Genel Okuma Hatası: {e}")
