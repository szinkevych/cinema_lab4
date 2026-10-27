"""Перегляд журналу дій (лише адміністратор)."""
from flask import Blueprint, render_template, request

from auth import roles_required
from database import query_all, query_one

bp = Blueprint("activity", __name__, url_prefix="/activity")
PAGE_SIZE = 50


@bp.route("/")
@roles_required("admin")
def list_activity():
    user = request.args.get("user", type=int)
    table = (request.args.get("table") or "").strip()
    action = (request.args.get("action") or "").strip()
    page = max(request.args.get("page", 1, type=int), 1)
    params = {"user": user, "table": table, "action": action}
    where = """(%(user)s IS NULL OR l.user_id = %(user)s)
               AND (%(table)s = '' OR l.table_name = %(table)s)
               AND (%(action)s = '' OR l.action = %(action)s)"""

    total = query_one(f"SELECT COUNT(*) AS n FROM activity_log l WHERE {where}", params)["n"]
    pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
    page = min(page, pages)
    rows = query_all(f"""
        SELECT l.log_id, l.created_at, u.username, l.action, l.table_name, l.record_id, l.details
        FROM activity_log l LEFT JOIN users u ON u.user_id = l.user_id
        WHERE {where}
        ORDER BY l.created_at DESC, l.log_id DESC
        LIMIT {PAGE_SIZE} OFFSET %(offset)s""", {**params, "offset": (page - 1) * PAGE_SIZE})

    return render_template(
        "activity.html", rows=rows, total=total, page=page, pages=pages,
        stats=query_one("""
            SELECT
                (SELECT COUNT(*) FROM movies) AS movies,
                (SELECT COUNT(*) FROM customers) AS customers,
                (SELECT COUNT(*) FROM screenings WHERE start_time > CURRENT_TIMESTAMP) AS upcoming,
                (SELECT COUNT(*) FROM tickets WHERE status = 'sold') AS tickets_sold,
                (SELECT COALESCE(SUM(price), 0) FROM tickets WHERE status = 'sold') AS revenue
        """),
        users=query_all("SELECT user_id, username FROM users ORDER BY username"),
        tables=[r["table_name"] for r in query_all(
            "SELECT DISTINCT table_name FROM activity_log WHERE table_name IS NOT NULL ORDER BY 1")],
        actions=[r["action"] for r in query_all("SELECT DISTINCT action FROM activity_log ORDER BY 1")],
        filters={"user": user, "table": table, "action": action})