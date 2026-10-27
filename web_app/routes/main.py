"""Публічна головна сторінка; оперативна статистика доступна лише персоналу."""
from flask import Blueprint, g, redirect, render_template, url_for

from auth import STAFF
from database import query_all

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    if g.user and g.user["role"] in STAFF:
        return redirect(url_for("movies.list_movies"))

    # Читаємо з представлення screening_occupancy (рівень 2)
    today = query_all("""
        SELECT screening_id, title, hall, start_time, sold_seats, total_seats, occupancy_pct
        FROM screening_occupancy
        WHERE start_time >= LOCALTIMESTAMP
          AND start_time < CURRENT_DATE + INTERVAL '1 day'
        ORDER BY start_time
    """)
    return render_template("index.html", today=today)