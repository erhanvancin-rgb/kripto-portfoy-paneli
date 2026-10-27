# ==========================================
# kasa_motoru.py
# ==========================================
import os
from datetime import datetime
import gspread
import streamlit as st
import pandas as pd

GOOGLE_SHEET_ID = "1likk2RqtqxPxj7nSNDroxT6GQGrQXJmfx-SoyHswgyo"

def _sheets_baglan(sayfa_adi):
    """Google Sheets bağlantısını kurar ve PEM anahtarındaki format hatalarını otomatik onarır."""
    try:
        if hasattr(st, "secrets") and "gcp_service_account" in st.secrets:
            sec = dict(st.secrets["gcp_service_account"])
            
            pk = str(sec.get("private_key", ""))
            if "\\n" in pk:
                pk = pk.replace("\\n", "\n")
            lines = pk.splitlines()
            cleaned_lines = [line.strip() for line in lines if line.strip()]
            sec["private_key"] = "\n".join(cleaned_lines)
            
            client = gspread.service_account_from_dict(sec)
        else:
            return None, "Streamlit Secrets içinde 'gcp_service_account' bulunamadı!"
            
        sh = client.open_by_key(GOOGLE_SHEET_ID)
        return sh.worksheet(sayfa_adi), None
    except Exception as e:
        return None, str(e)

def _verileri_tablodan_oku():
    """Tüm geçmişi ve güncel bakiyeyi doğrudan Google E-Tablodan okur."""
    sheet, hata = _sheets_baglan("KasaDefteri")
    if sheet is None:
        st.error(f"⚠️ Kasa E-Tablo Bağlantı Hatası: {hata}")
        return 0.0, []
        
    try:
        satirlar = sheet.get_all_values()
        if not satirlar or len(satirlar) <= 1:
            return 0.0, []
            
        veri_satirlari = satirlar[1:]
        gecmis = []
        bakiye = 0.0
        
        for row in veri_satirlari:
            if not row or len(row) < 3: 
                continue
            
            islem_id = row[0] if len(row) > 0 else ""
            zaman = row[1] if len(row) > 1 else ""
            tur = row[2] if len(row) > 2 else ""
            
            tutar_str = "0"
            for col_idx in [3, 4, 2]:
                if len(row) > col_idx:
                    val = str(row[col_idx]).strip()
                    if any(char.isdigit() for char in val):
                        tutar_str = val
                        break
            
            try:
                tutar = float(tutar_str.replace(' ', '').replace('₺', '').replace('$', '').replace(',', '.'))
            except ValueError:
                tutar = 0.0
                
            aciklama = row[4] if len(row) > 4 else (row[3] if len(row) > 3 else "")
            
            tur_kucuk = tur.lower()
            if any(k in tur_kucuk for k in ["yatir", "satim", "gelir", "ekle"]):
                bakiye += tutar
            elif any(k in tur_kucuk for k in ["cek", "alim", "gider", "komisyon", "zarar"]):
                bakiye -= abs(tutar)
            elif "trade" in tur_kucuk:
                bakiye += tutar
            else:
                bakiye += tutar
                
            gecmis.append({
                "id": islem_id,
                "tarih": zaman,
                "tur": tur,
                "tutar": round(tutar, 2),
                "aciklama": aciklama,
                "guncel_bakiye": round(bakiye, 2)
            })
            
        return round(bakiye, 2), gecmis
        
    except Exception as e:
        st.error(f"⚠️ Kasa Veri Okuma Hatası: {str(e)}")
        return 0.0, []

def bakiye_getir():
    bakiye, _ = _verileri_tablodan_oku()
    return bakiye

def gecmis_getir():
    _, gecmis = _verileri_tablodan_oku()
    return gecmis

def islem_gecmisi_getir(ortak_fiyat_havuzu=None):
    return gecmis_getir()

def islem_ekle(tur, tutar, aciklama="", komisyon=0.0):
    """Yeni işlemi tutar ve komisyonlardaki format hatalarını düzelterek Google Sheets'e yazar."""
    try:
        sheet, hata = _sheets_baglan("KasaDefteri")
        if sheet is None:
            return False, f"E-Tabloya bağlanılamadı. Hata: {hata}"
            
        if isinstance(tutar, str):
            tutar = tutar.replace(',', '.')
        try:
            tutar = float(tutar)
        except ValueError:
            return False, "Hata: Lütfen geçerli bir tutar girin."
        
        if isinstance(komisyon, str):
            komisyon = komisyon.replace(',', '.')
        try:
            komisyon = float(komisyon)
        except ValueError:
            komisyon = 0.0
            
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
        
        if komisyon > 0:
            aciklama = f"{aciklama} (Komisyon: {komisyon})"
            
        sheet.append_row([yeni_id, tarih_str, tur, round(tutar, 2), aciklama])
        return True, "İşlem başarıyla e-tabloya işlendi."
        
    except Exception as e:
        return False, f"E-tablo kayıt hatası: {str(e)}"
