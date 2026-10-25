"""
Matris puanlamasını GERÇEK Binance verisiyle sınar (kendi bilgisayarınızda çalıştırın: python matris_dogrulama.py).
Her 30 dakikada bir eski ve yeni matris puanını hesaplar; sinyalden 60 dakika sonraki fiyat hareketinin
sinyal yönüyle uyup uymadığını (isabet) ve yönlü ortalama getiriyi eşik bazında karşılaştırır.
Not: kısa dönem verisi küçük bir örnektir; sonuçları kesin kanıt değil, yön gösterici sayın.
"""
import sys
import numpy as np
import pandas as pd
import matris_motoru as mm

SEMBOLLER = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]
GUN_PARCA = 8            # her parça 1000 dakika; 8 parça ≈ 5,5 gün
ADIM_DK = 30
ILERI_DK = 60
ESIKLER = (55, 60, 65, 70)


def mumlari_getir(sembol, parca=GUN_PARCA):
    import requests
    parcalar, bitis = [], None
    for _ in range(parca):
        url = f"https://data-api.binance.vision/api/v3/klines?symbol={sembol}&interval=1m&limit=1000"
        if bitis:
            url += f"&endTime={bitis}"
        veri = requests.get(url, timeout=15).json()
        if not veri:
            break
        d = pd.DataFrame(veri).iloc[:, :6]
        d.columns = ["t", "Open", "High", "Low", "Close", "Volume"]
        d[["Open", "High", "Low", "Close"]] = d[["Open", "High", "Low", "Close"]].astype(float)
        parcalar.append(d)
        bitis = int(d["t"].iloc[0]) - 1
    df = pd.concat(parcalar[::-1]).drop_duplicates("t").reset_index(drop=True)
    return df[["Open", "High", "Low", "Close"]]


def topla(df1, k):
    g = len(df1) // k
    df1 = df1.iloc[-g * k:].reset_index(drop=True)
    grp = np.arange(len(df1)) // k
    return df1.groupby(grp).agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"), Close=("Close", "last")).reset_index(drop=True)


def pencereler(df1):
    d5, d15 = topla(df1, 5), topla(df1, 15)
    kaynak = {"1m": df1, "5m": d5, "15m": d15}
    return [(e, kaynak[a].tail(n), w) for e, a, n, w in mm.DILIMLER]


def eski_pencere(df, max_puan):
    df = df.copy()
    df["Body"] = df["Close"] - df["Open"]
    y, k = df[df["Body"] > 0]["Body"].sum(), abs(df[df["Body"] < 0]["Body"].sum())
    t = y + k
    yo, ko = ((y / t), (k / t)) if t > 0 else (0.5, 0.5)
    bl, bs = max_puan * yo, max_puan * ko
    p = float(df["Close"].iloc[-1]); e = float(df["Close"].ewm(span=20, adjust=False).mean().iloc[-1])
    c = min(1.0, np.log1p((abs(p - e) / e) * 100) / np.log1p(1.5)); mb = max_puan * 0.04
    bl += mb * c if p > e else 0; bs += mb * c if p < e else 0
    top = bl + bs
    if top > max_puan:
        bl, bs = bl / top * max_puan, bs / top * max_puan
    return bl, bs


def eski_matris(pencere_listesi):
    """Eski yapının sadeleştirilmiş hâli (gövde + EMA20) ve eski ağırlıklar."""
    agirliklar = [9.5, 15.5, 50.0, 15.5, 9.5]
    return sum(eski_pencere(df, w)[0] for (_, df, _), w in zip(pencere_listesi, agirliklar))


def calistir(veri):
    sonuc = {"eski": [], "yeni": []}
    for sembol, df1 in veri.items():
        for i in range(1000, len(df1) - ILERI_DK, ADIM_DK):
            gecmis = df1.iloc[:i + 1].reset_index(drop=True)
            w = pencereler(gecmis)
            ileri = df1["Close"].iloc[i + ILERI_DK] / df1["Close"].iloc[i] - 1.0
            for ad, long_puan in (("eski", eski_matris(w)), ("yeni", mm.matris_hesapla(w)["nihai_long"])):
                sonuc[ad].append((long_puan, ileri))
    print(f"{'eşik':>5} | {'':4}{'ESKİ: sinyal  isabet  yönlü ort.getiri':>42} | {'YENİ: sinyal  isabet  yönlü ort.getiri':>40}")
    for esik in ESIKLER:
        satir = []
        for ad in ("eski", "yeni"):
            yon_getiri = []
            for long_puan, ileri in sonuc[ad]:
                if long_puan >= esik:
                    yon_getiri.append(ileri)
                elif 100 - long_puan >= esik:
                    yon_getiri.append(-ileri)
            n = len(yon_getiri)
            isabet = (np.mean(np.array(yon_getiri) > 0) * 100) if n else 0
            ort = (np.mean(yon_getiri) * 100) if n else 0
            satir.append(f"{n:6d}   %{isabet:5.1f}   %{ort:+.3f}")
        print(f"{esik:5d} | {satir[0]:>40} | {satir[1]:>38}")


if __name__ == "__main__":
    veri = {}
    for s in SEMBOLLER:
        try:
            veri[s] = mumlari_getir(s)
            print(s, len(veri[s]), "mum alındı")
        except Exception as e:
            print(s, "alınamadı:", e)
    if not veri:
        sys.exit("Veri alınamadı (internet / Binance erişimi).")
    calistir(veri)
