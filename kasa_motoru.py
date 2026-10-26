import os
import json
from datetime import datetime

KASA_DOSYASI = "kasa_defteri.json"

def kasa_yukle():
    """Kasa defterini yerel JSON dosyasından okur. Dosya yoksa başlangıç bakiyesi oluşturur."""
    if not os.path.exists(KASA_DOSYASI):
        varsayilan = {
            "nakit_bakiye": 1000.0,  # Başlangıç nakit sermayesi
            "gecmis": []
        }
        kasa_kaydet(varsayilan)
        return varsayilan
    
    try:
        with open(KASA_DOSYASI, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"nakit_bakiye": 1000.0, "gecmis": []}

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
    Kasaya para ekleme, çekme veya trade (alım/satım/komisyon) hareketlerini kaydeder.
    tur: 'EKLE', 'CEK', 'ALIM', 'SATIM'
    """
    veri = kasa_yukle()
    nakit = float(veri.get("nakit_bakiye", 0.0))
    
    net_tutar = float(tutar) - float(komisyon)
    
    if tur in ["EKLE", "SATIM"]:
        nakit += net_tutar
    elif tur in ["CEK", "ALIM"]:
        nakit -= float(tutar)
        
    veri["nakit_bakiye"] = round(nakit, 2)
    
    yeni_hareket = {
        "tarih": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tur": tur,
        "tutar": round(float(tutar), 2),
        "komisyon": round(float(komisyon), 2),
        "aciklama": aciklama,
        "guncel_bakiye": round(nakit, 2)
    }
    
    veri["gecmis"].insert(0, yeni_hareket)
    kasa_kaydet(veri)
    return veri["nakit_bakiye"]

def gecmis_getir():
    """Tüm kasa hareket geçmişini döndürür."""
    veri = kasa_yukle()
    return veri.get("gecmis", [])
