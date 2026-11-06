#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Matris puanlamasını ve stop/hedef tablolarını GERÇEK Binance 1 dakikalık verisiyle, KOMİSYON DAHİL geriye dönük sınar.
GitHub Actions'ta arka planda çalışır (.github/workflows/dogrulama.yml); sonuç Telegram'a ve çalışma çıktısına (artifact) gelir.

Ne sınanır?
  1) Pencere ağırlık setleri   : mevcut (15/20/30/20/15) | önceki (10/20/40/20/10) | yeni (7/18/40/22/13)
  2) Risk/hedef tabloları      : mevcut (stop %0,50 sabit) | A (stop .27-.30) | B (stop .40-.45)
  3) Minimum giriş puanı       : 55 | 59 | 63
  4) Düzeltme koruması         : yok | kovalama engeli (15dk RSI>=70 iken Long / <=30 iken Short açma) |
                                 düzeltme (kovalama + RSI aşırı bölgeden dönüp 15dk kapanış EMA14'ün ters tarafına geçtiyse engelle)
  5) Başa baş stopu            : yok | fiyat +%0,30 lehe giderse stop girişe çekilir
  + KONTROL: aynı seviyelerle puansız işlemler (hep Long / hep Short / rastgele yön). Puanın gerçek bir yön avantajı
    olup olmadığı, sinyalli sonucun bu kontrolden farkıyla ölçülür.

Simülasyon kuralları: giriş, sinyal anındaki son kapanmış 1 dk mumun kapanışı (kayma yok); stop/hedefe ilk dokunuş 1 dk
mumların High/Low'una göre, aynı mumda ikisine de dokunulduysa STOP sayılır (muhafazakâr); giriş %0,05 (market), hedefte
çıkış %0,02 (limit), stop/başa baş/süre çıkışı %0,05 (market) komisyon, pozisyon büyüklüğüne (teminat x kaldıraç) uygulanır.
Sonuçlar 100 $ teminat x 5x = 500 $ pozisyon için dolar cinsindendir. Aynı coinde aynı anda tek pozisyon açılır.

Uyarı: çok sayıda varyant denendiği için en iyi görünen sonuç şansla da öyle görünebilir. Bu yüzden 1. ve 2. yarı sonuçları
ayrı verilir; yalnızca iki yarıda da tutarlı olan ve kontrolden belirgin üstün çıkan varyantlara güvenin.
"""
import os
import sys
import time
import argparse

import numpy as np
import pandas as pd
import requests

import matris_motoru as mm

COINLER = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]
ISITMA = mm.ISITMA_MUM
K = {"1m": 1, "3m": 3, "5m": 5, "15m": 15}

GIRIS_KOM, HEDEF_CIKIS_KOM, STOP_CIKIS_KOM = 0.05, 0.02, 0.05   # % (pozisyon büyüklüğü üzerinden)
NOTIONAL = 500.0                                                  # 100 $ teminat x 5x

PENCERE_SETLERI = {
    "mevcut(15/20/30/20/15)": [("8 Saat", "15m", 32, 15.0), ("4 Saat", "5m", 48, 20.0), ("2 Saat", "3m", 40, 30.0),
                               ("1 Saat", "1m", 60, 20.0), ("30 Dakika", "1m", 30, 15.0)],
    "onceki(10/20/40/20/10)": [("8 Saat", "15m", 32, 10.0), ("4 Saat", "5m", 48, 20.0), ("2 Saat", "3m", 40, 40.0),
                               ("1 Saat", "1m", 60, 20.0), ("30 Dakika", "1m", 30, 10.0)],
    "yeni(7/18/40/22/13)": [("16 Saat", "15m", 64, 7.0), ("8 Saat", "5m", 96, 18.0), ("4 Saat", "5m", 48, 40.0),
                            ("2 Saat", "1m", 120, 22.0), ("1 Saat", "1m", 60, 13.0)],
}
# (puan, stop %, hedef %)
TABLOLAR = {
    "mevcut": [(50, .50, .45), (55, .50, .50), (59, .50, .60), (63, .50, .65), (67, .50, .75), (71, .50, .80), (75, .50, .85)],
    "A": [(50, .30, .33), (55, .29, .33), (59, .28, .37), (63, .27, .40), (67, .28, .37), (71, .29, .37), (75, .30, .33)],
    "B": [(50, .45, .50), (55, .44, .52), (59, .42, .56), (63, .40, .60), (67, .42, .56), (71, .44, .52), (75, .45, .50)],
}
ESIKLER = (55, 59, 63)
KORUMALAR = ("yok", "kovalama", "duzeltme")
BE_SECENEKLERI = (None, 0.30)
HOSTLAR = ("https://data-api.binance.vision", "https://api.binance.com")


# ------------------------------------------------------------------ VERİ
def _json_al(yol, deneme=4):
    son_hata = "bilinmiyor"
    for no in range(deneme):
        for host in HOSTLAR:
            try:
                r = requests.get(host + yol, timeout=20)
                if r.status_code == 200:
                    return r.json()
                son_hata = f"HTTP {r.status_code} ({host})"
            except Exception as e:
                son_hata = f"{type(e).__name__} ({host})"
        time.sleep(1.5 * (no + 1))
    raise RuntimeError(f"Binance verisi alınamadı: {son_hata}")


def mumlari_getir(sembol, gun):
    """Son 'gun' günün 1 dakikalık mumları (tamamlanmamış son mum hariç). Sütunlar: t(ms), o, h, l, c."""
    bitis = int(time.time() * 1000) // 60000 * 60000
    hedef = bitis - int(gun * 86400 * 1000)
    parcalar, son = [], bitis - 1
    while True:
        veri = _json_al(f"/api/v3/klines?symbol={sembol}&interval=1m&limit=1000&endTime={son}")
        if not veri:
            break
        parcalar.append(veri)
        ilk = int(veri[0][0])
        if ilk <= hedef or len(veri) < 1000:
            break
        son = ilk - 1
        time.sleep(0.15)
    ham = [r for p in reversed(parcalar) for r in p]
    df = pd.DataFrame(ham).iloc[:, :5]
    df.columns = ["t", "o", "h", "l", "c"]
    for col in "ohlc":
        df[col] = df[col].astype(float)
    df["t"] = df["t"].astype("int64")
    return df[(df.t >= hedef) & (df.t < bitis)].drop_duplicates("t").sort_values("t").reset_index(drop=True)


def topla(o, h, l, c, k):
    g = len(c) // k
    o, h, l, c = [a[:g * k].reshape(g, k) for a in (o, h, l, c)]
    return pd.DataFrame({"Open": o[:, 0], "High": h.max(1), "Low": l.min(1), "Close": c[:, -1]})


def hazirla(df, bas, bit):
    """Ortak, kesintisiz 1 dk ızgarası [bas, bit) üzerinde diziler ve 3/5/15 dk mumlar; 15 dk RSI/EMA14."""
    grid = np.arange(bas, bit, 60000)
    s = df.set_index("t").reindex(grid)
    eksik = s["c"].isna().values
    c = s["c"].ffill().bfill().values
    o = np.where(eksik, c, s["o"].values)
    h = np.where(eksik, c, s["h"].values)
    l = np.where(eksik, c, s["l"].values)
    ser = {a: topla(o, h, l, c, k) for a, k in K.items()}
    c15 = ser["15m"]["Close"].values
    return {
        "o": o, "h": h, "l": l, "c": c, "ser": ser, "c15": c15,
        "rsi15": mm._rsi(pd.Series(c15)).values,
        "ema14": pd.Series(c15).ewm(span=14, adjust=False).mean().values,
        "eksik_oran": float(eksik.mean()),
    }


# ------------------------------------------------------------------ SİNYALLER
def skorlari_hesapla(veriler, TS, setler):
    """Her coin ve her değerlendirme anı için her pencere seti için (long, short) puanı. Aynı pencere analizi setler arası paylaşılır."""
    benzersiz = sorted({(a, nm) for ws in setler.values() for (_e, a, nm, _w) in ws})
    sonuc = {ad: {coin: np.zeros((len(TS), 2)) for coin in veriler} for ad in setler}
    toplam, yapilan, t0 = len(veriler) * len(TS), 0, time.time()
    for coin, d in veriler.items():
        for i, t in enumerate(TS):
            ana = {}
            for (a, nm) in benzersiz:
                nb = t // K[a]
                df = d["ser"][a].iloc[max(0, nb - (nm + ISITMA)):nb]
                an = mm.pencere_analiz(df, nm)
                pay, uyum, s_ham = mm.pencere_pay(an)
                ana[(a, nm)] = (an, pay, uyum, s_ham)
            for ad, ws in setler.items():
                tw = sum(w for *_x, w in ws)
                liste = [(et, w / tw) + (ana[(a, nm)][0], ana[(a, nm)][1], ana[(a, nm)][2], ana[(a, nm)][3]) for (et, a, nm, w) in ws]
                r = mm.matris_birlestir(liste)
                sonuc[ad][coin][i] = (r["nihai_long"], r["nihai_short"])
            yapilan += 1
        print(f"  puanlar hesaplandı: {coin} ({yapilan}/{toplam}, {time.time() - t0:.0f} sn)", flush=True)
    return sonuc


def koruma_dizileri(d, TS):
    """Her değerlendirme anında Long/Short girişini engelleyecek bayraklar (yalnızca KAPANMIŞ 15 dk mumlar kullanılır)."""
    n = len(TS)
    vl_k, vs_k, vl_d, vs_d = (np.zeros(n, bool) for _ in range(4))
    rsi, c15, e14 = d["rsi15"], d["c15"], d["ema14"]
    for i, t in enumerate(TS):
        b = t // 15
        if b < 8 or np.isnan(rsi[b - 1]):
            continue
        r = rsi[b - 1]
        vl_k[i], vs_k[i] = r >= 70, r <= 30
        son = rsi[b - 7:b - 1]
        if np.isnan(son).all():
            continue
        vl_d[i] = (np.nanmax(son) >= 70) and r < 70 and c15[b - 1] < e14[b - 1]
        vs_d[i] = (np.nanmin(son) <= 30) and r > 30 and c15[b - 1] > e14[b - 1]
    return {"yok": (np.zeros(n, bool), np.zeros(n, bool)), "kovalama": (vl_k, vs_k), "duzeltme": (vl_k | vl_d, vs_k | vs_d)}


# ------------------------------------------------------------------ İŞLEM SİMÜLASYONU
def tablo_fonk(tab):
    xs, ss, hs = [t[0] for t in tab], [t[1] for t in tab], [t[2] for t in tab]
    return lambda p: (float(np.interp(p, xs, ss)), float(np.interp(p, xs, hs)))


def islem_simule(d, t, long_mi, stop_p, hedef_p, H, be):
    """Giriş: t'den ÖNCEKİ son kapanmış mumun kapanışı. t'den itibaren H mum taranır. Döner: (net %, çıkış dakikası, tip, süre)."""
    c = d["c"]
    hi, lo = d["h"][t:t + H], d["l"][t:t + H]
    g = c[t - 1]
    INF = H + 1
    if long_mi:
        s, hd = g * (1 - stop_p / 100), g * (1 + hedef_p / 100)
        s_hit, h_hit = lo <= s, hi >= hd
    else:
        s, hd = g * (1 + stop_p / 100), g * (1 - hedef_p / 100)
        s_hit, h_hit = hi >= s, lo <= hd
    ti = int(np.argmax(h_hit)) if h_hit.any() else INF
    si = int(np.argmax(s_hit)) if s_hit.any() else INF
    stop_tipi = "stop"
    if be:
        fav = g * (1 + be / 100) if long_mi else g * (1 - be / 100)
        f_hit = (hi >= fav) if long_mi else (lo <= fav)
        bi = int(np.argmax(f_hit)) if f_hit.any() else INF
        if bi < INF:
            be_hit = ((lo <= g) if long_mi else (hi >= g)).copy()
            be_hit[:bi + 1] = False                    # başa baş stopu tetik mumundan SONRA geçerli
            ei = int(np.argmax(be_hit)) if be_hit.any() else INF
            if si > bi:
                si = INF                               # özgün stop yalnızca tetikten önce geçerliydi
            if ei < si:
                si, stop_tipi = ei, "be"
    if min(si, ti) == INF:                             # süre dolumu: son mumun kapanışında market çıkış
        son = c[t + H - 1]
        hareket = (son / g - 1) * 100 if long_mi else (g - son) / g * 100
        return hareket - GIRIS_KOM - STOP_CIKIS_KOM, t + H, "sure", H
    if si <= ti:                                       # eşitlikte stop
        hareket = -stop_p if stop_tipi == "stop" else 0.0
        return hareket - GIRIS_KOM - STOP_CIKIS_KOM, t + si + 1, stop_tipi, si + 1
    return hedef_p - GIRIS_KOM - HEDEF_CIKIS_KOM, t + ti + 1, "hedef", ti + 1


def varyant_calistir(veriler, TS, skor, guard, tablo, esik, koruma, be, H):
    f = tablo_fonk(TABLOLAR[tablo])
    islemler = []
    for coin, d in veriler.items():
        L, S = skor[coin][:, 0], skor[coin][:, 1]
        vl, vs = guard[coin][koruma]
        serbest = 0
        for i, t in enumerate(TS):
            if t < serbest:
                continue
            if L[i] >= esik and not vl[i]:
                long_mi, puan = True, L[i]
            elif S[i] >= esik and not vs[i]:
                long_mi, puan = False, S[i]
            else:
                continue
            stop_p, hedef_p = f(puan)
            net, cikis, tip, sure = islem_simule(d, t, long_mi, stop_p, hedef_p, H, be)
            islemler.append((t, coin, "Long" if long_mi else "Short", float(puan), net, tip, sure, cikis))
            serbest = cikis
    return islemler


def kontrol_calistir(veriler, TS, tablo, be, H, mod, tohum=0):
    """Puansız kontrol işlemleri: boş olduğunda her değerlendirme anında girer; seviyeler tablonun 59 puanlık satırıdır."""
    stop_p, hedef_p = tablo_fonk(TABLOLAR[tablo])(59)
    rng = np.random.default_rng(tohum)
    islemler = []
    for coin, d in veriler.items():
        serbest = 0
        for t in TS:
            if t < serbest:
                continue
            long_mi = True if mod == "long" else (False if mod == "short" else bool(rng.integers(0, 2)))
            net, cikis, tip, sure = islem_simule(d, t, long_mi, stop_p, hedef_p, H, be)
            islemler.append((t, coin, "Long" if long_mi else "Short", 59.0, net, tip, sure, cikis))
            serbest = cikis
    return islemler


def metrik(islemler, orta_t=None):
    if not islemler:
        return {"n": 0, "isabet": 0.0, "toplam": 0.0, "ort": 0.0, "pf": 0.0, "mdd": 0.0, "y1": 0.0, "y2": 0.0}
    a = np.array([r[4] for r in islemler]) * NOTIONAL / 100.0
    kaz, kay = a[a > 0].sum(), -a[a < 0].sum()
    sirali = sorted(islemler, key=lambda r: r[7])
    kum = np.cumsum([r[4] for r in sirali]) * NOTIONAL / 100.0
    mdd = float((np.maximum.accumulate(np.r_[0.0, kum])[1:] - kum).max()) if len(kum) else 0.0
    y1 = y2 = 0.0
    if orta_t is not None:
        y1 = float(sum(r[4] for r in islemler if r[0] < orta_t) * NOTIONAL / 100.0)
        y2 = float(sum(r[4] for r in islemler if r[0] >= orta_t) * NOTIONAL / 100.0)
    return {"n": len(a), "isabet": float((a > 0).mean() * 100), "toplam": float(a.sum()), "ort": float(a.mean()),
            "pf": float(kaz / kay) if kay > 0 else float("inf"), "mdd": mdd, "y1": y1, "y2": y2}


# ------------------------------------------------------------------ ANA AKIŞ
def calistir(ham, gun, adim=15, maks_dk=360, hizli_ozet=False):
    """ham: {sembol: DataFrame(t,o,h,l,c)}. Döner: (rapor_metni, en_iyi_varyantin_islem_csv_baytlari)."""
    if adim % 15:
        raise ValueError("adim 15'in katı olmalı (3/5/15 dk mumlar tam kapanmış olsun).")
    bas = max(int(d.t.iloc[0]) for d in ham.values())
    bit = min(int(d.t.iloc[-1]) + 60000 for d in ham.values())
    bas = (bas + 899999) // 900000 * 900000
    bit = bit // 900000 * 900000
    veriler = {c: hazirla(d, bas, bit) for c, d in ham.items()}
    N = (bit - bas) // 60000
    uyari = ""
    for c, d in veriler.items():
        if d["eksik_oran"] > 0.01:
            uyari += f"\n⚠️ {c}: mumların %{d['eksik_oran'] * 100:.1f}'i eksik (boşluklar doldurulduysa sonuç etkilenebilir)."
    warm = max((nm + ISITMA) * K[a] for ws in PENCERE_SETLERI.values() for (_e, a, nm, _w) in ws)
    ilk = -(-warm // 15) * 15
    TS = list(range(ilk, N - maks_dk, adim))
    if len(TS) < 20:
        raise RuntimeError(f"Veri yetersiz: {N} dk veri var, en az {ilk + maks_dk + 20 * adim} dk gerekir (--gun artırın).")
    orta_t = TS[len(TS) // 2]
    print(f"Veri: {len(veriler)} coin, {N} dk (~{N / 1440:.1f} gün); değerlendirme anı: {len(TS)} (her {adim} dk)", flush=True)

    skor = skorlari_hesapla(veriler, TS, PENCERE_SETLERI)
    guard = {coin: koruma_dizileri(d, TS) for coin, d in veriler.items()}

    # --- kontrol (puansız) ---
    kontrol = {}
    for tablo in TABLOLAR:
        for be in BE_SECENEKLERI:
            for mod in ("long", "short"):
                kontrol[(tablo, be, mod)] = metrik(kontrol_calistir(veriler, TS, tablo, be, maks_dk, mod), orta_t)
            seeds = [kontrol_calistir(veriler, TS, tablo, be, maks_dk, "rastgele", s) for s in range(5)]
            ms = [metrik(x, orta_t) for x in seeds]
            ort = {k: float(np.mean([m[k] for m in ms])) for k in ms[0]}
            havuz = [r[4] * NOTIONAL / 100.0 for x in seeds for r in x]
            ort["std"] = float(np.std(havuz)) if havuz else 0.0
            ort["n_havuz"] = len(havuz)
            kontrol[(tablo, be, "rastgele")] = ort

    # --- sinyalli varyantlar ---
    sonuc, islem_kayit = [], {}
    for ws in PENCERE_SETLERI:
        for tablo in TABLOLAR:
            for esik in ESIKLER:
                for kor in KORUMALAR:
                    for be in BE_SECENEKLERI:
                        isl = varyant_calistir(veriler, TS, skor[ws], guard, tablo, esik, kor, be, maks_dk)
                        m = metrik(isl, orta_t)
                        m.update({"pencere": ws, "tablo": tablo, "esik": esik, "koruma": kor, "be": be})
                        sonuc.append(m)
                        islem_kayit[(ws, tablo, esik, kor, be)] = isl

    def ad(m):
        return f"{m['pencere'].split('(')[0]}/{m['tablo']}/{m['esik']}/{m['koruma']}/{'BE' if m['be'] else '-'}"

    uygun = [m for m in sonuc if m["n"] >= 30]
    uygun.sort(key=lambda m: m["toplam"], reverse=True)
    referans = next((m for m in sonuc if m["pencere"].startswith("mevcut") and m["tablo"] == "mevcut" and m["esik"] == 55
                     and m["koruma"] == "yok" and m["be"] is None), None)

    s = []
    s.append(f"# Matris doğrulama raporu\nVeri: {len(veriler)} coin, ~{N / 1440:.1f} gün 1 dk mum | değerlendirme: her {adim} dk | "
             f"en uzun işlem {maks_dk} dk | 100 $ teminat x 5x (500 $) | tüm komisyonlar dahil{uyari}\n")
    s.append("## 1) Kontrol: puansız işlemler (stop/hedef/komisyon tek başına ne yapıyor?)\n```")
    s.append(f"{'tablo':7}{'BE':4}{'mod':9}{'n':>6}{'isabet%':>9}{'toplam$':>10}{'ort$/işlem':>12}")
    for tablo in TABLOLAR:
        for be in BE_SECENEKLERI:
            for mod in ("long", "short", "rastgele"):
                m = kontrol[(tablo, be, mod)]
                s.append(f"{tablo:7}{'BE' if be else '-':4}{mod:9}{m['n']:>6.0f}{m['isabet']:>9.1f}{m['toplam']:>10.1f}{m['ort']:>12.2f}")
    s.append("```\n")
    s.append("## 2) Sinyalli varyantlar: toplam $'a göre ilk 12 (en az 30 işlem)\n```")
    s.append(f"{'varyant (pencere/tablo/eşik/koruma/BE)':44}{'n':>5}{'isabet%':>9}{'toplam$':>9}{'ort$':>7}{'PF':>6}{'MDD$':>7}{'1.yarı':>8}{'2.yarı':>8}")
    for m in uygun[:12]:
        s.append(f"{ad(m):44}{m['n']:>5}{m['isabet']:>9.1f}{m['toplam']:>9.1f}{m['ort']:>7.2f}{min(m['pf'], 99):>6.2f}{m['mdd']:>7.1f}{m['y1']:>8.1f}{m['y2']:>8.1f}")
    if referans:
        s.append("-" * 105)
        s.append(f"{'REFERANS: ' + ad(referans):44}{referans['n']:>5}{referans['isabet']:>9.1f}{referans['toplam']:>9.1f}{referans['ort']:>7.2f}{min(referans['pf'], 99):>6.2f}{referans['mdd']:>7.1f}{referans['y1']:>8.1f}{referans['y2']:>8.1f}")
    s.append("```\n")

    # --- en iyi varyantın kontrole göre farkı ---
    csv_bytes = b""
    if uygun:
        eb = uygun[0]
        kt = kontrol[(eb["tablo"], eb["be"], "rastgele")]
        fark = eb["ort"] - kt["ort"]
        std_eb = float(np.std([r[4] * NOTIONAL / 100.0 for r in islem_kayit[(eb["pencere"], eb["tablo"], eb["esik"], eb["koruma"], eb["be"])]]))
        se = (std_eb ** 2 / max(eb["n"], 1) + kt["std"] ** 2 / max(kt["n_havuz"], 1)) ** 0.5
        t_stat = fark / se if se > 0 else 0.0
        s.append(f"## 3) En iyi varyant: {ad(eb)}\n```")
        s.append(f"işlem/işlem ortalaması {eb['ort']:+.2f} $ | aynı tablo+BE'nin rastgele-yön kontrolü {kt['ort']:+.2f} $ | fark {fark:+.2f} $/işlem | t ≈ {t_stat:.1f}")
        s.append("(t, işlemler birbiriyle ilişkili olduğundan olduğundan fazla çıkar; |t| < 2-3 ise avantaj kanıtlanmış sayılmaz.)")
        kayit = islem_kayit[(eb["pencere"], eb["tablo"], eb["esik"], eb["koruma"], eb["be"])]
        for yon in ("Long", "Short"):
            x = [r for r in kayit if r[2] == yon]
            mm_ = metrik(x)
            s.append(f"{yon:6} n={mm_['n']:4} isabet %{mm_['isabet']:.1f}  toplam {mm_['toplam']:+.1f} $")
        for coin in veriler:
            x = [r for r in kayit if r[1] == coin]
            mm_ = metrik(x)
            s.append(f"{coin:8} n={mm_['n']:4} isabet %{mm_['isabet']:.1f}  toplam {mm_['toplam']:+.1f} $")
        for lo, hi in ((55, 59), (59, 63), (63, 67), (67, 101)):
            x = [r for r in kayit if lo <= r[3] < hi]
            if x:
                mm_ = metrik(x)
                s.append(f"puan {lo}-{hi if hi < 101 else '+':<4} n={mm_['n']:4} isabet %{mm_['isabet']:.1f}  toplam {mm_['toplam']:+.1f} $")
        s.append("```\n")
        df_k = pd.DataFrame(kayit, columns=["giris_dk", "coin", "yon", "puan", "net_yuzde", "cikis_tipi", "sure_dk", "cikis_dk"])
        df_k["giris_zaman_utc"] = pd.to_datetime(bas + df_k["giris_dk"] * 60000, unit="ms")
        df_k["net_dolar_100x5"] = df_k["net_yuzde"] * NOTIONAL / 100.0
        csv_bytes = df_k.to_csv(index=False).encode("utf-8-sig")

    # --- hızlı karşılaştırmalar (tek boyutlu özetler) ---
    def grup(anahtar):
        d = {}
        for m in uygun if uygun else sonuc:
            d.setdefault(m[anahtar], []).append(m)
        return d
    s.append("## 4) Tek tek etki (bütün varyantların ortalaması; n≥30 olanlar)\n```")
    for anahtar, baslik in (("pencere", "Pencere seti"), ("tablo", "Tablo"), ("esik", "Min. puan"), ("koruma", "Koruma"), ("be", "Başa baş stopu")):
        s.append(f"{baslik}:")
        for deger, ms_ in grup(anahtar).items():
            s.append(f"   {str(deger):26} ort. toplam {np.mean([x['toplam'] for x in ms_]):+8.1f} $ | ort. isabet %{np.mean([x['isabet'] for x in ms_]):5.1f} | varyant sayısı {len(ms_)}")
    s.append("```")
    s.append("\nYorum rehberi: (1) Kontrol satırları negatifse sinyalsiz giriş komisyon+gürültü yüzünden kaybediyor demektir; "
             "puanın değeri kontrolden farkıdır. (2) 1. ve 2. yarı aynı işaretteyse sonuç daha güvenilirdir. "
             "(3) Tek bir 'en iyi' varyanta değil, yukarıdaki tek tek etkilerdeki tutarlı yöne bakın.")
    return "\n".join(s), csv_bytes


# ------------------------------------------------------------------ TELEGRAM
def telegram_gonder(metin, dosyalar=()):
    token = "".join(os.environ.get("TELEGRAM_BOT_TOKEN", "").split())
    chat = "".join(os.environ.get("TELEGRAM_CHAT_ID", "").split())
    if not token or not chat:
        print("Telegram gizli anahtarları yok; yalnızca dosyaya yazıldı.")
        return False
    ok = False
    try:
        kisa = metin if len(metin) <= 3900 else metin[:3850] + "\n... (devamı ekteki dosyada)"
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat, "text": kisa}, timeout=30)
        ok = r.status_code == 200
        for ad_, icerik, mime in dosyalar:
            if icerik:
                requests.post(f"https://api.telegram.org/bot{token}/sendDocument", data={"chat_id": chat},
                              files={"document": (ad_, icerik, mime)}, timeout=60)
    except Exception as e:
        print(f"Telegram gönderim hatası: {type(e).__name__}: {e}")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gun", type=float, default=14, help="kaç günlük 1 dk veri sınanacak (ısınma payı ayrıca eklenir)")
    ap.add_argument("--adim", type=int, default=15, help="değerlendirme aralığı (dk, 15'in katı)")
    ap.add_argument("--maks-dk", type=int, default=360, help="bir işlemin en uzun süresi (dk)")
    ap.add_argument("--coinler", default=",".join(COINLER))
    args = ap.parse_args()

    ham = {}
    for sembol in [x.strip() for x in args.coinler.split(",") if x.strip()]:
        print(f"{sembol} verisi alınıyor...", flush=True)
        ham[sembol] = mumlari_getir(sembol, args.gun + 2.0)   # +2 gün: EMA/RSI ısınması için
        print(f"  {len(ham[sembol])} mum", flush=True)
    rapor, csv_bytes = calistir(ham, args.gun, args.adim, args.maks_dk)
    print(rapor)
    with open("dogrulama_ozet.md", "w", encoding="utf-8") as f:
        f.write(rapor)
    if csv_bytes:
        with open("dogrulama_islemler.csv", "wb") as f:
            f.write(csv_bytes)
    telegram_gonder(rapor, [("dogrulama_ozet.md", rapor.encode("utf-8"), "text/markdown"),
                            ("dogrulama_islemler.csv", csv_bytes, "text/csv")])


if __name__ == "__main__":
    main()
