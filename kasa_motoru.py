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

# ------------------------------------------------------------------ "Kasa Bakiye" KOLONU (F)
def _satir_tutari(row):
    """_verileri_tablodan_oku ile aynı kural: D, E, C sütunlarında rakam içeren ilk hücre tutar sayılır."""
    tutar_str = "0"
    for col_idx in [3, 4, 2]:
        if len(row) > col_idx:
            val = str(row[col_idx]).strip()
            if any(ch.isdigit() for ch in val):
                tutar_str = val
                break
    try:
        return float(tutar_str.replace(' ', '').replace('₺', '').replace('$', '').replace(',', '.'))
    except ValueError:
        return 0.0


def _isaretli_tutar(tur, tutar):
    """Bakiyeye etkisi: yatırma/ekleme +, çekme/komisyon/zarar -, Trade_Sonuc ve diğerleri kendi işaretiyle."""
    t = str(tur).lower()
    if any(k in t for k in ["yatir", "satim", "gelir", "ekle"]):
        return tutar
    if any(k in t for k in ["cek", "alim", "gider", "komisyon", "zarar"]):
        return -abs(tutar)
    return tutar


def _defter_bakiyeleri(ham):
    """Her veri satırı için o satırdan SONRAKİ kasa bakiyesi listesi ve son bakiye."""
    bakiye, liste = 0.0, []
    for row in ham[1:]:
        if not row or len(row) < 3:
            liste.append("")
            continue
        bakiye += _isaretli_tutar(row[2], _satir_tutari(row))
        liste.append(round(bakiye, 2))
    return liste, round(bakiye, 2)


def _sayi_oku(metin):
    t = str(metin).strip().replace(' ', '')
    if ',' in t:
        t = t.replace('.', '').replace(',', '.')
    return float(t)


def _baslik_bicimini_kopyala(sheet):
    """Yeni F başlığına E başlığının biçimini (renk/yazı tipi) kopyalar. Görsel amaçlıdır; hata olursa yok sayılır."""
    try:
        sheet.spreadsheet.batch_update({"requests": [{"copyPaste": {
            "source": {"sheetId": sheet.id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 4, "endColumnIndex": 5},
            "destination": {"sheetId": sheet.id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 5, "endColumnIndex": 6},
            "pasteType": "PASTE_FORMAT"}}]})
    except Exception:
        pass


def _bakiye_kolonu_esitle(sheet, ham):
    """KasaDefteri F sütununu ('Kasa Bakiye') her satır için o anki bakiyeyle doldurur/düzeltir.
    Yalnızca fark varsa yazar. Son bakiyeyi döndürür."""
    liste, son = _defter_bakiyeleri(ham)
    baslik_tamam = len(ham[0]) > 5 and str(ham[0][5]).strip() == "Kasa Bakiye"
    fark = not baslik_tamam
    if not fark:
        for r, b in zip(ham[1:], liste):
            mevcut = str(r[5]).strip() if len(r) > 5 else ""
            if b == "":
                if mevcut != "":
                    fark = True
                    break
                continue
            try:
                if abs(_sayi_oku(mevcut) - b) > 0.005:
                    fark = True
                    break
            except ValueError:
                fark = True
                break
    if fark:
        sheet.update(range_name=f"F1:F{len(ham)}", values=[["Kasa Bakiye"]] + [[b] for b in liste])
        if not baslik_tamam:
            _baslik_bicimini_kopyala(sheet)
    return son


def bakiye_kolonu_senkronla():
    """Mevcut tüm defter satırları için 'Kasa Bakiye' kolonunu (F) bir kerede oluşturur/düzeltir."""
    sheet, hata = _sheets_baglan("KasaDefteri")
    if sheet is None:
        return False
    ham = sheet.get_all_values()
    if not ham:
        return False
    _bakiye_kolonu_esitle(sheet, ham)
    _ham_satirlar.clear()
    return True


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
            sheet.append_row(["Islem_ID", "Zaman", "Islem_Turu", "Tutar", "Aciklama", "Kasa Bakiye"])
            ham = [["Islem_ID", "Zaman", "Islem_Turu", "Tutar", "Aciklama", "Kasa Bakiye"]]
            
        idler = []
        for r in ham[1:]:
            if r and len(r) > 0 and str(r[0]).replace('.', '', 1).isdigit():
                idler.append(int(float(r[0])))
                
        yeni_id = (max(idler) if idler else 0) + 1
        
        tr_tz = pytz.timezone("Europe/Istanbul")
        tarih_str = datetime.now(tr_tz).strftime("%d.%m.%Y %H:%M")
        
        if komisyon > 0:
            aciklama = f"{aciklama} (Komisyon: {komisyon})"
            
        # Eski satırların ve başlığın 'Kasa Bakiye' değerleri tamamlanır; yeni satır kendi bakiyesiyle eklenir
        try:
            onceki_bakiye = _bakiye_kolonu_esitle(sheet, ham)
        except Exception:
            onceki_bakiye = _defter_bakiyeleri(ham)[1]
        yeni_bakiye = round(onceki_bakiye + _isaretli_tutar(tur, round(tutar, 2)), 2)
        sheet.append_row([yeni_id, tarih_str, tur, round(tutar, 2), aciklama, yeni_bakiye])
        _ham_satirlar.clear()  # sonraki okuma yeni kaydı görsün
        return True, "İşlem başarıyla kaydedildi ve e-tabloya işlendi."
        
    except Exception as e:
        return False, f"E-tablo kayıt hatası: {str(e)}"
