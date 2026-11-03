"""
Bağımsız Trade Kontrol ve Mail Motoru (GitHub Actions - her 5 dakikada bir)

Mail gönderen TEK kaynak burasıdır (panel_v2.py'de mail kapalıdır).

Mail koşulları:
  1) 5. Aşama sinyali : hafta içi 70,00 <= puan < 73,75 | hafta sonu 75,00 <= puan < 78,75
  2) 6. Aşama sinyali : hafta içi puan >= 73,75         | hafta sonu puan >= 78,75
     (her coin ve TOTAL için; aralığa girince 1 kez, aralıktan çıkınca sıfırlanır,
      aynı coin+aşama için en az SINYAL_BEKLEME_DK dakika arayla)
  3) Otomatik kapanış : stop veya kâr hedefi (panel veya bu motor kapatsa da, işlem başına 1 kez)

Bildirim kanalları: Telegram (öncelikli) ve Gmail. Biri başarılıysa olay 'gönderildi' sayılır.
Mail durumu Google Sheets'te "MailDurumu" sayfasında tutulur. Mail yalnızca
başarıyla gittikten sonra kaydedilir; başarısızsa sonraki turda yeniden denenir.
"""
import os
import re
import json
import time
import html
from datetime import datetime, timedelta
import pytz

import matris_motoru
import requests
import pandas as pd
import numpy as np
import gspread
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

TR_TZ = pytz.timezone("Europe/Istanbul")
GOOGLE_SHEET_DOSYA = "KriptoPortfoyVeritabani"
MAIL_DURUM_SAYFASI = "MailDurumu"
KALDIRAC = 5

# --- Komisyon ve risk ayarları (Binance USDⓈ-M Futures, standart kullanıcı / VIP 0) ---
KOMISYON_TAKER = 0.0005         # %0,05: piyasa emriyle giriş ve stop çıkışı
KOMISYON_MAKER = 0.0002         # %0,02: limit emirle hedef (kâr al) çıkışı
ISLEM_BASINA_RISK_YUZDE = 1.0   # tek işlemin (komisyon dahil) stop riski: kasanın en fazla %1'i
TOPLAM_RISK_LIMIT_YUZDE = 3.0   # tüm açık işlemlerin toplam stop riski: kasanın en fazla %3'ü


def satir_kaldiraci(row):
    """İşlem satırının kaldıracı (Kaldirac kolonu). Kayıt yoksa/geçersizse varsayılan KALDIRAC (panelle aynı)."""
    try:
        v = float(row.get("Kaldirac", 0) or 0)
    except Exception:
        v = 0.0
    return v if v >= 1 else float(KALDIRAC)


def giris_komisyonu(miktar, kaldirac=None):
    k = float(kaldirac) if kaldirac else float(KALDIRAC)
    return float(miktar) * k * KOMISYON_TAKER


def cikis_komisyonu(miktar, hedef_mi, kaldirac=None):
    """Hedef (limit emir) maker, stop (piyasa emri) taker öder."""
    k = float(kaldirac) if kaldirac else float(KALDIRAC)
    return float(miktar) * k * (KOMISYON_MAKER if hedef_mi else KOMISYON_TAKER)


BASLANGIC_BAKIYE = 0.0
SINYAL_BEKLEME_DK = 60       # aynı coin + aynı aşama için iki mail arası minimum süre
KAPANIS_PENCERESI_SAAT = 24  # bu süreden eski kapanışlar için mail atılmaz
ZAMAN_BUTCESI_SN = 180       # sinyal taraması bu süreden sonra bırakılır (kapanış mailleri öncelikli)
_T0 = time.time()

COINLER = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"]
GMAIL_ADRES = "erhanvancin@gmail.com"


# --- DURUM (KAPALI/AÇIK) KONTROLÜ ---
# Türkçe harf farklarından (ı/i, â/a, İ/i) ve pandas/pyarrow regex davranışından bağımsız çalışır.
# Örn. "Kısmi Kapandı (Kâr)" ve "Kapandi (Kar)" aynı şekilde kapalı sayılır.
_TR_ASCII = str.maketrans({
    "ı": "i", "İ": "i", "I": "i", "â": "a", "Â": "a", "î": "i", "Î": "i", "û": "u", "Û": "u",
    "ö": "o", "Ö": "o", "ü": "u", "Ü": "u", "ş": "s", "Ş": "s", "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g",
})


def durum_kapali_mi(durum):
    t = str(durum).translate(_TR_ASCII).lower()
    return any(k in t for k in ("kapandi", "kar", "zarar", "kismi"))


def durum_kapali_maskesi(seri):
    return seri.map(durum_kapali_mi).astype(bool)



def tr_zaman():
    return datetime.now(TR_TZ)


def hafta_sonu_mu():
    simdi = tr_zaman()
    gun, saat = simdi.weekday(), simdi.hour
    return (gun == 4 and saat >= 23) or (gun in [5, 6]) or (gun == 0 and saat < 3)


def aktif_min_puan_esigi_getir():
    return 60.0 if hafta_sonu_mu() else 55.0


# ----------------------------------------------------------------------------
# MAIL
# ----------------------------------------------------------------------------
_MAIL_ENGELLI = False  # Bu çalıştırmada tüm denemeler başarısız olduysa kalan mailler sonraki tura bırakılır


def gmail_bildirim_gonder(konu, icerik_html, hizli=False):
    """Başarılıysa True döner. Bağlantı kopmalarına karşı 3 deneme (465 SSL, 587 STARTTLS, 465 SSL).
    hizli=True: tek deneme, kısa zaman aşımı (Telegram zaten gittiyse mail ek olarak denenir)."""
    global _MAIL_ENGELLI
    if _MAIL_ENGELLI:
        print(f"ATLANDI ({konu}): bu turda Gmail bağlantısı kurulamadı, sonraki turda denenecek.")
        return False

    # Uygulama şifresi Google'da "abcd efgh ijkl mnop" gibi boşluklu gösterilir; boşluklar temizlenir.
    sifre = "".join(os.environ.get("GMAIL_PASSWORD", "").split())
    if not sifre:
        print(f"HATA ({konu}): GMAIL_PASSWORD tanımlı değil (GitHub Secret kontrol edin).")
        return False

    msg = MIMEMultipart()
    msg["From"] = GMAIL_ADRES
    msg["To"] = GMAIL_ADRES
    msg["Subject"] = konu
    msg.attach(MIMEText(icerik_html, "html", "utf-8"))
    govde = msg.as_string()

    denemeler = [("ssl", 465), ("starttls", 587), ("ssl", 465)]
    zaman_asimi = 30
    if hizli:
        denemeler, zaman_asimi = denemeler[:1], 12
    for no, (mod, port) in enumerate(denemeler, start=1):
        server = None
        try:
            if mod == "ssl":
                server = smtplib.SMTP_SSL("://gmail.com", port, timeout=zaman_asimi)
            else:
                server = smtplib.SMTP("://gmail.com", port, timeout=zaman_asimi)
                server.ehlo()
                server.starttls()
                server.ehlo()
            server.login(GMAIL_ADRES, sifre)
            server.sendmail(GMAIL_ADRES, [GMAIL_ADRES], govde)
            print(f"E-posta gönderildi ({mod}:{port}, deneme {no}): {konu}")
            return True
        except smtplib.SMTPAuthenticationError as e:
            print(f"HATA ({konu}): Gmail kimlik doğrulama başarısız. Uygulama şifresini kontrol edin: {e}")
            _MAIL_ENGELLI = True
            return False
        except Exception as e:
            print(f"Deneme {no}/{len(denemeler)} başarısız ({mod}:{port}) ({konu}): {type(e).__name__}: {e}")
            if no < len(denemeler):
                time.sleep(4 * no)
        finally:
            if server is not None:
                try:
                    server.quit()
                except Exception:
                    pass

    print(f"HATA ({konu}): tüm denemeler başarısız; sonraki turda yeniden denenecek.")
    _MAIL_ENGELLI = True
    return False


def html_to_metin(icerik_html):
    metin = re.sub(r"</(p|h\d|div)>|<br\s*/?>", "\n", icerik_html)
    metin = re.sub(r"<[^>]+>", "", metin)
    return html.unescape(metin).strip()


def telegram_bildirim_gonder(konu, icerik_html):
    """Başarılıysa True döner. Token/chat id tanımlı değilse False döner (sessizce)."""
    token = "".join(os.environ.get("TELEGRAM_BOT_TOKEN", "").split())
    chat_id = "".join(os.environ.get("TELEGRAM_CHAT_ID", "").split())
    if not token or not chat_id:
        return False

    metin = f"{konu}\n\n{html_to_metin(icerik_html)}"[:4000]
    url = f"https://telegram.org{token}/sendMessage"
    for no in range(1, 4):
        try:
            r = requests.post(url, data={"chat_id": chat_id, "text": metin}, timeout=15)
            if r.status_code == 200 and r.json().get("ok"):
                print(f"Telegram bildirimi gönderildi (deneme {no}): {konu}")
                return True
            if r.status_code in (400, 401, 403, 404):
                print(f"Telegram HATA ({konu}): HTTP {r.status_code} {r.text[:150]}")
                return False
            print(f"Telegram deneme {no}/3 başarısız ({konu}): HTTP {r.status_code}")
        except Exception as e:
            print(f"Telegram deneme {no}/3 başarısız ({konu}): {type(e).__name__}: {e}")
        if no < 3:
            time.sleep(2 * no)
    return False


def bildirim_gonder(konu, icerik_html):
    """Bildirimleri yalnızca Telegram kanalı üzerinden gönderir."""
    return telegram_bildirim_gonder(konu, icerik_html)


# ----------------------------------------------------------------------------
# FİYAT / MUM VERİSİ  (başarısızsa None / boş döner; sahte "baz fiyat" KULLANILMAZ)
# ----------------------------------------------------------------------------
def fiyat_cek_binance(coin_symbol):
    sym = coin_symbol.replace("/", "")
    for ep in (
        f"https://binance.vision{sym}",
        f"https://binance.com{sym}",
    ):
        try:
            r = requests.get(ep, timeout=5)
            if r.status_code == 200:
                val = float(r.json()["price"])
                if val > 0:
                    return val
        except Exception:
            continue
    return None


def kline_cek_binance(coin_symbol, interval, limit):
    sym = coin_symbol.replace("/", "")
    for ep in (
        f"https://binance.vision{sym}&interval={interval}&limit={limit}",
        f"https://binance.com{sym}&interval={interval}&limit={limit}",
    ):
        try:
            r = requests.get(ep, timeout=8)
            if r.status_code == 200:
                df = pd.DataFrame(
                    r.json(),
                    columns=["timestamp", "Open", "High", "Low", "Close", "Volume",
                             "Close_Time", "QAV", "Num_Trades", "Taker_BBAV", "Taker_BQAV", "Ignore"],
                )
                for col in ["Open", "High", "Low", "Close"]:
                    df[col] = df[col].astype(float)
                return df[["timestamp", "Open", "High", "Low", "Close"]]
        except Exception:
            continue
    return pd.DataFrame()


