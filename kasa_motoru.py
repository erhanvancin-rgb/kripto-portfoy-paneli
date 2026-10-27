# ==========================================
# kasa_motoru.py
# ==========================================
import os
from datetime import datetime
import gspread
import streamlit as st
import pandas as pd

GOOGLE_SHEET_ID = "1likk2RqtqxPxj7nSNDroxT6GQGrQXJmfx-SoyHswgyo"

@st.cache_resource(ttl=3600, show_spinner=False)
def _sayfa_getir(sayfa_adi):
    """Google Sheets sayfasına bir kez bağlanır ve 1 saat boyunca önbellekte tutar (hata durumunda önbelleğe alınmaz)."""
    if not (hasattr(st, "secrets") and "gcp_service_account" in st.secrets):
        raise RuntimeError("Streamlit Secrets içinde 'gcp_service_account' bulunamadı!")

    sec = dict(st.secrets["gcp_service_account"])
    pk = str(sec.get("private_key", ""))
    if "\\n" in pk:
        pk = pk.replace("\\n", "\n")
    lines = pk.splitlines()
    cleaned_lines = [line.strip() for line in lines if line.strip()]
    sec["private_key"] = "\n".join(cleaned_lines)

    client = gspread.service_account_from_dict(sec)
    sh = client.open_by_key(GOOGLE_SHEET_ID)
    return sh.worksheet(sayfa_adi)

def _sheets_baglan(sayfa_adi):
    """Eski imza korunur: (sayfa, hata) döndürür."""
    try:
        return _sayfa_getir(sayfa_adi), None
    except Exception as e:
        try:
            _sayfa_getir.clear()
        except Exception:
            pass
        return None, str(e)

@st.cache_data(ttl=15, show_spinner=False)
def _ham_satirlar():
    """KasaDefteri'nin tüm satırlarını okur; 15 sn önbellekte tutulur. Yazma sonrası temizlenir."""
    sheet, hata = _sheets_baglan("KasaDefteri")
    if sheet is None:
        raise RuntimeError(hata)
    return sheet.get_all_values()

def _verileri_tablodan_oku():
    """Tüm geçmişi ve güncel bakiyeyi doğrudan Google E-Tablodan okur."""
    try:
        satirlar = _ham_satirlar()
    except Exception as e:
        st.error(f"⚠️ Kasa E-Tablo Bağlantı Hatası: {e}")
        return 0.0, []

    try:
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
    import pytz
    from datetime import datetime
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

        # --- YENİ EMNİYET KİLİDİ: KASADA YETERLİ NAKİT VAR MI? ---
        if tur in ["Para_Cek", "CEK"]:
            _ham_satirlar.clear()  # çekim kontrolü her zaman güncel bakiye ile yapılır
            mevcut_nakit = bakiye_getir() # Mevcut kasadaki bakiye fonksiyonu
            if tutar > mevcut_nakit:
                return False, f"⚠️ Yetersiz bakiye! Kasada çekilebilecek yalnızca {mevcut_nakit:,.2f} $ var."
        # ---------------------------------------------------------
            
        ham = sheet.get_all_values()
        if not ham or len(ham) == 0:
            sheet.append_row(["Islem_ID", "Zaman", "Islem_Turu", "Tutar", "Aciklama"])
            ham = [["Islem_ID"]]
            
        idler = []
        for r in ham[1:]:
            if r and len(r) > 0 and str(r[0]).replace('.', '', 1).isdigit():
                idler.append(int(float(r[0])))
                
        yeni_id = (max(idler) if idler else 0) + 1
        
        tr_tz = pytz.timezone("Europe/Istanbul")
        tarih_str = datetime.now(tr_tz).strftime("%d.%m.%Y %H:%M")
        
        if komisyon > 0:
            aciklama = f"{aciklama} (Komisyon: {komisyon})"
            
        sheet.append_row([yeni_id, tarih_str, tur, round(tutar, 2), aciklama])
        _ham_satirlar.clear()  # sonraki okuma yeni kaydı görsün
        return True, "İşlem başarıyla kaydedildi ve e-tabloya işlendi."
        
    except Exception as e:
        return False, f"E-tablo kayıt hatası: {str(e)}"
