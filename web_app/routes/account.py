"""Особистий кабінет глядача."""
import psycopg2
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from auth import roles_required
from database import db_error_message, query_one, transaction
from validators import get_email, get_phone, get_text, get_username

bp = Blueprint("account", __name__, url_prefix="/account")


def load_account():
    return query_one("""
        SELECT u.user_id, u.username, u.email, c.customer_id,
               c.first_name, c.last_name, c.phone
        FROM users u
        JOIN customers c ON c.customer_id = u.customer_id
        WHERE u.user_id = %s
    """, (g.user["user_id"],))


def validate_account(form, account):
    errors = {}
    data = {
        "username": get_username(form, "username", "Логін", errors),
        "first_name": get_text(form, "first_name", "Ім'я", errors, max_len=50),
        "last_name": get_text(form, "last_name", "Прізвище", errors, max_len=50),
        "email": get_email(form, "email", "Email", errors),
        "phone": get_phone(form, "phone", "Телефон", errors),
    }
    if data["username"] and query_one(
        "SELECT 1 AS x FROM users WHERE lower(username) = lower(%s) AND user_id <> %s",
        (data["username"], account["user_id"]),
    ):
        errors["username"] = "Цей логін уже зайнятий."
    if data["email"]:
        if query_one(
            "SELECT 1 AS x FROM users WHERE lower(email) = lower(%s) AND user_id <> %s",
            (data["email"], account["user_id"]),
        ) or query_one(
            "SELECT 1 AS x FROM customers WHERE lower(email) = lower(%s) AND customer_id <> %s",
            (data["email"], account["customer_id"]),
        ):
            errors["email"] = "Ця адреса вже використовується іншим акаунтом."
    if data["phone"]:
        if query_one(
            "SELECT 1 AS x FROM customers WHERE phone = %s AND customer_id <> %s",
            (data["phone"], account["customer_id"]),
        ):
            errors["phone"] = "Цей телефон уже зареєстровано."
    return data, errors


@bp.route("/")
@roles_required("customer")
def profile():
    account = load_account()
    if account is None:
        abort(404)
    return render_template("account.html", account=account)


@bp.route("/edit", methods=["GET", "POST"])
@roles_required("customer")
def edit_profile():
    account = load_account()
    if account is None:
        abort(404)

    if request.method == "POST":
        data, errors = validate_account(request.form, account)
        if not errors:
            try:
                with transaction() as cur:
                    cur.execute("""
                        UPDATE customers
                        SET first_name = %(first_name)s, last_name = %(last_name)s,
                            email = %(email)s, phone = %(phone)s
                        WHERE customer_id = %(customer_id)s
                    """, {**data, "customer_id": account["customer_id"]})
                    cur.execute("""
                        UPDATE users SET username = %(username)s, email = %(email)s
                        WHERE user_id = %(user_id)s
                    """, {**data, "user_id": account["user_id"]})
                flash("Дані акаунта оновлено.", "success")
                return redirect(url_for("account.profile"))
            except psycopg2.errors.UniqueViolation as error:
                constraint = error.diag.constraint_name or ""
                if "username" in constraint:
                    errors["username"] = "Цей логін уже зайнятий."
                elif "phone" in constraint:
                    errors["phone"] = "Цей телефон уже зареєстровано."
                else:
                    errors["email"] = "Ця адреса вже використовується іншим акаунтом."
            except psycopg2.Error as error:
                flash(db_error_message(error), "error")
        return render_template(
            "account_form.html", account=account, values=request.form, form_errors=errors
        ), 400

    return render_template(
        "account_form.html", account=account, values=account, form_errors={}
    )
