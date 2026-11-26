import numpy as np
import pandas as pd
import matris_motoru


def candles(n=180, trend=1.0, spike=False):
    close = 100 + np.arange(n) * trend * 0.03
    op = close - trend * 0.01
    hi = np.maximum(op, close) + 0.08
    lo = np.minimum(op, close) - 0.08
    if spike:
        hi[-2] += 2.0
        lo[-2] -= 2.0
    return pd.DataFrame({"Open": op, "High": hi, "Low": lo, "Close": close})


def test_yetersiz_veri_engellenir():
    r = matris_motoru.otomatik_islem_kontrol(candles(20), "Long")
    assert not r["izin"]


def test_volatilite_sicramasi_engellenir():
    r = matris_motoru.otomatik_islem_kontrol(candles(spike=True), "Long")
    assert any("Ani volatilite" in x for x in r["nedenler"])


def test_dinamik_stop_long_ve_short():
    d = candles()
    long = matris_motoru.volatilite_stop_hedef(d, "Long", 105.0, 75)
    short = matris_motoru.volatilite_stop_hedef(d, "Short", 105.0, 75)
    assert long and long[0] < 105.0 and long[1] > 105.0
    assert short and short[0] > 105.0 and short[1] < 105.0

if __name__ == "__main__":
    test_yetersiz_veri_engellenir()
    test_volatilite_sicramasi_engellenir()
    test_dinamik_stop_long_ve_short()
    print("3 otomatik koruma testi başarılı")
