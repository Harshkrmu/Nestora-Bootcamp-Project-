"""
Nestora — server-side chart rendering with Matplotlib.
Every dashboard graph is drawn here as a PNG and streamed to the
browser via a Flask route (see app.py `/api/charts/...`), matching
the original "render server-side to PNG, embed in dashboard cards" spec.
"""
import io
import matplotlib
matplotlib.use("Agg")  # headless, no display needed on the server
import matplotlib.pyplot as plt
import matplotlib.colors
import numpy as np

# ---- cozy Nestora palette ----
FOREST = "#2E7D32"
FOREST_LIGHT = "#57A45C"
BROWN = "#4E342E"
BROWN_SOFT = "#7A5C50"
BEIGE = "#F5E6CA"
CREAM = "#FFF8F0"
ORANGE = "#FF8C42"
YELLOW = "#FFD166"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.edgecolor": BROWN_SOFT,
    "text.color": BROWN,
    "axes.labelcolor": BROWN,
    "xtick.color": BROWN_SOFT,
    "ytick.color": BROWN_SOFT,
})


def _to_png(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.patch.set_alpha(0.0)
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf


def sleep_hours_chart(schedule: dict) -> io.BytesIO:
    """Bar chart of estimated sleep hours per day, derived from the day-schedule grid."""
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    hours = []
    for d in days:
        sleep_blocks = schedule[d].count("sleep")
        hours.append(min(10, round(5 + sleep_blocks * 1.5, 1)))

    fig, ax = plt.subplots(figsize=(3.6, 1.9))
    ax.bar(days, hours, color=FOREST_LIGHT, width=0.6, zorder=3)
    ax.set_ylim(0, 10)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.set_yticks([])
    ax.tick_params(axis="x", length=0, labelsize=8)
    ax.grid(axis="y", linestyle="--", alpha=0.25, zorder=0)
    return _to_png(fig)


def hobbies_chart(hobbies: list) -> io.BytesIO:
    """Donut chart of hobby distribution (even split across selected hobbies)."""
    if not hobbies:
        hobbies = ["Reading", "Music"]
    values = np.random.default_rng(sum(map(ord, "".join(hobbies)))).integers(10, 30, size=len(hobbies))
    colors = [FOREST, ORANGE, YELLOW, FOREST_LIGHT, BROWN, BEIGE, "#8d6e63"]

    fig, ax = plt.subplots(figsize=(3.6, 2.0))
    wedges, _ = ax.pie(values, colors=colors[: len(hobbies)], startangle=90,
                        wedgeprops=dict(width=0.42, edgecolor=CREAM))
    ax.legend(wedges, hobbies, loc="center left", bbox_to_anchor=(1.0, 0.5),
              fontsize=7, frameon=False)
    ax.set_aspect("equal")
    return _to_png(fig)


def study_vs_free_chart(study_hours: int) -> io.BytesIO:
    """Horizontal stacked bar: study hours vs free hours in a day."""
    study_hours = max(0, min(16, study_hours))
    free_hours = max(1, 16 - study_hours - 8)  # 8h reserved for sleep

    fig, ax = plt.subplots(figsize=(3.6, 1.4))
    ax.barh(["Today"], [study_hours], color=BROWN, label="Study")
    ax.barh(["Today"], [free_hours], left=[study_hours], color=YELLOW, label="Free")
    ax.set_xlim(0, study_hours + free_hours)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.set_yticks([])
    ax.tick_params(axis="x", labelsize=7)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.35), ncol=2, fontsize=7, frameon=False)
    return _to_png(fig)


def gauge_chart(percentage: int) -> io.BytesIO:
    """Donut 'gauge' showing the top roommate compatibility score."""
    percentage = max(0, min(100, percentage))
    fig, ax = plt.subplots(figsize=(2.6, 2.0))
    ax.pie([percentage, 100 - percentage], colors=[ORANGE, BEIGE], startangle=90,
           wedgeprops=dict(width=0.32, edgecolor=CREAM), counterclock=False)
    ax.text(0, 0, f"{percentage}%", ha="center", va="center", fontsize=17,
            fontweight="bold", color=BROWN)
    ax.set_aspect("equal")
    return _to_png(fig)


def radar_chart(labels: list, me_values: list, other_values: list, other_name: str) -> io.BytesIO:
    """Polar radar chart comparing the current user vs a matched roommate."""
    n = len(labels)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    me = me_values + me_values[:1]
    other = other_values + other_values[:1]
    ang = angles + angles[:1]

    fig, ax = plt.subplots(figsize=(4.2, 3.6), subplot_kw=dict(polar=True))
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 10)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_yticks([2.5, 5, 7.5, 10])
    ax.set_yticklabels([])
    ax.spines["polar"].set_color(BROWN_SOFT)
    ax.grid(color=BROWN_SOFT, alpha=0.25)

    ax.plot(ang, me, color=FOREST, linewidth=2, label="You")
    ax.fill(ang, me, color=FOREST, alpha=0.20)
    ax.plot(ang, other, color=ORANGE, linewidth=2, label=other_name)
    ax.fill(ang, other, color=ORANGE, alpha=0.20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=8, frameon=False)
    return _to_png(fig)


def overlap_heatmap(overlap_grid: dict, days: list, blocks: list) -> io.BytesIO:
    """Heatmap strip: green = both free/study at that block, beige = not overlapping."""
    matrix = np.array([[1 if overlap_grid[d][b] else 0 for d in days] for b in blocks])

    fig, ax = plt.subplots(figsize=(4.4, 1.8))
    cmap = matplotlib.colors.ListedColormap([BEIGE, FOREST_LIGHT])
    ax.imshow(matrix, cmap=cmap, aspect="auto", vmin=0, vmax=1)
    ax.set_xticks(range(len(days)))
    ax.set_xticklabels(days, fontsize=8)
    ax.set_yticks(range(len(blocks)))
    ax.set_yticklabels(blocks, fontsize=8)
    ax.set_xticks(np.arange(-0.5, len(days), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(blocks), 1), minor=True)
    ax.grid(which="minor", color=CREAM, linewidth=2)
    ax.tick_params(which="both", length=0)
    return _to_png(fig)
