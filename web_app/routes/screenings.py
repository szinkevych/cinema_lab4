"""Розділ «Сеанси»: розклад з фільтрами, додавання, зміна, видалення.

Перетин сеансів у залі перевіряє тригер trg_screening_overlap (у базі),
а тут його повідомлення показується біля поля «Початок».
"""
import psycopg2
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from auth import roles_required
from database import db_error_message, execute, query_all, query_one
from validators import get_choice, get_datetime, get_decimal

bp = Blueprint("screenings", __name__, url_prefix="/screenings")

# Умова за періодом береться лише з цього словника
WHEN_SQL = {
    "upcoming": "s.start_time >= LOCALTIMESTAMP",
    "today": "s.start_time::date = CURRENT_DATE",
    "past": "s.start_time < LOCALTIMESTAMP",
    "all": "TRUE",
}


def load_movies():
    return query_all("SELECT movie_id, title, duration_min FROM movies ORDER BY title")


def load_halls():
    return query_all("SELECT hall_id, name, hall_type FROM halls ORDER BY hall_id")


def db_now():
    """Поточний час за часовим поясом бази (так само, як у процедурах і тригерах)."""
    return query_one("SELECT LOCALTIMESTAMP AS now")["now"]


def validate_screening(form, movies, halls, locked_hall_id=None):
    errors = {}
    movie_id = get_choice(form, "movie_id", "Фільм", errors, {m["movie_id"] for m in movies}, cast=int)
    if locked_hall_id is not None:
        hall_id = locked_hall_id          # зал не змінюється, якщо вже є квитки
    else:
        hall_id = get_choice(form, "hall_id", "Зал", errors, {h["hall_id"] for h in halls}, cast=int)
    start = get_datetime(form, "start_time", "Початок", errors)
    price = get_decimal(form, "base_price", "Базова ціна", errors, 0, 10000)
    if start is not None and start <= db_now():
        errors["start_time"] = "Початок сеансу має бути в майбутньому."
    return {"movie_id": movie_id, "hall_id": hall_id, "start_time": start, "base_price": price}, errors


def screening_error(e, form_errors):
    """Помилки бази -> повідомлення біля потрібного поля."""
    if isinstance(e, psycopg2.errors.RaiseException):
        form_errors["start_time"] = e.diag.message_primary      # повідомлення тригера
    elif isinstance(e, psycopg2.errors.UniqueViolation):
        form_errors["start_time"] = "У цьому залі вже є сеанс на цей час."
    else:
        flash(db_error_message(e), "error")


@bp.route("/")
def list_screenings():
    when = request.args.get("when", "upcoming")
    if when not in WHEN_SQL:
        when = "upcoming"
    movie = request.args.get("movie", type=int)
    hall = request.args.get("hall", type=int)
    direction = "DESC" if when == "past" else "ASC"

    screenings = query_all(f"""
        SELECT o.screening_id, o.title, o.hall, o.start_time, o.sold_seats, o.total_seats,
               o.occupancy_pct, s.base_price, s.movie_id, h.hall_type
        FROM screening_occupancy o
        JOIN screenings s ON s.screening_id = o.screening_id
        JOIN halls h      ON h.hall_id = s.hall_id
        WHERE {WHEN_SQL[when]}
          AND (%(movie)s IS NULL OR s.movie_id = %(movie)s)
          AND (%(hall)s IS NULL OR s.hall_id = %(hall)s)
        ORDER BY o.start_time {direction}
    """, {"movie": movie, "hall": hall})
    return render_template("screenings.html", screenings=screenings, movies=load_movies(),
                           halls=load_halls(), filters={"when": when, "movie": movie, "hall": hall},
                           now=db_now())


@bp.route("/add", methods=["GET", "POST"])
@roles_required("admin")
def add_screening():
    movies, halls = load_movies(), load_halls()
    if request.method == "POST":
        data, form_errors = validate_screening(request.form, movies, halls)
        if not form_errors:
            try:
                execute("""INSERT INTO screenings (movie_id, hall_id, start_time, base_price)
                           VALUES (%(movie_id)s, %(hall_id)s, %(start_time)s, %(base_price)s)""", data)
                flash("Сеанс додано.", "success")
                return redirect(url_for("screenings.list_screenings"))
            except psycopg2.Error as e:
                screening_error(e, form_errors)
        return render_template("screening_form.html", heading="Додати сеанс", values=request.form,
                               form_errors=form_errors, movies=movies, halls=halls,
                               hall_locked=False), 400
    return render_template("screening_form.html", heading="Додати сеанс", values={}, form_errors={},
                           movies=movies, halls=halls, hall_locked=False)


@bp.route("/<int:screening_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def edit_screening(screening_id):
    screening = query_one("SELECT * FROM screenings WHERE screening_id = %s", (screening_id,))
    if screening is None:
        abort(404)
    if screening["start_time"] <= db_now():
        flash("Сеанс уже розпочався або завершився, змінювати його не можна.", "error")
        return redirect(url_for("screenings.list_screenings", when="all"))

    movies, halls = load_movies(), load_halls()
    tickets = query_one("SELECT COUNT(*) AS n FROM tickets WHERE screening_id = %s",
                        (screening_id,))["n"]
    locked = screening["hall_id"] if tickets else None     # з квитками зал змінювати не можна
    heading = f"Редагувати сеанс №{screening_id}"

    if request.method == "POST":
        data, form_errors = validate_screening(request.form, movies, halls, locked)
        if not form_errors:
            try:
                execute("""UPDATE screenings
                           SET movie_id = %(movie_id)s, hall_id = %(hall_id)s,
                               start_time = %(start_time)s, base_price = %(base_price)s
                           WHERE screening_id = %(id)s""", {**data, "id": screening_id})
                flash("Зміни збережено.", "success")
                return redirect(url_for("screenings.list_screenings"))
            except psycopg2.Error as e:
                screening_error(e, form_errors)
        values = {**request.form, "hall_id": str(screening["hall_id"])} if locked else request.form
        return render_template("screening_form.html", heading=heading, values=values,
                               form_errors=form_errors, movies=movies, halls=halls,
                               hall_locked=bool(locked)), 400

    values = {
        "movie_id": str(screening["movie_id"]),
        "hall_id": str(screening["hall_id"]),
        "start_time": screening["start_time"].strftime("%Y-%m-%dT%H:%M"),
        "base_price": str(screening["base_price"]),
    }
    return render_template("screening_form.html", heading=heading, values=values, form_errors={},
                           movies=movies, halls=halls, hall_locked=bool(locked))


@bp.route("/<int:screening_id>/delete", methods=["POST"])
@roles_required("admin")
def delete_screening(screening_id):
    if query_one("SELECT 1 AS ok FROM screenings WHERE screening_id = %s", (screening_id,)) is None:
        abort(404)
    tickets = query_one("SELECT COUNT(*) AS n FROM tickets WHERE screening_id = %s",
                        (screening_id,))["n"]
    if tickets:
        flash(f"Сеанс №{screening_id} видалити не можна: на нього є квитки ({tickets}), "
              "зокрема скасовані. Історія продажів зберігається.", "error")
        return redirect(url_for("screenings.list_screenings"))
    try:
        execute("DELETE FROM screenings WHERE screening_id = %s", (screening_id,))
        flash(f"Сеанс №{screening_id} видалено.", "success")
    except psycopg2.Error as e:
        flash(db_error_message(e), "error")
    return redirect(url_for("screenings.list_screenings"))