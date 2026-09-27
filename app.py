"""
Fresh Feed — a fair-discovery music sharing MVP, with a built-in A/B experiment.

The idea being tested: does giving small artists EQUAL exposure actually get
them heard? To prove it's the fairness (not just the site), every listener is
randomly assigned to one of two feeds:

  * fair    — Discover shows the LEAST-seen tracks first (guaranteed rotation)
  * popular — Discover shows the MOST-played tracks first (normal popularity)

Every impression, play, and like is logged with the listener's variant, so you
can compare: do small tracks get more reach in the fair feed? See /stats.

Anonymous: no accounts. Each visitor gets a random "Listener-XXXX" id + a
variant, both in cookies.

Run:
    pip install -r requirements.txt
    python app.py            # then open http://localhost:5000
    python seed.py           # optional: add sample tracks so it isn't empty
"""

import os
import re
import random
import secrets
import sqlite3
import time
from urllib.parse import quote, urlparse

from flask import (
    Flask, g, request, redirect, url_for, render_template,
    make_response, jsonify, abort,
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "freshfeed.db")

app = Flask(__name__)

DISCOVER_LIMIT = 12       # tracks shown per Discover visit
RATE_PRIOR = 5            # smoothing for the like-rate ranking
VARIANTS = ("fair", "popular")


# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS tracks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            artist      TEXT NOT NULL,
            url         TEXT NOT NULL,
            kind        TEXT NOT NULL,
            embed       TEXT,
            note        TEXT,
            created_at  REAL NOT NULL,
            impressions INTEGER NOT NULL DEFAULT 0,   -- fair-feed rotation counter
            plays       INTEGER NOT NULL DEFAULT 0,
            likes       INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS likes (
            track_id  INTEGER NOT NULL,
            anon_id   TEXT NOT NULL,
            PRIMARY KEY (track_id, anon_id)
        );
        CREATE TABLE IF NOT EXISTS comments (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id   INTEGER NOT NULL,
            anon_id    TEXT NOT NULL,
            body       TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        -- event log powers the A/B analysis
        CREATE TABLE IF NOT EXISTS events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            anon_id    TEXT NOT NULL,
            variant    TEXT NOT NULL,          -- fair | popular
            kind       TEXT NOT NULL,          -- impression | play | like | unlike
            track_id   INTEGER NOT NULL,
            created_at REAL NOT NULL
        );
        """
    )
    db.commit()
    db.close()


# --------------------------------------------------------------------------- #
# Anonymous identity + A/B variant (cookies only)
# --------------------------------------------------------------------------- #
def get_anon_id():
    anon = request.cookies.get("anon")
    if not anon or not re.fullmatch(r"[0-9a-f]{12}", anon):
        anon = secrets.token_hex(6)
        g.new_anon = anon
    return anon


def get_variant():
    v = request.cookies.get("variant")
    if v not in VARIANTS:
        v = random.choice(VARIANTS)   # 50/50 random assignment, sticky per listener
        g.new_variant = v
    return v


def anon_name(anon_id):
    return "Listener-" + anon_id[:4].upper()


def attach_cookies(resp):
    if g.get("new_anon"):
        resp.set_cookie("anon", g.new_anon, max_age=31_536_000, samesite="Lax")
    if g.get("new_variant"):
        resp.set_cookie("variant", g.new_variant, max_age=31_536_000, samesite="Lax")
    return resp


def log_event(db, anon, variant, kind, track_id):
    db.execute(
        "INSERT INTO events (anon_id, variant, kind, track_id, created_at) VALUES (?,?,?,?,?)",
        (anon, variant, kind, track_id, time.time()),
    )


# --------------------------------------------------------------------------- #
# Link -> embed detection
# --------------------------------------------------------------------------- #
YT_RE = re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})")
AUDIO_EXT = (".mp3", ".wav", ".ogg", ".m4a", ".flac")


def classify_link(url):
    url = url.strip()
    m = YT_RE.search(url)
    if m:
        return "youtube", f"https://www.youtube.com/embed/{m.group(1)}"
    if "soundcloud.com" in url:
        return "soundcloud", (
            "https://w.soundcloud.com/player/?url=" + quote(url, safe="")
            + "&color=%232e5a88&auto_play=false&show_comments=false"
        )
    if urlparse(url).path.lower().endswith(AUDIO_EXT):
        return "audio", url
    return "link", url


# --------------------------------------------------------------------------- #
# Feeds
# --------------------------------------------------------------------------- #
@app.route("/")
def discover():
    db = get_db()
    anon = get_anon_id()
    variant = get_variant()

    if variant == "popular":
        rows = db.execute(
            """SELECT * FROM tracks
               ORDER BY plays DESC, likes DESC, created_at DESC
               LIMIT ?""", (DISCOVER_LIMIT,)
        ).fetchall()
    else:  # fair
        rows = db.execute(
            """SELECT * FROM tracks
               ORDER BY impressions ASC, created_at DESC
               LIMIT ?""", (DISCOVER_LIMIT,)
        ).fetchall()

    if rows:
        for r in rows:
            log_event(db, anon, variant, "impression", r["id"])
        if variant == "fair":
            # only the fair feed counts impressions for its rotation
            db.executemany(
                "UPDATE tracks SET impressions = impressions + 1 WHERE id = ?",
                [(r["id"],) for r in rows],
            )
        db.commit()

    liked = liked_set(db, anon)
    resp = make_response(render_template(
        "index.html", tracks=rows, liked=liked, tab="discover",
        anon_name=anon_name(anon)))
    return attach_cookies(resp)


@app.route("/rising")
def rising():
    db = get_db()
    anon = get_anon_id()
    get_variant()
    rows = db.execute(
        """SELECT *, (CAST(likes AS REAL) / (plays + ?)) AS rate
           FROM tracks
           WHERE plays > 0 OR likes > 0
           ORDER BY rate DESC, likes DESC
           LIMIT ?""", (RATE_PRIOR, DISCOVER_LIMIT)
    ).fetchall()
    liked = liked_set(db, anon)
    resp = make_response(render_template(
        "index.html", tracks=rows, liked=liked, tab="rising",
        anon_name=anon_name(anon)))
    return attach_cookies(resp)


@app.route("/submit", methods=["GET", "POST"])
def submit():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        artist = (request.form.get("artist") or "").strip() or "Anonymous"
        url = (request.form.get("url") or "").strip()
        note = (request.form.get("note") or "").strip()[:280]

        errors = []
        if not title:
            errors.append("Please give your track a title.")
        if not url or not re.match(r"^https?://", url):
            errors.append("Please paste a valid link (starting with http).")
        if errors:
            resp = make_response(render_template(
                "submit.html", errors=errors,
                title=title, artist=artist, url=url, note=note))
            return attach_cookies(resp)

        kind, embed = classify_link(url)
        db = get_db()
        cur = db.execute(
            """INSERT INTO tracks (title, artist, url, kind, embed, note, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (title, artist, url, kind, embed, note, time.time()))
        db.commit()
        return redirect(url_for("track_page", track_id=cur.lastrowid))

    get_anon_id(); get_variant()
    resp = make_response(render_template("submit.html", errors=None))
    return attach_cookies(resp)


@app.route("/track/<int:track_id>")
def track_page(track_id):
    db = get_db()
    t = db.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
    if t is None:
        abort(404)
    comments = db.execute(
        "SELECT * FROM comments WHERE track_id = ? ORDER BY created_at ASC",
        (track_id,)).fetchall()
    anon = get_anon_id(); get_variant()
    liked = liked_set(db, anon)
    resp = make_response(render_template(
        "track.html", t=t, comments=comments, liked=liked,
        anon_name=anon_name(anon)))
    return attach_cookies(resp)


@app.route("/play/<int:track_id>", methods=["POST"])
def play(track_id):
    db = get_db()
    anon = get_anon_id(); variant = get_variant()
    db.execute("UPDATE tracks SET plays = plays + 1 WHERE id = ?", (track_id,))
    log_event(db, anon, variant, "play", track_id)
    db.commit()
    row = db.execute("SELECT plays FROM tracks WHERE id = ?", (track_id,)).fetchone()
    return attach_cookies(jsonify(plays=row["plays"] if row else 0))


@app.route("/like/<int:track_id>", methods=["POST"])
def like(track_id):
    db = get_db()
    anon = get_anon_id(); variant = get_variant()
    existing = db.execute(
        "SELECT 1 FROM likes WHERE track_id = ? AND anon_id = ?", (track_id, anon)).fetchone()
    if existing:
        db.execute("DELETE FROM likes WHERE track_id = ? AND anon_id = ?", (track_id, anon))
        db.execute("UPDATE tracks SET likes = likes - 1 WHERE id = ?", (track_id,))
        log_event(db, anon, variant, "unlike", track_id)
        liked = False
    else:
        db.execute("INSERT INTO likes (track_id, anon_id) VALUES (?, ?)", (track_id, anon))
        db.execute("UPDATE tracks SET likes = likes + 1 WHERE id = ?", (track_id,))
        log_event(db, anon, variant, "like", track_id)
        liked = True
    db.commit()
    row = db.execute("SELECT likes FROM tracks WHERE id = ?", (track_id,)).fetchone()
    return attach_cookies(jsonify(liked=liked, likes=row["likes"] if row else 0))


@app.route("/comment/<int:track_id>", methods=["POST"])
def comment(track_id):
    body = (request.form.get("body") or "").strip()[:500]
    if body:
        db = get_db()
        anon = get_anon_id()
        db.execute(
            "INSERT INTO comments (track_id, anon_id, body, created_at) VALUES (?,?,?,?)",
            (track_id, anon, body, time.time()))
        db.commit()
    return attach_cookies(make_response(redirect(url_for("track_page", track_id=track_id))))


# --------------------------------------------------------------------------- #
# Stats — the experiment dashboard
# --------------------------------------------------------------------------- #
@app.route("/stats")
def stats():
    db = get_db()
    total_tracks = db.execute("SELECT COUNT(*) c FROM tracks").fetchone()["c"]

    per_variant = {}
    for v in VARIANTS:
        listeners = db.execute(
            "SELECT COUNT(DISTINCT anon_id) c FROM events WHERE variant = ?", (v,)
        ).fetchone()["c"]
        plays = db.execute(
            "SELECT COUNT(*) c FROM events WHERE variant = ? AND kind='play'", (v,)
        ).fetchone()["c"]
        likes = db.execute(
            "SELECT COUNT(*) c FROM events WHERE variant = ? AND kind='like'", (v,)
        ).fetchone()["c"]

        # plays per track within this variant
        rows = db.execute(
            "SELECT track_id, COUNT(*) c FROM events WHERE variant=? AND kind='play' GROUP BY track_id",
            (v,)).fetchall()
        track_plays = {r["track_id"]: r["c"] for r in rows}
        tracks_with_a_play = len(track_plays)
        unheard = max(0, total_tracks - tracks_with_a_play)
        top_share = None
        if plays > 0:
            top_share = round(100 * max(track_plays.values()) / plays)

        per_variant[v] = dict(
            listeners=listeners, plays=plays, likes=likes,
            reached=tracks_with_a_play, unheard=unheard, top_share=top_share,
        )

    # per-track table (overall counters)
    tracks = db.execute(
        "SELECT * FROM tracks ORDER BY created_at DESC").fetchall()

    return render_template("stats.html", pv=per_variant, total_tracks=total_tracks,
                           tracks=tracks)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def liked_set(db, anon):
    rows = db.execute("SELECT track_id FROM likes WHERE anon_id = ?", (anon,)).fetchall()
    return {r["track_id"] for r in rows}


@app.template_filter("ago")
def ago(ts):
    secs = max(0, int(time.time() - ts))
    if secs < 60: return "just now"
    m = secs // 60
    if m < 60: return f"{m}m ago"
    h = m // 60
    if h < 24: return f"{h}h ago"
    return f"{h // 24}d ago"


@app.context_processor
def inject_helpers():
    def like_rate(t):
        plays = t["plays"] or 0
        if plays == 0:
            return None
        return round(100 * (t["likes"] or 0) / plays)
    return dict(like_rate=like_rate)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
