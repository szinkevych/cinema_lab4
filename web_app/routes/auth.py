"""Реєстрація, вхід і вихід."""
import time

import psycopg2
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from auth import safe_next
from database import db_error_message, log_action, query_one, transaction
from validators import get_email, get_password, get_phone, get_text, get_username

bp = Blueprint("auth", __name__)

# ---------------------------------------------------------------------
# Захист від підбору пароля: не більше MAX_ATTEMPTS невдалих спроб
# за WINDOW секунд для пари (IP, логін). Лічильник зберігається в пам'яті.
# ---------------------------------------------------------------------
MAX_ATTEMPTS = 5
WINDOW = 300
_failures = {}
_DUMMY_HASH = generate_password_hash("dummy-password-for-timing")


def _key(username):
    return (request.remote_addr, username.lower())


def blocked_minutes(username):
    """Скільки хвилин лишилось до розблокування (0, якщо не заблоковано)."""
    now = time.monotonic()
    attempts = [t for t in _failures.get(_key(username), []) if now - t < WINDOW]
    _failures[_key(username)] = attempts
    if len(attempts) >= MAX_ATTEMPTS:
        return int((WINDOW - (now - attempts[0])) // 60) + 1
    return 0


def register_failure(username):
    _failures.setdefault(_key(username), []).append(time.monotonic())


def start_session(user):
    """Нова сесія після входу (стара очищується, щоб не успадкувати чужі дані)."""
    session.clear()
    session["user_id"] = user["user_id"]
    session["username"] = user["username"]
    session.permanent = True


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.get("user"):
        return redirect(url_for("main.index"))
    next_url = safe_next(request.values.get("next"))
    error = None
    username = ""

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        wait = blocked_minutes(username) if username else 0
        if wait:
            error = f"Забагато невдалих спроб входу. Спробуйте через {wait} хв."
        else:
            user = query_one("""SELECT user_id, username, password_hash FROM users
                                WHERE lower(username) = lower(%s)""", (username,))
            # Хеш перевіряється завжди, навіть для неіснуючого логіна: однаковий час відповіді
            valid = check_password_hash(user["password_hash"] if user else _DUMMY_HASH, password)
            if user and valid:
                _failures.pop(_key(username), None)
                start_session(user)
                g.user = user
                log_action("LOGIN", "users", user["user_id"], "Успішний вхід", user_id=user["user_id"])
                flash(f"Вітаємо, {user['username']}!", "success")
                return redirect(next_url or url_for("main.index"))
            register_failure(username)
            log_action("LOGIN_FAILED", "users", user["user_id"] if user else None,
                       f"Невдала спроба входу, логін «{username[:50]}», IP {request.remote_addr}")
            error = "Неправильний логін або пароль."
        return render_template("login.html", error=error, username=username, next_url=next_url), 400
    return render_template("login.html", error=None, username="", next_url=next_url)


@bp.route("/logout", methods=["POST"])
def logout():
    if g.get("user"):
        log_action("LOGOUT", "users", g.user["user_id"], "Вихід із системи")
    session.clear()
    flash("Ви вийшли з системи.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.get("user"):
        return redirect(url_for("main.index"))
    form_errors = {}
    if request.method == "POST":
        data = {
            "username": get_username(request.form, "username", "Логін", form_errors),
            "first_name": get_text(request.form, "first_name", "Ім'я", form_errors, max_len=50),
            "last_name": get_text(request.form, "last_name", "Прізвище", form_errors, max_len=50),
            "email": get_email(request.form, "email", "Email", form_errors),
            "phone": get_phone(request.form, "phone", "Телефон", form_errors),
        }
        password = get_password(request.form, "password", "Пароль", form_errors)
        if password and request.form.get("password2") != password:
            form_errors["password2"] = "Паролі не збігаються."
        if data["username"] and query_one("SELECT 1 AS x FROM users WHERE lower(username) = lower(%s)",
                                          (data["username"],)):
            form_errors["username"] = "Цей логін уже зайнятий."

        if not form_errors:
            try:
                # Профіль клієнта й обліковий запис створюються однією транзакцією
                with transaction() as cur:
                    cur.execute("""INSERT INTO customers (first_name, last_name, email, phone)
                                   VALUES (%(first_name)s, %(last_name)s, %(email)s, %(phone)s)
                                   RETURNING customer_id""", data)
                    customer_id = cur.fetchone()["customer_id"]
                    cur.execute("""INSERT INTO users (username, password_hash, email, role, customer_id)
                                   VALUES (%s, %s, %s, 'customer', %s)
                                   RETURNING user_id, username""",
                                (data["username"], generate_password_hash(password, method="pbkdf2:sha256"),
                                 data["email"], customer_id))
                    user = cur.fetchone()
                start_session(user)
                g.user = user
                log_action("REGISTER", "users", user["user_id"], "Реєстрація нового глядача",
                           user_id=user["user_id"])
                flash("Реєстрацію завершено. Ласкаво просимо!", "success")
                return redirect(url_for("main.index"))
            except psycopg2.errors.UniqueViolation as e:
                constraint = e.diag.constraint_name or ""
                if "phone" in constraint:
                    form_errors["phone"] = "Цей телефон уже зареєстровано."
                elif "email" in constraint:
                    form_errors["email"] = ("Ця адреса вже є в системі. Якщо це ваша адреса, "
                                            "зверніться до касира або адміністратора.")
                else:
                    form_errors["username"] = "Цей логін уже зайнятий."
            except psycopg2.Error as e:
                flash(db_error_message(e), "error")
        return render_template("register.html", values=request.form, form_errors=form_errors), 400
    return render_template("register.html", values={}, form_errors={})