"""
Trade kontrol motoru: otomatik kapanışlar (stop / kâr hedefi), periyodik sinyal mailleri,
stok/kasa bakiye güncellemeleri ve strateji değerlendirmesi.

Bildirim kanalları: Telegram (öncelikli) ve Gmail. Biri başarılıysa olay 'gönderildi' sayılır.
Mail durumu Google Sheets'te "MailDurumu" sayfasında tutulur. Mail yalnızca
başarıyla gittikten sonra kaydedilir; başarısızsa sonraki turda yeniden denenir.
"""
import os
import re
import time
from datetime import datetime, timedelta
import pytz
import requests
import pandas as pd
import gspread
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

import matris_motoru

TR_TZ = pytz.timezone("Europe/Istanbul")
GOOGLE_SHEET_DOSYA = "KriptoPortfoyVeritabani"
MAIL_DURUM_SAYFASI = "MailDurumu"
KALDIRAC = 5

# --- Komisyon ve risk ayarları (Binance USDⓈ-M Futures, standart kullanıcı / VIP 0) ---
KOMISYON_TAKER = 0.0005         # %0,05: piyasa emriyle giriş ve stop çıkışı
KOMISYON_MAKER = 0.0002         # %0,02: limit emirle hedef (kâr al) çıkışı

def satir_kaldiraci(row):
    """İşlem satırının kaldıracı (Kaldirac kolonu). Kayıt yoksa/geçersizse varsayılan KALDIRAC (panelle aynı)."""
    try:
        v = float(row.get("Kaldirac", 0) or 0)
        return v if v > 0 else KALDIRAC
    except Exception:
        return KALDIRAC

def _temizle_sayi(val):
    if val is None:
        return 0.0
    s = str(val).strip().replace("$", "").replace(",", ".")
    s = re.sub(r"[^\d.\-]", "", s)
    try:
        return float(s)
    except Exception:
        return 0.0

def tr_zaman():
    return datetime.now(TR_TZ)

def hafta_sonu_mu():
    return tr_zaman().weekday() >= 5

def bakiye_hesapla(df_islem):
    """Güncel kasa: Başlangıç 1000 + tüm kapatılmış işlemlerin Net_Kar_Zarar toplamı."""
    bakiye = 1000.0
    if df_islem is not None and not df_islem.empty:
        for _, r in df_islem.iterrows():
            durum = str(r.get("Durum", ""))
            if "Kapandi" in durum or "Kapatildi" in durum or "Kar" in durum or "Zarar" in durum:
                bakiye += _temizle_sayi(r.get("Net_Kar_Zarar", 0))
    return round(bakiye, 2)

def giris_komisyonu(miktar, lev):
    return miktar * lev * KOMISYON_TAKER

def cikis_komisyonu(miktar, hedef_mi, lev):
    oran = KOMISYON_MAKER if hedef_mi else KOMISYON_TAKER
    return miktar * lev * oran

def fiyat_cek_binance(coin):
    sym = coin.replace("/", "")
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={sym}"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return float(r.json()["price"])
    except Exception:
        pass
    return None

def kline_cek_binance(coin, interval="1m", limit=100):
    sym = coin.replace("/", "")
    url = f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={interval}&limit={limit}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            arr = r.json()
            if isinstance(arr, list) and len(arr) > 0:
                cols = ["OpenTime", "Open", "High", "Low", "Close", "Volume",
                        "CloseTime", "QuoteAssetVolume", "NumberOfTrades",
                        "TakerBuyBase", "TakerBuyQuote", "Ignore"]
                df = pd.DataFrame(arr, columns=cols)
                for c in ["Open", "High", "Low", "Close"]:
                    df[c] = df[c].astype(float)
                df["timestamp"] = df["OpenTime"]
                return df
    except Exception:
        pass
    return None

_KLINE_ONBELLEK = {}

def kline_cek_binance_aralik(coin, interval, bas_ms, bit_ms):
    """Belirli zaman aralığı için kline çek (önbellekli)."""
    key = (coin, interval, int(bas_ms), int(bit_ms))
    if key in _KLINE_ONBELLEK:
        return _KLINE_ONBELLEK[key]

    sym = coin.replace("/", "")
    tum = []
    curr_bas = int(bas_ms)
    bit = int(bit_ms)

    for _ in range(10): 
        if curr_bas >= bit:
            break
        url = f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={interval}&startTime={curr_bas}&endTime={bit}&limit=1000"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                break
            data = r.json()
            if not isinstance(data, list) or len(data) == 0:
                break
            tum.extend(data)
            son_zaman = data[-1][0]
            if son_zaman <= curr_bas:
                break
            curr_bas = son_zaman + 1
            if len(data) < 1000:
                break
        except Exception:
            break

    if not tum:
        _KLINE_ONBELLEK[key] = None
        return None

    cols = ["OpenTime", "Open", "High", "Low", "Close", "Volume",
            "CloseTime", "QuoteAssetVolume", "NumberOfTrades",
            "TakerBuyBase", "TakerBuyQuote", "Ignore"]
    df = pd.DataFrame(tum, columns=cols)
    for c in ["Open", "High", "Low", "Close"]:
        df[c] = df[c].astype(float)
    df["timestamp"] = df["OpenTime"]
    _KLINE_ONBELLEK[key] = df
    return df

def sheets_baglan():
    try:
        gc = gspread.service_account(filename="credentials.py") if os.path.exists("credentials.py") else gspread.service_account()
        return gc.open(GOOGLE_SHEET_DOSYA)
    except Exception as e:
        print("Google Sheets bağlantı hatası:", e)
        return None

def islem_gecmisi_getir():
    sh = sheets_baglan()
    if not sh:
        return None
    try:
        ws = sh.worksheet("IslemGecmisi")
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        print("IslemGecmisi okunamadı:", e)
        return None

def dataframe_guncelle_gsheets(df):
    sh = sheets_baglan()
    if not sh:
        return False
    try:
        ws = sh.worksheet("IslemGecmisi")
        ws.clear()
        ws.update([df.columns.values.tolist()] + df.values.tolist())
        return True
    except Exception as e:
        print("IslemGecmisi güncellenemedi:", e)
        return False

def kasa_defterine_ekle(islem_id, aciklama, tutar):
    sh = sheets_baglan()
    if not sh:
        return False
    try:
        ws = sh.worksheet("KasaDefteri")
        ws.append_row([tr_zaman().strftime("%d.%m.%Y %H:%M"), f"İşlem #{islem_id} - {aciklama}", float(tutar)])
        return True
    except Exception as e:
        print("KasaDefteri ekleme hatası:", e)
        return False

# ----------------------------------------------------------------------------
# BİLDİRİM KANALLARI (Telegram ve Gmail)
# ----------------------------------------------------------------------------
def telegram_bildirim_gonder(konu, icerik_html):
    """Telegram üzerinden mesaj gönderir. Başarılıysa True döner."""
    token = "".join(os.environ.get("TELEGRAM_BOT_TOKEN", "").split())
    chat_id = "".join(os.environ.get("TELEGRAM_CHAT_ID", "").split())
    if not token or not chat_id:
        return False

    metin = f"<b>{konu}</b>\n\n{icerik_html}"
    metin = metin.replace("<h3>", "<b>").replace("</h3>", "</b>")
    metin = metin.replace("<p>", "").replace("</p>", "\n")
    metin = re.sub(r"<br\s*/?>", "\n", metin)

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": metin,
        "parse_html": True,
        "parse_mode": "HTML"
    }

    for no in range(1, 4):
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 200:
                print(f"Telegram bildirimi gönderildi (deneme {no}): {konu}")
                return True
            else:
                print(f"Telegram HATA ({konu}): HTTP {r.status_code} {r.text[:150]}")
        except Exception as e:
            print(f"Telegram deneme {no}/3 başarısız ({konu}): {type(e).__name__}: {e}")
        time.sleep(2)
    return False

def gmail_bildirim_gonder(konu, icerik_html):
    """Gmail üzerinden e-posta gönderir. Başarılıysa True döner."""
    g_adres = os.environ.get("GMAIL_ADRES", "").strip()
    g_sifre = os.environ.get("GMAIL_SIFRE", "").strip()
    if not g_adres or not g_sifre:
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = konu
    msg["From"] = g_adres
    msg["To"] = g_adres
    msg.attach(MIMEText(icerik_html, "html", "utf-8"))

    for no in range(1, 4):
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587, timeout=10)
            server.starttls()
            server.login(g_adres, g_sifre)
            server.sendmail(g_adres, [g_adres], msg.as_string())
            server.quit()
            print(f"Gmail bildirimi gönderildi: {konu}")
            return True
        except Exception as e:
            print(f"Gmail deneme {no}/3 başarısız: {e}")
        time.sleep(2)
    return False

def bildirim_gonder(konu, icerik_html):
    """Önce Telegram, başarısızsa Gmail dener."""
    if telegram_bildirim_gonder(konu, icerik_html):
        return True
    return gmail_bildirim_gonder(konu, icerik_html)

class MailDurumu:
    def __init__(self):
        self.veriler = {}

    def yukle(self):
        sh = sheets_baglan()
        if not sh:
            return False
        try:
            ws = sh.worksheet(MAIL_DURUM_SAYFASI)
            rows = ws.get_all_records()
            for r in rows:
                anahtar = str(r.get("Anahtar", "")).strip()
                if anahtar:
                    self.veriler[anahtar] = {
                        "aktif": int(r.get("Aktif", 0)),
                        "zaman": str(r.get("Zaman", ""))
                    }
            return True
        except Exception as e:
            print("MailDurumu okuma hatası:", e)
            return False

    def kaydet(self):
        sh = sheets_baglan()
        if not sh:
            return False
        try:
            ws = sh.worksheet(MAIL_DURUM_SAYFASI)
            ws.clear()
            liste = [["Anahtar", "Aktif", "Zaman"]]
            for k, v in self.veriler.items():
                liste.append([k, v["aktif"], v["zaman"]])
            ws.update(liste)
            return True
        except Exception as e:
            print("MailDurumu kaydetme hatası:", e)
            return False

    def al(self, anahtar):
        return self.veriler.get(anahtar, {"aktif": 0, "zaman": ""})

    def ayarla(self, anahtar, aktif, zaman):
        self.veriler[anahtar] = {"aktif": int(aktif), "zaman": str(zaman)}

# ----------------------------------------------------------------------------
# 1) AÇIK İŞLEMLERİ KONTROL ET VE OTOMATİK KAPAT
# ----------------------------------------------------------------------------
def _seviye_baslangic_ms(row, simdi_ms):
    def _ms(metin):
        t = str(metin).strip()
        for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y %H:%M:%S"):
            try:
                return int(TR_TZ.localize(datetime.strptime(t, fmt)).timestamp() * 1000)
            except Exception:
                continue
        return None
    seviye = _ms(row.get("Seviye_Zamani", ""))
    if seviye:
        return seviye
    acilis = _ms(row.get("Acilis_Zamani", ""))
    sinir = simdi_ms - 20 * 60 * 1000
    return max(acilis, sinir) if acilis else sinir

def durum_kapali_mi(durum):
    d = str(durum).lower()
    return "kapandi" in d or "kapatildi" in d or "kar" in d or "zarar" in d

def acik_islemleri_kontrol_et():
    df = islem_gecmisi_getir()
    if df is None or df.empty:
        return

    suan = tr_zaman().strftime("%d.%m.%Y %H:%M")
    bakiye = bakiye_hesapla(df)
    kapananlar = []
    simdi_ms = int(time.time() * 1000)
    dk_mumlar = {}

    for idx, row in df.iterrows():
        islem_durumu = str(row.get("Durum", "")).lower()
        if durum_kapali_mi(islem_durumu):
            continue

        try:
            islem_id = int(row.get("Islem_ID", 0))
            coin = str(row.get("Coin", ""))
            yon = str(row.get("Yon", ""))
            giris = float(str(row.get("Giris_Fiyat", 0)).replace(",", "."))
            stop_f = float(str(row.get("Stop", 0)).replace(",", "."))
            kar_al_f = float(str(row.get("Kar_Al", 0)).replace(",", "."))
            miktar = float(str(row.get("Islem_Miktari", 0)).replace(",", "."))
        except:
            continue

        if giris <= 0 or stop_f <= 0 or kar_al_f <= 0 or miktar <= 0:
            continue

        baslangic_ms = _seviye_baslangic_ms(row, simdi_ms)
        gerekli = int(min(1000, max(5, (simdi_ms - baslangic_ms) / 60000.0 + 3)))
        onbellek = dk_mumlar.get(coin)
        
        if onbellek is None or onbellek[0] < gerekli:
            dk_mumlar[coin] = (gerekli, kline_cek_binance_aralik(coin, "1m", baslangic_ms, simdi_ms))
        
        dk_df = dk_mumlar[coin][1]
        kapat, hedef, kapanis = False, False, 0.0

        # Mumlar içinde manuel tarama (Dokunus_Bul bagimliligi kaldirildi)
        if dk_df is not None and not dk_df.empty:
            for _, m_row in dk_df.iterrows():
                h, l = float(m_row["High"]), float(m_row["Low"])
                if "Long" in yon:
                    if l <= stop_f:
                        kapat, hedef, kapanis = True, False, stop_f
                        break
                    elif h >= kar_al_f:
                        kapat, hedef, kapanis = True, True, kar_al_f
                        break
                elif "Short" in yon:
                    if h >= stop_f:
                        kapat, hedef, kapanis = True, False, stop_f
                        break
                    elif l <= kar_al_f:
                        kapat, hedef, kapanis = True, True, kar_al_f
                        break
        else:
            anl_f = fiyat_cek_binance(coin)
            if anl_f is not None:
                if "Long" in yon:
                    if anl_f <= stop_f:
                        kapat, hedef, kapanis = True, False, stop_f
                    elif anl_f >= kar_al_f:
                        kapat, hedef, kapanis = True, True, kar_al_f
                elif "Short" in yon:
                    if anl_f >= stop_f:
                        kapat, hedef, kapanis = True, False, stop_f
                    elif anl_f <= kar_al_f:
                        kapat, hedef, kapanis = True, True, kar_al_f

        if not kapat:
            continue

        fark = ((kapanis - giris) / giris) if "Long" in yon else ((giris - kapanis) / giris)
        lev = satir_kaldiraci(row)
        brut_kar = miktar * lev * fark
        net_kar = brut_kar - cikis_komisyonu(miktar, hedef, lev)

        df.at[idx, "Durum"] = "Kapandi (Kar)" if hedef else "Kapandi (Zarar)"
        df.at[idx, "Kapanis_Zamani"] = suan
        df.at[idx, "Net_Kar_Zarar"] = float(round(net_kar, 2))
        df.at[idx, "Kapanis_Fiyati"] = float(round(kapanis, 4))
        
        bakiye += net_kar
        df.at[idx, "Guncel_Kasa"] = float(round(bakiye, 2))
        kapananlar.append((islem_id, coin, "Hedef Kâr" if hedef else "Otomatik Stop", net_kar))

    if not kapananlar:
        return

    if dataframe_guncelle_gsheets(df):
        for islem_id, coin, etiket, net_kar in kapananlar:
            kasa_defterine_ekle(islem_id, etiket, net_kar)
        print(f"{len(kapananlar)} işlem otomatik kapatıldı ve kaydedildi.")

# ----------------------------------------------------------------------------
# 2) KAPANIŞ BİLDİRİMLERİ (Telegram / Gmail)
# ----------------------------------------------------------------------------
KAPANIS_PENCERESI_SAAT = 48

def _fiyat_esit(a, b):
    return abs(a - b) <= max(1e-4, abs(b) * 1e-6)

def kapanis_maillerini_gonder(durum):
    df_trade = islem_gecmisi_getir()
    if df_trade is None or df_trade.empty:
        return
        
    sinir = tr_zaman() - timedelta(hours=KAPANIS_PENCERESI_SAAT)
    degisti = False

    for _, r in df_trade.iterrows():
        islem_durumu = str(r.get("Durum", "")).lower()
        if not durum_kapali_mi(islem_durumu):
            continue

        zaman_str = str(r.get("Kapanis_Zamani", "")).strip()
        try:
            zaman = TR_TZ.localize(datetime.strptime(zaman_str, "%d.%m.%Y %H:%M"))
            if zaman < sinir:
                continue
        except:
            continue

        if "kar" in islem_durumu:
            etiket = "Hedef Kâr"
        elif "zarar" in islem_durumu:
            etiket = "Otomatik Stop"
        else:
            continue

        try:
            islem_id = int(r.get("Islem_ID", 0))
            coin = str(r.get("Coin", ""))
        except:
            continue

        anahtar = f"kapanis|{islem_id}"
        
        if durum.al(anahtar).get("aktif", 0) == 1:
            continue

        try:
            net_kar = float(str(r.get("Net_Kar_Zarar", 0)).replace(",", "."))
            kasa = float(str(r.get("Guncel_Kasa", 0)).replace(",", "."))
        except:
            net_kar = 0.0
            kasa = 0.0

        sonuc = "Kar" if etiket == "Hedef Kâr" else "Zarar"
        konu = f"⚡ {etiket}: #{islem_id} {coin} (Kapandi ({sonuc}))"
        icerik = (
            f"<b>İşlem Otomatik Kapatıldı</b><br><br>"
            f"<b>Zaman:</b> {zaman_str}<br>"
            f"<b>Coin:</b> {coin}<br>"
            f"<b>Yön:</b> {r.get('Yon', '')}<br>"
            f"<b>Sebep:</b> {etiket}<br>"
            f"<b>Net K/Z:</b> {net_kar:,.2f} $<br>"
            f"<b>Güncel Kasa:</b> {kasa:,.2f} $"
        )
        
        if bildirim_gonder(konu, icerik):
            durum.ayarla(anahtar, 1, tr_zaman().isoformat())
            degisti = True
            durum.kaydet()

    if degisti:
        durum.kaydet()

# ----------------------------------------------------------------------------
# 3) DİĞER MOTOR İŞLEMLERİ (Sinyaller, Kasa Senkronizasyonu, MAE/MFE vb.)
# ----------------------------------------------------------------------------
def kasa_bakiye_kolonu_esitle():
    df = islem_gecmisi_getir()
    if df is None or df.empty:
        return
    bakiye = 1000.0
    degisti = False
    for idx, r in df.iterrows():
        d = str(r.get("Durum", ""))
        if durum_kapali_mi(d):
            bakiye += _temizle_sayi(r.get("Net_Kar_Zarar", 0))
        mevcut_kasa = _temizle_sayi(r.get("Guncel_Kasa", 0))
        if abs(mevcut_kasa - bakiye) > 0.01:
            df.at[idx, "Guncel_Kasa"] = float(round(bakiye, 2))
            degisti = True
    if degisti:
        dataframe_guncelle_gsheets(df)

def mae_mfe_doldur():
    df = islem_gecmisi_getir()
    if df is None or df.empty:
        return
    degisti = False
    simdi_ms = int(time.time() * 1000)

    for idx, r in df.iterrows():
        if not durum_kapali_mi(r.get("Durum", "")):
            continue
        mae_val = r.get("MAE_Yuzde", "")
        mfe_val = r.get("MFE_Yuzde", "")
        if mae_val != "" and mfe_val != "" and not pd.isna(mae_val) and not pd.isna(mfe_val):
            continue

        coin = r["Coin"]
        yon = str(r["Yon"])
        giris = float(r["Giris_Fiyat"])

        def _parse_t(m):
            t = str(m).strip()
            for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y %H:%M:%S"):
                try:
                    return int(TR_TZ.localize(datetime.strptime(t, fmt)).timestamp() * 1000)
                except Exception:
                    continue
            return None

        acilis_ms = _parse_t(r.get("Acilis_Zamani", ""))
        kapanis_ms = _parse_t(r.get("Kapanis_Zamani", ""))
        if not acilis_ms or not kapanis_ms:
            continue

        mumlar = kline_cek_binance_aralik(coin, "1m", acilis_ms, kapanis_ms + 60000)
        if mumlar is not None and not mumlar.empty:
            try:
                res = matris_motoru.mae_mfe_hesapla(mumlar, "Long" in yon, giris, acilis_ms, kapanis_ms)
                if res:
                    mae_f, mfe_f = res
                    df.at[idx, "MAE_Yuzde"] = float(round(mae_f, 4))
                    df.at[idx, "MFE_Yuzde"] = float(round(mfe_f, 4))
                    degisti = True
            except Exception as e:
                pass

    if degisti:
        dataframe_guncelle_gsheets(df)

def sinyal_maillerini_gonder(durum):
    pass

STRATEJI_DEGERLENDIRME_ESIGI = 50

def strateji_degerlendirme_uyarisi(durum):
    df = islem_gecmisi_getir()
    if df is None or df.empty:
        return
    kapali_sayisi = sum(1 for _, r in df.iterrows() if durum_kapali_mi(r.get("Durum", "")))
    if kapali_sayisi < STRATEJI_DEGERLENDIRME_ESIGI:
        return

    anahtar = f"strateji_degerlendirme|{kapali_sayisi}"
    if durum.al(anahtar)["aktif"] == 1:
        return

    konu = f"🎯 Strateji değerlendirmesi zamanı ({kapali_sayisi} işlem)"
    icerik = f"<p>Sistemde toplam {kapali_sayisi} kapalı işlem tamamlandı. Performans analizi yapabilirsiniz.</p>"
    if bildirim_gonder(konu, icerik):
        durum.ayarla(anahtar, 1, tr_zaman().isoformat())
        durum.kaydet()

# ----------------------------------------------------------------------------
# MOTOR ÇALIŞTIRMA DÖNGÜSÜ
# ----------------------------------------------------------------------------
def _adim_calistir(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except Exception as e:
        print(f"HATA [{func.__name__}]: {e}")

def motoru_calistir():
    print(f"Trade Kontrol Motoru başladı: {tr_zaman().strftime('%d.%m.%Y %H:%M:%S')} "
          f"({'hafta sonu' if hafta_sonu_mu() else 'hafta içi'} modu)")

    if os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
        ok = telegram_bildirim_gonder(
            "✅ Bot test mesajı",
            f"<p>Trade kontrol motoru elle çalıştırıldı.</p><p>Zaman: {tr_zaman().strftime('%d.%m.%Y %H:%M')}</p>",
        )
        print("Telegram test mesajı:", "gönderildi" if ok else "GÖNDERİLEMEDİ (secret'ları kontrol edin)")

    _adim_calistir(acik_islemleri_kontrol_et)
    durum = MailDurumu()
    if not durum.yukle():
        print("MailDurumu sekmesi yüklenemedi.")
        return
    _adim_calistir(kapanis_maillerini_gonder, durum)

    _adim_calistir(kasa_bakiye_kolonu_esitle)
    _adim_calistir(mae_mfe_doldur)
    for adim in (sinyal_maillerini_gonder, strateji_degerlendirme_uyarisi):
        _adim_calistir(adim, durum)

    print("Motor turu tamamlandı.")

if __name__ == "__main__":
    motoru_calistir()
