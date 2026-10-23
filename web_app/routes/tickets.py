"""Розділ «Квитки»: схема залу з вибором місць (продаж), список квитків, скасування.

Продаж і скасування виконують збережені процедури бази (sell_ticket, cancel_ticket),
тож усі правила (сеанс не почався, місце вільне, ціна зі знижкою, скасування не пізніше
ніж за годину) лежать в одному місці й однакові для будь-якого застосунку.
"""
import re
from decimal import Decimal

import psycopg2
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from database import db_error_message, query_all, query_one, transaction
from validators import get_choice

bp = Blueprint("tickets", __name__, url_prefix="/tickets")

# Тип квитка -> (назва, коефіцієнт). Коефіцієнт тут лише для підказки суми на сторінці,
# реальну ціну рахує процедура sell_ticket у базі.
TICKET_TYPES = {
    "regular": ("Звичайний", Decimal("1.0")),
    "child": ("Дитячий (−50%)", Decimal("0.5")),
    "student": ("Студентський (−20%)", Decimal("0.8")),
}
MAX_SEATS = 10                # місць у одному замовленні
APP_USER = "web"              # ім'я для аудиту (на рівні 3 буде логін користувача)
SEAT_RE = re.compile(r"^(\d{1,3}):(\d{1,3})$")


def db_now():
    return query_one("SELECT LOCALTIMESTAMP AS now")["now"]


def load_layout(screening_id):
    """Місця залу сеансу, згруповані по рядах: {ряд: [місця]}. sold = місце вже продане."""
    rows = query_all("""
        SELECT st.row_number, st.seat_number, (t.ticket_id IS NOT NULL) AS sold
        FROM screenings sc
        JOIN seats st ON st.hall_id = sc.hall_id
        LEFT JOIN tickets t ON t.seat_id = st.seat_id
                           AND t.screening_id = sc.screening_id AND t.status = 'sold'
        WHERE sc.screening_id = %s
        ORDER BY st.row_number, st.seat_number""", (screening_id,))
    layout = {}
    for r in rows:
        layout.setdefault(r["row_number"], []).append(r)
    return layout


@bp.route("/sell/<int:screening_id>", methods=["GET", "POST"])
def sell_tickets(screening_id):
    screening = query_one("""
        SELECT s.screening_id, s.start_time, s.base_price, m.title, h.name AS hall, h.hall_type
        FROM screenings s
        JOIN movies m ON m.movie_id = s.movie_id
        JOIN halls h  ON h.hall_id = s.hall_id
        WHERE s.screening_id = %s""", (screening_id,))
    if screening is None:
        abort(404)

    closed = screening["start_time"] <= db_now()
    customers = query_all("""SELECT customer_id, first_name, last_name, email
                             FROM customers ORDER BY last_name, first_name""")
    layout = load_layout(screening_id)
    existing = {(r, s["seat_number"]) for r, seats in layout.items() for s in seats}
    form_errors, selected, values = {}, [], {"ticket_type": "regular"}

    if request.method == "POST":
        values = request.form
        seats = []
        if closed:
            form_errors["seats"] = "Сеанс уже розпочався, продаж закрито."
        else:
            for raw in request.form.getlist("seats"):
                m = SEAT_RE.match(raw)
                if not m or (int(m.group(1)), int(m.group(2))) not in existing:
                    form_errors["seats"] = "Обрано неіснуюче місце."
                    break
                seats.append((int(m.group(1)), int(m.group(2))))
            seats = list(dict.fromkeys(seats))       # прибираємо дублікати, зберігаючи порядок
            if "seats" not in form_errors:
                if not seats:
                    form_errors["seats"] = "Оберіть хоча б одне місце на схемі."
                elif len(seats) > MAX_SEATS:
                    form_errors["seats"] = f"В одному замовленні не більше {MAX_SEATS} місць."
        customer_id = get_choice(request.form, "customer_id", "Клієнт", form_errors,
                                 {c["customer_id"] for c in customers}, cast=int)
        ticket_type = get_choice(request.form, "ticket_type", "Тип квитка", form_errors,
                                 set(TICKET_TYPES))
        selected = [f"{r}:{s}" for r, s in seats]

        if not form_errors:
            try:
                # Усі місця замовлення продаються в одній транзакції: або всі, або жодного
                with transaction(APP_USER) as cur:
                    ids = []
                    for row, seat in seats:
                        cur.execute("SELECT sell_ticket(%s, %s, %s, %s, %s) AS ticket_id",
                                    (screening_id, row, seat, customer_id, ticket_type))
                        ids.append(cur.fetchone()["ticket_id"])
                    cur.execute("SELECT SUM(price) AS total FROM tickets WHERE ticket_id = ANY(%s)",
                                (ids,))
                    total = cur.fetchone()["total"]
                numbers = ", ".join(f"№{i}" for i in ids)
                flash(f"Продано квитків: {len(ids)} ({numbers}). Сума: {total:.2f} грн.", "success")
                return redirect(url_for("tickets.sell_tickets", screening_id=screening_id))
            except psycopg2.errors.RaiseException as e:
                form_errors["seats"] = e.diag.message_primary      # повідомлення процедури
            except psycopg2.Error as e:
                flash(db_error_message(e), "error")
            layout = load_layout(screening_id)                      # стан місць міг змінитись

    total_seats = sum(len(s) for s in layout.values())
    sold_seats = sum(1 for s in layout.values() for x in s if x["sold"])
    return render_template(
        "seat_map.html", screening=screening, layout=layout, customers=customers,
        ticket_types=TICKET_TYPES, closed=closed, form_errors=form_errors, selected=selected,
        values=values, total_seats=total_seats, sold_seats=sold_seats,
        max_seats=MAX_SEATS), (400 if form_errors else 200)


@bp.route("/")
def list_tickets():
    status = request.args.get("status", "")
    if status not in ("sold", "cancelled"):
        status = ""
    when = request.args.get("when", "all")
    if when not in ("all", "upcoming", "past"):
        when = "all"
    q = (request.args.get("q") or "").strip()
    like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"

    when_sql = {"all": "TRUE", "upcoming": "tf.start_time >= LOCALTIMESTAMP",
                "past": "tf.start_time < LOCALTIMESTAMP"}[when]
    # Читаємо з представлення tickets_full (рівень 2)
    tickets = query_all(f"""
        SELECT tf.*,
               (tf.status = 'sold' AND tf.start_time > LOCALTIMESTAMP + INTERVAL '1 hour') AS cancelable
        FROM tickets_full tf
        WHERE (%(status)s = '' OR tf.status = %(status)s)
          AND {when_sql}
          AND (%(q)s = '' OR tf.movie ILIKE %(like)s OR tf.customer ILIKE %(like)s)
        ORDER BY tf.purchased_at DESC, tf.ticket_id DESC
        LIMIT 300
    """, {"status": status, "q": q, "like": like})
    total = sum(t["price"] for t in tickets if t["status"] == "sold")
    return render_template("tickets.html", tickets=tickets, total=total,
                           filters={"status": status, "when": when, "q": q})


@bp.route("/<int:ticket_id>/cancel", methods=["POST"])
def cancel_ticket(ticket_id):
    try:
        with transaction(APP_USER) as cur:
            cur.execute("SELECT cancel_ticket(%s)", (ticket_id,))
        flash(f"Квиток №{ticket_id} скасовано, місце знову вільне.", "success")
    except psycopg2.errors.RaiseException as e:
        flash(e.diag.message_primary, "error")
    except psycopg2.Error as e:
        flash(db_error_message(e), "error")
    return redirect(url_for("tickets.list_tickets"))