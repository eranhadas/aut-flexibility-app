import os
import csv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import streamlit as st

LOGFILE = "responses.csv"  # still usable locally
USE_SHEETS = True

def _init_sheet():
    credentials_dict = json.loads(st.secrets["google"]["credentials"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open(st.secrets["google"]["sheet_name"]).sheet1
    return sheet

def log(entry):
    if USE_SHEETS:
        try:
            sheet = _init_sheet()
            values = [entry[key] for key in entry]  # assuming order is consistent
            sheet.append_row(values)
        except Exception as e:
            st.error(f"Failed to log to Google Sheets: {e}")
    else:
        file_exists = os.path.exists(LOGFILE)
        with open(LOGFILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=entry.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(entry)
