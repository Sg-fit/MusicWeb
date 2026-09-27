# Fresh Feed

A tiny fair-discovery music site — built to test two problems:

1. **Teen musicians can't get heard.**
2. **Listeners can't find good, unpopular music.**

The whole idea lives in the ranking:

- **Discover** shows the **least-seen tracks first** (guaranteed rotation), so a
  brand-new artist gets real ears regardless of followers.
- **Rising** ranks by **like rate** (`likes / (plays + 5)`), *not* total plays —
  so a great unknown track beats a popular-but-skippable one.

No accounts. Each visitor gets an anonymous `Listener-XXXX` id in a cookie,
only so likes aren't double-counted and comments have a handle.

Paste-a-link, no audio hosting: YouTube, SoundCloud, or a direct audio file
(`.mp3/.wav/.ogg/.m4a/.flac`) all embed; anything else shows as an open-in-new-tab link.

## Run it

```bash
cd MusicWeb
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000 . The SQLite database (`freshfeed.db`) is created
automatically on first run.

## Put it online for the experiment

You already used a Cloudflare Tunnel for Charweb — same idea:

```bash
cloudflared tunnel --url http://localhost:5000
```

Share the URL with your two teen creators + a handful of listener friends.

## What to measure this week

The data you need is already logged in `freshfeed.db`:

- **impressions / plays / likes** per track (`tracks` table)
- **comments** (`comments` table)

Questions to answer:

- Do the *unknown* tracks actually get played through, or ignored?
- Do listeners like anything they didn't already know?
- Do the creators feel heard? (ask them after — compare to what the logs show)

## Files

- `app.py` — the whole app: routes, DB, fair-rotation + like-rate logic
- `templates/` — pages (`index`, `track`, `submit`) + `_card.html`
- `static/style.css`, `static/app.js` — styling + play/like interactions

## Next steps (after the experiment, if it proves out)

- Real audio uploads instead of links
- Anti-gaming: cap fake plays / bot accounts — this is where your Charweb
  behavioral-detection work plugs in
- Taste-matching recommendations (audio features + listening history)
