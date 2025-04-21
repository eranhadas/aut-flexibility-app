"""
logger.py – logging utilities for the AUT Flexibility app.

Each participant entry is written to Google Sheets (when enabled) and/or to
a local CSV file as a fallback.  Column order is fixed by FIELDNAMES so the
layout is identical across both destinations.
"""

import os
import csv
import json
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st

LOGFILE = "responses.csv"        # local backup file
USE_SHEETS = True                # set to False to disable Google Sheets

# --------------------------------------------------------------------
# Fixed column order – keep this identical in Google Sheets and in CSV
# --------------------------------------------------------------------
FIELDNAMES = [
    "timestamp",
    "participant_id",
    "study_id",
    "object",
    "response",
    "rating",
    "phase",
]

# --------------------------------------------------------------------
# Google Sheets connection
# --------------------------------------------------------------------
def _init_sheet():
    """Connect to Google Sheets using the JSON service‑account key in st.secrets."""
    try:
        credentials_dict = json.loads(st.secrets["google"]["credentials"])
        credentials_dict["private_key"] = credentials_dict["private_key"].replace("\\n", "\n")

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open(st.secrets["google"]["sheet_name"]).sheet1
        return sheet
    except Exception as e:
        st.error("Google Sheets login failed.")
        st.exception(e)
        return None

# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def _build_row(entry: dict) -> list:
    """Convert an entry dict to a list in FIELDNAMES order."""
    return [str(entry.get(col, "")) for col in FIELDNAMES]

# --------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------
def log(entry: dict):
    """
    Record a single entry.

    • Adds a timestamp if missing.
    • Tries Google Sheets first; falls back to CSV if Sheets is unavailable.
    • Always appends starting at column A with the fixed column order.
    """
    # Auto‑timestamp if not already provided
    entry.setdefault("timestamp", time.strftime("%Y-%m-%d %H:%M:%S"))

    if USE_SHEETS:
        sheet = _init_sheet()
        if sheet:
            try:
                row = _build_row(entry)
                sheet.append_row(
                    row,
                    table_range="A1",              # force start at column A
                    value_input_option="USER_ENTERED",
                    insert_data_option="INSERT_ROWS",
                )
            except Exception as e:
                st.error("Failed to write to Google Sheet.")
                st.exception(e)
                _log_to_csv(entry)                 # fallback
        else:
            st.warning("Falling back to local CSV logging.")
            _log_to_csv(entry)
    else:
        _log_to_csv(entry)

# --------------------------------------------------------------------
# CSV fallback
# --------------------------------------------------------------------
def _log_to_csv(entry: dict):
    """Write the entry to a local CSV file (creates header row if needed)."""
    file_exists = os.path.exists(LOGFILE)
    with open(LOGFILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow({k: entry.get(k, "") for k in FIELDNAMES})
