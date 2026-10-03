# --- DİNAMİK VE RENKLİ HAREKETLİ MATRİS ---
def dinamik_volatilite_ve_risk_yonetimi(coin_symbol, anlik_fiyat, degisim_24s, degisim_30m, degisim_1h, degisim_4s):
    egilim_puani = (degisim_30m * 2.5) + (degisim_1h * 1.5) + (degisim_24s * 0.5)
    yesil_asil_orani = max(0.05, min(0.90, 0.5 + (egilim_puani / 8.0)))
    
    # Hafifletilmiş ama renk çeşitliliği sunan 10'lu LED simülasyonu
    aktif_ledler = []
    for _ in range(10):
        zar = random.random()
        if zar < (yesil_asil_orani - 0.1):
            aktif_ledler.append("🟢")
        elif zar > (yesil_asil_orani + 0.1):
            aktif_ledler.append("🔴")
        else:
            aktif_ledler.append("🟡")
            
    yesil_sayisi = aktif_ledler.count("🟢")
    kirmizi_sayisi = aktif_ledler.count("🔴")
    
    ham_yon = "Nötr (Beklemede)"
    if yesil_sayisi >= 6: ham_yon = "Long"
    elif kirmizi_sayisi >= 6: ham_yon = "Short"
        
    onceki_yon = st.session_state['onceki_yonler'].get(coin_symbol, "Nötr (Beklemede)")
    if ham_yon == onceki_yon:
        st.session_state['yon_istikrar_sayaci'][coin_symbol] += 1
        kesin_yon = ham_yon
    else:
        if st.session_state['yon_istikrar_sayaci'].get(coin_symbol, 0) >= 1:
            st.session_state['onceki_yonler'][coin_symbol] = ham_yon
            st.session_state['yon_istikrar_sayaci'][coin_symbol] = 0
            kesin_yon = ham_yon
        else:
            st.session_state['yon_istikrar_sayaci'][coin_symbol] += 1
            kesin_yon = onceki_yon

    volatilite_faktoru = max(abs(degisim_24s), 0.5) / 100.0
    if kesin_yon == "Long":
        stop_yuzde = max(0.4, 0.4 + (volatilite_faktoru * 30))
        hedef_yuzde = max(1.2, stop_yuzde * 2.8)
        stop_fiyat = anlik_fiyat * (1 - (stop_yuzde / 100.0))
        hedef_fiyat = anlik_fiyat * (1 + (hedef_yuzde / 100.0))
    elif kesin_yon == "Short":
        stop_yuzde = max(0.4, 0.4 + (volatilite_faktoru * 30))
        hedef_yuzde = max(1.2, stop_yuzde * 2.8)
        stop_fiyat = anlik_fiyat * (1 + (stop_yuzde / 100.0))
        hedef_fiyat = anlik_fiyat * (1 - (hedef_yuzde / 100.0))
    else:
        stop_fiyat = anlik_fiyat * 0.99
        hedef_fiyat = anlik_fiyat * 1.01

    teyit_sunumu = "".join(aktif_ledler)
    return kesin_yon, abs(degisim_24s) + 1.0, teyit_sunumu, hedef_fiyat, stop_fiyat, (kesin_yon == "Nötr (Beklemede)")