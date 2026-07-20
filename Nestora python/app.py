"""
Nestora — Smart Hostel & Roommate Finder
Flask + SQLite + pandas + numpy + matplotlib backend.

Run:
    pip install -r requirements.txt
    python app.py
Then open http://127.0.0.1:5000
"""
import os
import re
import json
import random
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, session,
    jsonify, send_file, flash
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

import db
import matching
import charts

app = Flask(__name__)
app.secret_key = "nestora-dev-secret-change-me"  # change this in production
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  # 4MB avatar upload cap

UPLOAD_DIR = os.path.join(app.static_folder, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# in-memory OTP store for the "forgot password" demo flow: {email: otp}
OTP_STORE = {}


# ------------------------------------------------------------------ helpers
def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("auth", tab="login"))
        return f(*a, **kw)
    return wrapper


def current_user_row():
    uid = session.get("user_id")
    return db.get_user_by_id(uid) if uid else None


# ------------------------------------------------------------------ pages
@app.route("/")
def landing():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")


@app.route("/auth")
def auth():
    tab = request.args.get("tab", "login")
    return render_template("auth.html", tab=tab)


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user_row()
    profile = db.get_profile(user["id"])
    profile["hobbies"] = json.loads(profile["hobbies"])
    prefs = db.get_preferences(user["id"])
    prefs["music"] = json.loads(prefs["music"])
    schedule = db.get_schedule(user["id"])
    hostel_history, roommate_history = db.get_history(user["id"])
    all_hostels = db.get_all_hostels()
    roommates_df = matching.compute_scores(prefs, db.get_all_mock_roommates())
    roommates = matching.sanitize_records(roommates_df)
    for r in roommates:
        r["reasons"] = matching.match_reasons(prefs, r)

    return render_template(
        "dashboard.html",
        user=user, profile=profile, prefs=prefs, schedule=schedule,
        hostel_history=hostel_history, roommate_history=roommate_history,
        hostels=all_hostels, roommates=roommates,
        days=matching.DAYS, blocks=matching.BLOCKS,
        hobby_list=["Reading", "Gaming", "Music", "Sports", "Cooking", "Art",
                    "Movies", "Coding", "Fitness", "Photography", "Dance", "Travel"],
        music_list=["Pop", "Rock", "Lo-fi", "Hip-Hop", "Classical", "EDM", "Indie", "Bollywood"],
        cache_bust=random.randint(1, 999999),
    )


# ------------------------------------------------------------------ auth actions
@app.route("/signup", methods=["POST"])
def signup():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role", "student")

    if not name or not email or not password:
        flash("Please fill in all fields.", "signup_err")
        return redirect(url_for("auth", tab="signup"))
    if not EMAIL_RE.match(email):
        flash("Enter a valid email address.", "signup_err")
        return redirect(url_for("auth", tab="signup"))
    if len(password) < 6:
        flash("Password must be at least 6 characters.", "signup_err")
        return redirect(url_for("auth", tab="signup"))
    if db.get_user_by_email(email):
        flash("An account with this email already exists.", "signup_err")
        return redirect(url_for("auth", tab="signup"))

    uid = db.create_user(name, email, generate_password_hash(password), role)
    session["user_id"] = uid
    flash("Account created — welcome to Nestora!", "success")
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    user = db.get_user_by_email(email)
    if not user or not check_password_hash(user["password_hash"], password):
        flash("Invalid email or password.", "login_err")
        return redirect(url_for("auth", tab="login"))
    session["user_id"] = user["id"]
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/forgot/send-otp", methods=["POST"])
def forgot_send_otp():
    email = request.form.get("email", "").strip().lower()
    if not db.get_user_by_email(email):
        flash("No account found with that email.", "login_err")
        return redirect(url_for("auth", tab="login"))
    otp = str(random.randint(1000, 9999))
    OTP_STORE[email] = otp
    flash(f"Demo OTP for {email}: {otp}", "otp_sent")
    return redirect(url_for("auth", tab="login"))


@app.route("/forgot/reset", methods=["POST"])
def forgot_reset():
    email = request.form.get("email", "").strip().lower()
    otp = request.form.get("otp", "").strip()
    new_password = request.form.get("new_password", "")
    if OTP_STORE.get(email) != otp:
        flash("Incorrect OTP.", "login_err")
        return redirect(url_for("auth", tab="login"))
    if len(new_password) < 6:
        flash("New password must be at least 6 characters.", "login_err")
        return redirect(url_for("auth", tab="login"))
    db.update_password(email, generate_password_hash(new_password))
    OTP_STORE.pop(email, None)
    flash("Password reset — please log in.", "success")
    return redirect(url_for("auth", tab="login"))


# ------------------------------------------------------------------ preferences / schedule / profile APIs
@app.route("/api/preferences", methods=["POST"])
@login_required
def api_save_preferences():
    data = request.get_json(force=True)
    prefs = {
        "sleep": int(data.get("sleep", 23)), "wake": int(data.get("wake", 7)),
        "clean": int(data.get("clean", 7)), "study": int(data.get("study", 4)),
        "budget": int(data.get("budget", 8000)), "social": int(data.get("social", 5)),
        "food": data.get("food", "Vegetarian"), "lang": data.get("lang", "English"),
        "smoke": data.get("smoke", "None"), "pets": data.get("pets", "No preference"),
        "music": data.get("music", []),
    }
    db.save_preferences(session["user_id"], prefs)
    return jsonify({"ok": True})


@app.route("/api/schedule", methods=["POST"])
@login_required
def api_save_schedule():
    data = request.get_json(force=True)
    db.save_schedule(session["user_id"], data.get("schedule", {}))
    return jsonify({"ok": True})


@app.route("/api/profile", methods=["POST"])
@login_required
def api_save_profile():
    college = request.form.get("college", "")
    bio = request.form.get("bio", "")
    study_hours = int(request.form.get("study_hours", 4) or 4)
    hobbies = request.form.getlist("hobbies")

    avatar_path = None
    file = request.files.get("avatar")
    if file and file.filename:
        fname = secure_filename(f"user{session['user_id']}_{file.filename}")
        file.save(os.path.join(UPLOAD_DIR, fname))
        avatar_path = url_for("static", filename=f"uploads/{fname}")

    db.save_profile(session["user_id"], college, bio, study_hours, hobbies, avatar_path)
    return redirect(url_for("dashboard") + "#profile")


# ------------------------------------------------------------------ hostel finder
@app.route("/api/hostels")
@login_required
def api_hostels():
    search = request.args.get("search", "").lower()
    budget = request.args.get("budget", type=int)
    gender = request.args.get("gender", "")
    ac = request.args.get("ac", "")
    wifi = request.args.get("wifi", "")

    import pandas as pd
    df = pd.DataFrame(db.get_all_hostels())
    if search:
        df = df[df["name"].str.lower().str.contains(search)]
    if budget:
        df = df[df["price"] <= budget]
    if gender:
        df = df[df["gender"] == gender]
    if ac:
        df = df[df["ac"] == ac]
    if wifi:
        df = df[df["wifi"] == wifi]
    return jsonify(matching.sanitize_records(df))


@app.route("/api/hostels/book", methods=["POST"])
@login_required
def api_book_hostel():
    data = request.get_json(force=True)
    name = data.get("name", "Hostel")
    rating = round(random.uniform(4.0, 5.0), 1)
    db.add_hostel_history(session["user_id"], name, rating)
    return jsonify({"ok": True, "rating": rating})


# ------------------------------------------------------------------ roommate finder
@app.route("/api/roommates")
@login_required
def api_roommates():
    prefs = db.get_preferences(session["user_id"])
    prefs["music"] = json.loads(prefs["music"])
    df = matching.compute_scores(prefs, db.get_all_mock_roommates())
    records = matching.sanitize_records(df)
    for r in records:
        r["reasons"] = matching.match_reasons(prefs, r)
    return jsonify(records)


@app.route("/api/roommates/connect", methods=["POST"])
@login_required
def api_connect_roommate():
    data = request.get_json(force=True)
    db.add_roommate_history(session["user_id"], data.get("name", "Roommate"), int(data.get("score", 0)))
    return jsonify({"ok": True})


@app.route("/api/schedule/overlap/<int:rid>")
@login_required
def api_schedule_overlap(rid):
    my_schedule = db.get_schedule(session["user_id"])
    roommate = db.get_mock_roommate(rid)
    if not roommate:
        return jsonify({"error": "not found"}), 404
    result = matching.schedule_overlap(my_schedule, roommate["schedule"])
    return jsonify(result)


# ------------------------------------------------------------------ chatbot (HostBot)
@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    text = request.get_json(force=True).get("message", "").lower()
    if any(k in text for k in ["hostel", "room", "pg", "stay", "rent", "book"]):
        reply, tab = "Here are cozy hostels matching typical budgets nearby! Want me to open the Hostel Finder?", "hostel"
    elif any(k in text for k in ["roommate", "match", "compatib", "partner"]):
        reply, tab = "I can show you your best-matched roommates based on sleep, study & budget habits!", "roommate"
    elif any(k in text for k in ["budget", "price", "cost", "cheap"]):
        reply, tab = "You can filter hostels by max budget in the Hostel Finder — I'll take you there.", "hostel"
    elif any(k in text for k in ["schedule", "free time", "overlap", "timetable"]):
        reply, tab = "Set your Day Schedule and I'll help find overlapping free hours with your matches!", "schedule"
    elif any(k in text for k in ["safety", "safe", "security"]):
        reply, tab = ("Most listed hostels have verified owners, CCTV & warden support. "
                       "Always visit in person before booking, and share your location with a friend."), None
    elif any(k in text for k in ["hi", "hello", "hey"]):
        reply, tab = "Hi there! Want help finding a hostel or a roommate today?", None
    else:
        reply, tab = "I can help with hostel search, roommate matching, budgets, or your schedule — try asking about one of those!", None
    return jsonify({"reply": reply, "suggest_tab": tab})


# ------------------------------------------------------------------ matplotlib chart endpoints
@app.route("/api/charts/sleep.png")
@login_required
def chart_sleep():
    schedule = db.get_schedule(session["user_id"])
    return send_file(charts.sleep_hours_chart(schedule), mimetype="image/png")


@app.route("/api/charts/hobbies.png")
@login_required
def chart_hobbies():
    profile = db.get_profile(session["user_id"])
    hobbies = json.loads(profile["hobbies"])
    return send_file(charts.hobbies_chart(hobbies), mimetype="image/png")


@app.route("/api/charts/study.png")
@login_required
def chart_study():
    prefs = db.get_preferences(session["user_id"])
    return send_file(charts.study_vs_free_chart(prefs["study"]), mimetype="image/png")


@app.route("/api/charts/gauge.png")
@login_required
def chart_gauge():
    prefs = db.get_preferences(session["user_id"])
    df = matching.compute_scores(prefs, db.get_all_mock_roommates())
    best = int(df.iloc[0]["score"]) if not df.empty else 0
    return send_file(charts.gauge_chart(best), mimetype="image/png")


@app.route("/api/charts/radar/<int:rid>.png")
@login_required
def chart_radar(rid):
    prefs = db.get_preferences(session["user_id"])
    roommate = db.get_mock_roommate(rid)
    if not roommate:
        return "not found", 404
    labels = ["Sleep", "Cleanliness", "Study Habits", "Budget", "Social Energy"]
    me = matching.radar_axes(prefs)
    other = matching.radar_axes(roommate)
    return send_file(charts.radar_chart(labels, me, other, roommate["name"]), mimetype="image/png")


@app.route("/api/charts/overlap/<int:rid>.png")
@login_required
def chart_overlap(rid):
    my_schedule = db.get_schedule(session["user_id"])
    roommate = db.get_mock_roommate(rid)
    if not roommate:
        return "not found", 404
    result = matching.schedule_overlap(my_schedule, roommate["schedule"])
    return send_file(
        charts.overlap_heatmap(result["grid"], result["days"], result["blocks"]),
        mimetype="image/png",
    )


if __name__ == "__main__":
    db.init_db()
    app.run(debug=True, port=5000)
