"""
Nestora — database layer.
Uses plain sqlite3 (no ORM) so the SQL stays easy to read.
Pandas is used on top of this in matching.py to do the actual
data-analysis / compatibility-scoring work.
"""
import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "instance", "nestora.db")

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
BLOCKS = ["Morning", "Afternoon", "Evening", "Night"]


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def default_schedule():
    """7 days x 4 blocks. Night defaults to sleep, one afternoon block to study."""
    grid = {}
    for d in DAYS:
        grid[d] = ["free", "study", "free", "sleep"]
    return grid


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'student',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    college TEXT DEFAULT '',
    bio TEXT DEFAULT '',
    study_hours INTEGER DEFAULT 4,
    hobbies TEXT DEFAULT '[]',
    avatar TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS preferences (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    sleep INTEGER DEFAULT 23,
    wake INTEGER DEFAULT 7,
    clean INTEGER DEFAULT 7,
    study INTEGER DEFAULT 4,
    budget INTEGER DEFAULT 8000,
    social INTEGER DEFAULT 5,
    food TEXT DEFAULT 'Vegetarian',
    lang TEXT DEFAULT 'English',
    smoke TEXT DEFAULT 'None',
    pets TEXT DEFAULT 'No preference',
    music TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS schedules (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS history_hostels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    hostel_name TEXT,
    date TEXT,
    rating REAL
);

CREATE TABLE IF NOT EXISTS history_roommates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    roommate_name TEXT,
    score INTEGER,
    date TEXT,
    feedback TEXT
);

CREATE TABLE IF NOT EXISTS hostels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT, price INTEGER, distance REAL, rating REAL,
    ac TEXT, wifi TEXT, gender TEXT, emoji TEXT
);

CREATE TABLE IF NOT EXISTS mock_roommates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT, sleep INTEGER, wake INTEGER, clean INTEGER, study INTEGER,
    budget INTEGER, social INTEGER, hobbies TEXT, schedule TEXT
);
"""

SEED_HOSTELS = [
    ("Green Nest PG", 6500, 0.8, 4.5, "Non-AC", "Yes", "Boys", "🌿"),
    ("Maple Comfort Hostel", 9200, 1.4, 4.7, "AC", "Yes", "Co-ed", "🍁"),
    ("Sunrise Girls PG", 7800, 0.5, 4.6, "AC", "Yes", "Girls", "🌅"),
    ("Budget Buddy Hostel", 4200, 2.1, 3.9, "Non-AC", "No", "Boys", "💸"),
    ("Willow Study Nest", 8600, 1.0, 4.4, "AC", "Yes", "Co-ed", "📖"),
    ("Cedar Comfort Rooms", 5900, 1.7, 4.1, "Non-AC", "Yes", "Girls", "🌲"),
    ("Fireside Boys PG", 7200, 0.9, 4.3, "AC", "Yes", "Boys", "🔥"),
    ("Harbor View Hostel", 9900, 2.6, 4.8, "AC", "Yes", "Co-ed", "🌆"),
]

SEED_ROOMMATES = [
    ("Riya Kapoor", 23, 7, 8, 5, 8000, 4, ["Reading", "Music", "Art"]),
    ("Arjun Mehta", 24, 8, 6, 3, 7000, 8, ["Gaming", "Sports", "Music"]),
    ("Simran Kaur", 22, 6, 9, 6, 9000, 3, ["Cooking", "Reading", "Fitness"]),
    ("Devansh Rao", 25, 9, 5, 4, 6000, 7, ["Coding", "Gaming", "Movies"]),
    ("Neha Joshi", 23, 7, 7, 5, 8500, 5, ["Dance", "Art", "Travel"]),
    ("Kabir Singh", 24, 8, 6, 4, 7500, 6, ["Sports", "Photography", "Music"]),
]


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()

    if conn.execute("SELECT COUNT(*) c FROM hostels").fetchone()["c"] == 0:
        conn.executemany(
            "INSERT INTO hostels (name,price,distance,rating,ac,wifi,gender,emoji) VALUES (?,?,?,?,?,?,?,?)",
            SEED_HOSTELS,
        )

    if conn.execute("SELECT COUNT(*) c FROM mock_roommates").fetchone()["c"] == 0:
        for name, sleep, wake, clean, study, budget, social, hobbies in SEED_ROOMMATES:
            seed = len(name)
            sched = {}
            for di, d in enumerate(DAYS):
                sched[d] = []
                for bi in range(4):
                    sched[d].append("free" if (di + bi + seed) % 3 != 0 else "busy")
            conn.execute(
                "INSERT INTO mock_roommates (name,sleep,wake,clean,study,budget,social,hobbies,schedule) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (name, sleep, wake, clean, study, budget, social, json.dumps(hobbies), json.dumps(sched)),
            )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------- users
def create_user(name, email, password_hash, role):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO users (name,email,password_hash,role,created_at) VALUES (?,?,?,?,?)",
        (name, email, password_hash, role, datetime.utcnow().isoformat()),
    )
    uid = cur.lastrowid
    conn.execute("INSERT INTO profiles (user_id,hobbies) VALUES (?,?)", (uid, json.dumps(["Reading", "Music"])))
    conn.execute("INSERT INTO preferences (user_id,music) VALUES (?,?)", (uid, json.dumps(["Lo-fi", "Pop"])))
    conn.execute("INSERT INTO schedules (user_id,data) VALUES (?,?)", (uid, json.dumps(default_schedule())))
    conn.commit()
    conn.close()
    return uid


def get_user_by_email(email):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row


def get_user_by_id(uid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    conn.close()
    return row


def update_password(email, new_hash):
    conn = get_conn()
    conn.execute("UPDATE users SET password_hash = ? WHERE email = ?", (new_hash, email))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------- profile
def get_profile(uid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (uid,)).fetchone()
    conn.close()
    return dict(row) if row else {}


def save_profile(uid, college, bio, study_hours, hobbies, avatar=None):
    conn = get_conn()
    if avatar is not None:
        conn.execute(
            "UPDATE profiles SET college=?, bio=?, study_hours=?, hobbies=?, avatar=? WHERE user_id=?",
            (college, bio, study_hours, json.dumps(hobbies), avatar, uid),
        )
    else:
        conn.execute(
            "UPDATE profiles SET college=?, bio=?, study_hours=?, hobbies=? WHERE user_id=?",
            (college, bio, study_hours, json.dumps(hobbies), uid),
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------- preferences
def get_preferences(uid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM preferences WHERE user_id = ?", (uid,)).fetchone()
    conn.close()
    return dict(row) if row else {}


def save_preferences(uid, prefs: dict):
    conn = get_conn()
    conn.execute(
        """UPDATE preferences SET sleep=?, wake=?, clean=?, study=?, budget=?, social=?,
           food=?, lang=?, smoke=?, pets=?, music=? WHERE user_id=?""",
        (
            prefs["sleep"], prefs["wake"], prefs["clean"], prefs["study"], prefs["budget"],
            prefs["social"], prefs["food"], prefs["lang"], prefs["smoke"], prefs["pets"],
            json.dumps(prefs["music"]), uid,
        ),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------- schedule
def get_schedule(uid):
    conn = get_conn()
    row = conn.execute("SELECT data FROM schedules WHERE user_id = ?", (uid,)).fetchone()
    conn.close()
    return json.loads(row["data"]) if row else default_schedule()


def save_schedule(uid, schedule: dict):
    conn = get_conn()
    conn.execute("UPDATE schedules SET data=? WHERE user_id=?", (json.dumps(schedule), uid))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------- history
def add_hostel_history(uid, hostel_name, rating):
    conn = get_conn()
    conn.execute(
        "INSERT INTO history_hostels (user_id,hostel_name,date,rating) VALUES (?,?,?,?)",
        (uid, hostel_name, datetime.utcnow().strftime("%d %b %Y"), rating),
    )
    conn.commit()
    conn.close()


def add_roommate_history(uid, roommate_name, score):
    conn = get_conn()
    conn.execute(
        "INSERT INTO history_roommates (user_id,roommate_name,date,score,feedback) VALUES (?,?,?,?,?)",
        (uid, roommate_name, datetime.utcnow().strftime("%d %b %Y"), score, "Pending first meetup"),
    )
    conn.commit()
    conn.close()


def get_history(uid):
    conn = get_conn()
    hostels = conn.execute(
        "SELECT * FROM history_hostels WHERE user_id=? ORDER BY id DESC LIMIT 8", (uid,)
    ).fetchall()
    roommates = conn.execute(
        "SELECT * FROM history_roommates WHERE user_id=? ORDER BY id DESC LIMIT 8", (uid,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in hostels], [dict(r) for r in roommates]


# ---------------------------------------------------------------- hostels / roommates
def get_all_hostels():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM hostels").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_mock_roommates():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM mock_roommates").fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["hobbies"] = json.loads(d["hobbies"])
        d["schedule"] = json.loads(d["schedule"])
        out.append(d)
    return out


def get_mock_roommate(rid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM mock_roommates WHERE id=?", (rid,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["hobbies"] = json.loads(d["hobbies"])
    d["schedule"] = json.loads(d["schedule"])
    return d
