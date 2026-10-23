"""Розділ «Звіти»: виручка по залах за період (процедура), по фільмах (представлення), по днях."""
from datetime import timedelta

from flask import Blueprint, render_template, request

from database import query_all, query_one
from validators import get_date

bp = Blueprint("reports", __name__, url_prefix="/reports")


@bp.route("/")
def reports_page():
    today = query_one("SELECT CURRENT_DATE AS d")["d"]
    errors = {}
    date_from = get_date(request.args, "from", "Початок періоду", errors, required=False)
    date_to = get_date(request.args, "to", "Кінець періоду", errors, required=False)
    if "from" not in errors and date_from is None:
        date_from = today - timedelta(days=7)
    if "to" not in errors and date_to is None:
        date_to = today + timedelta(days=7)
    if not errors and date_from > date_to:
        errors["to"] = "Кінець періоду не може бути раніше за початок."

    halls, halls_total = [], 0
    if not errors:
        # Збережена процедура hall_revenue_report (рівень 2)
        halls = query_all("SELECT * FROM hall_revenue_report(%s, %s)", (date_from, date_to))
        halls_total = sum(h["revenue"] for h in halls)
        top = max((h["revenue"] for h in halls), default=0) or 1
        for h in halls:
            h["share"] = round(float(h["revenue"]) / float(top) * 100)

    movies = query_all("SELECT title, tickets_sold, revenue FROM movie_revenue ORDER BY revenue DESC, title")
    days = query_all("""
        SELECT s.start_time::date AS day, COUNT(t.ticket_id) AS tickets, SUM(t.price) AS revenue,
               SUM(SUM(t.price)) OVER (ORDER BY s.start_time::date) AS running_total
        FROM tickets t
        JOIN screenings s ON s.screening_id = t.screening_id
        WHERE t.status = 'sold'
        GROUP BY s.start_time::date
        ORDER BY day""")
    return render_template("reports.html", halls=halls, halls_total=halls_total, movies=movies,
                           days=days, errors=errors, date_from=date_from, date_to=date_to,
                           form_values={"from": request.args.get("from", date_from.isoformat() if date_from else ""),
                                        "to": request.args.get("to", date_to.isoformat() if date_to else "")})