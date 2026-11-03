import datetime
import time
import json
import os
import pytz
import pandas as pd
from pycoingecko import CoinGeckoAPI
import gspread
from google.oauth2.service_account import Credentials

cg = CoinGeckoAPI()

ANA_TABLO_ID = "1likk2RqtqxPxj7nSNDroxT6GQGrQXJmfx-SoyHswgyo"
RAPOR_TABLO_ID = "1BCTDr3SXSZDHgYjVZObAsALQdem5BCIaKMzb157ntsY"

symbols = {
    "BTC/USDT": "bitcoin",
    "ETH/USDT": "ethereum",
    "BNB/USDT": "binancecoin",
    "XRP/USDT": "ripple",
    "SOL/USDT": "solana"
}

def tr_float(val):
    v = str(val).strip()
    if not v or v == "-" or v == "nan": return 0.0
    if '.' in v and ',' in v:
        v = v.replace('.', '').replace(',', '.')
    elif ',' in v:
        v = v.replace(',', '.')
    try:
        return float(v)
    except:
        return 0.0

def format_tr_number(val, is_price=False, is_percent=False):
    try:
        if pd.isna(val) or str(val).strip() == "" or str(val) == "-" or str(val) == "nan":
            return "-"
        f_val = float(val)
        
        if f_val == 0.0:
            if is_percent or is_price: return "0,00"
            return "0"
            
        if is_price:
            s = f"{f_val:,.4f}" if abs(f_val) < 10 else f"{f_val:,.2f}"
        else:
            if is_percent:
                s = f"{f_val:,.2f}"
            else:
                s = f"{int(f_val):,}" if f_val.is_integer() else f"{f_val:,.2f}"
            
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(val)

def tabloyu_analiz_et():
    print("=" * 115)
    print("     SABİT BULUT TABLOSU ENTEGRASYONLU KRİPTO ANALİZ VE OPTİMİZASYON MOTORU")
    print("=" * 115)
    print("Ana tablodan güncel veriler çekiliyor...\n")

    try:
        gcp_json_str = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
        if not gcp_json_str:
            print("[HATA] GCP_SERVICE_ACCOUNT_JSON bulunamadı!")
            return False
            
        service_account_info = json.loads(gcp_json_str)
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        
        creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
        client = gspread.authorize(creds)
        
        ana_sheet = client.open_by_key(ANA_TABLO_ID).worksheet("KriptoPortfoyVeritabani")
        raw_data = ana_sheet.get_all_values()
        
        if len(raw_data) < 2:
            print("[HATA] Veri bulunamadı!")
            return False

        headers = raw_data[0]
        records = [dict(zip(headers, row)) for row in raw_data[1:]]

        sonuclar = []
        tr_tz = pytz.timezone("Europe/Istanbul")

        for index, row in enumerate(records):
            try:
                parite = str(row.get('Coin', '')).strip()
                yon = str(row.get('Yon', '')).lower().strip()
                giriş_fiyatı = tr_float(row.get('Giris_Fiyat', '0'))
                giriş_dt_ham = str(row.get('Acilis_Zamani', '')).strip()
                
                tp_fiyatı = tr_float(row.get('Kar_Al', '0'))
                sl_fiyatı = tr_float(row.get('Stop', '0'))
                beklenen_kar = tr_float(row.get('Beklenen_Kar', '0'))
                olasi_stop = tr_float(row.get('Olasi_Stop', '0'))
                net_kar = tr_float(row.get('Net_Kar_Zarar', '0'))
                kasa = tr_float(row.get('Guncel_Kasa', '0'))
                miktar = tr_float(row.get('Islem_Miktari', '0'))
                orijinal_durum = str(row.get('Durum', '')).lower()

                if not giriş_dt_ham or parite == "" or parite == "nan" or giriş_fiyatı == 0:
                    continue

                # Kâr ve Zararla kapandığını anla
                islem_karda_mi = "kar" in orijinal_durum

                # 1. AÇILIŞ ZAMANI
                if ".2026" in giriş_dt_ham or ".202" in giriş_dt_ham:
                    giriş_dt = datetime.datetime.strptime(giriş_dt_ham[:16], "%d.%m.%Y %H:%M")
                else:
                    giriş_dt = datetime.datetime.strptime(giriş_dt_ham[:16], "%Y-%m-%d %H:%M")

                giriş_dt_aware = tr_tz.localize(giriş_dt)
                start_timestamp = int(giriş_dt_aware.timestamp())
                
                # 2. KAPANIŞ ZAMANI
                kapanis_dt_ham = str(row.get('Kapanis_Zamani', '')).strip()
                if kapanis_dt_ham and kapanis_dt_ham not in ["-", "nan", "xxx", ""]:
                    try:
                        if ".2026" in kapanis_dt_ham or ".202" in kapanis_dt_ham:
                            kapanis_dt = datetime.datetime.strptime(kapanis_dt_ham[:16], "%d.%m.%Y %H:%M")
                        else:
                            kapanis_dt = datetime.datetime.strptime(kapanis_dt_ham[:16], "%Y-%m-%d %H:%M")
                        kapanis_dt_aware = tr_tz.localize(kapanis_dt)
                        end_timestamp = int(kapanis_dt_aware.timestamp())
                    except:
                        end_timestamp = int(time.time())
                else:
                    end_timestamp = int(time.time())
                
                if end_timestamp <= start_timestamp:
                    end_timestamp = start_timestamp + 3600
                elif end_timestamp - start_timestamp < 3600:
                    end_timestamp = start_timestamp + 3600
                
                coin_id = symbols.get(parite)
                if not coin_id: continue

                data = cg.get_coin_market_chart_range_by_id(id=coin_id, vs_currency="usd", from_timestamp=start_timestamp, to_timestamp=end_timestamp)
                prices = data.get("prices", [])
                if not prices: continue

                df_fiyat = pd.DataFrame(prices, columns=["Zaman_Ms", "Fiyat"])
                df_fiyat["Fiyat"] = pd.to_numeric(df_fiyat["Fiyat"])

                if yon == "long":
                    en_iyi = df_fiyat.loc[df_fiyat["Fiyat"].idxmax()]
                    en_kotu = df_fiyat.loc[df_fiyat["Fiyat"].idxmin()]
                else:
                    en_iyi = df_fiyat.loc[df_fiyat["Fiyat"].idxmin()]
                    en_kotu = df_fiyat.loc[df_fiyat["Fiyat"].idxmax()]

                max_fiyat = en_iyi["Fiyat"]
                min_fiyat = en_kotu["Fiyat"]

                # Orijinal hesaplanan yüzdeler (strateji kontrolü için)
                orj_tp_yuzde = abs(tp_fiyatı - giriş_fiyatı) / giriş_fiyatı * 100
                
                # Gerçekleşen (Piyasa) yüzdeleri
                if yon == "long":
                    piyasa_sl_yuzde = ((giriş_fiyatı - min_fiyat) / giriş_fiyatı) * 100
                    piyasa_tp_yuzde = ((max_fiyat - giriş_fiyatı) / giriş_fiyatı) * 100
                else:
                    piyasa_sl_yuzde = ((max_fiyat - giriş_fiyatı) / giriş_fiyatı) * 100
                    piyasa_tp_yuzde = ((giriş_fiyatı - min_fiyat) / giriş_fiyatı) * 100

                # === MANTIKSAL KURGU UYGULANIYOR ===
                if islem_karda_mi:
                    # İşlem KÂRLA KAPANDIYSA: Karı aynı bırak, sadece maksimum terste kalmayı hesapla
                    opt_kar_al = tp_fiyatı
                    opt_stop = min_fiyat
                    opt_tp_yuzde = orj_tp_yuzde
                    opt_sl_yuzde = piyasa_sl_yuzde
                    opt_durum = "Kapandı (Kar)"
                    opt_beklenen_kar = beklenen_kar
                    opt_olasi_stop = 0 # Kar ile kapandıysa zarar 0'dır.
                else:
                    # İşlem ZARARLA KAPANDIYSA: Gördüğü maksimum karı hesapla
                    opt_kar_al = max_fiyat
                    opt_stop = sl_fiyatı
                    opt_tp_yuzde = piyasa_tp_yuzde
                    opt_sl_yuzde = abs(sl_fiyatı - giriş_fiyatı) / giriş_fiyatı * 100 # Stop olduğu yer
                    
                    # Eğer stoplamadan önce 1:1 kâr fırsatı verdiyse, "Kâra kapatabilirdin" statüsü
                    if opt_tp_yuzde > opt_sl_yuzde and opt_tp_yuzde > 0:
                        opt_durum = "Kapandı (Kar)" # Optimizasyonda kâra döndü
                        opt_beklenen_kar = beklenen_kar * (opt_tp_yuzde / opt_sl_yuzde) if opt_sl_yuzde > 0 else beklenen_kar
                        opt_olasi_stop = 0
                    else:
                        opt_durum = "Kapandı (Zarar)"
                        opt_beklenen_kar = 0
                        opt_olasi_stop = olasi_stop

                islem_oncesi_kasa = kasa - net_kar
                opt_kasa = islem_oncesi_kasa + (opt_beklenen_kar if opt_durum == "Kapandı (Kar)" else opt_olasi_stop)

                # MATRİS FORMATLAMA
                sl_str = format_tr_number(max(0, opt_sl_yuzde), is_percent=True)
                
                if not islem_karda_mi and opt_tp_yuzde <= 0:
                    tp_str = "Ulasilamaz"
                else:
                    tp_str = format_tr_number(opt_tp_yuzde, is_percent=True)
                
                matris_ham = str(row.get('Matris_Puan_RH', '')).strip()
                base_puan = matris_ham.split(' ')[0] if matris_ham else "0,00"
                optimum_matris = f"{base_puan} ({sl_str} / {tp_str})"

                satir_verisi = {
                    "Reel_Durum_Islem_ID": row.get('Islem_ID', ''),
                    "Reel_Durum_Acilis_Zamani": row.get('Acilis_Zamani', ''),
                    "Reel_Durum_Coin": row.get('Coin', ''),
                    "Reel_Durum_Yon": row.get('Yon', ''),
                    "Reel_Durum_Zaman_Dilimi": row.get('Zaman_Dilimi', ''),
                    "Reel_Durum_Giris_Fiyat": format_tr_number(giriş_fiyatı, is_price=True),
                    "Reel_Durum_Islem_Miktari": format_tr_number(miktar),
                    "Reel_Durum_Stop": format_tr_number(sl_fiyatı, is_price=True),
                    "Reel_Durum_Kar_Al": format_tr_number(tp_fiyatı, is_price=True),
                    "Reel_Durum_Beklenen_Kar": format_tr_number(beklenen_kar),
                    "Reel_Durum_Matris_Puan_RH": row.get('Matris_Puan_RH', ''),
                    "Reel_Durum_Olasi_Stop": format_tr_number(olasi_stop),
                    "Reel_Durum_Durum": row.get('Durum', ''),
                    "Reel_Durum_Net_Kar_Zarar": format_tr_number(net_kar),
                    "Reel_Durum_Guncel_Kasa": format_tr_number(kasa),
                    "Reel_Durum_Kapanis_Zamani": row.get('Kapanis_Zamani', ''),
                    "Reel_Durum_Kapanis_Fiyati": format_tr_number(tr_float(row.get('Kapanis_Fiyati', '0')), is_price=True),
                    "Reel_Durum_Kaldirac": row.get('Kaldirac', ''),
                    
                    "Optimizasyon_Giris_Fiyat": format_tr_number(giriş_fiyatı, is_price=True),
                    "Optimizasyon_Islem_Miktari": format_tr_number(miktar),
                    "Optimizasyon_Stop": format_tr_number(opt_stop, is_price=True) if opt_durum == "Kapandı (Kar)" else format_tr_number(sl_fiyatı, is_price=True),
                    "Optimizasyon_Kar_Al": format_tr_number(opt_kar_al, is_price=True) if opt_durum == "Kapandı (Kar)" else "-",
                    "Optimizasyon_Beklenen_Kar": format_tr_number(opt_beklenen_kar) if opt_durum == "Kapandı (Kar)" else "-",
                    "Optimizasyon_Matris_Puan_RH": optimum_matris,
                    "Optimizasyon_Olasi_Stop": format_tr_number(opt_olasi_stop),
                    "Optimizasyon_Durum": opt_durum,
                    "Optimizasyon_Net_Kar_Zarar": format_tr_number(opt_beklenen_kar if opt_durum == "Kapandı (Kar)" else opt_olasi_stop),
                    "Optimizasyon_Guncel_Kasa": format_tr_number(opt_kasa),
                    "Optimizasyon_Kapanis_Zamani": en_iyi["Zaman"].strftime("%d.%m.%Y %H:%M") if opt_durum == "Kapandı (Kar)" else row.get('Kapanis_Zamani', ''),
                    "Optimizasyon_Kapanis_Fiyati": format_tr_number(opt_kar_al, is_price=True) if opt_durum == "Kapandı (Kar)" else format_tr_number(sl_fiyatı, is_price=True),
                    "Optimizasyon_Kaldirac": row.get('Kaldirac', '')
                }

                sonuclar.append(satir_verisi)
                print(f"[İŞLENDİ] {parite} Win/Loss kurgusuyla tamamlandı.")
                time.sleep(1.2)

            except Exception as e:
                print(f"Satır atlandı: {e}")

        if sonuclar:
            df_yeni = pd.DataFrame(sonuclar).fillna("-")
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
                print(f"\n[BAŞARILI] Rapor bulutta mantıksal Win/Loss formatıyla güncellendi!")
                return True
            except Exception as e:
                print(f"Drive rapor yazma hatası: {e}")
                return False
    except Exception as e:
        print(f"Sistem Hatası: {e}")
        return False

if __name__ == "__main__":
    tabloyu_analiz_et()
