
import time

def start_timer():
    return time.monotonic()

def elapsed(start_time):
    return time.monotonic() - start_time
