"""
Background scheduler that sends a specific WhatsApp message to a specific
contact at a fixed time every day.

It reuses send_message.py (calls send_whatsapp_message) so all the WhatsApp
login / search / send logic lives in one place.

Run it (it keeps running in the foreground of whatever terminal you start it in):

    python scheduler.py

To run it truly in the background on Windows, start it with pythonw (no console)
or via Task Scheduler — see the notes at the bottom of this file.
"""

import time
from datetime import datetime, timedelta

from send_message import send_whatsapp_message

# ---------------------------------------------------------------------------
# CONFIGURE YOUR DAILY MESSAGE(S) HERE
# Each entry: send `message` to `contact` every day at `time` (24-hour "HH:MM").
# You can add more dicts to send multiple scheduled messages.
# ---------------------------------------------------------------------------
SCHEDULES = [
    {
        "time": "15:53",  # 4:15 PM
        "contact": "M.USAMA Gakhar",
        "message": "shift the main breaker lever and each floor individual breakers to wapda",
    },
]


def _seconds_until(target_hhmm: str) -> float:
    """Return seconds from now until the next occurrence of HH:MM today/tomorrow."""
    now = datetime.now()
    hour, minute = map(int, target_hhmm.split(":"))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        # time already passed today -> schedule for tomorrow
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _run_one(entry: dict) -> None:
    """Send a single scheduled message."""
    contact = entry["contact"]
    message = entry["message"]
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] Sending to '{contact}': {message!r}")
    try:
        # unattended=True skips the interactive prompt in send_message.py so the
        # browser closes on its own and the scheduler can continue.
        send_whatsapp_message(data={
            "contact": contact,
            "message": message,
            "unattended": True,
        })
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Sent OK.")
    except Exception as e:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] FAILED: {e}")


def main():
    print("=" * 60)
    print("WhatsApp daily scheduler started.")
    for s in SCHEDULES:
        print(f"  - {s['time']} daily -> '{s['contact']}': {s['message']!r}")
    print("Leave this running. Press Ctrl+C to stop.")
    print("=" * 60)

    # Track the last date each entry fired, so we send only once per day.
    last_sent_date = {i: None for i in range(len(SCHEDULES))}

    while True:
        now = datetime.now()
        for i, entry in enumerate(SCHEDULES):
            hour, minute = map(int, entry["time"].split(":"))
            today = now.date()
            # Fire when the clock reaches HH:MM and we haven't already sent today.
            if (now.hour == hour and now.minute == minute
                    and last_sent_date[i] != today):
                last_sent_date[i] = today
                _run_one(entry)

        # Sleep until the start of the next minute to stay aligned and cheap.
        seconds_to_next_minute = 60 - datetime.now().second
        time.sleep(max(1, seconds_to_next_minute))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nScheduler stopped by user.")

# ---------------------------------------------------------------------------
# Running it in the background on Windows:
#
# Option A — no console window (quick):
#     pythonw scheduler.py
#   (pythonw.exe runs without a terminal. Find it next to python.exe, e.g.
#    .\myenv\Scripts\pythonw.exe scheduler.py)
#
# Option B — survives reboots (recommended for "daily forever"):
#     Use Windows Task Scheduler:
#       1. Open "Task Scheduler" -> Create Basic Task
#       2. Trigger: Daily (or "When the computer starts")
#       3. Action: Start a program
#          Program:  C:\projects\wa_scrapping\myenv\Scripts\pythonw.exe
#          Arguments: scheduler.py
#          Start in:  C:\projects\wa_scrapping
#   Note: the machine must be ON and logged in for the browser to launch, and
#   the WhatsApp session (profile) must already be linked.
# ---------------------------------------------------------------------------
