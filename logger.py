"""
logger.py – Logging utilities for the AUT Flexibility app.

Writes every participant entry to Google Sheets (if enabled) and/or to
a local CSV backup.  A fixed column order guarantees that both targets
have identical layout.
"""

import os
import csv
import json
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st

LOGFILE = "responses.csv"          # local backup
USE_SHEETS = True                  # set False to disable Google Sheets
#VERBOSE = st.sidebar.checkbox("Verbose logging")  # enable live debug
VERBOSE = False  # Disable verbose UI logging


# --------------------------------------------------------------------
# Fixed column order – keep identical in Google Sheets and CSV
# --------------------------------------------------------------------
FIELDNAMES = [
    "timestamp",
    "participant",
    "study_id",
    "group_id",
    "phase_name",
    "phase_index",
    "object",
    "trial",
    "use_text",
    "category",
    "response_time_sec_phase",
    "hints_enabled_group",
    "shown_hints",

]

# --------------------------------------------------------------------
# Google Sheets connection helpers
# --------------------------------------------------------------------
def _init_sheet():
    """Connect to the Google Sheet defined in st.secrets."""
    try:
        credentials_dict = json.loads(st.secrets["google"]["credentials"])
        credentials_dict["private_key"] = credentials_dict["private_key"].replace("\\n", "\n")

        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open(st.secrets["google"]["sheet_name"]).sheet1
        _ensure_header(sheet)  # make sure the first row is the header
        return sheet

    except Exception as e:
        st.error("Google Sheets login failed.")
        st.exception(e)
        return None


def _ensure_header(sheet):
    """
    Make sure the first row contains exactly FIELDNAMES without blanks.
    Call once at startup; harmless if the header already exists.
    """
    try:
        current = sheet.row_values(1)
        if current != FIELDNAMES:
            sheet.delete_rows(1) if current else None  # remove partial header
            sheet.insert_row(FIELDNAMES, 1)
            if VERBOSE:
                st.info("Header row refreshed.")
    except Exception as e:
        st.warning("Could not verify header row.")
        if VERBOSE:
            st.exception(e)

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
    • Tries Google Sheets first; falls back to CSV if Sheets unavailable
      or if the write fails.
    """
    entry.setdefault("timestamp", time.strftime("%Y-%m-%d %H:%M:%S"))

    if USE_SHEETS:
        sheet = _init_sheet()
        if sheet:
            try:
                row = _build_row(entry)
                sheet.append_row(
                    row,
                    value_input_option="USER_ENTERED",
                    insert_data_option="INSERT_ROWS",
                )
                if VERBOSE:
                    st.success("Logged to Google Sheets")
                return
            except Exception as e:
                st.error("Failed to write to Google Sheets.")
                st.exception(e)
                # intentional fall‑through to CSV backup

        else:
            st.warning("Google Sheets unavailable; logging to CSV.")

    # CSV fallback (or primary if USE_SHEETS=False)
    _log_to_csv(entry)


# --------------------------------------------------------------------
# CSV backup
# --------------------------------------------------------------------
def _log_to_csv(entry: dict):
    """Write the entry to a local CSV file (creates header row if needed)."""
    try:
        file_exists = os.path.exists(LOGFILE)
        with open(LOGFILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if not file_exists:
                writer.writeheader()
            writer.writerow({k: entry.get(k, "") for k in FIELDNAMES})
        if VERBOSE:
            st.success("Logged to CSV")
    except Exception as e:
        st.error("Failed to write to local CSV!")
        st.exception(e)
