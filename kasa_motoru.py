import os
import json
from datetime import datetime
import gspread

KASA_DOSYASI = "kasa_defteri.json"
GOOGLE_SHEET_ID = "1likk2RqtqxPxj7nSNDroxT6GQGrQXJmfx-SoyHswgyo"
BASLANGIC_BAKIYE = 0.0

def _sheets_baglan(sayfa_adi):
    """Google Sheets bağlantısını dener ve hatayı detaylı döndürür."""
    try:
        import streamlit as st
        import gspread
        
        client = None
        # 1. Öncelik: Streamlit Cloud Secrets
        if hasattr(st, "secrets") and "gcp_service_account" in st.secrets:
            sec = dict(st.secrets["gcp_service_account"])
            pk = str(sec.get("private_key", "")).replace("\\n", "\n").strip()
            if pk:
                sec["private_key"] = pk + "\n"
            sec["token_uri"] = "https://oauth2.googleapis.com/token"
            sec["auth_uri"] = "https://accounts.google.com/o/oauth2/auth"
            sec["universe_domain"] = "googleapis.com"
            client = gspread.service_account_from_dict(sec)
        # 2. Öncelik: Yerel credentials.json dosyası
        elif os.path.exists("credentials.json"):
            client = gspread.service_account(filename="credentials.json")
        else:
            return None, "Ne Streamlit Secrets (gcp_service_account) ne de credentials.json dosyası bulunamadı!"
            
        sh = client.open_by_key("1likk2RqtqxPxj7nSNDroxT6GQGrQXJmfx-SoyHswgyo")
        return sh.worksheet(sayfa_adi), None
    except Exception as e:
        return None, str(e)

def islem_ekle(tur, tutar, aciklama="", komisyon=0.0):
    veri = kasa_yukle()
    nakit = float(veri.get("nakit_bakiye", 0.0))
    
    net_tutar = float(tutar)
    if tur in ["Para_Yatir", "SATIM"]:
        nakit += net_tutar
    elif tur in ["Para_Cek", "ALIM", "Komisyon"]:
        nakit -= abs(net_tutar)
    elif tur == "Trade_Sonuc":
        nakit += net_tutar
        
    veri["nakit_bakiye"] = round(nakit, 2)
    
    tarih_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    yeni_hareket = {
        "tarih": tarih_str,
        "tur": tur,
        "tutar": round(float(tutar), 2),
        "komisyon": round(float(komisyon), 2),
        "aciklama": aciklama,
        "guncel_bakiye": round(nakit, 2)
    }
    
    veri["gecmis"].insert(0, yeni_hareket)
    kasa_kaydet(veri)

    # Google Sheets Senkronizasyonu ve Gerçek Hata Bildirimi
    try:
        sheet, hata_detayi = _sheets_baglan("KasaDefteri")
        if sheet is not None:
            ham = sheet.get_all_values()
            if not ham or len(ham) == 0:
                sheet.append_row(["Islem_ID", "Zaman", "Islem_Turu", "Tutar", "Aciklama"])
                ham = [["Islem_ID"]]
            idler = []
            for r in ham[1:]:
                if r and len(r) > 0 and str(r[0]).replace('.', '', 1).isdigit():
                    idler.append(int(float(r[0])))
            yeni_id = (max(idler) if idler else 0) + 1
            sheet.append_row([yeni_id, tarih_str, tur, round(float(tutar), 2), aciklama])
            return True, "İşlem başarıyla kaydedildi ve e-tabloya işlendi."
        else:
            return False, f"Yerel kayıt yapıldı ancak e-tabloya bağlanılamadı. Hata: {hata_detayi}"
    except Exception as e:
        return False, f"Yerel kayıt yapıldı, e-tablo hatası: {str(e)}"

def gecmis_getir():
    veri = kasa_yukle()
    return veri.get("gecmis", [])
