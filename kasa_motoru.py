import os
from datetime import datetime
import gspread

GOOGLE_SHEET_ID = "1likk2RqtqxPxj7nSNDroxT6GQGrQXJmfx-SoyHswgyo"

def _sheets_baglan(sayfa_adi):
    """Google Sheets bağlantısını yerel credentials.py üzerinden kurar."""
    try:
        import gspread
        
        # Doğrudan proje içindeki gizli py dosyasından alıyoruz
        try:
            from credentials import GCP_SECRETS
            sec = dict(GCP_SECRETS)
        except ImportError:
            import streamlit as st
            sec = dict(st.secrets["gcp_service_account"])
            
        pk = str(sec.get("private_key", "")).replace("\\n", "\n").replace("\r", "")
        sec["private_key"] = pk
        
        sec["token_uri"] = "https://oauth2.googleapis.com/token"
        sec["auth_uri"] = "https://accounts.google.com/o/oauth2/auth"
        sec["universe_domain"] = "googleapis.com"
        
        client = gspread.service_account_from_dict(sec)
        sh = client.open_by_key(GOOGLE_SHEET_ID)
        return sh.worksheet(sayfa_adi), None
    except Exception as e:
        return None, str(e)

def _verileri_tablodan_oku():
    """
    Tüm geçmişi ve güncel bakiyeyi SADECE E-Tablodan okur.
    Böylece e-tabloda elle yapılan her düzeltme panele anında yansır.
    """
    sheet, hata = _sheets_baglan("KasaDefteri")
    if sheet is None:
        print(f"E-Tablo okuma hatası: {hata}")
        return 0.0, []
        
    try:
        satirlar = sheet.get_all_values()
        if not satirlar or len(satirlar) <= 1:
            return 0.0, [] # Sadece başlık varsa bakiye 0
            
        veri_satirlari = satirlar[1:]
        gecmis = []
        bakiye = 0.0
        
        # Satırları baştan sona okuyup güncel bakiyeyi dinamik hesaplıyoruz
        for row in veri_satirlari:
            if len(row) < 4: continue
            
            islem_id = row[0]
            zaman = row[1]
            tur = row[2]
            
            try:
                # E-tablodaki virgülleri noktaya çevirip sayıya dönüştürüyoruz
                tutar = float(str(row[3]).replace(',', '.'))
            except ValueError:
                tutar = 0.0
                
            aciklama = row[4] if len(row) > 4 else ""
            
            # İşlem türüne göre bakiyeye etki
            if tur in ["Para_Yatir", "SATIM"]:
                bakiye += tutar
            elif tur in ["Para_Cek", "ALIM", "Komisyon"]:
                bakiye -= abs(tutar)
            elif tur == "Trade_Sonuc":
                bakiye += tutar # Kâr artı, zarar zaten eksi olarak gelir
                
            gecmis.append({
                "id": islem_id,
                "tarih": zaman,
                "tur": tur,
                "tutar": round(tutar, 2),
                "aciklama": aciklama,
                "guncel_bakiye": round(bakiye, 2)
            })
            
        # Panelin en son işlemi en üstte göstermesi için listeyi ters çeviriyoruz
        gecmis.reverse()
        return round(bakiye, 2), gecmis
        
    except Exception as e:
        print(f"E-tablo verisi işlenirken hata: {e}")
        return 0.0, []

def bakiye_getir():
    bakiye, _ = _verileri_tablodan_oku()
    return bakiye

def gecmis_getir():
    _, gecmis = _verileri_tablodan_oku()
    return gecmis

def islem_ekle(tur, tutar, aciklama="", komisyon=0.0):
    """
    Yerel dosyayı tamamen devre dışı bırakır ve
    yeni işlemi DOĞRUDAN Google E-Tabloya yazar.
    """
    try:
        sheet, hata = _sheets_baglan("KasaDefteri")
        if sheet is None:
            return False, f"E-Tabloya bağlanılamadı. Hata: {hata}"
            
        ham = sheet.get_all_values()
        if not ham or len(ham) == 0:
            sheet.append_row(["Islem_ID", "Zaman", "Islem_Turu", "Tutar", "Aciklama"])
            ham = [["Islem_ID"]]
            
        idler = []
        for r in ham[1:]:
            if r and len(r) > 0 and str(r[0]).replace('.', '', 1).isdigit():
                idler.append(int(float(r[0])))
                
        yeni_id = (max(idler) if idler else 0) + 1
        tarih_str = datetime.now().strftime("%d.%m.%Y %H:%M")
        
        # Ekstra komisyon açıklamasını ekle
        if komisyon > 0:
            aciklama = f"{aciklama} (Komisyon: {komisyon})"
            
        sheet.append_row([yeni_id, tarih_str, tur, round(float(tutar), 2), aciklama])
        return True, "İşlem başarıyla kaydedildi ve e-tabloya işlendi."
        
    except Exception as e:
        return False, f"E-tablo kayıt hatası: {str(e)}"
