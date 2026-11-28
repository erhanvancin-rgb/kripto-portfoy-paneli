"""
Matris puanlama motoru: panel (panel_v2.py) ve GitHub motoru (check_engine.py) AYNI hesabı kullanır.

Süre      | Ağırlık | Mum aralığı | Puanlanan mum sayısı
8 Saat    |   7%    | 15 dakika   | 32
4 Saat    |  18%    |  5 dakika   | 48
2 Saat    |  40%    |  5 dakika   | 24
1 Saat    |  22%    |  5 dakika   | 12
30 Dakika |  13%    |  3 dakika   | 10

ISINMA: EMA (9/20/50), RSI ve ATR yalnızca pencerenin kendi mumlarıyla hesaplanırsa oturmaz (ör. 30 mumda EMA50 anlamsızdır).
Bu yüzden her aralıkta puanlanan mumların ÖNCESİNDE ISITMA_MUM kadar ek geçmiş mum çekilir; EMA/RSI/ATR bu uzun seriyle
hesaplanır, gövde/fibonacci/mıknatıs/verimlilik ise yalnızca son N (puanlanan) mumdan çıkarılır.

TOTAL (Top 5) puanı BTC mumlarıyla değil, 5 coinin piyasa değeri ağırlıklı endeksiyle (Σ arz × fiyat) hesaplanır.

Her süre penceresi için 6 kanıt üretilir (her biri -1 = Short ... +1 = Long):
  1) Mum gövdesi baskınlığı      (yeşil/kırmızı gövde büyüklükleri)
  2) EMA etkisi                   (fiyatın EMA20'ye konumu, EMA20 eğimi, EMA9/20/50 dizilimi)
  3) RSI etkisi                   (seviye + ivme, aşırı bölgede yorgunluk cezası)
  4) Fibonacci olası yön          (son bacak yönü + geri çekilme derinliği: sığ geri çekilme = devam)
  5) Fiyatın manyetik çekimi      (fibonacci seviyeleri + EMA20/50 mıknatıs; yakın olan daha çok çeker)
  6) Trend verimliliği            (net yer değiştirme / toplam yol: düz gidişat güçlü, testere gibi hareket zayıf trenddir)

Karar yapısı (her pencere):
  ANA YÖN   = gövde baskınlığı + trend verimliliği (net hareketin yönü)
  TEYİTÇİ   = EMA, RSI, Fibonacci yönü, manyetik çekim: ana yönü destekliyorsa puan güçlenir (çarpan en çok 1,5),
              çelişiyorsa zayıflar (çarpan en az 0,35)
  KAPI      = trend verimliliği düşükse (testere / yatay) puan 50'ye çekilir
Çoklu süre teyidi: baskın yönü destekleyen sürelerin ağırlık toplamı büyükse tüm pencereler güçlenir.
"""
import numpy as np
import pandas as pd

# ------------------------------------------------------------------ AYARLAR (YENİ İNTRADAY SWING KURGUSU)
DILIMLER = [
    # (etiket, mum aralığı, PUANLANAN mum sayısı, ağırlık) - toplam ağırlık 100
    ("8 Saat", "15m", 32, 7.0),
    ("4 Saat", "5m", 48, 18.0),
    ("2 Saat", "5m", 24, 40.0),
    ("1 Saat", "5m", 12, 22.0),
    ("30 Dakika", "3m", 10, 13.0),
]
# EMA50'nin ~%98 oturması için puanlanan mumların öncesine eklenen geçmiş mum sayısı (EMA/RSI/ATR için)
ISITMA_MUM = 100

# Top 5 piyasa değeri endeksi için dolaşımdaki arz (Σ arz × fiyat = Top 5 toplam piyasa değeri)
TOP5_ARZ = {
    "BTC/USDT": 19_700_000,
    "ETH/USDT": 120_000_000,
    "BNB/USDT": 145_000_000,
    "SOL/USDT": 470_000_000,
    "XRP/USDT": 5_700_000_000,
}

# ANA YÖN: net hareketin yönünü belirleyen kanıtlar (gövde baskınlığı + trend verimliliği)
ANA_AGIRLIK = {"govde": 0.6, "trend": 0.4}
# TEYİTÇİLER: Vur-kaç mantığına göre momentum odaklı esnetilmiş ağırlıklar
TEYITCI_AGIRLIK = {"ema": 0.40, "rsi": 0.40, "fib": 0.10, "mik": 0.10}

TEYIT_K = 1.2                 # teyit çarpanı = 1 + K x (teyitçilerin ana yönle uyumu, -1..+1)
TEYIT_MIN, TEYIT_MAX = 0.35, 1.5
VERIMLILIK_TAM = 0.35         # bu verimlilikte trend kanıtı tam güce ulaşır (Kaufman verimlilik oranı)
VERIMLILIK_KAPI = 0.40        # bu verimlilikten düşük (testere) pencerelerde puan 50'ye çekilir
KAPI_TABAN = 0.30             # verimlilik sıfırken puan çarpanı

AKTIF_KANIT_ESIGI = 0.15      # bir teyitçinin "oy kullanmış" sayılması için asgari güç
KESINLIK = 0.5                # tanh dikliği: büyüdükçe puan 50'den daha hızlı uzaklaşır
MTF_TABAN, MTF_ARTIS = 0.75, 0.50   # çoklu süre çarpanı = 0,75 + 0,50 x uyum (uyum 0..1)

EMA_KONUM_OLCEK = 1.5         # (fiyat - EMA20) / ATR bu değerde tanh ~0,76
EMA_EGIM_OLCEK = 3.0          # EMA20'nin k mumdaki değişimi / ATR
RSI_SEVIYE_OLCEK = 20.0
RSI_IVME_OLCEK = 12.0
MIKNATIS_OLCEK = 0.6

# Geri çekilme derinliği -> devam gücü
FIB_DEVAM = [(0.0, 1.0), (0.236, 1.0), (0.382, 0.8), (0.5, 0.5), (0.618, 0.2), (0.786, -0.3), (1.0, -0.8)]
FIB_SEVIYELER = (0.236, 0.382, 0.5, 0.618, 0.786)
MIKNATIS_KUTLE = {"hi": 0.7, "lo": 0.7, 0.236: 0.6, 0.382: 0.8, 0.5: 1.0, 0.618: 1.0, 0.786: 0.6, "ema20": 1.0, "ema50": 0.8}


# ------------------------------------------------------------------ R/R (ÇAN EĞRİSİ) SEÇİCİ
# Puan -> (stop %, hedef %) fiyat mesafesi. 75 puan merkezdir.
# Bu değerler sermaye riski değildir; pozisyon büyüklüğü ayrıca risk_kapasitesi() ile sınırlanır.
RISK_HEDEF_ANCHORS = ((50.0, 0.30, 0.40), (75.0, 0.45, 0.65), (100.0, 0.25, 0.30))

def _oran_sec(puan):
    """Puanı 50-100 bandında doğrusal ara değerleyerek stop/hedef yüzdesi döndürür."""
    p = float(np.clip(float(puan), 50.0, 100.0))
    xs = [x[0] for x in RISK_HEDEF_ANCHORS]
    stops = [x[1] for x in RISK_HEDEF_ANCHORS]
    targets = [x[2] for x in RISK_HEDEF_ANCHORS]
    return float(np.interp(p, xs, stops)), float(np.interp(p, xs, targets))


# ------------------------------------------------------------------ YARDIMCILAR
def _tanh(x):
    return float(np.tanh(x))


def _kenet(x, alt=-1.0, ust=1.0):
    return float(min(ust, max(alt, x)))


def _atr(df, n=14):
    h, l, c = df["High"].astype(float), df["Low"].astype(float), df["Close"].astype(float)
    onceki = c.shift(1)
    tr = pd.concat([(h - l), (h - onceki).abs(), (l - onceki).abs()], axis=1).max(axis=1)
    atr = float(tr.rolling(n, min_periods=1).mean().iloc[-1])
    if not np.isfinite(atr) or atr <= 0:
        atr = max(float(c.iloc[-1]) * 1e-4, 1e-12)
    return atr


def _rsi(close, n=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=n, min_periods=n).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=n, min_periods=n).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.where(~((loss == 0) & (gain > 0)), 100.0)
    return rsi


def _parcali(x, noktalar):
    xs, ys = [p[0] for p in noktalar], [p[1] for p in noktalar]
    return float(np.interp(x, xs, ys))


# ------------------------------------------------------------------ PENCERE ANALİZİ
def pencere_analiz(df, n_skor=None):
    nötr = {"govde": 0.0, "ema": 0.0, "rsi": 0.0, "fib": 0.0, "mik": 0.0, "trend": 0.0}
    gerekli = ("Open", "High", "Low", "Close")
    if df is None or len(df) < 10 or any(c not in df.columns for c in gerekli):
        return {"s": nötr.copy(), "y_adet": 0, "k_adet": 0,
                "detay": {"veri_gecerli": False, "veri_nedeni": "Eksik sütun veya 10'dan az mum"}}
    tam = df.copy().reset_index(drop=True)
    for c in gerekli:
        tam[c] = pd.to_numeric(tam[c], errors="coerce")
    tam = tam.dropna(subset=list(gerekli)).reset_index(drop=True)
    if len(tam) < 10 or not np.isfinite(tam[list(gerekli)].to_numpy(dtype=float)).all():
        return {"s": nötr.copy(), "y_adet": 0, "k_adet": 0,
                "detay": {"veri_gecerli": False, "veri_nedeni": "Geçerli OHLC mum sayısı yetersiz"}}
    d = tam.tail(int(n_skor)).reset_index(drop=True) if (n_skor and len(tam) > int(n_skor)) else tam
    if len(d) < 3:
        return {"s": nötr.copy(), "y_adet": 0, "k_adet": 0,
                "detay": {"veri_gecerli": False, "veri_nedeni": "Puanlama penceresi 3 mumdan kısa"}}
    op, hi, lo, cl = (d[c].astype(float) for c in gerekli)
    cl_tam = tam["Close"].astype(float)
    n = len(d)
    fiyat = float(cl.iloc[-1])
    atr = _atr(tam)

    govde = cl - op
    yesil, kirmizi = float(govde[govde > 0].sum()), float(-govde[govde < 0].sum())
    toplam = yesil + kirmizi
    s_govde = ((yesil - kirmizi) / toplam) if toplam > 0 else 0.0

    e7, e14, e21 = (cl_tam.ewm(span=s, adjust=False).mean() for s in (7, 14, 21))
    ema7, ema14, ema21 = float(e7.iloc[-1]), float(e14.iloc[-1]), float(e21.iloc[-1])
    k = max(3, min(10, n // 5))
    s_konum = _tanh(((fiyat - ema14) / atr) / EMA_KONUM_OLCEK)
    s_egim = _tanh((float(e14.iloc[-1]) - float(e14.iloc[-1 - k])) / atr / EMA_EGIM_OLCEK)
    s_dizilim = 0.6 * np.sign(ema7 - ema14) + 0.4 * np.sign(ema14 - ema21)
    s_ema = 0.35 * s_konum + 0.30 * s_egim + 0.35 * s_dizilim

    rsi = _rsi(cl_tam)
    rsi_gecerli = rsi.dropna()
    if len(rsi_gecerli) >= 1:
        rsi_now = float(rsi_gecerli.iloc[-1])
        rsi_prev = float(rsi_gecerli.iloc[-6]) if len(rsi_gecerli) > 5 else float(rsi_gecerli.iloc[0])
    else:
        rsi_now = rsi_prev = 50.0
    s_seviye = _kenet((rsi_now - 50.0) / RSI_SEVIYE_OLCEK)
    s_ivme = _kenet((rsi_now - rsi_prev) / RSI_IVME_OLCEK)
    asiri = 0.0
    if rsi_now > 80:
        asiri = -0.3 * (rsi_now - 80.0) / 20.0
    elif rsi_now < 20:
        asiri = 0.3 * (20.0 - rsi_now) / 20.0
    s_rsi = _kenet(0.65 * s_seviye + 0.35 * s_ivme + asiri)

    en_yuksek, en_dusuk = float(hi.max()), float(lo.min())
    aralik = en_yuksek - en_dusuk
    i_hi, i_lo = int(np.argmax(hi.values)), int(np.argmin(lo.values))
    s_fib, geri_cekilme, bacak = 0.0, None, 0
    if aralik > 0 and i_hi != i_lo:
        bacak = 1 if i_lo < i_hi else -1
        geri_cekilme = _kenet(((en_yuksek - fiyat) if bacak == 1 else (fiyat - en_dusuk)) / aralik, 0.0, 1.0)
        olcek = min(1.0, max(0.35, aralik / (atr * 8.0)))
        s_fib = bacak * _parcali(geri_cekilme, FIB_DEVAM) * olcek

    mikn = {"hi": en_yuksek, "lo": en_dusuk, "ema20": ema14, "ema50": ema21}
    if aralik > 0:
        for f in FIB_SEVIYELER:
            mikn[f] = en_dusuk + aralik * f
    toplam_cekim, net_cekim = 0.0, 0.0
    for ad, seviye in mikn.items():
        mesafe = abs(seviye - fiyat) / atr
        if mesafe < 0.15:
            continue
        g = MIKNATIS_KUTLE[ad] / (1.0 + mesafe) ** 2
        toplam_cekim += g
        net_cekim += g * (1.0 if seviye > fiyat else -1.0)
    s_mik = (net_cekim / toplam_cekim) * _tanh(toplam_cekim / MIKNATIS_OLCEK) if toplam_cekim > 0 else 0.0

    yol = float(cl.diff().abs().sum())
    net_hareket = float(cl.iloc[-1] - cl.iloc[0])
    verimlilik = (abs(net_hareket) / yol) if yol > 0 else 0.0
    s_trend = float(np.sign(net_hareket)) * min(1.0, verimlilik / VERIMLILIK_TAM)
    return {
        "s": {"govde": s_govde, "ema": s_ema, "rsi": s_rsi, "fib": s_fib, "mik": s_mik, "trend": s_trend},
        "y_adet": int((govde > 0).sum()), "k_adet": int((govde < 0).sum()),
        "detay": {"rsi": rsi_now, "atr": atr, "geri_cekilme": geri_cekilme, "bacak": bacak,
                  "ema7": ema7, "ema14": ema14, "ema21": ema21, "verimlilik": verimlilik,
                  "veri_gecerli": True, "mum_sayisi": len(tam), "skorlanan_mum": len(d)},
    }


def pencere_pay(analiz, guclu_trend=False):
    s = analiz["s"]
    s_ana = sum(ANA_AGIRLIK[k] * s[k] for k in ANA_AGIRLIK)
    # Ana yön kanıtları birbirini götürüyorsa teyitçilerden zayıf yön çıkar.
    # Bu fallback, gövde/trend yönü belirginken onların ağırlığını değiştirmez.
    if abs(s_ana) < 0.035:
        yedek_agirlik = {"ema": 0.45, "rsi": 0.30, "fib": 0.15, "mik": 0.10}
        yedek_yon = sum(yedek_agirlik[k] * s[k] for k in yedek_agirlik)
        if abs(yedek_yon) < 0.04:
            return 0.5, 0.0, 0.0
        s_ana = yedek_yon
    yon = float(np.sign(s_ana))
    teyit_agirlik = ({"ema": 0.45, "rsi": 0.30, "fib": 0.20, "mik": 0.05}
                     if guclu_trend else TEYITCI_AGIRLIK)
    a = sum(teyit_agirlik[k] * s[k] * yon for k in teyit_agirlik)
    uyan = sum(1 for k in TEYITCI_AGIRLIK if abs(s[k]) >= AKTIF_KANIT_ESIGI and np.sign(s[k]) == yon)
    uyum = uyan / float(len(TEYITCI_AGIRLIK))
    carpan = _kenet(1.0 + TEYIT_K * a, TEYIT_MIN, TEYIT_MAX)
    verimlilik = analiz.get("detay", {}).get("verimlilik", 0.0)
    kapi = KAPI_TABAN + (1.0 - KAPI_TABAN) * min(1.0, verimlilik / VERIMLILIK_KAPI)
    s_son = s_ana * carpan * kapi
    pay = 0.5 + 0.5 * _tanh(KESINLIK * s_son)
    return float(pay), float(uyum), float(s_ana)


# ------------------------------------------------------------------ MATRİS
def matris_hesapla(pencereler):
    """Verisi geçerli pencereleri ağırlıkları yeniden ölçekleyerek hesaplar; eksik veri nötr oy sayılmaz."""
    analizler = []
    for p_ in pencereler:
        etiket, df, agirlik = p_[0], p_[1], float(p_[2])
        n_skor = p_[3] if len(p_) > 3 else None
        a = pencere_analiz(df, n_skor)
        analizler.append((etiket, agirlik, a))
    gecerli = [(e, w, a) for e, w, a in analizler if a.get("detay", {}).get("veri_gecerli", False)]
    toplam_agirlik = sum(w for _, w, _ in gecerli)
    if not gecerli or toplam_agirlik <= 0:
        return {"nihai_long": 0.0, "nihai_short": 0.0, "katkilar": {
            e: {"sl": 0.0, "ss": 0.0, "y_adet": 0, "k_adet": 0, "pay": 0.5, "uyum": 0.0,
                "kanitlar": a["s"], "detay": a["detay"]} for e, _, a in analizler},
            "mtf_uyum": 0.0, "mtf_carpan": MTF_TABAN, "guclu_trend_modu": False,
            "teyit_modu": "Veri yok", "veri_durumu": "veri_yok", "gecerli_pencere": 0,
            "gecersiz_pencere": len(analizler)}

    analizler = [(e, w / toplam_agirlik, a) for e, w, a in gecerli]
    def birlestir(guclu_trend):
        ara = []
        for etiket, w, a in analizler:
            pay, uyum, s_ham = pencere_pay(a, guclu_trend=guclu_trend)
            ara.append((etiket, w, a, pay, uyum, s_ham))
        l0 = sum(w * pay for _, w, _, pay, _, _ in ara)
        uzun_yon = l0 >= 0.5
        mtf_uyum = sum(w for _, w, _, pay, _, _ in ara if (pay > 0.5 if uzun_yon else pay < 0.5))
        mtf_carpan = MTF_TABAN + MTF_ARTIS * mtf_uyum
        katkilar, long_toplam, short_toplam = {}, 0.0, 0.0
        for etiket, w, a, pay, uyum, s_ham in ara:
            pay2 = _kenet(0.5 + (pay - 0.5) * mtf_carpan, 0.0, 1.0)
            sl, ss = 100.0 * w * pay2, 100.0 * w * (1.0 - pay2)
            long_toplam += sl; short_toplam += ss
            katkilar[etiket] = {"sl": round(sl, 2), "ss": round(ss, 2), "y_adet": a["y_adet"],
                "k_adet": a["k_adet"], "pay": round(pay2, 4), "uyum": round(uyum, 2),
                "kanitlar": {k: round(v, 3) for k, v in a["s"].items()}, "detay": a["detay"]}
        # Veri olmayan zaman dilimlerini ekle; ancak toplam puana ağırlık katkısı yapmazlar.
        for etiket, _, a in analizler_all:
            if etiket not in katkilar:
                katkilar[etiket] = {"sl": 0.0, "ss": 0.0, "y_adet": 0, "k_adet": 0,
                    "pay": 0.5, "uyum": 0.0, "kanitlar": a["s"], "detay": a["detay"]}
        return {"nihai_long": round(long_toplam, 2), "nihai_short": round(short_toplam, 2),
                "katkilar": katkilar, "mtf_uyum": round(mtf_uyum, 3), "mtf_carpan": round(mtf_carpan, 3)}
    analizler_all = analizler[:]
    ilk = birlestir(False)
    guclu_trend = max(ilk["nihai_long"], ilk["nihai_short"]) >= 70.0
    sonuc = birlestir(True) if guclu_trend else ilk
    sonuc["guclu_trend_modu"] = bool(guclu_trend)
    sonuc["teyit_modu"] = "EMA7/14/21 + RSI + Fibonacci ağırlıklı" if guclu_trend else "Standart"
    sonuc["veri_durumu"] = "tam" if len(gecerli) == len(pencereler) else "kismi"
    sonuc["gecerli_pencere"] = len(gecerli)
    sonuc["gecersiz_pencere"] = len(pencereler) - len(gecerli)
    return sonuc


# ------------------------------------------------------------------ TOP 5 ENDEKSİ
def birlesik_endeks(coin_dfleri):
    parcalar = []
    for coin, arz in TOP5_ARZ.items():
        df = coin_dfleri.get(coin)
        if df is None or len(df) == 0:
            return pd.DataFrame()
        parcalar.append(df.set_index("timestamp")[["Open", "High", "Low", "Close"]].astype(float) * float(arz))
    ortak = parcalar[0].index
    for p_ in parcalar[1:]:
        ortak = ortak.intersection(p_.index)
    if len(ortak) == 0:
        return pd.DataFrame()
    toplam = parcalar[0].loc[ortak]
    for p_ in parcalar[1:]:
        toplam = toplam + p_.loc[ortak]
    return toplam.reset_index()


# ------------------------------------------------------------------ STOP / HEDEF DOKUNUŞU
def dokunus_bul(mumlar, long_mi, stop, hedef, baslangic_utc_ms):
    if mumlar is None or len(mumlar) == 0:
        return None
    zs = mumlar["timestamp"]
    if np.issubdtype(zs.dtype, np.number):
        ms = zs.astype("int64").values
    else:
        ms = ((pd.to_datetime(zs, utc=True) - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(milliseconds=1)).values.astype("int64")
    hi = mumlar["High"].astype(float).values
    lo = mumlar["Low"].astype(float).values
    for i in np.argsort(ms):
        if ms[i] <= baslangic_utc_ms:
            continue
        if long_mi:
            stop_vurdu, hedef_vurdu = lo[i] <= stop, hi[i] >= hedef
        else:
            stop_vurdu, hedef_vurdu = hi[i] >= stop, lo[i] <= hedef
        if stop_vurdu:
            return "stop", int(ms[i])
        if hedef_vurdu:
            return "hedef", int(ms[i])
    return None




# ------------------------------------------------------------------ OTOMATIK ISLEM KAPISI + VOLATILITE STOPU
def otomatik_islem_kontrol(df, yon, atr_asiri=2.2, ani_sicrama=2.5, seviye_atr=0.20):
    """Zorunlu giriş filtresi. Veri yetersizse güvenli tarafta kalıp işlemi engeller."""
    nedenler = []
    if df is None or len(df) < 60:
        return {"izin": False, "nedenler": ["Yeterli mum verisi yok (en az 60 mum gerekli)"], "atr": None}
    d = df.copy()
    for c in ("Open", "High", "Low", "Close"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["Open", "High", "Low", "Close"])
    if len(d) < 60:
        return {"izin": False, "nedenler": ["Geçerli mum sayısı yetersiz"], "atr": None}
    c, h, l = d.Close, d.High, d.Low
    atr_ser = (pd.concat([(h-l), (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1).rolling(14).mean())
    atr = float(atr_ser.iloc[-2] if len(atr_ser) > 2 else atr_ser.iloc[-1])
    if not np.isfinite(atr) or atr <= 0:
        return {"izin": False, "nedenler": ["ATR hesaplanamadı"], "atr": None}
    son = d.iloc[-2]  # kapanmış mum; açık mumla karar verme
    onceki_atr = atr
    son_aralik = float(son.High - son.Low)
    if son_aralik > ani_sicrama * onceki_atr:
        nedenler.append(f"Ani volatilite: son mum aralığı {son_aralik/atr:.2f} ATR")
    atr_ref = float(atr_ser.iloc[-52:-2].median()) if len(atr_ser.dropna()) >= 20 else atr
    if atr_ref > 0 and atr / atr_ref > atr_asiri:
        nedenler.append(f"Aşırı ATR: geçmiş medyanın {atr/atr_ref:.2f} katı")
    e7, e14, e21 = c.ewm(span=7, adjust=False).mean().iloc[-2], c.ewm(span=14, adjust=False).mean().iloc[-2], c.ewm(span=21, adjust=False).mean().iloc[-2]
    rsi_ser = _rsi(c)
    rsi = float(rsi_ser.iloc[-2]) if pd.notna(rsi_ser.iloc[-2]) else 50.0
    long = "long" in str(yon).lower()
    if long and not (e7 > e14 > e21 and rsi >= 50):
        nedenler.append(f"LONG teyidi yok: EMA7/14/21 veya RSI uyumsuz (RSI {rsi:.1f})")
    if not long and not (e7 < e14 < e21 and rsi <= 50):
        nedenler.append(f"SHORT teyidi yok: EMA7/14/21 veya RSI uyumsuz (RSI {rsi:.1f})")
    # Yakın swing ve Fibonacci bölgelerinde yeni pozisyon açma: fiyatın nefes alanı kalmalı.
    hi, lo, fiyat = float(h.iloc[-22:-2].max()), float(l.iloc[-22:-2].min()), float(c.iloc[-2])
    span = hi - lo
    if span > 0:
        fibs = [hi - span*x for x in FIB_SEVIYELER]
        yakin_fib = min(abs(fiyat-x) for x in fibs) / atr
        karsi_seviye = abs(hi-fiyat)/atr if long else abs(fiyat-lo)/atr
        if yakin_fib < seviye_atr:
            nedenler.append(f"Fibonacci seviyesine çok yakın ({yakin_fib:.2f} ATR)")
        if karsi_seviye < 0.35:
            nedenler.append("Yakın swing direnç/destek: hedef için yeterli alan yok")
    return {"izin": not nedenler, "nedenler": nedenler, "atr": atr, "fiyat": fiyat, "rsi": rsi}


def volatilite_stop_hedef(df, yon, giris, puan, atr_katsayi=1.6):
    """ATR + swing stop; skor hedefi korunur, stop en az ATR tamponu kadar genişletilir."""
    stop_pct, hedef_pct = _oran_sec(puan)
    if df is None or len(df) < 30 or not giris:
        return None
    d = df.iloc[:-1] if len(df) > 30 else df
    atr = _atr(d)
    long = "long" in str(yon).lower()
    swing_low = float(d["Low"].astype(float).tail(20).min())
    swing_high = float(d["High"].astype(float).tail(20).max())
    atr_pct = atr / float(giris) * 100.0
    mesafe_pct = max(stop_pct, atr_pct * atr_katsayi)
    # Swing seviyesi ATR tamponunun gerisinde olmalı; stop hiçbir zaman girişin yanlış tarafına geçmez.
    if long:
        stop = min(float(giris) * (1-mesafe_pct/100), swing_low - 0.25*atr)
        hedef = float(giris) * (1+hedef_pct/100)
    else:
        stop = max(float(giris) * (1+mesafe_pct/100), swing_high + 0.25*atr)
        hedef = float(giris) * (1-hedef_pct/100)
    gercek_stop_pct = abs(float(giris) - float(stop)) / float(giris) * 100.0
    return float(stop), float(hedef), float(atr), float(gercek_stop_pct)


# ------------------------------------------------------------------ MAE / MFE
def mae_mfe_hesapla(mumlar, long_mi, giris, baslangic_ms, bitis_ms):
    if mumlar is None or len(mumlar) == 0 or not giris:
        return None
    zs = mumlar["timestamp"]
    if np.issubdtype(zs.dtype, np.number):
        ms = zs.astype("int64").values
    else:
        ms = ((pd.to_datetime(zs, utc=True) - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(milliseconds=1)).values.astype("int64")
    sec = (ms > baslangic_ms) & (ms <= bitis_ms)
    if not sec.any():
        return None
    ust = float(mumlar["High"].astype(float).values[sec].max())
    alt = float(mumlar["Low"].astype(float).values[sec].min())
    if long_mi:
        mae, mfe = (giris - alt) / giris * 100.0, (ust - giris) / giris * 100.0
    else:
        mae, mfe = (ust - giris) / giris * 100.0, (giris - alt) / giris * 100.0
    return max(0.0, mae), max(0.0, mfe)
