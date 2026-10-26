import os
from datetime import datetime
import gspread
import streamlit as st

GOOGLE_SHEET_ID = "1likk2RqtqxPxj7nSNDroxT6GQGrQXJmfx-SoyHswgyo"

def _sheets_baglan(sayfa_adi):
    """Google Sheets bağlantısını Streamlit Secrets üzerinden kurar."""
    try:
        if hasattr(st, "secrets") and "gcp_service_account" in st.secrets:
            sec = dict(st.secrets["gcp_service_account"])
            # Üçlü tırnak formatı kullanıldığı için private_key zaten düzgün okunur
            client = gspread.service_account_from_dict(sec)
        else:
            return None, "Streamlit Secrets içinde 'gcp_service_account' bulunamadı!"
            
        sh = client.open_by_key(GOOGLE_SHEET_ID)
        return sh.worksheet(sayfa_adi), None
    except Exception as e:
        return None, str(e)
