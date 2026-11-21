import unittest
import numpy as np
import pandas as pd
import matris_motoru as mm

class YeniYapiTestleri(unittest.TestCase):
    def test_stop_hedef_ankorlari_ve_aradegerler(self):
        self.assertEqual(mm._oran_sec(50), (0.30, 0.40))
        self.assertEqual(mm._oran_sec(75), (0.45, 0.65))
        self.assertEqual(mm._oran_sec(100), (0.25, 0.30))
        s70, h70 = mm._oran_sec(70)
        self.assertAlmostEqual(s70, 0.42, places=8)
        self.assertAlmostEqual(h70, 0.60, places=8)
        self.assertEqual(mm._oran_sec(10), mm._oran_sec(50))
        self.assertEqual(mm._oran_sec(120), mm._oran_sec(100))

    def test_mae_mfe_long_short(self):
        candles = pd.DataFrame({
            "timestamp": [1000, 2000, 3000],
            "High": [101.0, 103.0, 102.0],
            "Low": [100.0, 99.0, 99.5],
        })
        self.assertEqual(mm.mae_mfe_hesapla(candles, True, 100.0, 1000, 3000), (1.0, 3.0))
        self.assertEqual(mm.mae_mfe_hesapla(candles, False, 100.0, 1000, 3000), (3.0, 1.0))

    def test_70_ustu_guclu_trend_modu(self):
        n = 250
        close = np.linspace(100, 112, n) + np.sin(np.arange(n) / 5) * 0.15
        op = np.r_[close[0], close[:-1]]
        df = pd.DataFrame({
            "timestamp": pd.date_range("2026-11-01", periods=n, freq="5min", tz="UTC"),
            "Open": op, "High": np.maximum(op, close) + 0.08,
            "Low": np.minimum(op, close) - 0.08, "Close": close,
        })
        windows = [("8 Saat", df, 7, 32), ("4 Saat", df, 18, 48),
                   ("2 Saat", df, 40, 24), ("1 Saat", df, 22, 12),
                   ("30 Dakika", df, 13, 10)]
        result = mm.matris_hesapla(windows)
        self.assertTrue(result["guclu_trend_modu"])
        self.assertEqual(result["teyit_modu"], "EMA7/14/21 + RSI + Fibonacci ağırlıklı")
        self.assertAlmostEqual(result["nihai_long"] + result["nihai_short"], 100.0, places=2)

if __name__ == "__main__":
    unittest.main(verbosity=2)
