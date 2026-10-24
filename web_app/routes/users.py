"""Керування користувачами (лише адміністратор): список, створення, зміна ролі, видалення."""
import psycopg2
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from auth import ROLE_LABELS, roles_required
from database import db_error_message, execute, query_all, query_one
from validators import get_choice, get_email, get_password, get_username

bp = Blueprint("users", __name__, url_prefix="/users")


def load_users():
    return query_all("""
        SELECT u.user_id, u.username, u.email, u.role, u.customer_id,
               c.first_name || ' ' || c.last_name AS customer_name
        FROM users u LEFT JOIN customers c ON c.customer_id = u.customer_id
        ORDER BY CASE u.role WHEN 'admin' THEN 1 WHEN 'cashier' THEN 2 ELSE 3 END, u.username""")


@bp.route("/", methods=["GET", "POST"])
@roles_required("admin")
def list_users():
    """GET - список; POST - створення облікового запису співробітника."""
    form_errors = {}
    if request.method == "POST":
        data = {
            "username": get_username(request.form, "username", "Логін", form_errors),
            "email": get_email(request.form, "email", "Email", form_errors),
            "role": get_choice(request.form, "role", "Роль", form_errors, ["admin", "cashier"]),
        }
        password = get_password(request.form, "password", "Пароль", form_errors)
        if data["username"] and query_one("SELECT 1 AS x FROM users WHERE lower(username) = lower(%s)",
                                          (data["username"],)):
            form_errors["username"] = "Цей логін уже зайнятий."
        if not form_errors:
            try:
                execute("""INSERT INTO users (username, password_hash, email, role)
                           VALUES (%s, %s, %s, %s)""",
                        (data["username"], generate_password_hash(password, method="pbkdf2:sha256"),
                         data["email"], data["role"]))
                flash(f"Обліковий запис «{data['username']}» створено.", "success")
                return redirect(url_for("users.list_users"))
            except psycopg2.errors.UniqueViolation:
                form_errors["email"] = "Користувач з такою адресою вже є."
            except psycopg2.Error as e:
                flash(db_error_message(e), "error")
        return render_template("users.html", users=load_users(), values=request.form,
                               form_errors=form_errors, role_labels=ROLE_LABELS), 400
    return render_template("users.html", users=load_users(), values={}, form_errors={},
                           role_labels=ROLE_LABELS)


@bp.route("/<int:user_id>/role", methods=["POST"])
@roles_required("admin")
def change_role(user_id):
    user = query_one("SELECT username FROM users WHERE user_id = %s", (user_id,))
    if user is None:
        abort(404)
    if user_id == g.user["user_id"]:
        flash("Свою власну роль змінювати не можна (щоб не втратити доступ).", "error")
        return redirect(url_for("users.list_users"))
    errors = {}
    role = get_choice(request.form, "role", "Роль", errors, list(ROLE_LABELS))
    if errors:
        flash("Оберіть коректну роль.", "error")
        return redirect(url_for("users.list_users"))
    execute("UPDATE users SET role = %s WHERE user_id = %s", (role, user_id))
    flash(f"Роль користувача «{user['username']}»: {ROLE_LABELS[role]}.", "success")
    return redirect(url_for("users.list_users"))


@bp.route("/<int:user_id>/delete", methods=["POST"])
@roles_required("admin")
def delete_user(user_id):
    user = query_one("SELECT username FROM users WHERE user_id = %s", (user_id,))
    if user is None:
        abort(404)
    if user_id == g.user["user_id"]:
        flash("Видаляти власний обліковий запис не можна.", "error")
        return redirect(url_for("users.list_users"))
    try:
        execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        flash(f"Користувача «{user['username']}» видалено. Профіль клієнта й історія покупок збережені.",
              "success")
    except psycopg2.Error as e:
        flash(db_error_message(e), "error")
    return redirect(url_for("users.list_users"))