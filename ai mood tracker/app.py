"""
AI Mood Tracker — Flask Backend
Intelligent emotion analysis using AI (Groq) with lexicon fallback.
Analyzes context and real-life situations for accurate mood detection.
"""

from flask import Flask, request, jsonify, render_template
import sqlite3, os, re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
    
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

MOOD_SWING_TRIGGERS = {
    "jealous": {
        "mood": "fear",
        "emotion": "Jealousy",
        "swing": "fear + anger + insecurity",
        "polarity": -0.6
    },
    "jealousy": {
        "mood": "fear",
        "emotion": "Jealousy",
        "swing": "fear + anger + insecurity",
        "polarity": -0.6
    },
    "envy": {
        "mood": "fear",
        "emotion": "Jealousy",
        "swing": "fear + anger + insecurity",
        "polarity": -0.6
    },
    "guilt": {
        "mood": "sad",
        "emotion": "Guilt",
        "swing": "sadness + fear",
        "polarity": -0.6
    },
    "guilty": {
        "mood": "sad",
        "emotion": "Guilt",
        "swing": "sadness + fear",
        "polarity": -0.6
    },
    "pride": {
        "mood": "happy",
        "emotion": "Pride",
        "swing": "happiness + confidence",
        "polarity": 0.7
    },
    "proud": {
        "mood": "happy",
        "emotion": "Pride",
        "swing": "happiness + confidence",
        "polarity": 0.7
    },
    "shame": {
        "mood": "fear",
        "emotion": "Shame",
        "swing": "fear + sadness",
        "polarity": -0.6
    },
    "ashamed": {
        "mood": "fear",
        "emotion": "Shame",
        "swing": "fear + sadness",
        "polarity": -0.6
    },
    "embarrassment": {
        "mood": "fear",
        "emotion": "Embarrassment",
        "swing": "fear + sadness + insecurity",
        "polarity": -0.6
    },
    "embarrassed": {
        "mood": "fear",
        "emotion": "Embarrassment",
        "swing": "fear + sadness + insecurity",
        "polarity": -0.6
    }
}

MOOD_META = {
    "happy":       {"emoji": "😊", "color": "#f59e0b"},
    "excited":     {"emoji": "🤩", "color": "#ff6b35"},
    "proud":       {"emoji": "😌", "color": "#6366f1"},
    "relaxed":     {"emoji": "😌", "color": "#10b981"},
    "loved":       {"emoji": "😍", "color": "#ec4899"},
    "sad":         {"emoji": "😢", "color": "#3b82f6"},
    "angry":       {"emoji": "😠", "color": "#ef4444"},
    "fear":        {"emoji": "😨", "color": "#7c3aed"},
    "anxiety":     {"emoji": "😟", "color": "#a78bfa"},
    "stress":      {"emoji": "😤", "color": "#f97316"},
    "lonely":      {"emoji": "😔", "color": "#0e7490"},
    "disappointed": {"emoji": "😞", "color": "#6b7280"},
    "neutral":     {"emoji": "😐", "color": "#8b5cf6"},
    "confused":    {"emoji": "😕", "color": "#eab308"},
    "surprise":    {"emoji": "😲", "color": "#fb923c"},
}

EMOTION_META = {
    "jealousy": {"emoji": "😒🔥", "color": "#9333ea"},
    "guilt":    {"emoji": "😔⚖️", "color": "#2563eb"},
    "pride":    {"emoji": "😌🏆", "color": "#f59e0b"},
    "shame":    {"emoji": "😳🙈", "color": "#f97316"},
    "embarrassment": {"emoji": "🫣", "color": "#fb7185"},
}

# ─────────────────────────────────────────────────────────────
# REASONS & SUGGESTIONS
# ─────────────────────────────────────────────────────────────

REASONS = {
    "happy": [
        "Social interaction",
        "Success or achievement",
        "Positive moment with loved ones",
        "Enjoyable experience",
        "Personal growth"
    ],
    "sad": [
        "Disappointment or loss",
        "Loneliness",
        "Academic or personal failure",
        "Conflict with others",
        "Feeling overwhelmed",
        "Uncertainty about future"
    ],
    "angry": [
        "Conflict or disagreement",
        "Feeling disrespected",
        "Frustration with situation",
        "Unfair treatment",
        "Loss of control"
    ],
    "neutral": [
        "Routine day",
        "No significant events",
        "Balanced state",
        "Steady mood"
    ]
}

SUGGESTIONS = {
    "happy": ["Meet friends", "Share joy", "Celebrate achievement", "Try new hobby"],
    "excited": ["Plan something fun", "Share excitement", "Capture the moment", "Explore ideas"],
    "proud": ["Celebrate yourself", "Tell someone", "Reflect on success", "Set new goals"],
    "relaxed": ["Enjoy the moment", "Do nothing", "Read a book", "Listen to music"],
    "loved": ["Spend time together", "Say thank you", "Plan a date", "Express affection"],
    "sad": ["Talk to friend", "Rest well", "Cry if needed", "Seek support"],
    "angry": ["Breathe slow", "Walk away", "Count to ten", "Express calmly"],
    "fear": ["Take support", "Face it slowly", "Breathe deeply", "Talk it out"],
    "anxiety": ["Deep breaths", "Ground yourself", "Journal thoughts", "Practice mindfulness"],
    "stress": ["Take a break", "Relax", "Exercise lightly", "Prioritize tasks"],
    "lonely": ["Reach out", "Join groups", "Call a friend", "Volunteer"],
    "disappointed": ["Try again", "Learn from it", "Talk to someone", "Self-compassion"],
    "neutral": ["Try new", "Add fun", "Plan activity", "Reflect on day"],
    "confused": ["Ask for help", "Take time", "Research topic", "Break it down"],
    "surprise": ["Embrace it", "Share it", "Process feelings", "Adapt quickly"]
}


def tokenize(text):
    # Remove apostrophes to handle contractions (don't -> dont)
    text = text.replace("'", "").replace("\u2019", "")
    return re.findall(r"[a-z]+", text.lower())


def detect_mood_swing(tokens):
    for word in tokens:
        if word in MOOD_SWING_TRIGGERS:
            return MOOD_SWING_TRIGGERS[word]
    return None


def get_reason(text, mood, tokens):
    """Determine reason for the detected mood based on keywords."""
    import random
    
    # Keyword categories
    social_keywords = {"friend", "family", "friends", "party", "people", "with", "together", "hang", "spent", "social"}
    achievement_keywords = {"win", "success", "passed", "achieved", "accomplish", "solved", "completed", "finished", "goal", "promotion", "scored"}
    conflict_keywords = {"fight", "fight", "argue", "argument", "disagreement", "conflict", "fight", "yell", "scream", "blame", "fault"}
    failure_keywords = {"failed", "fail", "lost", "low", "bad", "poor", "score", "marks", "exam", "broke", "mistake", "wrong"}
    loneliness_keywords = {"alone", "lonely", "isolated", "abandoned", "scare", "scared"}
    accident_keywords = {"accident", "injured", "injury", "hurt", "shock", "shocked", "trauma", "traumatic", "scared", "nervous"}
    
    token_set = set(tokens)
    
    if mood == "happy":
        if social_keywords & token_set:
            return "Social interaction"
        elif achievement_keywords & token_set:
            return "Success or achievement"
        else:
            return random.choice(REASONS[mood])
    
    elif mood == "sad":
        if failure_keywords & token_set:
            return "Academic or personal failure"
        elif loneliness_keywords & token_set:
            return "Loneliness"
        elif conflict_keywords & token_set:
            return "Conflict with others"
        elif accident_keywords & token_set:
            return "Unexpected traumatic event"
        else:
            return random.choice(REASONS[mood])
    
    elif mood == "angry":
        if conflict_keywords & token_set:
            return "Conflict or disagreement"
        elif failure_keywords & token_set:
            return "Frustration with situation"
        else:
            return random.choice(REASONS[mood])
    
    else:  # neutral
        return random.choice(REASONS[mood])


def analyze_sentiment(text):
    """Enhanced sentiment analysis using AI for better understanding."""
    load_dotenv(override=True)
    groq_key = os.getenv("GROQ_API_KEY", "")
    
    # Map emotion to itself (no conversion needed)
    emotion_mapping = {
        "happy": "happy",
        "excited": "excited",
        "proud": "proud",
        "relaxed": "relaxed",
        "loved": "loved",
        "sad": "sad",
        "angry": "angry",
        "fear": "fear",
        "anxiety": "anxiety",
        "stress": "stress",
        "lonely": "lonely",
        "disappointed": "disappointed",
        "jealousy": "fear",
        "guilt": "sad",
        "pride": "happy",
        "shame": "fear",
        "embarrassment": "fear",
        "embarrassed": "fear",
        "confidence": "happy",
        "insecurity": "sad",
        "neutral": "neutral",
        "confused": "confused",
        "surprise": "surprise"
    }
    
    try:
        client = Groq(api_key=groq_key)

        prompt = f"""You are an AI Mood Tracker.

Analyze the user's input and choose the most suitable emotion ONLY from this list:
Happy, Excited, Proud, Relaxed, Loved,
Sad, Angry, Fear, Anxiety, Stress, Lonely, Disappointed,
Jealousy, Guilt, Pride, Shame, Embarrassment,
Neutral, Confused, Surprise

Then give:
1. Emotion (only from the list)
2. Reason (3 short lines)
3. Suggestion (4 short tips)

Rules:
- Use simple English
- Keep answers short
- Understand meaning, not just keywords
- Choose the strongest emotion

Input: "{text}"

Output:

Emotion:
Reason:
Suggestion:
- 
- 
- 
- 
"""

        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            max_tokens=300
        )
        
        response = chat_completion.choices[0].message.content.strip()
        
        # Parse the response
        lines = response.split('\n')
        emotion = "neutral"
        reason = "Routine day"
        suggestions = ["Try something new", "Add small activities"]
        
        current_section = None
        reason_lines = []
        for line in lines:
            line = line.strip()
            if line.startswith("Emotion:"):
                emotion = line.replace("Emotion:", "").strip().lower()
                current_section = "emotion"
            elif line.startswith("Reason:"):
                reason_lines = [line.replace("Reason:", "").strip()]
                current_section = "reason"
            elif line.startswith("Suggestion:"):
                suggestions = []
                current_section = "suggestion"
                # Join reason lines
                reason = " ".join(reason_lines).strip()
            elif current_section == "reason" and line and not line.startswith("Emotion:") and not line.startswith("Suggestion:"):
                # Continue collecting reason lines, up to 3
                if len(reason_lines) < 3:
                    reason_lines.append(line)
            elif line.startswith("- ") and current_section == "suggestion":
                if len(suggestions) < 4:  # Take up to 4 suggestions
                    suggestions.append(line[2:].strip())
            elif line and current_section == "suggestion" and not line.startswith("Emotion:") and not line.startswith("Reason:"):
                # Handle multi-line suggestions
                if suggestions and not suggestions[-1].endswith('.'):
                    suggestions[-1] += " " + line
                else:
                    suggestions.append(line)
        
        # If no suggestions found, use defaults based on emotion
        if not suggestions:
            suggestions = SUGGESTIONS.get(emotion_mapping.get(emotion, "neutral"), ["Try new", "Add fun", "Connect with others", "Practice gratitude"])
        
        mood = emotion_mapping.get(emotion, "neutral")
        
        # Calculate polarity based on emotion
        polarity_map = {
            "happy": 0.8,
            "excited": 0.9,
            "proud": 0.7,
            "relaxed": 0.6,
            "loved": 0.8,
            "sad": -0.7,
            "angry": -0.8,
            "fear": -0.7,
            "anxiety": -0.6,
            "stress": -0.6,
            "lonely": -0.7,
            "disappointed": -0.6,
            "jealousy": -0.6,
            "guilt": -0.6,
            "pride": 0.7,
            "shame": -0.6,
            "embarrassment": -0.6,
            "confidence": 0.7,
            "insecurity": -0.5,
            "neutral": 0.0,
            "confused": -0.2,
            "surprise": 0.3
        }
        polarity = polarity_map.get(mood, 0.0)
        
        meta = EMOTION_META.get(emotion.lower(), MOOD_META.get(mood, MOOD_META["neutral"]))
        swing = None
        if emotion.lower() in MOOD_SWING_TRIGGERS:
            swing = MOOD_SWING_TRIGGERS[emotion.lower()]["swing"]

        return {
            "emotion":    emotion.capitalize(),  # Return actual emotion
            "mood":       mood,
            "emoji":      meta["emoji"],
            "color":      meta["color"],
            "polarity":   polarity,
            "confidence": 85.0,  # AI-based, so high confidence
            "reason":     reason,
            "suggestions": suggestions,
            "swing":      swing,
        }
    except Exception as e:
        print(f"Groq API Error: {e}")
        # Fallback to lexicon
        return analyze_sentiment_lexicon(text)


def analyze_sentiment_lexicon(text):
    """Original lexicon-based analysis as fallback."""
    tokens = tokenize(text)
    swing = detect_mood_swing(tokens)
    if swing:
        mood = swing["mood"]
        emotion = swing["emotion"]
        meta = EMOTION_META.get(emotion.lower(), MOOD_META.get(mood, MOOD_META["neutral"]))
        reason = get_reason(text, mood, tokens)
        return {
            "emotion":    emotion,
            "mood":       mood,
            "emoji":      meta["emoji"],
            "color":      meta["color"],
            "polarity":   swing.get("polarity", 0.0),
            "confidence": 88.0,
            "reason":     reason,
            "suggestions": SUGGESTIONS.get(mood, SUGGESTIONS["neutral"]),
            "swing":      swing["swing"],
        }

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
    reason = get_reason(text, mood, tokens)
    
    # Map mood to emotion name
    mood_to_emotion = {
        "happy": "Happy",
        "sad": "Sad",
        "angry": "Angry",
        "neutral": "Neutral"
    }
    
    return {
        "emotion":    mood_to_emotion.get(mood, "Neutral"),
        "mood":       mood,
        "emoji":      meta["emoji"],
        "color":      meta["color"],
        "polarity":   round(max(-1.0, min(1.0, polarity)), 3),
        "confidence": confidence,
        "reason":     reason,
        "suggestions": SUGGESTIONS[mood],
    }


# ─────────────────────────────────────────────────────────────
# RECOMMENDATIONS
# ─────────────────────────────────────────────────────────────

RECOMMENDATIONS = {
    "happy": {
        "books": ["The Happiness Project by Gretchen Rubin", "Big Magic by Elizabeth Gilbert"],
        "quotes": ["Happiness is not by chance, but by choice.", "Keep spreading that positive energy!"],
        "activities": ["Share your joy with a friend", "Start a gratitude journal", "Dance to your favorite upbeat song"],
        "movies": ["La La Land", "Singin' in the Rain", "Paddington 2"],
        "music": ["'Walking on Sunshine' - Katrina & The Waves", "'Don't Stop Me Now' - Queen", "Upbeat Pop Playlist"]
    },
    "excited": {
        "books": ["The Magic of Thinking Big by David Schwartz", "Steal Like an Artist by Austin Kleon"],
        "quotes": ["Adventure is worthwhile!", "Life is either a daring adventure or nothing at all."],
        "activities": ["Plan your next adventure", "Try something new and exciting", "Share your excitement with others"],
        "movies": ["Whiplash", "Rocky", "The Greatest Showman"],
        "music": ["'Eye of the Tiger' - Survivor", "Energetic Pop Playlist", "Pump Up Playlist"]
    },
    "proud": {
        "books": ["Mindset by Carol Dweck", "Start with Why by Simon Sinek"],
        "quotes": ["Be proud of who you are.", "Your only limit is your soul."],
        "activities": ["Write down your accomplishments", "Tell someone about your success", "Celebrate yourself"],
        "movies": ["Rocky", "Hidden Figures", "The Pursuit of Happiness"],
        "music": ["'Champion' - Fallout Boy", "Powerful Anthem Playlist", "Victory Music"]
    },
    "relaxed": {
        "books": ["The Art of Doing Nothing by Veronique Vienne", "Four Thousand Weeks by Oliver Burkeman"],
        "quotes": ["Peace comes from within.", "Sometimes what you're searching for is already there."],
        "activities": ["Take a leisurely walk in nature", "Meditate or do yoga", "Enjoy a slow tea or coffee"],
        "movies": ["Lost in Translation", "Amélie", "Moonlight"],
        "music": ["'Weightless' - Marconi Union", "Ambient Relaxation", "Spa and Wellness Playlist"]
    },
    "loved": {
        "books": ["The Art of Love by Erich Fromm", "All the Bright Places by Jennifer Niven"],
        "quotes": ["Love is patient, love is kind.", "The greatest thing you'll ever learn is just to love and be loved in return."],
        "activities": ["Spend quality time with loved ones", "Write a heartfelt letter", "Share a meaningful conversation"],
        "movies": ["The Notebook", "Clueless", "About Time"],
        "music": ["'All of Me' - John Legend", "Love Songs Playlist", "Romantic Ballads"]
    },
    "sad": {
        "books": ["Reasons to Stay Alive by Matt Haig", "Tiny Beautiful Things by Cheryl Strayed"],
        "quotes": ["This too shall pass.", "Tears come from the heart and not from the brain."],
        "activities": ["Take a warm bath", "Practice gentle yoga or stretching", "Write down your feelings without judgment"],
        "movies": ["Inside Out", "The Pursuit of Happyness", "Spirited Away"],
        "music": ["'Fix You' - Coldplay", "Soothing Acoustic Playlist", "Lo-Fi relaxing beats"]
    },
    "angry": {
        "books": ["The Dance of Anger by Harriet Lerner", "Anger: Wisdom for Cooling the Flames by Thich Nhat Hanh"],
        "quotes": ["For every minute you remain angry, you give up sixty seconds of peace of mind.", "Hold your words when you are angry."],
        "activities": ["Do an intense workout or go for a run", "Practice deep breathing (box breathing: 4-4-4-4)", "Punch a pillow or tear up unneeded paper"],
        "movies": ["Fight Club", "Mad Max: Fury Road", "A calming nature documentary like Planet Earth"],
        "music": ["'Break Stuff' - Limp Bizkit", "High-Energy Rock Playlist", "Calm Classical Music to de-escalate"]
    },
    "fear": {
        "books": ["Feel the Fear and Do It Anyway by Susan Jeffers", "The Courage to Be Disliked by Kishimi Ichiro"],
        "quotes": ["Courage is not the absence of fear.", "Fear is only as deep as the mind allows it."],
        "activities": ["Reach out to someone you trust", "Practice grounding techniques", "Take small steps toward facing your fear"],
        "movies": ["Forrest Gump", "The Shawshank Redemption", "Life is Beautiful"],
        "music": ["'Stronger (What Doesn't Kill You)' - Kelly Clarkson", "Empowering Playlist", "Motivational Soundtrack"]
    },
    "anxiety": {
        "books": ["The Anxiety and Phobia Workbook by Edmund J. Bourne", "Dare by Barry McDonagh"],
        "quotes": ["Anxiety is temporary; strength is permanent.", "You are not your thoughts."],
        "activities": ["Practice breathing exercises", "Progressive muscle relaxation", "Create a safe space to relax"],
        "movies": ["Paterson", "Her", "The Secret Life of Walter Mitty"],
        "music": ["'Ocean Breathes Salty' - Modest Mouse", "Calm Ambient Playlist", "Meditation and Mindfulness Music"]
    },
    "stress": {
        "books": ["The Stress Cure by Rangan Chatterjee", "Why Zebras Don't Get Ulcers by Robert Sapolsky"],
        "quotes": ["Stress is caused by being here, but wanting to be there.", "Take care of your body. It's the only place you have to live."],
        "activities": ["Taking a mental health day", "Go for a nature walk", "Try progressive muscle relaxation"],
        "movies": ["Groundhog Day", "About Time", "Eat Pray Love"],
        "music": ["'Let It Be' - The Beatles", "Calming Instrumental", "Nature Sounds and Ambient Music"]
    },
    "lonely": {
        "books": ["Never Let Me Go by Kazuo Ishiguro", "The Midnight Library by Matt Haig"],
        "quotes": ["You are never truly alone.", "Connection is why we're here."],
        "activities": ["Reach out to a friend", "Join a community or group", "Volunteer for a cause you care about"],
        "movies": ["Forrest Gump", "Finding Neverland", "Juno"],
        "music": ["'You are Not Alone' - Michael Jackson", "Uplifting Music Playlist", "Feel Good Hits"]
    },
    "disappointed": {
        "books": ["The Gap and the Gain by Dan Sullivan", "Atomic Habits by James Clear"],
        "quotes": ["Failure is just the beginning of success.", "Every expert was once a beginner."],
        "activities": ["Reflect on what you learned", "Plan your next attempt", "Celebrate small progress"],
        "movies": ["Rocky", "The Blind Side", "Erin Brockovich"],
        "music": ["'Stronger (What Doesn't Kill You)' - Kelly Clarkson", "Motivational Playlist", "Comeback Anthem"]
    },
    "neutral": {
        "books": ["Atomic Habits by James Clear", "The Power of Habit by Charles Duhigg"],
        "quotes": ["Balance is not something you find, it's something you create.", "A quiet mind is able to hear intuition over fear."],
        "activities": ["Read a chapter of a new book", "Declutter your workspace", "Try a short mindfulness meditation"],
        "movies": ["The Secret Life of Walter Mitty", "Chef", "Lost In Translation"],
        "music": ["'Weightless' - Marconi Union", "Instrumental Focus Playlist", "Ambient electronic music"]
    },
    "confused": {
        "books": ["Thinking, Fast and Slow by Daniel Kahneman", "The Art of Problem Solving by Russell L. Ackoff"],
        "quotes": ["Clarity comes with questions.", "Out of confusion arises clarity."],
        "activities": ["Write down your thoughts", "Talk it through with someone", "Take time to process"],
        "movies": ["Inception", "Eternal Sunshine of the Spotless Mind", "The Matrix"],
        "music": ["'Don't Stop Believin'' - Journey", "Clarity Instrumental", "Focus and Concentration Music"]
    },
    "surprise": {
        "books": ["The Black Swan by Nassim Nicholas Taleb", "A Man Called Ove by Fredrik Backman"],
        "quotes": ["Surprise is the greatest gift.", "Life is what happens when you're busy making other plans."],
        "activities": ["Embrace the moment", "Share the surprise with others", "Reflect on the unexpected"],
        "movies": ["Amélie", "Juno", "About Time"],
        "music": ["'Good as Hell' - Lizzo", "Uplifting Pop Playlist", "Feel Good Music"]
    }
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
        "emotion":    result.get("emotion", result["mood"].capitalize()),
        "mood":       result["mood"].capitalize(),
        "emoji":      result["emoji"],
        "color":      result["color"],
        "polarity":   result["polarity"],
        "confidence": result["confidence"],
        "reason":     result["reason"],
        "suggestions": result["suggestions"],
        "timestamp":  now,
        "recommendations": RECOMMENDATIONS[result["mood"]],
        "swing":      result.get("swing")
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

    all_moods = ["happy", "excited", "proud", "relaxed", "loved", "sad", "angry", "fear", "anxiety", "stress", "lonely", "disappointed", "neutral", "confused", "surprise"]
    distribution = {mood: 0 for mood in all_moods}
    daily = {}

    for r in rows:
        distribution[r["mood"]] = distribution.get(r["mood"], 0) + 1
        day = r["created_at"][:10]
        if day not in daily:
            daily[day] = {mood: 0 for mood in all_moods}
            daily[day]["total"] = 0
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


@app.route("/api/chat", methods=["POST"])
def chat():
    load_dotenv(override=True)
    groq_key = os.getenv("GROQ_API_KEY", "")
    
    if not groq_key:
        return jsonify({"error": "GROQ_API_KEY is missing in .env"}), 500
        
    data = request.get_json(silent=True) or {}
    messages = data.get("messages", [])
    current_mood = data.get("current_mood", "unknown")
    
    if not messages:
        return jsonify({"error": "No messages provided."}), 400
        
    try:
        client = Groq(api_key=groq_key)
        
        system_content = "You are a highly empathetic, supportive, and kind AI companion. Your goal is to listen to the user, validate their feelings, and help improve their mood through conversational support. Do not act like a medical professional, but be a supportive friend. Keep your responses concise, warm, and conversational."
        if current_mood and current_mood != "unknown":
            system_content += f" IMPORTANT CONTEXT: The user's current detected mood is '{current_mood}'. Please immediately adapt your initial tone taking this emotion into account!"

        system_prompt = {
            "role": "system",
            "content": system_content
        }
        
        chat_completion = client.chat.completions.create(
            messages=[system_prompt] + messages,
            model="llama-3.3-70b-versatile",
        )
        return jsonify({"response": chat_completion.choices[0].message.content})
    except Exception as e:
        print(f"Groq API Error: {e}")
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("🚀  http://127.0.0.1:5000")
    app.run(debug=True)
