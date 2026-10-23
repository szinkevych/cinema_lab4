"""Головна сторінка: загальна статистика та розклад на сьогодні."""
from flask import Blueprint, render_template

from database import query_all, query_one

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    stats = query_one("""
        SELECT
            (SELECT COUNT(*) FROM movies)                                      AS movies,
            (SELECT COUNT(*) FROM customers)                                   AS customers,
            (SELECT COUNT(*) FROM screenings WHERE start_time > CURRENT_TIMESTAMP) AS upcoming,
            (SELECT COUNT(*) FROM tickets WHERE status = 'sold')               AS tickets_sold,
            (SELECT COALESCE(SUM(price), 0) FROM tickets WHERE status = 'sold') AS revenue
    """)
    # Читаємо з представлення screening_occupancy (рівень 2)
    today = query_all("""
        SELECT screening_id, title, hall, start_time, sold_seats, total_seats, occupancy_pct
        FROM screening_occupancy
        WHERE start_time::date = CURRENT_DATE
        ORDER BY start_time
    """)
    return render_template("index.html", stats=stats, today=today)