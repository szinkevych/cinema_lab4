"""Розділ «Фільми»: список з пошуком і фільтрами, картка фільму, додавання, зміна, видалення."""
from datetime import date

import psycopg2
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from database import db_error_message, execute, query_all, query_one, transaction
from validators import get_choice, get_int, get_text

bp = Blueprint("movies", __name__, url_prefix="/movies")

AGE_RATINGS = [0, 6, 12, 16, 18]

# Сортування: ключ з форми -> стовпець SQL. Беремо лише зі словника,
# щоб у запит ніколи не потрапив довільний текст від користувача.
SORT_COLUMNS = {
    "title": "m.title",
    "year": "m.release_year",
    "duration": "m.duration_min",
    "rating": "m.age_rating",
}


def load_genres():
    return query_all("SELECT genre_id, name FROM genres ORDER BY name")


def validate_movie(form, genres):
    """Повертає (очищені дані, словник помилок)."""
    errors = {}
    data = {
        "title": get_text(form, "title", "Назва", errors, max_len=200),
        "description": get_text(form, "description", "Опис", errors, required=False, max_len=2000),
        "duration_min": get_int(form, "duration_min", "Тривалість", errors, 1, 600),
        "release_year": get_int(form, "release_year", "Рік випуску", errors,
                                1888, date.today().year + 5),
        "age_rating": get_choice(form, "age_rating", "Віковий рейтинг", errors, AGE_RATINGS, cast=int),
    }
    valid_ids = {g["genre_id"] for g in genres}
    selected = []
    for raw in form.getlist("genres"):
        if raw.isdigit() and int(raw) in valid_ids:
            selected.append(int(raw))
        else:
            errors["genres"] = "Обрано неіснуючий жанр."
    data["genres"] = selected
    return data, errors


def like_pattern(text):
    """Екранує спецсимволи LIKE (% і _), щоб пошук шукав саме введений текст."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@bp.route("/")
def list_movies():
    q = (request.args.get("q") or "").strip()
    genre = request.args.get("genre", type=int)
    age = request.args.get("age", type=int)
    if age not in AGE_RATINGS:
        age = None
    sort = request.args.get("sort", "title")
    if sort not in SORT_COLUMNS:
        sort = "title"
    order = "DESC" if request.args.get("order") == "desc" else "ASC"

    movies = query_all(f"""
        SELECT m.movie_id, m.title, m.release_year, m.duration_min, m.age_rating,
               COALESCE(string_agg(g.name, ', ' ORDER BY g.name), '') AS genres,
               (SELECT COUNT(*) FROM screenings s
                WHERE s.movie_id = m.movie_id AND s.start_time > CURRENT_TIMESTAMP) AS upcoming
        FROM movies m
        LEFT JOIN movie_genres mg ON mg.movie_id = m.movie_id
        LEFT JOIN genres g        ON g.genre_id  = mg.genre_id
        WHERE (%(q)s = '' OR m.title ILIKE %(like)s)
          AND (%(genre)s IS NULL OR EXISTS (SELECT 1 FROM movie_genres x
                                            WHERE x.movie_id = m.movie_id AND x.genre_id = %(genre)s))
          AND (%(age)s IS NULL OR m.age_rating <= %(age)s)
        GROUP BY m.movie_id
        ORDER BY {SORT_COLUMNS[sort]} {order}, m.title
    """, {"q": q, "like": like_pattern(q), "genre": genre, "age": age})

    return render_template(
        "movies.html", movies=movies, genres=load_genres(), ratings=AGE_RATINGS,
        filters={"q": q, "genre": genre, "age": age, "sort": sort, "order": order.lower()},
    )


@bp.route("/<int:movie_id>")
def movie_detail(movie_id):
    movie = query_one("SELECT * FROM movies WHERE movie_id = %s", (movie_id,))
    if movie is None:
        abort(404)
    genres = query_all("""
        SELECT g.name FROM genres g
        JOIN movie_genres mg ON mg.genre_id = g.genre_id
        WHERE mg.movie_id = %s ORDER BY g.name""", (movie_id,))
    screenings = query_all("""
        SELECT o.screening_id, o.hall, o.start_time, o.sold_seats, o.total_seats, o.occupancy_pct
        FROM screening_occupancy o
        JOIN screenings s ON s.screening_id = o.screening_id
        WHERE s.movie_id = %s
        ORDER BY o.start_time""", (movie_id,))
    return render_template("movie_detail.html", movie=movie, genres=genres, screenings=screenings)


@bp.route("/add", methods=["GET", "POST"])
def add_movie():
    genres = load_genres()
    if request.method == "POST":
        data, form_errors = validate_movie(request.form, genres)
        if not form_errors:
            try:
                # Фільм і його жанри додаються однією транзакцією
                with transaction() as cur:
                    cur.execute(
                        """INSERT INTO movies (title, description, duration_min, release_year, age_rating)
                           VALUES (%s, %s, %s, %s, %s) RETURNING movie_id""",
                        (data["title"], data["description"], data["duration_min"],
                         data["release_year"], data["age_rating"]))
                    movie_id = cur.fetchone()["movie_id"]
                    for genre_id in data["genres"]:
                        cur.execute("INSERT INTO movie_genres (movie_id, genre_id) VALUES (%s, %s)",
                                    (movie_id, genre_id))
                flash("Фільм додано.", "success")
                return redirect(url_for("movies.movie_detail", movie_id=movie_id))
            except psycopg2.errors.UniqueViolation:
                form_errors["title"] = "Фільм з такою назвою і роком випуску вже є."
            except psycopg2.Error as e:
                flash(db_error_message(e), "error")
        return render_template(
            "movie_form.html", heading="Додати фільм", values=request.form, form_errors=form_errors,
            genres=genres, selected_genres=data["genres"], ratings=AGE_RATINGS), 400
    return render_template(
        "movie_form.html", heading="Додати фільм", values={"age_rating": "0"}, form_errors={},
        genres=genres, selected_genres=[], ratings=AGE_RATINGS)


@bp.route("/<int:movie_id>/edit", methods=["GET", "POST"])
def edit_movie(movie_id):
    movie = query_one("SELECT * FROM movies WHERE movie_id = %s", (movie_id,))
    if movie is None:
        abort(404)
    genres = load_genres()

    if request.method == "POST":
        data, form_errors = validate_movie(request.form, genres)
        if not form_errors:
            try:
                with transaction() as cur:
                    cur.execute(
                        """UPDATE movies
                           SET title = %s, description = %s, duration_min = %s,
                               release_year = %s, age_rating = %s
                           WHERE movie_id = %s""",
                        (data["title"], data["description"], data["duration_min"],
                         data["release_year"], data["age_rating"], movie_id))
                    cur.execute("DELETE FROM movie_genres WHERE movie_id = %s", (movie_id,))
                    for genre_id in data["genres"]:
                        cur.execute("INSERT INTO movie_genres (movie_id, genre_id) VALUES (%s, %s)",
                                    (movie_id, genre_id))
                flash("Зміни збережено.", "success")
                return redirect(url_for("movies.movie_detail", movie_id=movie_id))
            except psycopg2.errors.UniqueViolation:
                form_errors["title"] = "Фільм з такою назвою і роком випуску вже є."
            except psycopg2.Error as e:
                flash(db_error_message(e), "error")
        return render_template(
            "movie_form.html", heading=f"Редагувати: {movie['title']}", values=request.form,
            form_errors=form_errors, genres=genres, selected_genres=data["genres"],
            ratings=AGE_RATINGS), 400

    selected = [r["genre_id"] for r in query_all(
        "SELECT genre_id FROM movie_genres WHERE movie_id = %s", (movie_id,))]
    values = {**movie, "description": movie["description"] or "", "age_rating": str(movie["age_rating"])}
    return render_template(
        "movie_form.html", heading=f"Редагувати: {movie['title']}", values=values, form_errors={},
        genres=genres, selected_genres=selected, ratings=AGE_RATINGS)


@bp.route("/<int:movie_id>/delete", methods=["POST"])
def delete_movie(movie_id):
    movie = query_one("SELECT title FROM movies WHERE movie_id = %s", (movie_id,))
    if movie is None:
        abort(404)
    upcoming = query_one("SELECT COUNT(*) AS n FROM screenings WHERE movie_id = %s", (movie_id,))["n"]
    if upcoming:
        flash(f"Фільм «{movie['title']}» видалити не можна: у розкладі є сеанси ({upcoming}). "
              "Спочатку видаліть їх.", "error")
        return redirect(url_for("movies.list_movies"))
    try:
        execute("DELETE FROM movies WHERE movie_id = %s", (movie_id,))
        flash(f"Фільм «{movie['title']}» видалено.", "success")
    except psycopg2.Error as e:
        flash(db_error_message(e), "error")
    return redirect(url_for("movies.list_movies"))