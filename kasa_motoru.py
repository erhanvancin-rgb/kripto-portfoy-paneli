import os
import json
from datetime import datetime
import gspread

KASA_DOSYASI = "kasa_defteri.json"
GOOGLE_SHEET_DOSYA = "KriptoPortfoyVeritabani"

def _sheets_baglan(sayfa_adi):
    """Google Sheets'e bağlanarak ilgili sayfayı döndürür."""
    try:
        import streamlit as st
        if "gcp_service_account" in st.secrets:
            sec = dict(st.secrets["gcp_service_account"])
            pk = str(sec.get("private_key", "")).replace("\\n", "\n").strip()
            if pk:
                sec["private_key"] = pk + "\n"
            sec["token_uri"] = "https://oauth2.googleapis.com/token"
            sec["auth_uri"] = "https://accounts.google.com/o/oauth2/auth"
            sec["universe_domain"] = "googleapis.com"
            client = gspread.service_account_from_dict(sec)
            return client.open(GOOGLE_SHEET_DOSYA).worksheet(sayfa_adi)
    except Exception as e:
        print(f"Google Sheets bağlantı hatası ({sayfa_adi}): {e}")
    
    try:
        if os.path.exists("credentials.json"):
            client = gspread.service_account(filename="credentials.json")
            return client.open(GOOGLE_SHEET_DOSYA).worksheet(sayfa_adi)
    except Exception as e:
        print(f"credentials.json bağlantı hatası ({sayfa_adi}): {e}")
        
    return None

def kasa_yukle():
    """Kasa defterini yerel JSON dosyasından okur. Dosya yoksa başlangıç bakiyesi oluşturur."""
    if not os.path.exists(KASA_DOSYASI):
        varsayilan = {
            "nakit_bakiye": 0.0,
            "gecmis": []
        }
        kasa_kaydet(varsayilan)
        return varsayilan
    
    try:
        with open(KASA_DOSYASI, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"nakit_bakiye": 0.0, "gecmis": []}

def kasa_kaydet(veri):
    """Kasa verilerini yerel JSON dosyasına yazar."""
    with open(KASA_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=4)

def bakiye_getir():
    """Güncel nakit bakiyeyi döndürür."""
    veri = kasa_yukle()
    return float(veri.get("nakit_bakiye", 0.0))

def islem_ekle(tur, tutar, aciklama="", komisyon=0.0):
    """
    Kasaya para ekleme, çekme veya trade hareketlerini kaydeder ve Google E-Tablo'ya senkronize eder.
    """
    veri = kasa_yukle()
    nakit = float(veri.get("nakit_bakiye", 0.0))
    
    net_tutar = float(tutar) - float(komisyon)
    
    if tur in ["EKLE", "SATIM"]:
        nakit += net_tutar
    elif tur in ["CEK", "ALIM"]:
        nakit -= float(tutar)
        
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

    # --- GOOGLE E-TABLO SENKRONİZASYONU (KasaDefteri) ---
    try:
        sheet = _sheets_baglan("KasaDefteri")
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
            
            islem_turu_sheet = "Para_Yatir" if tur in ["EKLE", "SATIM"] else "Para_Cek"
            sheet.append_row([yeni_id, tarih_str, islem_turu_sheet, round(float(tutar), 2), aciklama])
        else:
            print("Google Sheets 'KasaDefteri' sayfasına bağlanılamadı.")
    except Exception as e:
        print(f"E-Tablo Kasa Defteri senkronizasyon kritik hatası: {e}")

    return veri["nakit_bakiye"]

def gecmis_getir():
    """Tüm kasa hareket geçmişini döndürür."""
    veri = kasa_yukle()
    return veri.get("gecmis", [])
