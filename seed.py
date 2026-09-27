"""
Seed Fresh Feed with a few sample tracks so the feed isn't empty when you demo.

Uses SoundHelix sample songs — free, stable, direct-audio MP3s (no copyright
worries, they actually play). Run once:

    python seed.py

Safe to re-run: it skips samples already present. Delete them later by removing
rows from freshfeed.db, or just delete freshfeed.db to start fresh.
"""

import sqlite3, time, os
import app as A

SAMPLES = [
    ("Neon Hours",       "Auroralux",     3),
    ("Paper Boats",      "Mira Vale",     5),
    ("Basement Tapes",   "Low Ceiling",   7),
    ("Afterglow",        "Kite String",   9),
    ("Second Language",  "Halcyon Fox",  11),
    ("Rooftop Season",   "Idle Hands",   13),
]
BASE = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-{}.mp3"


def run():
    if not os.path.exists(A.DB_PATH):
        A.init_db()
    db = sqlite3.connect(A.DB_PATH)
    added = 0
    for title, artist, n in SAMPLES:
        url = BASE.format(n)
        exists = db.execute("SELECT 1 FROM tracks WHERE url = ?", (url,)).fetchone()
        if exists:
            continue
        db.execute(
            """INSERT INTO tracks (title, artist, url, kind, embed, note, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (title, artist, url, "audio", url, "Sample track (demo seed).", time.time()),
        )
        added += 1
    db.commit()
    db.close()
    print(f"Seed complete — added {added} sample track(s).")


if __name__ == "__main__":
    run()
