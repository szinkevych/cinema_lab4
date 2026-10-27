"""Вебзастосунок "Кінотеатр" (Flask + PostgreSQL).

Запуск:  python app.py   ->  http://127.0.0.1:5000
"""
import os
import secrets
from datetime import timedelta

import psycopg2
from flask import Flask, abort, g, jsonify, redirect, render_template, request, session, url_for

from auth import ROLE_LABELS, STAFF
from database import close_db, query_one
from routes.activity import bp as activity_bp
from routes.account import bp as account_bp
from routes.api import bp as api_bp
from routes.auth import bp as auth_bp
from routes.customers import bp as customers_bp
from routes.main import bp as main_bp
from routes.movies import bp as movies_bp
from routes.reports import bp as reports_bp
from routes.screenings import bp as screenings_bp
from routes.tickets import bp as tickets_bp
from routes.users import bp as users_bp

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,          # JavaScript не бачить cookie сесії
    SESSION_COOKIE_SAMESITE="Lax",         # cookie не надсилається з чужих сайтів
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)

# Підключаємо розділи сайту
for blueprint in (main_bp, auth_bp, api_bp, account_bp, movies_bp, customers_bp, screenings_bp, tickets_bp,
                  reports_bp, users_bp, activity_bp):
    app.register_blueprint(blueprint)

# Пункти меню: (назва, маршрут, ролі, яким це видно; None = усім)
NAV = [
    ("Головна", "main.index", None),
    ("Фільми", "movies.list_movies", STAFF),
    ("Клієнти", "customers.list_customers", STAFF),
    ("Сеанси", "screenings.list_screenings", None),
    ("Квитки", "tickets.list_tickets", ("admin", "cashier", "customer")),
    ("Мій акаунт", "account.profile", ("customer",)),
    ("Звіти", "reports.reports_page", ("admin",)),
    ("Користувачі", "users.list_users", ("admin",)),
    ("Журнал", "activity.list_activity", ("admin",)),
]

# Сторінки, доступні без входу
PUBLIC_ENDPOINTS = {
    "auth.login", "auth.register", "static", "main.index", "screenings.list_screenings",
    "api.list_movies", "api.list_screenings", "api.screening_availability",
}

# Після кожного запиту закриваємо з'єднання з базою
app.teardown_appcontext(close_db)

# Поточний час за часовим поясом бази (так само, як у процедурах і тригерах)
app.jinja_env.globals["now"] = lambda: query_one("SELECT LOCALTIMESTAMP AS now")["now"]
app.jinja_env.globals["role_labels"] = ROLE_LABELS


# ---------------------------------------------------------------------
# Захист від CSRF: кожна форма POST містить прихований токен, який
# зберігається і в сесії. Якщо токени не збігаються, запит відхиляється.
# ---------------------------------------------------------------------
def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def verify_csrf():
    if request.method == "POST":
        sent = request.form.get("_csrf", "")
        expected = session.get("_csrf", "")
        if not expected or not secrets.compare_digest(sent, expected):
            abort(400)


# ---------------------------------------------------------------------
# Автентифікація: на кожному запиті користувача заново читаємо з бази,
# тож видалення акаунта чи зміна ролі діють негайно, без повторного входу.
# ---------------------------------------------------------------------
@app.before_request
def load_user_and_require_login():
    g.user = None
    user_id = session.get("user_id")
    if user_id:
        g.user = query_one("""SELECT user_id, username, role, customer_id
                              FROM users WHERE user_id = %s""", (user_id,))
        if g.user is None:
            session.clear()

    if request.endpoint is None or request.endpoint in PUBLIC_ENDPOINTS:
        return None
    if g.user is None:
        target = request.full_path.rstrip("?") if request.method == "GET" else None
        return redirect(url_for("auth.login", next=target))
    return None


@app.context_processor
def inject_layout():
    """Дані для всіх шаблонів: поточний користувач і меню, відфільтроване за роллю."""
    user = g.get("user")
    role = user["role"] if user else "guest"
    items = []
    for label, endpoint, roles in NAV:
        if roles is None or role in roles:
            if role in STAFF and endpoint == "main.index":
                label, endpoint = "Головна", "movies.list_movies"
            elif role in STAFF and endpoint == "movies.list_movies":
                continue
            if endpoint == "tickets.list_tickets" and user and user["role"] == "customer":
                label = "Мої квитки"
            items.append((label, endpoint))
    return {"nav_items": items, "current_endpoint": request.endpoint, "current_user": user}


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


@app.errorhandler(400)
def bad_request(error):
    return render_template("error.html", title="Недійсний запит",
                           message="Форма застаріла або не пройшла перевірку безпеки. "
                                   "Поверніться назад, оновіть сторінку і спробуйте ще раз."), 400


@app.errorhandler(403)
def forbidden(error):
    return render_template("error.html", title="Доступ заборонено",
                           message="У вас немає прав для цієї дії або сторінки."), 403


@app.errorhandler(404)
def not_found(error):
    if request.path.startswith("/api/"):
        return jsonify(error={"code": 404, "message": "Ендпойнт не знайдено."}), 404
    return render_template("error.html", title="Сторінку не знайдено",
                           message="Такої сторінки не існує."), 404


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)