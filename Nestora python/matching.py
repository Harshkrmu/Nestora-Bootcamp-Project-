"""
Nestora — AI / data logic.
This is where pandas + numpy actually do work:
  - compatibility scoring is a vectorized weighted-distance calc across
    every candidate roommate at once (numpy), not a per-row Python loop
  - the roommate table itself is loaded and filtered with pandas
  - schedule overlap is computed by comparing two pandas-backed day grids
"""
import numpy as np
import pandas as pd

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
BLOCKS = ["Morning", "Afternoon", "Evening", "Night"]

# relative importance of each trait in the match score
WEIGHTS = np.array([0.22, 0.20, 0.20, 0.18, 0.20])  # sleep, clean, study, budget, social


def roommates_to_dataframe(roommates: list) -> pd.DataFrame:
    """Turn the list of mock-roommate dict rows (from SQLite) into a pandas DataFrame."""
    return pd.DataFrame(roommates)


def compute_scores(user_prefs: dict, roommates: list) -> pd.DataFrame:
    """
    Vectorized compatibility score (0-100) between the current user's
    preferences and every candidate roommate, using numpy broadcasting
    instead of scoring one pair at a time.
    """
    df = roommates_to_dataframe(roommates)
    if df.empty:
        return df

    sleep_diff = np.minimum(np.abs(df["sleep"] - user_prefs["sleep"]), 6) / 6.0
    clean_diff = np.abs(df["clean"] - user_prefs["clean"]) / 9.0
    study_diff = np.abs(df["study"] - user_prefs["study"]) / 10.0
    budget_diff = np.minimum(np.abs(df["budget"] - user_prefs["budget"]), 6000) / 6000.0
    social_diff = np.abs(df["social"] - user_prefs["social"]) / 9.0

    diffs = np.vstack([sleep_diff, clean_diff, study_diff, budget_diff, social_diff]).T  # (n,5)
    weighted = diffs @ WEIGHTS  # matrix-vector product -> (n,)
    scores = np.round((1 - weighted) * 100).astype(int)
    scores = np.clip(scores, 0, 100)

    df = df.copy()
    df["score"] = scores
    df["sleep_diff"] = sleep_diff
    df["clean_diff"] = clean_diff
    df["study_diff"] = study_diff
    df["budget_diff"] = budget_diff
    df["social_diff"] = social_diff
    return df.sort_values("score", ascending=False).reset_index(drop=True)


def sanitize_records(df: pd.DataFrame) -> list:
    """Convert a DataFrame to JSON-safe records (numpy int64/float64 -> native Python types)."""
    if df.empty:
        return []
    records = df.to_dict("records")
    clean = []
    for rec in records:
        row = {}
        for k, v in rec.items():
            if isinstance(v, (np.integer,)):
                row[k] = int(v)
            elif isinstance(v, (np.floating,)):
                row[k] = round(float(v), 3)
            elif isinstance(v, np.ndarray):
                row[k] = v.tolist()
            else:
                row[k] = v
        clean.append(row)
    return clean


def match_reasons(user_prefs: dict, roommate: dict) -> list:
    reasons = []
    if abs(user_prefs["sleep"] - roommate["sleep"]) <= 1:
        reasons.append("Similar sleep time")
    if abs(user_prefs["clean"] - roommate["clean"]) <= 2:
        reasons.append("Cleanliness match")
    if abs(user_prefs["study"] - roommate["study"]) <= 1:
        reasons.append("Study habits")
    if abs(user_prefs["budget"] - roommate["budget"]) <= 1500:
        reasons.append("Budget fit")
    if abs(user_prefs["social"] - roommate["social"]) <= 2:
        reasons.append("Social energy")
    return reasons or ["Some shared habits"]


def radar_axes(prefs: dict) -> list:
    """Map raw preference fields onto 5 comparable 0-10 axes for the radar chart."""
    return [
        max(0, 10 - abs(prefs["sleep"] - 23)),   # closeness to a "typical" 11pm sleep time
        prefs["clean"],
        prefs["study"],
        min(10, prefs["budget"] / 1000),
        prefs["social"],
    ]


def schedule_overlap(my_schedule: dict, their_schedule: dict) -> dict:
    """
    Compare two 7x4 day-schedule grids with pandas and return which
    blocks are free for both people, plus the best shared slot.
    """
    my_df = pd.DataFrame(my_schedule, index=BLOCKS)[DAYS]
    their_df = pd.DataFrame(their_schedule, index=BLOCKS)[DAYS]

    my_free = my_df.isin(["free", "study"])
    their_free = their_df.isin(["free", "study"])
    overlap = my_free & their_free  # boolean DataFrame, True = both free

    total_overlap = int(overlap.values.sum())
    best = None
    for block in BLOCKS:
        for day in DAYS:
            if overlap.loc[block, day]:
                best = (day, block)
                break
        if best:
            break

    grid = {day: {block: bool(overlap.loc[block, day]) for block in BLOCKS} for day in DAYS}

    return {
        "grid": grid,   # {day: {block: bool}}
        "days": DAYS,
        "blocks": BLOCKS,
        "total_overlap_blocks": total_overlap,
        "best_day": best[0] if best else None,
        "best_block": best[1] if best else None,
    }
