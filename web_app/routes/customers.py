"""Розділ «Клієнти»: список з пошуком, картка з історією покупок, додавання, зміна, видалення."""
import psycopg2
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from auth import STAFF, roles_required
from database import db_error_message, execute, query_all, query_one
from validators import get_email, get_phone, get_text

bp = Blueprint("customers", __name__, url_prefix="/customers")

# Сортування: ключ з форми -> список стовпців SQL (лише з цього словника)
SORT_COLUMNS = {
    "name": ["c.last_name", "c.first_name"],
    "email": ["c.email"],
    "tickets": ["tickets_count"],
    "spent": ["total_spent"],
}


def like_pattern(text):
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def validate_customer(form):
    errors = {}
    data = {
        "first_name": get_text(form, "first_name", "Ім'я", errors, max_len=50),
        "last_name": get_text(form, "last_name", "Прізвище", errors, max_len=50),
        "email": get_email(form, "email", "Email", errors),
        "phone": get_phone(form, "phone", "Телефон", errors),
    }
    return data, errors


def unique_violation_to_errors(e, form_errors):
    """Визначає за назвою обмеження, яке саме поле повторюється."""
    constraint = e.diag.constraint_name or ""
    if "phone" in constraint:
        form_errors["phone"] = "Клієнт з таким телефоном уже є."
    elif "email" in constraint:
        form_errors["email"] = "Клієнт з такою адресою вже є."
    else:
        form_errors["email"] = "Такий клієнт уже існує."


@bp.route("/")
@roles_required(*STAFF)
def list_customers():
    q = (request.args.get("q") or "").strip()
    sort = request.args.get("sort", "name")
    if sort not in SORT_COLUMNS:
        sort = "name"
    order = "DESC" if request.args.get("order") == "desc" else "ASC"
    order_by = ", ".join(f"{col} {order}" for col in SORT_COLUMNS[sort])

    customers = query_all(f"""
        SELECT c.customer_id, c.first_name, c.last_name, c.email, c.phone,
               COUNT(t.ticket_id) FILTER (WHERE t.status = 'sold') AS tickets_count,
               COALESCE(SUM(t.price) FILTER (WHERE t.status = 'sold'), 0) AS total_spent
        FROM customers c
        LEFT JOIN tickets t ON t.customer_id = c.customer_id
        WHERE (%(q)s = ''
               OR c.first_name ILIKE %(like)s OR c.last_name ILIKE %(like)s
               OR (c.first_name || ' ' || c.last_name) ILIKE %(like)s
               OR c.email ILIKE %(like)s OR COALESCE(c.phone, '') ILIKE %(like)s)
        GROUP BY c.customer_id
        ORDER BY {order_by}
    """, {"q": q, "like": like_pattern(q)})
    return render_template("customers.html", customers=customers,
                           filters={"q": q, "sort": sort, "order": order.lower()})


@bp.route("/<int:customer_id>")
def customer_detail(customer_id):
    # Глядач бачить лише власну картку; співробітники - будь-яку
    if g.user["role"] == "customer" and g.user["customer_id"] != customer_id:
        abort(403)
    customer = query_one("SELECT * FROM customers WHERE customer_id = %s", (customer_id,))
    if customer is None:
        abort(404)
    tickets = query_all("""
        SELECT t.ticket_id, m.title, h.name AS hall, s.start_time,
               st.row_number, st.seat_number, t.price, t.status
        FROM tickets t
        JOIN screenings s ON s.screening_id = t.screening_id
        JOIN movies m     ON m.movie_id = s.movie_id
        JOIN halls h      ON h.hall_id = s.hall_id
        JOIN seats st     ON st.seat_id = t.seat_id
        WHERE t.customer_id = %s
        ORDER BY s.start_time DESC, t.ticket_id DESC""", (customer_id,))
    sold = [t for t in tickets if t["status"] == "sold"]
    return render_template("customer_detail.html", customer=customer, tickets=tickets,
                           sold_count=len(sold), total_spent=sum(t["price"] for t in sold))


@bp.route("/add", methods=["GET", "POST"])
@roles_required(*STAFF)
def add_customer():
    if request.method == "POST":
        data, form_errors = validate_customer(request.form)
        if not form_errors:
            try:
                row = execute(
                    """INSERT INTO customers (first_name, last_name, email, phone)
                       VALUES (%(first_name)s, %(last_name)s, %(email)s, %(phone)s)
                       RETURNING customer_id""", data, returning=True)
                flash("Клієнта додано.", "success")
                return redirect(url_for("customers.customer_detail", customer_id=row["customer_id"]))
            except psycopg2.errors.UniqueViolation as e:
                unique_violation_to_errors(e, form_errors)
            except psycopg2.Error as e:
                flash(db_error_message(e), "error")
        return render_template("customer_form.html", heading="Додати клієнта",
                               values=request.form, form_errors=form_errors), 400
    return render_template("customer_form.html", heading="Додати клієнта", values={}, form_errors={})


@bp.route("/<int:customer_id>/edit", methods=["GET", "POST"])
@roles_required(*STAFF)
def edit_customer(customer_id):
    customer = query_one("SELECT * FROM customers WHERE customer_id = %s", (customer_id,))
    if customer is None:
        abort(404)
    heading = f"Редагувати: {customer['first_name']} {customer['last_name']}"

    if request.method == "POST":
        data, form_errors = validate_customer(request.form)
        if not form_errors:
            try:
                execute("""UPDATE customers
                           SET first_name = %(first_name)s, last_name = %(last_name)s,
                               email = %(email)s, phone = %(phone)s
                           WHERE customer_id = %(id)s""", {**data, "id": customer_id})
                flash("Зміни збережено.", "success")
                return redirect(url_for("customers.customer_detail", customer_id=customer_id))
            except psycopg2.errors.UniqueViolation as e:
                unique_violation_to_errors(e, form_errors)
            except psycopg2.Error as e:
                flash(db_error_message(e), "error")
        return render_template("customer_form.html", heading=heading,
                               values=request.form, form_errors=form_errors), 400

    values = {**customer, "phone": customer["phone"] or ""}
    return render_template("customer_form.html", heading=heading, values=values, form_errors={})


@bp.route("/<int:customer_id>/delete", methods=["POST"])
@roles_required(*STAFF)
def delete_customer(customer_id):
    customer = query_one("SELECT first_name, last_name FROM customers WHERE customer_id = %s",
                         (customer_id,))
    if customer is None:
        abort(404)
    name = f"{customer['first_name']} {customer['last_name']}"
    tickets = query_one("SELECT COUNT(*) AS n FROM tickets WHERE customer_id = %s", (customer_id,))["n"]
    if tickets:
        flash(f"Клієнта {name} видалити не можна: з ним пов'язано квитків ({tickets}). "
              "Історія продажів зберігається.", "error")
        return redirect(url_for("customers.list_customers"))
    try:
        execute("DELETE FROM customers WHERE customer_id = %s", (customer_id,))
        flash(f"Клієнта {name} видалено.", "success")
    except psycopg2.Error as e:
        flash(db_error_message(e), "error")
    return redirect(url_for("customers.list_customers"))