
import csv
import os

LOGFILE = "responses.csv"

def log(entry):
    file_exists = os.path.exists(LOGFILE)
    with open(LOGFILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=entry.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(entry)
