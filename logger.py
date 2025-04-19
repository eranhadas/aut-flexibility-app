import os
import csv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import streamlit as st

LOGFILE = "responses.csv"  # still usable locally
USE_SHEETS = True

def _init_sheet():
    try:
        credentials_dict = json.loads(st.secrets["google"]["credentials"])
        # Fix the private key format
        credentials_dict["private_key"] = credentials_dict["private_key"].replace("\\n", "\n")
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open(st.secrets["google"]["sheet_name"]).sheet1
        return sheet
    except Exception as e:
        st.error("Google Sheets login failed.")
        st.exception(e)  # shows full traceback
        return None


def log(entry):
    if USE_SHEETS:
        sheet = _init_sheet()
        if sheet:
            try:
                values = [entry[key] for key in entry]
                sheet.append_row(values)
            except Exception as e:
                st.error("Failed to write to Google Sheet")
                st.exception(e)
        else:
            st.warning("Falling back to local CSV logging.")
            _log_to_csv(entry)
    else:
        _log_to_csv(entry)


def _log_to_csv(entry):
    file_exists = os.path.exists(LOGFILE)
    with open(LOGFILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=entry.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(entry)
