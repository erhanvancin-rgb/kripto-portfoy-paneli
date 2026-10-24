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
KALDIRAC = 3

# --- Komisyon ve risk ayarları (Binance USDⓈ-M Futures, standart kullanıcı / VIP 0) ---
KOMISYON_TAKER = 0.0005         # %0,05: piyasa emriyle giriş ve stop çıkışı
KOMISYON_MAKER = 0.0002         # %0,02: limit emirle hedef (kâr al) çıkışı
ISLEM_BASINA_RISK_YUZDE = 1.0   # tek işlemin (komisyon dahil) stop riski: kasanın en fazla %1'i
TOPLAM_RISK_LIMIT_YUZDE = 3.0   # tüm açık işlemlerin toplam stop riski: kasanın en fazla %3'ü


def giris_komisyonu(miktar):
    return float(miktar) * KALDIRAC * KOMISYON_TAKER


def cikis_komisyonu(miktar, hedef_mi):
    """Hedef (limit emir) maker, stop (piyasa emri) taker öder."""
    return float(miktar) * KALDIRAC * (KOMISYON_MAKER if hedef_mi else KOMISYON_TAKER)


# --- RSI BONUS AYARLARI (panel_v2.py ve check_engine.py'de AYNI olmalı) ---
# "momentum": RSI ve fiyat konumu aynı tarafta ise o yönde bonus (trend yönlü, eski kalibrasyonla uyumlu)
# "sapma"   : RSI ile fiyat konumu arasındaki fark yönüne bonus (trend karşıtı / uyumsuzluk)
RSI_MODU = "momentum"
RSI_MOMENTUM_TAVAN = 0.03   # momentum modunda bonus tavanı (max_puanın oranı)
RSI_SAPMA_TAVAN = 0.12      # sapma modunda bonus tavanı (max_puanın oranı)

BASLANGIC_BAKIYE = 500.0
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
                server = smtplib.SMTP_SSL("smtp.gmail.com", port, timeout=zaman_asimi)
            else:
                server = smtplib.SMTP("smtp.gmail.com", port, timeout=zaman_asimi)
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
    url = f"https://api.telegram.org/bot{token}/sendMessage"
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
    """Telegram ve Gmail'den en az biri başarılıysa True döner (tekrar mail olmasın diye 'gönderildi' sayılır)."""
    telegram_ok = telegram_bildirim_gonder(konu, icerik_html)
    if telegram_ok:
        gmail_bildirim_gonder(konu, icerik_html, hizli=True)
        return True
    return gmail_bildirim_gonder(konu, icerik_html)


# ----------------------------------------------------------------------------
# FİYAT / MUM VERİSİ  (başarısızsa None / boş döner; sahte "baz fiyat" KULLANILMAZ)
# ----------------------------------------------------------------------------
def fiyat_cek_binance(coin_symbol):
    sym = coin_symbol.replace("/", "")
    for ep in (
        f"https://data-api.binance.vision/api/v3/ticker/price?symbol={sym}",
        f"https://api.binance.com/api/v3/ticker/price?symbol={sym}",
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
        f"https://data-api.binance.vision/api/v3/klines?symbol={sym}&interval={interval}&limit={limit}",
        f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={interval}&limit={limit}",
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


# ----------------------------------------------------------------------------
# MATRİS PUANI (RSI bonusu: RSI_MODU ayarına göre momentum veya sapma)
# ----------------------------------------------------------------------------
def oransal_matris_ve_teknik_faktorler_hesapla(df, max_puan):
    if df.empty or len(df) < 10:
        return max_puan / 2.0, max_puan / 2.0, 0, 0

    df["Body"] = df["Close"] - df["Open"]
    toplam_yesil_boy = df[df["Body"] > 0]["Body"].sum()
    toplam_kirmizi_boy = abs(df[df["Body"] < 0]["Body"].sum())
    toplam_boy = toplam_yesil_boy + toplam_kirmizi_boy

    if toplam_boy > 0:
        yesil_oran = toplam_yesil_boy / toplam_boy
        kirmizi_oran = toplam_kirmizi_boy / toplam_boy
    else:
        yesil_oran, kirmizi_oran = 0.5, 0.5

    baz_long_puan = max_puan * yesil_oran
    baz_short_puan = max_puan * kirmizi_oran

    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
    anlik_fiyat = float(df["Close"].iloc[-1])
    anlik_ema = float(df["EMA20"].iloc[-1])
    fark_yuzde = (abs(anlik_fiyat - anlik_ema) / anlik_ema) * 100.0
    ema_log_carpan = min(1.0, np.log1p(fark_yuzde) / np.log1p(1.5))
    max_ema_bonus = max_puan * 0.04
    ema_l = max_ema_bonus * ema_log_carpan if anlik_fiyat > anlik_ema else 0.0
    ema_s = max_ema_bonus * ema_log_carpan if anlik_fiyat < anlik_ema else 0.0

    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi_serisi = 100 - (100 / (1 + rs))
    rsi_anlik = float(rsi_serisi.iloc[-1]) if not rsi_serisi.isna().all() else 50.0

    # --- RSI BONUSU (mod: RSI_MODU) ---
    # Fark, pencerenin fiyat aralığına göre 0-1 arası ölçülür; böylece zaman dilimi ve coin'den bağımsızdır.
    max_f = float(df["High"].max())
    min_f = float(df["Low"].min())
    fiyat_fark = max_f - min_f

    rsi_l, rsi_s = 0.0, 0.0
    if fiyat_fark > 0 and not rsi_serisi.isna().all():
        rsi_oran = rsi_anlik / 100.0
        fiyat_konum = (anlik_fiyat - min_f) / fiyat_fark  # 0 = pencere dibi, 1 = pencere tepesi

        if RSI_MODU == "sapma":
            bosluk = abs(rsi_oran - fiyat_konum)
            bonus = max_puan * RSI_SAPMA_TAVAN * bosluk
            if rsi_oran > fiyat_konum:
                rsi_l = bonus
            elif rsi_oran < fiyat_konum:
                rsi_s = bonus
        else:
            rsi_gucu = min(1.0, np.log1p(abs(rsi_anlik - 50.0)) / np.log1p(20.0))
            konum_gucu = min(1.0, abs(fiyat_konum - 0.5) / 0.25)
            bonus = max_puan * RSI_MOMENTUM_TAVAN * min(rsi_gucu, konum_gucu)
            if rsi_oran > 0.5 and fiyat_konum > 0.5:
                rsi_l = bonus
            elif rsi_oran < 0.5 and fiyat_konum < 0.5:
                rsi_s = bonus
    else:
        fark_rsi = abs(rsi_anlik - 50.0)
        rsi_log_carpan = min(1.0, np.log1p(fark_rsi) / np.log1p(20.0))
        max_rsi_bonus = max_puan * 0.03
        rsi_l = max_rsi_bonus * rsi_log_carpan if rsi_anlik > 50 else 0.0
        rsi_s = max_rsi_bonus * rsi_log_carpan if rsi_anlik < 50 else 0.0

    fib_l, fib_s = 0.0, 0.0
    if fiyat_fark > 0:
        fib_050 = min_f + (fiyat_fark * 0.5)
        fib_618 = min_f + (fiyat_fark * 0.618)
        mesafe_050 = abs(anlik_fiyat - fib_050) / fiyat_fark
        mesafe_618 = abs(anlik_fiyat - fib_618) / fiyat_fark
        min_mesafe = min(mesafe_050, mesafe_618)
        if min_mesafe < 0.05:
            yaklasim = (0.05 - min_mesafe) / 0.05
            fib_log_carpan = np.log1p(yaklasim * 10) / np.log1p(10)
            max_fib_bonus = max_puan * 0.03
            if anlik_fiyat >= anlik_ema:
                fib_l = max_fib_bonus * fib_log_carpan
            else:
                fib_s = max_fib_bonus * fib_log_carpan

    final_long = baz_long_puan + ema_l + rsi_l + fib_l
    final_short = baz_short_puan + ema_s + rsi_s + fib_s

    grup_toplam = final_long + final_short
    if grup_toplam > 0 and grup_toplam > max_puan:
        final_long = (final_long / grup_toplam) * max_puan
        final_short = (final_short / grup_toplam) * max_puan

    y_adet = len(df[df["Body"] > 0])
    k_adet = len(df[df["Body"] < 0])
    return round(final_long, 2), round(final_short, 2), y_adet, k_adet


def matris_puani_hesapla(sembol):
    """(nihai_puan, yon) döner. Veri eksikse None döner (sahte sinyal üretmemek için)."""
    sembol_istek = sembol if sembol != "TOTAL" else "BTC/USDT"
    dilimler = [
        (kline_cek_binance(sembol_istek, "15m", 64), 9.5),
        (kline_cek_binance(sembol_istek, "5m", 96), 15.5),
        (kline_cek_binance(sembol_istek, "5m", 48), 50.0),
        (kline_cek_binance(sembol_istek, "1m", 120), 15.5),
        (kline_cek_binance(sembol_istek, "1m", 60), 9.5),
    ]
    if any(df.empty or len(df) < 10 for df, _ in dilimler):
        return None

    long_toplam = short_toplam = 0.0
    for df, max_puan in dilimler:
        sl, ss, _, _ = oransal_matris_ve_teknik_faktorler_hesapla(df, max_puan)
        long_toplam += sl
        short_toplam += ss

    nihai_long, nihai_short = round(long_toplam, 2), round(short_toplam, 2)
    esik = aktif_min_puan_esigi_getir()
    if nihai_long >= esik:
        return nihai_long, "Long"
    if nihai_short >= esik:
        return nihai_short, "Short"
    return round(max(nihai_long, nihai_short), 2), ("Long" if nihai_long >= nihai_short else "Short")


def asama_durumu(puan):
    """(5. aşama mı, 6. aşama mı)"""
    if not hafta_sonu_mu():
        return (70.00 <= puan < 73.75), (puan >= 73.75)
    return (75.00 <= puan < 78.75), (puan >= 78.75)


# ----------------------------------------------------------------------------
# GOOGLE SHEETS
# ----------------------------------------------------------------------------
_spreadsheet = None


def spreadsheet_ac():
    global _spreadsheet
    if _spreadsheet is not None:
        return _spreadsheet
    try:
        if "GCP_SERVICE_ACCOUNT_JSON" in os.environ:
            sec = json.loads(os.environ["GCP_SERVICE_ACCOUNT_JSON"])
            if "private_key" in sec:
                sec["private_key"] = sec["private_key"].replace(r"\n", "\n")
            client = gspread.service_account_from_dict(sec)
        else:
            client = gspread.service_account(filename="credentials.json")
        _spreadsheet = client.open(GOOGLE_SHEET_DOSYA)
        return _spreadsheet
    except Exception as e:
        print(f"GSheets bağlantı hatası: {e}")
        return None


def google_sheets_baglan(sayfa_adi):
    ss = spreadsheet_ac()
    if ss is None:
        return None
    try:
        return ss.worksheet(sayfa_adi)
    except Exception as e:
        print(f"GSheets sayfa hatası ({sayfa_adi}): {e}")
        return None


def sayi_cevir(deger):
    """Sheets'ten gelen metni sayıya çevirir. Türkçe biçimi destekler:
    '81.690,44' -> 81690.44 | '-4,29' -> -4.29 | '81106,51' -> 81106.51 | '200' -> 200.0
    Çevrilemezse NaN döner."""
    t = str(deger).strip().replace(" ", "").replace("\u00a0", "").replace("$", "")
    if not t:
        return float("nan")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1 or re.fullmatch(r"-?\d{1,3}\.\d{3}", t):
        t = t.replace(".", "")  # binlik ayracı
    try:
        return float(t)
    except ValueError:
        return float("nan")


def islem_gecmisi_getir():
    kolonlar = [
        "Islem_ID", "Acilis_Zamani", "Coin", "Yon", "Zaman_Dilimi",
        "Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Beklenen_Kar",
        "Matris_Puan_RH", "Olasi_Stop", "Durum", "Net_Kar_Zarar",
        "Guncel_Kasa", "Kapanis_Zamani", "Kapanis_Fiyati",
    ]
    sheet = google_sheets_baglan("KriptoPortfoyVeritabani")
    if sheet is None:
        return None
    try:
        ham = sheet.get_all_values()
    except Exception as e:
        print(f"İşlem geçmişi okunamadı: {e}")
        return None
    if not ham or len(ham) < 2:
        return pd.DataFrame(columns=kolonlar)

    satirlar = []
    for s in ham[1:]:
        s = list(s)
        s.extend([""] * (len(kolonlar) - len(s)))
        satirlar.append(s[: len(kolonlar)])

    df = pd.DataFrame(satirlar, columns=kolonlar)
    df = df[df["Islem_ID"].notna() & (df["Islem_ID"] != "") & (df["Islem_ID"].astype(str) != "Islem_ID")]
    df["Islem_ID"] = pd.to_numeric(df["Islem_ID"], errors="coerce").fillna(0).astype(int)
    for col in ["Giris_Fiyat", "Islem_Miktari", "Stop", "Kar_Al", "Beklenen_Kar",
                "Olasi_Stop", "Net_Kar_Zarar", "Guncel_Kasa", "Kapanis_Fiyati"]:
        df[col] = df[col].map(sayi_cevir).fillna(0.0).astype(float)
    return df


def dataframe_guncelle_gsheets(df):
    """Başarılıysa True döner."""
    sheet = google_sheets_baglan("KriptoPortfoyVeritabani")
    if sheet is None:
        return False
    try:
        df = df.copy()
        df["Islem_ID"] = df["Islem_ID"].astype(int)
        df = df.sort_values(by="Islem_ID").reset_index(drop=True)
        sheet.update([df.columns.tolist()] + df.values.tolist())
        return True
    except Exception as e:
        print(f"GSheets güncelleme hatası: {e}")
        return False


def kasa_defteri_oku():
    sheet = google_sheets_baglan("KasaDefteri")
    if sheet is None:
        return None
    try:
        return sheet.get_all_values()
    except Exception as e:
        print(f"Kasa defteri okunamadı: {e}")
        return None


def _defter_id_oku(deger):
    try:
        return int(float(str(deger).replace(".", "").replace(",", ".")))
    except Exception:
        return None


def kasa_islem_ekle_deftere(islem_turu, tutar, aciklama):
    """Başarılıysa True döner. Yalnızca satır EKLER (silip baştan yazmaz); geçici hatalarda 3 deneme yapar."""
    for no in range(1, 4):
        sheet = google_sheets_baglan("KasaDefteri")
        if sheet is not None:
            try:
                ham = sheet.get_all_values()
                idler = [i for i in (_defter_id_oku(s[0]) for s in ham[1:] if s) if i is not None]
                yeni_id = (max(idler) if idler else 0) + 1
                sheet.append_row([yeni_id, tr_zaman().strftime("%d.%m.%Y %H:%M"), islem_turu, round(float(tutar), 4), aciklama])
                return True
            except Exception as e:
                print(f"Kasa defteri kayıt hatası (deneme {no}/3): {e}")
        if no < 3:
            time.sleep(3 * no)
    return False


KAPANIS_ETIKETLERI = ("Hedef Kâr", "Otomatik Stop", "Trade K/Z")


def kapanis_defterde_var(islem_id):
    """Aynı işlemin tam kapanışı deftere daha önce yazıldı mı? (panel ve motor çift işlemesin)"""
    sheet = google_sheets_baglan("KasaDefteri")
    if sheet is None:
        return False
    try:
        for s in sheet.get_all_values()[1:]:
            if len(s) >= 5 and s[2] == "Trade_Sonuc":
                if any(str(s[4]).startswith(f"{e}: #{islem_id} ") for e in KAPANIS_ETIKETLERI):
                    return True
    except Exception as e:
        print(f"Kapanış kontrolü okunamadı: {e}")
    return False


def kapanis_deftere_yaz_tekil(islem_id, etiket, coin, tutar):
    """Kapanış kaydı zaten varsa yazmaz (True döner). Yoksa yazar."""
    if kapanis_defterde_var(islem_id):
        print(f"#{islem_id} kapanışı defterde zaten var, tekrar yazılmadı.")
        return True
    return kasa_islem_ekle_deftere("Trade_Sonuc", float(round(tutar, 2)), f"{etiket}: #{islem_id} {coin}")


def bakiye_hesapla(df_trade):
    """Panelle aynı mantık: başlangıç + defter toplamı (+ defterde eksik kalan kapanış farkı).
    Giriş komisyonları defterde 'Komisyon' satırı olarak zaten düşülmüştür."""
    toplam = BASLANGIC_BAKIYE
    ham = kasa_defteri_oku()
    trade_sonuc_defterde = 0.0
    if ham:
        for s in ham[1:]:
            if len(s) >= 4:
                tutar = sayi_cevir(s[3])
                if tutar == tutar:  # NaN değilse
                    toplam += tutar
                    if len(s) > 2 and s[2] == "Trade_Sonuc":
                        trade_sonuc_defterde += tutar
    if df_trade is not None and not df_trade.empty:
        kap = df_trade[durum_kapali_maskesi(df_trade["Durum"])]
        gercek = float(pd.to_numeric(kap["Net_Kar_Zarar"], errors="coerce").fillna(0.0).sum())
        if abs(gercek - trade_sonuc_defterde) > 1e-9:
            toplam += gercek - trade_sonuc_defterde
    return float(toplam)


# ----------------------------------------------------------------------------
# MAIL DURUMU (Google Sheets - "MailDurumu" sayfası)
# ----------------------------------------------------------------------------
class MailDurumu:
    BASLIK = ["Anahtar", "Aktif", "SonMailZamani"]

    def __init__(self):
        self.sheet = None
        self.veri = {}
        self.ilk_calisma = False
        self.hazir = False

    def yukle(self):
        ss = spreadsheet_ac()
        if ss is None:
            return False
        try:
            try:
                self.sheet = ss.worksheet(MAIL_DURUM_SAYFASI)
            except gspread.WorksheetNotFound:
                self.sheet = ss.add_worksheet(title=MAIL_DURUM_SAYFASI, rows=1000, cols=3)
                self.sheet.update([self.BASLIK])
                self.ilk_calisma = True
            for satir in self.sheet.get_all_values()[1:]:
                if satir and satir[0]:
                    satir = satir + [""] * (3 - len(satir))
                    self.veri[satir[0]] = {"aktif": 1 if str(satir[1]).strip() == "1" else 0, "son": satir[2]}
            self.hazir = True
            return True
        except Exception as e:
            print(f"MailDurumu yüklenemedi: {e}")
            return False

    def kaydet(self):
        try:
            satirlar = [self.BASLIK] + [[k, v["aktif"], v["son"]] for k, v in self.veri.items()]
            if len(satirlar) + 20 > self.sheet.row_count:
                self.sheet.resize(rows=len(satirlar) + 200, cols=3)
            self.sheet.update(satirlar)
            return True
        except Exception as e:
            print(f"MailDurumu kaydedilemedi: {e}")
            return False

    def al(self, anahtar):
        return self.veri.get(anahtar, {"aktif": 0, "son": ""})

    def ayarla(self, anahtar, aktif, son=None):
        mevcut = self.al(anahtar)
        self.veri[anahtar] = {"aktif": aktif, "son": mevcut["son"] if son is None else son}

    def dakika_gecti_mi(self, anahtar, dakika):
        son = self.al(anahtar)["son"]
        if not son:
            return True
        try:
            return tr_zaman() - datetime.fromisoformat(son) >= timedelta(minutes=dakika)
        except Exception:
            return True


# ----------------------------------------------------------------------------
# 1) İŞLEM KAPATMA (stop / kâr hedefi)
# ----------------------------------------------------------------------------
def acik_islemleri_kontrol_et():
    df = islem_gecmisi_getir()
    if df is None:
        print("İşlem verisi alınamadı, bu tur atlandı.")
        return
    if df.empty:
        print("Kontrol edilecek işlem yok.")
        return

    suan = tr_zaman().strftime("%d.%m.%Y %H:%M")
    bakiye = bakiye_hesapla(df)
    kapananlar = []  # (islem_id, coin, etiket, net_kar)

    for idx, row in df.iterrows():
        if durum_kapali_mi(row["Durum"]):
            continue

        islem_id, coin, yon = int(row["Islem_ID"]), row["Coin"], str(row["Yon"])
        giris, stop_f, kar_al_f, miktar = float(row["Giris_Fiyat"]), float(row["Stop"]), float(row["Kar_Al"]), float(row["Islem_Miktari"])

        # Bozuk/boş satır (sayıya çevrilemeyen değerler 0'a düşer) tüm motoru çökertmesin
        if giris <= 0 or stop_f <= 0 or kar_al_f <= 0 or miktar <= 0 or not str(coin).strip():
            print(f"UYARI: #{islem_id} satırı atlandı (geçersiz değer): Coin='{coin}' Durum='{row['Durum']}' "
                  f"Giris={row['Giris_Fiyat']} Stop={row['Stop']} Kar_Al={row['Kar_Al']} Miktar={row['Islem_Miktari']}. "
                  f"Google Sheets'te bu satırı kontrol edin.")
            continue

        anl_f = fiyat_cek_binance(coin)
        if anl_f is None:
            print(f"#{islem_id} {coin}: fiyat alınamadı, atlandı.")
            continue

        print(f"#{islem_id} {coin} {yon}: fiyat={anl_f:,.4f} | giris={giris:,.4f} stop={stop_f:,.4f} hedef={kar_al_f:,.4f} miktar={miktar:,.2f}")
        kapat, hedef, kapanis = False, False, 0.0
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
        brut_kar = miktar * KALDIRAC * fark
        # Giriş komisyonu açılışta kasadan zaten düşüldü; çıkış komisyonu burada düşülür.
        net_kar = brut_kar - cikis_komisyonu(miktar, hedef)
        df.at[idx, "Durum"] = "Kapandi (Kar)" if hedef else "Kapandi (Zarar)"
        df.at[idx, "Kapanis_Zamani"] = suan
        df.at[idx, "Net_Kar_Zarar"] = float(round(net_kar, 2))
        df.at[idx, "Kapanis_Fiyati"] = float(round(kapanis, 4))
        bakiye += net_kar
        df.at[idx, "Guncel_Kasa"] = float(round(bakiye, 2))
        kapananlar.append((islem_id, coin, "Hedef Kâr" if hedef else "Otomatik Stop", net_kar))

    if not kapananlar:
        print("Kapatılması gereken yeni işlem yok.")
        return

    if not dataframe_guncelle_gsheets(df):
        print("İşlem tablosu yazılamadı; kapanışlar sonraki tura bırakıldı.")
        return

    for islem_id, coin, etiket, net_kar in kapananlar:
        ok = kapanis_deftere_yaz_tekil(islem_id, etiket, coin, net_kar)
        if not ok:
            print(f"UYARI: #{islem_id} kasa defterine yazılamadı (panel bakiyeyi kendisi düzeltir); mail yine de gönderilecek.")
    print(f"{len(kapananlar)} işlem kapatıldı.")


# ----------------------------------------------------------------------------
# 2) KAPANIŞ MAİLLERİ
# ----------------------------------------------------------------------------
def _fiyat_esit(a, b):
    return abs(a - b) <= max(1e-4, abs(b) * 1e-6)


def kapanis_maillerini_gonder(durum):
    """Kaynak: işlem tablosu (KasaDefteri'ne bağlı değil). Böylece kasa kaydı yazılamasa
    bile otomatik kapanan her işlem için, mail gidene kadar her turda yeniden denenir."""
    df_trade = islem_gecmisi_getir()
    if df_trade is None or df_trade.empty:
        return
    sinir = tr_zaman() - timedelta(hours=KAPANIS_PENCERESI_SAAT)
    degisti = False

    for _, r in df_trade.iterrows():
        d = str(r["Durum"]).translate(_TR_ASCII).lower()
        if "kapandi" not in d or "kismi" in d:
            continue

        zaman_str = str(r["Kapanis_Zamani"]).strip()
        try:
            zaman = TR_TZ.localize(datetime.strptime(zaman_str, "%d.%m.%Y %H:%M"))
        except Exception:
            continue
        if zaman < sinir:
            continue

        # Otomatik kapanış = kapanış fiyatı stop veya kâr hedefiyle aynı (manuel kapanışlara mail atılmaz)
        kapanis_f = float(r["Kapanis_Fiyati"])
        if _fiyat_esit(kapanis_f, float(r["Kar_Al"])):
            etiket = "Hedef Kâr"
        elif _fiyat_esit(kapanis_f, float(r["Stop"])):
            etiket = "Otomatik Stop"
        else:
            continue

        islem_id, coin = int(r["Islem_ID"]), str(r["Coin"])
        anahtar = f"kapanis|{islem_id}"
        if durum.al(anahtar)["aktif"] == 1:
            continue

        if durum.ilk_calisma:
            durum.ayarla(anahtar, 1, tr_zaman().isoformat())
            degisti = True
            continue

        net_kar = float(r["Net_Kar_Zarar"])
        kasa = f"{float(r['Guncel_Kasa']):,.2f} $"
        sonuc = "Kar" if etiket == "Hedef Kâr" else "Zarar"
        konu = f"⚡ {etiket}: #{islem_id} {coin} (Kapandi ({sonuc}))"
        icerik = (
            f"<h3>İşlem Otomatik Kapatıldı</h3>"
            f"<p><b>Zaman:</b> {zaman_str}</p><p><b>Coin:</b> {coin}</p><p><b>Yön:</b> {r['Yon']}</p>"
            f"<p><b>Sebep:</b> {etiket}</p><p><b>Net K/Z:</b> {net_kar:,.2f} $</p>"
            f"<p><b>Güncel Kasa:</b> {kasa}</p>"
        )
        if bildirim_gonder(konu, icerik):
            durum.ayarla(anahtar, 1, tr_zaman().isoformat())
            degisti = True
            durum.kaydet()

    if degisti:
        durum.kaydet()


# ----------------------------------------------------------------------------
# 3) SİNYAL MAİLLERİ (5. ve 6. aşama)
# ----------------------------------------------------------------------------
def sinyal_maillerini_gonder(durum):
    degisti = False
    for sembol in COINLER + ["TOTAL"]:
        if time.time() - _T0 > ZAMAN_BUTCESI_SN:
            print("Zaman bütçesi doldu; kalan sinyal taraması sonraki tura bırakıldı.")
            break
        sonuc = matris_puani_hesapla(sembol)
        if sonuc is None:
            print(f"{sembol}: veri eksik, sinyal kontrolü atlandı.")
            continue
        puan, yon = sonuc
        a5, a6 = asama_durumu(puan)
        fiyat = fiyat_cek_binance(sembol) if sembol != "TOTAL" else None

        for asama, sart, baslik, konu_on in (
            (5, a5, "Çok Güçlü Trende Ulaşıldı!", "🔥🔥 Çok Güçlü Trend Sinyali (5. Aşama)"),
            (6, a6, "6. Aşama Zirveye Ulaşıldı!", "🔥🔥🔥 Zirve Sinyali (6. Aşama - Boğa/Ayı Vuruşu)"),
        ):
            anahtar = f"asama{asama}|{sembol}"
            mevcut = durum.al(anahtar)

            if not sart:
                if mevcut["aktif"] == 1:
                    durum.ayarla(anahtar, 0)
                    degisti = True
                continue

            if mevcut["aktif"] == 1:
                continue

            if durum.ilk_calisma:
                durum.ayarla(anahtar, 1, tr_zaman().isoformat())
                degisti = True
                continue

            if not durum.dakika_gecti_mi(anahtar, SINYAL_BEKLEME_DK):
                print(f"{sembol} {asama}. aşama: bekleme süresi dolmadı.")
                continue

            konu = f"{konu_on}: {sembol} (Puan: {puan:.1f})"
            fiyat_satir = f"<p><b>Fiyat:</b> {fiyat:,.4f} $</p>" if fiyat else ""
            icerik = (
                f"<h3>{baslik}</h3><p><b>Zaman:</b> {tr_zaman().strftime('%d.%m.%Y %H:%M')}</p>"
                f"<p><b>Sembol/Coin:</b> {sembol}</p>{fiyat_satir}"
                f"<p><b>Matris Puanı:</b> {puan:.1f} / 100</p><p><b>Yön:</b> {yon}</p>"
                f"<p><b>Mod:</b> {'Hafta sonu' if hafta_sonu_mu() else 'Hafta içi'}</p>"
            )
            if bildirim_gonder(konu, icerik):
                durum.ayarla(anahtar, 1, tr_zaman().isoformat())
                durum.kaydet()
                degisti = True

    if degisti:
        durum.kaydet()


# ----------------------------------------------------------------------------
def motoru_calistir():
    print(f"Trade Kontrol Motoru başladı: {tr_zaman().strftime('%d.%m.%Y %H:%M:%S')} "
          f"({'hafta sonu' if hafta_sonu_mu() else 'hafta içi'} modu)")

    if os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
        ok = telegram_bildirim_gonder(
            "✅ Bot test mesajı",
            f"<p>Trade kontrol motoru elle çalıştırıldı.</p><p>Zaman: {tr_zaman().strftime('%d.%m.%Y %H:%M')}</p>",
        )
        print("Telegram test mesajı:", "gönderildi" if ok else "GÖNDERİLEMEDİ (secret'ları kontrol edin)")

    try:
        acik_islemleri_kontrol_et()
    except Exception as e:
        # Bir hata kapanış/sinyal maillerini engellemesin
        import traceback
        print(f"HATA: acik_islemleri_kontrol_et çöktü, mail aşamasına devam ediliyor: {type(e).__name__}: {e}")
        traceback.print_exc()

    durum = MailDurumu()
    if not durum.yukle():
        print("MailDurumu yüklenemedi; mailler bu tur gönderilmedi (tekrar mail olmaması için).")
        return
    if durum.ilk_calisma:
        print("İlk çalışma: mevcut durumlar mail atılmadan kaydedilecek.")

    for adim in (kapanis_maillerini_gonder, sinyal_maillerini_gonder):
        try:
            adim(durum)
        except Exception as e:
            import traceback
            print(f"HATA: {adim.__name__} çöktü: {type(e).__name__}: {e}")
            traceback.print_exc()

    if durum.ilk_calisma:
        durum.kaydet()
    print("Tamamlandı.")


if __name__ == "__main__":
    motoru_calistir()
