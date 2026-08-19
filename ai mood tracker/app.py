"""
AI Mood Tracker — Flask Backend
Pure-Python NLP sentiment analysis (no external AI libraries required).
Uses a weighted keyword lexicon + rule-based logic for Happy/Sad/Angry/Neutral.
"""

from flask import Flask, request, jsonify, render_template
import sqlite3, os, re
from datetime import datetime, timedelta

app = Flask(__name__)

# ─────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(__file__), "moods.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS moods (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                text        TEXT    NOT NULL,
                mood        TEXT    NOT NULL,
                score       REAL    NOT NULL,
                emoji       TEXT    NOT NULL,
                created_at  TEXT    NOT NULL
            )
        """)
        conn.commit()
    print("✅  Database ready.")


# ─────────────────────────────────────────────────────────────
# PURE-PYTHON NLP — WEIGHTED SENTIMENT LEXICON
# ─────────────────────────────────────────────────────────────

POSITIVE_LEXICON = {
    "amazing": 2, "wonderful": 2, "fantastic": 2, "ecstatic": 2,
    "thrilled": 2, "overjoyed": 2, "elated": 2, "blessed": 2,
    "brilliant": 2, "awesome": 2, "excellent": 2, "incredible": 2,
    "outstanding": 2, "euphoric": 2, "joyful": 2, "love": 2,
    "happy": 1, "good": 1, "great": 1, "glad": 1, "pleased": 1,
    "cheerful": 1, "content": 1, "grateful": 1, "thankful": 1,
    "excited": 1, "hopeful": 1, "optimistic": 1, "delighted": 1,
    "proud": 1, "calm": 1, "relaxed": 1, "satisfied": 1,
    "enjoy": 1, "enjoyed": 1, "smile": 1, "smiling": 1,
    "better": 1, "positive": 1, "fine": 0.5, "okay": 0.5, "ok": 0.5,
    "decent": 0.5, "alright": 0.5,
}

NEGATIVE_LEXICON = {
    "terrible": -2, "horrible": -2, "awful": -2, "dreadful": -2,
    "miserable": -2, "hopeless": -2, "devastated": -2, "heartbroken": -2,
    "depressed": -2, "worthless": -2, "disgusting": -2, "hate": -2,
    "sad": -1, "unhappy": -1, "upset": -1, "bad": -1, "down": -1,
    "gloomy": -1, "lonely": -1, "tired": -1, "exhausted": -1,
    "worried": -1, "anxious": -1, "stressed": -1, "nervous": -1,
    "scared": -1, "afraid": -1, "hurt": -1, "pain": -1,
    "crying": -1, "cry": -1, "tears": -1, "sorrow": -1, "grief": -1,
    "lost": -1, "confused": -1, "bored": -0.5,
}

ANGRY_LEXICON = {
    "furious": -2, "outraged": -2, "livid": -2, "enraged": -2,
    "infuriated": -2, "rage": -2, "seething": -2,
    "angry": -1, "mad": -1, "annoyed": -1, "frustrated": -1,
    "irritated": -1, "bitter": -1, "resentful": -1, "agitated": -1,
    "hostile": -1, "aggressive": -1,
}

NEGATIONS = {"not", "no", "never", "dont", "doesnt", "didnt", "cant",
             "cannot", "wont", "isnt", "arent", "wasnt", "werent",
             "hardly", "barely"}

INTENSIFIERS = {"very": 1.5, "really": 1.5, "so": 1.3, "extremely": 2.0,
                "incredibly": 2.0, "absolutely": 1.8, "totally": 1.4,
                "quite": 1.2, "pretty": 1.1, "super": 1.5}

MOOD_META = {
    "happy":   {"emoji": "😊", "color": "#f59e0b"},
    "sad":     {"emoji": "😢", "color": "#3b82f6"},
    "angry":   {"emoji": "😠", "color": "#ef4444"},
    "neutral": {"emoji": "😐", "color": "#8b5cf6"},
}


def tokenize(text):
    # Remove apostrophes to handle contractions (don't -> dont)
    text = text.replace("'", "").replace("\u2019", "")
    return re.findall(r"[a-z]+", text.lower())


def analyze_sentiment(text):
    tokens = tokenize(text)
    pos_score = 0.0
    neg_score = 0.0
    anger_score = 0.0
    negate = False
    intensity = 1.0

    for word in tokens:
        if word in NEGATIONS:
            negate = True
            intensity = 1.0
            continue
        if word in INTENSIFIERS:
            intensity = INTENSIFIERS[word]
            continue

        hit = False

        w = POSITIVE_LEXICON.get(word, 0)
        if w:
            hit = True
            if negate:
                neg_score += abs(w) * intensity
            else:
                pos_score += w * intensity

        w = NEGATIVE_LEXICON.get(word, 0)
        if w:
            hit = True
            if negate:
                pos_score += abs(w) * intensity
            else:
                neg_score += abs(w) * intensity

        w = ANGRY_LEXICON.get(word, 0)
        if w:
            hit = True
            if negate:
                pos_score += abs(w) * intensity * 0.5
            else:
                anger_score += abs(w) * intensity
                neg_score   += abs(w) * intensity * 0.5

        if hit:
            negate = False
            intensity = 1.0

    total = pos_score + neg_score + anger_score + 0.001

    polarity = (pos_score - neg_score - anger_score * 0.5) / total

    if anger_score > 0 and anger_score >= neg_score * 0.6:
        mood = "angry"
    elif pos_score > neg_score and pos_score > anger_score:
        mood = "happy"
    elif neg_score > pos_score or anger_score > pos_score:
        mood = "sad"
    else:
        mood = "neutral"

    if pos_score == 0 and neg_score == 0 and anger_score == 0:
        mood = "neutral"
        polarity = 0.0

    raw_conf = (max(pos_score, neg_score, anger_score) / total) * 100
    confidence = min(round(raw_conf, 1), 100)

    meta = MOOD_META[mood]
    return {
        "mood":       mood,
        "emoji":      meta["emoji"],
        "color":      meta["color"],
        "polarity":   round(max(-1.0, min(1.0, polarity)), 3),
        "confidence": confidence,
    }


# ─────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()

    if not text:
        return jsonify({"error": "Please enter some text."}), 400
    if len(text) > 1000:
        return jsonify({"error": "Text too long (max 1000 characters)."}), 400

    result = analyze_sentiment(text)
    now    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        conn.execute(
            "INSERT INTO moods (text, mood, score, emoji, created_at) VALUES (?,?,?,?,?)",
            (text, result["mood"], result["polarity"], result["emoji"], now)
        )
        conn.commit()

    return jsonify({
        "mood":       result["mood"].capitalize(),
        "emoji":      result["emoji"],
        "color":      result["color"],
        "polarity":   result["polarity"],
        "confidence": result["confidence"],
        "timestamp":  now,
    })


@app.route("/api/history")
def history():
    limit = min(int(request.args.get("limit", 20)), 100)
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM moods ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/trends")
def trends():
    since = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        rows = conn.execute(
            "SELECT mood, score, created_at FROM moods WHERE created_at >= ? ORDER BY created_at",
            (since,)
        ).fetchall()

    distribution = {"happy": 0, "sad": 0, "angry": 0, "neutral": 0}
    daily = {}

    for r in rows:
        distribution[r["mood"]] = distribution.get(r["mood"], 0) + 1
        day = r["created_at"][:10]
        if day not in daily:
            daily[day] = {"happy": 0, "sad": 0, "angry": 0, "neutral": 0, "total": 0}
        daily[day][r["mood"]] += 1
        daily[day]["total"]   += 1

    sorted_daily = [{"date": d, **v} for d, v in sorted(daily.items())]
    return jsonify({"distribution": distribution, "daily": sorted_daily, "total": len(rows)})


@app.route("/api/stats")
def stats():
    with get_db() as conn:
        total       = conn.execute("SELECT COUNT(*) FROM moods").fetchone()[0]
        today       = datetime.now().strftime("%Y-%m-%d")
        today_count = conn.execute(
            "SELECT COUNT(*) FROM moods WHERE created_at LIKE ?", (today + "%",)
        ).fetchone()[0]
        common = conn.execute("""
            SELECT mood, COUNT(*) as cnt FROM moods
            GROUP BY mood ORDER BY cnt DESC LIMIT 1
        """).fetchone()
        since7    = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        avg_score = conn.execute(
            "SELECT AVG(score) FROM moods WHERE created_at >= ?", (since7,)
        ).fetchone()[0]

    return jsonify({
        "total":        total,
        "today":        today_count,
        "top_mood":     dict(common) if common else None,
        "avg_polarity": round(avg_score, 3) if avg_score else 0,
    })


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("🚀  http://127.0.0.1:5000")
    app.run(debug=True)
