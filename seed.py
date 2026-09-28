"""
Seed Fresh Feed with sample tracks so the feed is ready for the experiment.

Uses SoundHelix sample songs — free, stable, direct-audio MP3s that actually
play in the browser (no copyright worries). These are placeholders so you can run
the mechanics today; swap in real Creative-Commons tracks from Free Music
Archive / Jamendo (with credit) when you have them.

Each track has a short "story" note — handy for the story-vs-song experiment.
For that A/B test, clear the note on half of them (set story="") so you have a
with-story group and a without-story group.

Run on the server:
    python seed.py

Safe to re-run: it skips samples already present. To start clean, delete
freshfeed.db first (this wipes ALL data, including real submissions).
"""

import sqlite3, time, os
import app as A

# (title, artist, SoundHelix song number, short story)
SAMPLES = [
    ("Neon Hours",      "Auroralux",    1,  "Made in a dorm room over one weekend."),
    ("Paper Boats",     "Mira Vale",    2,  "Her first track after learning to produce on a phone."),
    ("Basement Tapes",  "Low Ceiling",  3,  "Recorded in an actual basement with one borrowed mic."),
    ("Afterglow",       "Kite String",  4,  "A 16-year-old's late-night beat that never got shared."),
    ("Second Language", "Halcyon Fox",  5,  "Written while learning English, one word at a time."),
    ("Rooftop Season",  "Idle Hands",   6,  "Made the summer he couldn't afford studio time."),
    ("Slow Traffic",    "Verrine",      7,  "Composed entirely on a cracked laptop."),
    ("Wire & Glass",    "Nocturne Ave", 8,  "A bedroom project no label ever heard."),
    ("Cold Open",       "Sable Youth",  9,  "Her most-loved song — 40 total plays."),
    ("Half Light",      "Ember Court",  10, "Two friends, one keyboard, zero followers."),
]
BASE = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-{}.mp3"


def run():
    if not os.path.exists(A.DB_PATH):
        A.init_db()
    db = sqlite3.connect(A.DB_PATH)
    added = 0
    for title, artist, n, story in SAMPLES:
        url = BASE.format(n)
        if db.execute("SELECT 1 FROM tracks WHERE url = ?", (url,)).fetchone():
            continue
        db.execute(
            """INSERT INTO tracks (title, artist, url, kind, embed, note, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (title, artist, url, "audio", url, story, time.time()),
        )
        added += 1
    db.commit()
    db.close()
    print(f"Seed complete — added {added} track(s).")


if __name__ == "__main__":
    run()
