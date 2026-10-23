"""Вебзастосунок "Кінотеатр" (Flask + PostgreSQL).

Запуск:  python app.py   ->  http://127.0.0.1:5000
"""
import os
import secrets

import psycopg2
from flask import Flask, abort, render_template, request, session

from database import close_db, query_one
from routes.main import bp as main_bp
from routes.movies import bp as movies_bp
from routes.customers import bp as customers_bp
from routes.screenings import bp as screenings_bp
from routes.tickets import bp as tickets_bp
from routes.reports import bp as reports_bp

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-in-production")

# Підключаємо розділи сайту
app.register_blueprint(main_bp)
app.register_blueprint(movies_bp)
app.register_blueprint(customers_bp)
app.register_blueprint(screenings_bp)
app.register_blueprint(tickets_bp)
app.register_blueprint(reports_bp)

# Пункти меню: (назва, ім'я маршруту)
NAV = [
    ("Головна", "main.index"),
    ("Фільми", "movies.list_movies"),
    ("Клієнти", "customers.list_customers"),
    ("Сеанси", "screenings.list_screenings"),
    ("Квитки", "tickets.list_tickets"),
    ("Звіти", "reports.reports_page"),
]

# Після кожного запиту закриваємо з'єднання з базою
app.teardown_appcontext(close_db)


# ---------------------------------------------------------------------
# Захист від CSRF: кожна форма POST містить прихований токен, який
# зберігається і в сесії. Якщо токени не збігаються, запит відхиляється.
# ---------------------------------------------------------------------
def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token
# Поточний час за часовим поясом бази (так само, як у процедурах і тригерах)
app.jinja_env.globals["now"] = lambda: query_one("SELECT LOCALTIMESTAMP AS now")["now"]


@app.before_request
def verify_csrf():
    if request.method == "POST":
        sent = request.form.get("_csrf", "")
        expected = session.get("_csrf", "")
        if not expected or not secrets.compare_digest(sent, expected):
            abort(400)


@app.errorhandler(400)
def bad_request(error):
    return render_template("error.html", title="Недійсний запит",
                           message="Форма застаріла або не пройшла перевірку безпеки. "
                                   "Поверніться назад, оновіть сторінку і спробуйте ще раз."), 400


@app.context_processor
def inject_nav():
    """Робить список меню доступним у всіх шаблонах."""
    return {"nav_items": NAV, "current_endpoint": request.endpoint}


@app.template_filter("money")
def money(value):
    """150 -> '150.00 грн'"""
    return f"{value:.2f} грн"


@app.template_filter("dt")
def dt(value):
    """Дата й час у вигляді '2026-10-20 18:00'"""
    return value.strftime("%Y-%m-%d %H:%M") if value else ""


@app.errorhandler(psycopg2.OperationalError)
@app.errorhandler(UnicodeDecodeError)
def database_unavailable(error):
    """Не вдалося підключитися до бази (UnicodeDecodeError - так Windows показує цю помилку)."""
    return render_template(
        "error.html",
        title="База даних недоступна",
        message="Не вдалося підключитися до PostgreSQL. Перевірте, що Docker Desktop запущено, "
                "контейнер працює (docker compose ps) і порт у database.py збігається з docker-compose.yml.",
    ), 503


@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", title="Сторінку не знайдено",
                           message="Такої сторінки не існує."), 404


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)