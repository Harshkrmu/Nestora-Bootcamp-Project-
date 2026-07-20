# Nestora — Smart Hostel & Roommate Finder

A cozy, student-only web app for finding hostels and compatible roommates.
Built with **Flask + SQLite + pandas + NumPy + Matplotlib** on the backend,
and plain HTML/CSS/JS on the frontend.

## Tech stack

| Layer | Tool | Used for |
|---|---|---|
| Web server / routing | **Flask** | pages, REST API, sessions, auth |
| Storage | **SQLite** (via `sqlite3`) | users, preferences, schedules, history |
| Data analysis | **pandas** | filtering hostels, building roommate tables |
| Compatibility scoring | **NumPy** | vectorized weighted-distance match score across all candidates at once |
| Charts | **Matplotlib** | every dashboard graph (sleep, hobbies, study/free, gauge, radar, overlap heatmap) — rendered server-side to PNG and embedded via `<img>` |
| Frontend | HTML/CSS + vanilla JS (fetch) | dashboard tabs, forms, chat widget |

## Setup

```bash
cd nestora_flask
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

The SQLite database (`instance/nestora.db`) and seed data (hostels + mock
roommates) are created automatically the first time you run `app.py`.

## Project structure

```
nestora_flask/
├── app.py            # Flask routes (pages + REST API + chart endpoints)
├── db.py              # SQLite schema, queries, seed data
├── matching.py         # pandas/NumPy compatibility scoring + schedule overlap
├── charts.py            # Matplotlib chart generators (return PNG bytes)
├── requirements.txt
├── templates/
│   ├── landing.html     # home page with hero + two CTA buttons
│   ├── auth.html         # login/signup with faded hostel background
│   ├── dashboard.html     # sidebar tabs: home, hostel/roommate finder,
│   │                        preferences, schedule, profile
│   └── _logo.html          # shared home-figure SVG logo
├── static/
│   ├── css/style.css
│   ├── js/main.js         # tab switching + fetch calls to the API
│   └── uploads/            # profile photo uploads land here
└── instance/
    └── nestora.db          # created automatically on first run
```

## Features

- **Auth** — signup/login with hashed passwords (Werkzeug), server-side
  validation, mock OTP-based forgot-password flow.
- **Dashboard** — sleep-hours, hobbies, study-vs-free, and top-match-score
  charts, all rendered server-side with Matplotlib and refreshed after you
  save preferences/schedule.
- **Hostel Finder** — pandas-filtered hostel search (budget, gender, AC, WiFi).
- **Roommate Finder** — NumPy-vectorized weighted compatibility score (0–100%)
  across sleep, cleanliness, study habits, budget, and social energy, plus
  a per-match Matplotlib radar chart and a pandas-computed schedule-overlap
  heatmap.
- **Day Schedule** — click-to-cycle weekly grid (Free/Study/Sleep/Busy) used
  for the overlap finder.
- **Profile** — editable bio/college/hobbies + photo upload.
- **HostBot** — rule-based chat widget that routes you to the right tab.

## Notes

- `app.secret_key` in `app.py` is a placeholder — change it before deploying
  anywhere real.
- The Flask dev server (`app.run(debug=True)`) is for local use only; use a
  production WSGI server (gunicorn/uwsgi) for real deployment.
- Roommates are seeded mock data for demo purposes — swap `db.SEED_ROOMMATES`
  for real user-matching once you have more than one signed-up student.
