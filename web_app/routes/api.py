"""Публічний read-only API каталогу кінотеатру (версія 1)."""
from datetime import date
from decimal import Decimal

from flask import Blueprint, jsonify, request
from werkzeug.exceptions import HTTPException

from database import query_all, query_one

bp = Blueprint("api", __name__, url_prefix="/api/v1")
DEFAULT_LIMIT = 50
MAX_LIMIT = 100


def parse_limit():
    raw = request.args.get("limit", str(DEFAULT_LIMIT))
    try:
        limit = int(raw)
    except ValueError:
        return None
    return limit if 1 <= limit <= MAX_LIMIT else None


def parse_date(name):
    raw = request.args.get(name)
    if raw is None:
        return None, None
    try:
        return date.fromisoformat(raw), None
    except ValueError:
        return None, f"Параметр «{name}» має бути датою у форматі YYYY-MM-DD."


def json_safe(value):
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


@bp.errorhandler(HTTPException)
def json_http_error(error):
    return jsonify(error={"code": error.code, "message": error.description}), error.code


@bp.route("/movies")
def list_movies():
    limit = parse_limit()
    if limit is None:
        return jsonify(error={"code": 400, "message": "Параметр limit має бути від 1 до 100."}), 400

    q = (request.args.get("q") or "").strip()
    escaped_q = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    like = f"%{escaped_q}%"
    movies = query_all("""
        SELECT m.movie_id, m.title, m.description, m.duration_min, m.release_year, m.age_rating,
               COALESCE(array_agg(g.name ORDER BY g.name)
                   FILTER (WHERE g.name IS NOT NULL), ARRAY[]::VARCHAR[]) AS genres
        FROM movies m
        LEFT JOIN movie_genres mg ON mg.movie_id = m.movie_id
        LEFT JOIN genres g ON g.genre_id = mg.genre_id
        WHERE (%s = '' OR m.title ILIKE %s ESCAPE E'\\\\')
        GROUP BY m.movie_id
        ORDER BY m.title, m.movie_id
        LIMIT %s
    """, (q, like, limit))
    return jsonify(data=json_safe(movies), limit=limit, count=len(movies))


@bp.route("/screenings")
def list_screenings():
    limit = parse_limit()
    if limit is None:
        return jsonify(error={"code": 400, "message": "Параметр limit має бути від 1 до 100."}), 400

    date_from, error = parse_date("from")
    if error:
        return jsonify(error={"code": 400, "message": error}), 400
    date_to, error = parse_date("to")
    if error:
        return jsonify(error={"code": 400, "message": error}), 400
    if date_from and date_to and date_from > date_to:
        return jsonify(error={"code": 400, "message": "Параметр from не може бути пізніше за to."}), 400

    raw_movie_id = request.args.get("movie_id")
    if raw_movie_id is not None:
        try:
            movie_id = int(raw_movie_id)
        except ValueError:
            return jsonify(error={"code": 400, "message": "Параметр movie_id має бути цілим числом."}), 400
        if movie_id < 1:
            return jsonify(error={"code": 400, "message": "Параметр movie_id має бути додатним числом."}), 400
    else:
        movie_id = None
    screenings = query_all("""
        SELECT s.screening_id, m.movie_id, m.title, h.name AS hall, h.hall_type,
               s.start_time, s.base_price, o.total_seats, o.sold_seats, o.free_seats
        FROM screenings s
        JOIN movies m ON m.movie_id = s.movie_id
        JOIN halls h ON h.hall_id = s.hall_id
        JOIN screening_occupancy o ON o.screening_id = s.screening_id
        WHERE s.start_time >= LOCALTIMESTAMP
          AND (%s IS NULL OR m.movie_id = %s)
          AND (%s IS NULL OR s.start_time >= %s::date)
          AND (%s IS NULL OR s.start_time < %s::date + INTERVAL '1 day')
        ORDER BY s.start_time, s.screening_id
        LIMIT %s
    """, (movie_id, movie_id, date_from, date_from, date_to, date_to, limit))
    return jsonify(data=json_safe(screenings), limit=limit, count=len(screenings))


@bp.route("/screenings/<int:screening_id>/availability")
def screening_availability(screening_id):
    screening = query_one("""
        SELECT s.screening_id, m.title, h.name AS hall, h.hall_type, s.start_time,
               s.base_price, o.total_seats, o.sold_seats, o.free_seats
        FROM screenings s
        JOIN movies m ON m.movie_id = s.movie_id
        JOIN halls h ON h.hall_id = s.hall_id
        JOIN screening_occupancy o ON o.screening_id = s.screening_id
        WHERE s.screening_id = %s AND s.start_time >= LOCALTIMESTAMP
    """, (screening_id,))
    if screening is None:
        return jsonify(error={"code": 404, "message": "Сеанс не знайдено."}), 404
    return jsonify(data=json_safe(screening))
