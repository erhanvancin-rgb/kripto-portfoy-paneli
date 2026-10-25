"""
Matris puanlama motoru: panel (panel_v2.py) ve GitHub motoru (check_engine.py) AYNI hesabı kullanır.

Süre | Ağırlık | Mum aralığı | Mum sayısı
16 S |  7,30   | 15 dakika   | 64
 8 S | 11,80   |  5 dakika   | 96
 4 S | 61,80   |  5 dakika   | 48
 2 S | 11,80   |  1 dakika   | 120
 1 S |  7,30   |  1 dakika   | 60

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

# ------------------------------------------------------------------ AYARLAR
DILIMLER = [
    # (etiket, mum aralığı, mum sayısı, ağırlık)
    ("16 S", "15m", 64, 7.30),
    ("8 S", "5m", 96, 11.80),
    ("4 S", "5m", 48, 61.80),
    ("2 S", "1m", 120, 11.80),
    ("1 S", "1m", 60, 7.30),
]

# ANA YÖN: net hareketin yönünü belirleyen kanıtlar (gövde baskınlığı + trend verimliliği)
ANA_AGIRLIK = {"govde": 0.5, "trend": 0.5}
# TEYİTÇİLER: ana yönü doğrular ya da çürütür (EMA, RSI, Fibonacci yönü, manyetik çekim)
TEYITCI_AGIRLIK = {"ema": 0.35, "rsi": 0.25, "fib": 0.25, "mik": 0.15}
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

# Geri çekilme derinliği -> devam gücü (sığ geri çekilme trendi teyit eder, derin olan bozar)
FIB_DEVAM = [(0.0, 1.0), (0.236, 1.0), (0.382, 0.8), (0.5, 0.5), (0.618, 0.2), (0.786, -0.3), (1.0, -0.8)]
FIB_SEVIYELER = (0.236, 0.382, 0.5, 0.618, 0.786)
# Mıknatıs kütleleri (altın oran ve EMA20 daha güçlü çeker)
MIKNATIS_KUTLE = {"hi": 0.7, "lo": 0.7, 0.236: 0.6, 0.382: 0.8, 0.5: 1.0, 0.618: 1.0, 0.786: 0.6, "ema20": 1.0, "ema50": 0.8}


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
def pencere_analiz(df):
    """Tek bir mum penceresi için 5 kanıtı (-1..+1) ve ayrıntıları döndürür."""
    nötr = {"govde": 0.0, "ema": 0.0, "rsi": 0.0, "fib": 0.0, "mik": 0.0, "trend": 0.0}
    if df is None or len(df) < 10:
        return {"s": nötr, "y_adet": 0, "k_adet": 0, "detay": {}}

    d = df.reset_index(drop=True)
    op, hi, lo, cl = (d[c].astype(float) for c in ("Open", "High", "Low", "Close"))
    n = len(d)
    fiyat = float(cl.iloc[-1])
    atr = _atr(d)

    # 1) gövde baskınlığı
    govde = cl - op
    yesil, kirmizi = float(govde[govde > 0].sum()), float(-govde[govde < 0].sum())
    toplam = yesil + kirmizi
    s_govde = ((yesil - kirmizi) / toplam) if toplam > 0 else 0.0

    # 2) EMA etkisi
    e9, e20, e50 = (cl.ewm(span=s, adjust=False).mean() for s in (9, 20, 50))
    ema20, ema50 = float(e20.iloc[-1]), float(e50.iloc[-1])
    k = max(3, min(10, n // 5))
    s_konum = _tanh(((fiyat - ema20) / atr) / EMA_KONUM_OLCEK)
    s_egim = _tanh((float(e20.iloc[-1]) - float(e20.iloc[-1 - k])) / atr / EMA_EGIM_OLCEK)
    a = np.sign(float(e9.iloc[-1]) - ema20)
    b = np.sign(ema20 - ema50)
    s_dizilim = 0.6 * a + 0.4 * b
    s_ema = 0.4 * s_konum + 0.3 * s_egim + 0.3 * s_dizilim

    # 3) RSI etkisi
    rsi = _rsi(cl)
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
        asiri = -0.5 * (rsi_now - 80.0) / 20.0     # aşırı alım: long yorgunluğu
    elif rsi_now < 20:
        asiri = 0.5 * (20.0 - rsi_now) / 20.0      # aşırı satım: short yorgunluğu
    s_rsi = _kenet(0.65 * s_seviye + 0.35 * s_ivme + asiri)

    # 4) Fibonacci ile olası yön
    en_yuksek, en_dusuk = float(hi.max()), float(lo.min())
    aralik = en_yuksek - en_dusuk
    i_hi, i_lo = int(np.argmax(hi.values)), int(np.argmin(lo.values))
    s_fib, geri_cekilme, bacak = 0.0, None, 0
    if aralik > 0 and i_hi != i_lo:
        bacak = 1 if i_lo < i_hi else -1               # +1: yukarı bacak, -1: aşağı bacak
        geri_cekilme = _kenet(((en_yuksek - fiyat) if bacak == 1 else (fiyat - en_dusuk)) / aralik, 0.0, 1.0)
        olcek = min(1.0, max(0.35, aralik / (atr * 8.0)))   # küçük/çalkantılı aralıkta güven azalır
        s_fib = bacak * _parcali(geri_cekilme, FIB_DEVAM) * olcek

    # 5) Fiyatın manyetik çekimi
    mikn = {"hi": en_yuksek, "lo": en_dusuk, "ema20": ema20, "ema50": ema50}
    if aralik > 0:
        for f in FIB_SEVIYELER:
            mikn[f] = en_dusuk + aralik * f
    toplam_cekim, net_cekim = 0.0, 0.0
    for ad, seviye in mikn.items():
        mesafe = abs(seviye - fiyat) / atr
        if mesafe < 0.15:       # fiyat zaten mıknatısın üzerinde: yön vermez
            continue
        g = MIKNATIS_KUTLE[ad] / (1.0 + mesafe) ** 2
        toplam_cekim += g
        net_cekim += g * (1.0 if seviye > fiyat else -1.0)
    s_mik = (net_cekim / toplam_cekim) * _tanh(toplam_cekim / MIKNATIS_OLCEK) if toplam_cekim > 0 else 0.0

    # 6) trend verimliliği (Kaufman): net yer değiştirme / toplam yol
    yol = float(cl.diff().abs().sum())
    net_hareket = float(cl.iloc[-1] - cl.iloc[0])
    verimlilik = (abs(net_hareket) / yol) if yol > 0 else 0.0
    s_trend = float(np.sign(net_hareket)) * min(1.0, verimlilik / VERIMLILIK_TAM)

    return {
        "s": {"govde": s_govde, "ema": s_ema, "rsi": s_rsi, "fib": s_fib, "mik": s_mik, "trend": s_trend},
        "y_adet": int((govde > 0).sum()), "k_adet": int((govde < 0).sum()),
        "detay": {"rsi": rsi_now, "atr": atr, "geri_cekilme": geri_cekilme, "bacak": bacak, "ema20": ema20, "ema50": ema50,
                  "verimlilik": verimlilik},
    }


def pencere_pay(analiz):
    """Ana yönden ve teyitçilerden Long payını (0..1) üretir. Ayrıca teyitçi uyumunu (0..1) ve ham ana yönü döndürür."""
    s = analiz["s"]
    s_ana = sum(ANA_AGIRLIK[k] * s[k] for k in ANA_AGIRLIK)
    yon = float(np.sign(s_ana))
    if yon == 0:
        return 0.5, 0.0, 0.0
    # teyitçilerin ana yönle işaretli ortalaması: +1 tam teyit, -1 tam çelişki
    a = sum(TEYITCI_AGIRLIK[k] * s[k] * yon for k in TEYITCI_AGIRLIK)
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
    """
    pencereler: [(etiket, df, ağırlık), ...]  (ağırlıklar toplamı 100)
    Döner: {"nihai_long", "nihai_short", "katkilar": {etiket: {...}}, "mtf_uyum", "mtf_carpan"}
    """
    toplam_agirlik = float(sum(p[2] for p in pencereler)) or 100.0
    analizler = []
    for etiket, df, agirlik in pencereler:
        a = pencere_analiz(df)
        pay, uyum, s_ham = pencere_pay(a)
        analizler.append((etiket, agirlik / toplam_agirlik, a, pay, uyum, s_ham))

    l0 = sum(w * pay for _, w, _, pay, _, _ in analizler)
    uzun_yon = l0 >= 0.5
    mtf_uyum = sum(w for _, w, _, pay, _, _ in analizler if (pay > 0.5 if uzun_yon else pay < 0.5))
    mtf_carpan = MTF_TABAN + MTF_ARTIS * mtf_uyum

    katkilar, long_toplam, short_toplam = {}, 0.0, 0.0
    for etiket, w, a, pay, uyum, s_ham in analizler:
        pay2 = _kenet(0.5 + (pay - 0.5) * mtf_carpan, 0.0, 1.0)
        sl, ss = 100.0 * w * pay2, 100.0 * w * (1.0 - pay2)
        long_toplam += sl
        short_toplam += ss
        katkilar[etiket] = {"sl": round(sl, 2), "ss": round(ss, 2), "y_adet": a["y_adet"], "k_adet": a["k_adet"],
                            "pay": round(pay2, 4), "uyum": round(uyum, 2), "kanitlar": {k: round(v, 3) for k, v in a["s"].items()},
                            "detay": a["detay"]}
    return {"nihai_long": round(long_toplam, 2), "nihai_short": round(short_toplam, 2), "katkilar": katkilar,
            "mtf_uyum": round(mtf_uyum, 3), "mtf_carpan": round(mtf_carpan, 3)}
