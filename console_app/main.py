"""Консольний застосунок "Кінотеатр": CRUD над базою даних PostgreSQL."""
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation

import psycopg2
from psycopg2 import errors

from database import Database

db = Database()


# ---------------------------------------------------------------------
# Допоміжні функції: введення з перевіркою та вивід таблиць
# ---------------------------------------------------------------------
def ask_str(prompt, required=True):
    while True:
        value = input(prompt).strip()
        if value:
            return value
        if not required:
            return None
        print("  Поле обов'язкове.")


def ask_int(prompt, required=True, min_value=None, max_value=None):
    while True:
        value = input(prompt).strip()
        if not value:
            if not required:
                return None
            print("  Поле обов'язкове.")
            continue
        try:
            number = int(value)
        except ValueError:
            print("  Введіть ціле число.")
            continue
        if min_value is not None and number < min_value:
            print(f"  Значення не може бути менше {min_value}.")
            continue
        if max_value is not None and number > max_value:
            print(f"  Значення не може бути більше {max_value}.")
            continue
        return number


def ask_decimal(prompt, min_value=0):
    while True:
        value = input(prompt).strip().replace(",", ".")
        try:
            number = Decimal(value)
        except InvalidOperation:
            print("  Введіть число, наприклад 150 або 150.50.")
            continue
        if number < min_value:
            print(f"  Значення не може бути менше {min_value}.")
            continue
        return number


def ask_datetime(prompt):
    while True:
        value = input(prompt).strip()
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M")
        except ValueError:
            print("  Формат: РРРР-ММ-ДД ГГ:ХХ, наприклад 2026-10-25 18:30.")


def confirm(prompt):
    return input(f"{prompt} (так/ні): ").strip().lower() in ("так", "т", "y", "yes")


def print_table(headers, rows):
    if not rows:
        print("  (немає даних)")
        return
    text_rows = [["" if v is None else str(v) for v in row] for row in rows]
    widths = [max(len(h), *(len(r[i]) for r in text_rows)) for i, h in enumerate(headers)]
    print()
    print(" | ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("-+-".join("-" * w for w in widths))
    for row in text_rows:
        print(" | ".join(v.ljust(w) for v, w in zip(row, widths)))
    print(f"\nЗаписів: {len(text_rows)}")


def db_error_message(e):
    """Перекладає помилки бази у зрозуміле повідомлення."""
    if isinstance(e, errors.UniqueViolation):
        return "Помилка: такий запис уже існує (порушено унікальність)."
    if isinstance(e, errors.ForeignKeyViolation):
        return ("Помилка: запис пов'язаний з іншими даними (його не можна видалити), "
                "або посилається на неіснуючий запис.")
    if isinstance(e, errors.CheckViolation):
        return "Помилка: значення не відповідає обмеженням бази (CHECK)."
    if isinstance(e, errors.NotNullViolation):
        return "Помилка: не заповнено обов'язкове поле."
    return f"Помилка бази даних: {(e.pgerror or str(e)).strip()}"


# ---------------------------------------------------------------------
# Фільми
# ---------------------------------------------------------------------
def show_genres():
    rows = db.fetch_all("SELECT genre_id, name FROM genres ORDER BY genre_id")
    print_table(["ID", "Жанр"], rows)


def list_movies():
    rows = db.fetch_all("""
        SELECT m.movie_id, m.title, m.release_year, m.duration_min,
               m.age_rating || '+',
               COALESCE(string_agg(g.name, ', ' ORDER BY g.name), '-')
        FROM movies m
        LEFT JOIN movie_genres mg ON mg.movie_id = m.movie_id
        LEFT JOIN genres g        ON g.genre_id = mg.genre_id
        GROUP BY m.movie_id
        ORDER BY m.title
    """)
    print_table(["ID", "Назва", "Рік", "Хв", "Вік", "Жанри"], rows)


def add_movie():
    print("\n--- Додавання фільму ---")
    title = ask_str("Назва: ")
    description = ask_str("Опис (Enter - пропустити): ", required=False)
    duration = ask_int("Тривалість, хв: ", min_value=1, max_value=600)
    year = ask_int("Рік випуску: ", min_value=1881, max_value=2100)
    age = ask_int("Віковий рейтинг (0, 6, 12, 16, 18): ")
    show_genres()
    raw = input("ID жанрів через кому (Enter - пропустити): ").strip()
    genre_ids = [int(x) for x in raw.replace(" ", "").split(",") if x.isdigit()]

    # Фільм і його жанри додаються однією транзакцією: або все, або нічого
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO movies (title, description, duration_min, release_year, age_rating)
               VALUES (%s, %s, %s, %s, %s) RETURNING movie_id""",
            (title, description, duration, year, age),
        )
        movie_id = cur.fetchone()[0]
        for genre_id in genre_ids:
            cur.execute("INSERT INTO movie_genres (movie_id, genre_id) VALUES (%s, %s)",
                        (movie_id, genre_id))
    print(f"Фільм додано, ID = {movie_id}")


def update_movie():
    list_movies()
    movie_id = ask_int("\nID фільму для зміни: ")
    print("Залиште поле порожнім (Enter), щоб не змінювати його.")
    title = ask_str("Нова назва: ", required=False)
    duration = ask_int("Нова тривалість, хв: ", required=False, min_value=1, max_value=600)
    age = ask_int("Новий віковий рейтинг: ", required=False)
    changed = db.execute(
        """UPDATE movies
           SET title = COALESCE(%s, title),
               duration_min = COALESCE(%s, duration_min),
               age_rating = COALESCE(%s, age_rating)
           WHERE movie_id = %s""",
        (title, duration, age, movie_id),
    )
    print("Фільм оновлено." if changed else "Фільму з таким ID немає.")


def delete_movie():
    list_movies()
    movie_id = ask_int("\nID фільму для видалення: ")
    if not confirm(f"Видалити фільм ID {movie_id}?"):
        print("Скасовано.")
        return
    deleted = db.execute("DELETE FROM movies WHERE movie_id = %s", (movie_id,))
    print("Фільм видалено." if deleted else "Фільму з таким ID немає.")


# ---------------------------------------------------------------------
# Клієнти
# ---------------------------------------------------------------------
def list_customers():
    rows = db.fetch_all("""
        SELECT customer_id, last_name, first_name, email, COALESCE(phone, '-')
        FROM customers ORDER BY last_name, first_name
    """)
    print_table(["ID", "Прізвище", "Ім'я", "Email", "Телефон"], rows)


def add_customer():
    print("\n--- Додавання клієнта ---")
    first = ask_str("Ім'я: ")
    last = ask_str("Прізвище: ")
    email = ask_str("Email: ")
    phone = ask_str("Телефон, напр. +380501234567 (Enter - пропустити): ", required=False)
    row = db.fetch_one(
        """INSERT INTO customers (first_name, last_name, email, phone)
           VALUES (%s, %s, %s, %s) RETURNING customer_id""",
        (first, last, email, phone),
    )
    print(f"Клієнта додано, ID = {row[0]}")


def update_customer():
    list_customers()
    customer_id = ask_int("\nID клієнта для зміни: ")
    print("Залиште поле порожнім (Enter), щоб не змінювати його.")
    email = ask_str("Новий email: ", required=False)
    phone = ask_str("Новий телефон: ", required=False)
    changed = db.execute(
        """UPDATE customers
           SET email = COALESCE(%s, email), phone = COALESCE(%s, phone)
           WHERE customer_id = %s""",
        (email, phone, customer_id),
    )
    print("Клієнта оновлено." if changed else "Клієнта з таким ID немає.")


def delete_customer():
    list_customers()
    customer_id = ask_int("\nID клієнта для видалення: ")
    if not confirm(f"Видалити клієнта ID {customer_id}?"):
        print("Скасовано.")
        return
    deleted = db.execute("DELETE FROM customers WHERE customer_id = %s", (customer_id,))
    print("Клієнта видалено." if deleted else "Клієнта з таким ID немає.")


# ---------------------------------------------------------------------
# Сеанси
# ---------------------------------------------------------------------
def list_screenings():
    rows = db.fetch_all("""
        SELECT s.screening_id, to_char(s.start_time, 'YYYY-MM-DD HH24:MI'),
               m.title, h.name, s.base_price
        FROM screenings s
        JOIN movies m ON m.movie_id = s.movie_id
        JOIN halls  h ON h.hall_id  = s.hall_id
        WHERE s.start_time >= CURRENT_DATE
        ORDER BY s.start_time
    """)
    print_table(["ID", "Початок", "Фільм", "Зал", "Ціна"], rows)


def add_screening():
    print("\n--- Додавання сеансу ---")
    list_movies()
    movie_id = ask_int("ID фільму: ")
    rows = db.fetch_all("SELECT hall_id, name, hall_type FROM halls ORDER BY hall_id")
    print_table(["ID", "Зал", "Тип"], rows)
    hall_id = ask_int("ID залу: ")
    start = ask_datetime("Початок (РРРР-ММ-ДД ГГ:ХХ): ")
    price = ask_decimal("Базова ціна квитка: ")
    row = db.fetch_one(
        """INSERT INTO screenings (movie_id, hall_id, start_time, base_price)
           VALUES (%s, %s, %s, %s) RETURNING screening_id""",
        (movie_id, hall_id, start, price),
    )
    print(f"Сеанс додано, ID = {row[0]}")


def delete_screening():
    list_screenings()
    screening_id = ask_int("\nID сеансу для видалення: ")
    if not confirm(f"Видалити сеанс ID {screening_id}?"):
        print("Скасовано.")
        return
    deleted = db.execute("DELETE FROM screenings WHERE screening_id = %s", (screening_id,))
    print("Сеанс видалено." if deleted else "Сеансу з таким ID немає.")


def free_seats():
    list_screenings()
    screening_id = ask_int("\nID сеансу: ")
    rows = db.fetch_all("""
        SELECT st.row_number,
               string_agg(st.seat_number::text, ', ' ORDER BY st.seat_number)
        FROM screenings sc
        JOIN seats st ON st.hall_id = sc.hall_id
        WHERE sc.screening_id = %s
          AND NOT EXISTS (SELECT 1 FROM tickets t
                          WHERE t.screening_id = sc.screening_id
                            AND t.seat_id = st.seat_id AND t.status = 'sold')
        GROUP BY st.row_number
        ORDER BY st.row_number
    """, (screening_id,))
    print_table(["Ряд", "Вільні місця"], rows)


# ---------------------------------------------------------------------
# Квитки
# ---------------------------------------------------------------------
DISCOUNTS = {"1": ("Звичайний", Decimal("1.0")),
             "2": ("Дитячий (-50%)", Decimal("0.5")),
             "3": ("Студентський (-20%)", Decimal("0.8"))}


def sell_ticket():
    print("\n--- Продаж квитка ---")
    list_screenings()
    screening_id = ask_int("ID сеансу: ")
    row_number = ask_int("Ряд: ", min_value=1)
    seat_number = ask_int("Місце: ", min_value=1)
    list_customers()
    customer_id = ask_int("ID клієнта: ")
    print("Тип квитка: 1 - звичайний, 2 - дитячий, 3 - студентський")
    kind = ""
    while kind not in DISCOUNTS:
        kind = input("Оберіть (1-3): ").strip()
    coef = DISCOUNTS[kind][1]

    # Місце вибирається серед місць залу САМЕ ЦЬОГО сеансу, і лише для сеансу, що ще не почався
    row = db.fetch_one("""
        INSERT INTO tickets (screening_id, seat_id, customer_id, price)
        SELECT sc.screening_id, st.seat_id, %s, sc.base_price * %s
        FROM screenings sc
        JOIN seats st ON st.hall_id = sc.hall_id
        WHERE sc.screening_id = %s AND st.row_number = %s AND st.seat_number = %s
          AND sc.start_time > CURRENT_TIMESTAMP
        RETURNING ticket_id, price
    """, (customer_id, coef, screening_id, row_number, seat_number))
    if row:
        print(f"Квиток продано. Номер: {row[0]}, ціна: {row[1]} грн")
    else:
        print("Квиток не продано: сеансу немає, він уже почався, або такого місця немає в залі.")


def cancel_ticket():
    print("\n--- Скасування квитка ---")
    ticket_id = ask_int("Номер квитка: ")
    # Скасувати можна квиток, що ще діє, не пізніше ніж за годину до початку
    row = db.fetch_one("""
        UPDATE tickets t
        SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP
        FROM screenings s
        WHERE t.ticket_id = %s AND t.status = 'sold'
          AND s.screening_id = t.screening_id
          AND s.start_time > CURRENT_TIMESTAMP + INTERVAL '1 hour'
        RETURNING t.ticket_id
    """, (ticket_id,))
    if row:
        print("Квиток скасовано, місце знову вільне.")
    else:
        print("Не скасовано: квитка немає, він уже скасований, або до сеансу менше години.")


def customer_history():
    list_customers()
    customer_id = ask_int("\nID клієнта: ")
    rows = db.fetch_all("""
        SELECT t.ticket_id, m.title, h.name,
               to_char(s.start_time, 'YYYY-MM-DD HH24:MI'),
               st.row_number, st.seat_number, t.price, t.status
        FROM tickets t
        JOIN screenings s ON s.screening_id = t.screening_id
        JOIN movies m     ON m.movie_id = s.movie_id
        JOIN halls h      ON h.hall_id = s.hall_id
        JOIN seats st     ON st.seat_id = t.seat_id
        WHERE t.customer_id = %s
        ORDER BY s.start_time
    """, (customer_id,))
    print_table(["Квиток", "Фільм", "Зал", "Початок", "Ряд", "Місце", "Ціна", "Статус"], rows)


# ---------------------------------------------------------------------
# Звіти
# ---------------------------------------------------------------------
def report_today():
    rows = db.fetch_all("""
        SELECT to_char(s.start_time, 'HH24:MI'), m.title, h.name, h.hall_type, s.base_price
        FROM screenings s
        JOIN movies m ON m.movie_id = s.movie_id
        JOIN halls  h ON h.hall_id  = s.hall_id
        WHERE s.start_time::date = CURRENT_DATE
        ORDER BY s.start_time
    """)
    print_table(["Час", "Фільм", "Зал", "Тип", "Ціна"], rows)


def report_revenue():
    rows = db.fetch_all("""
        SELECT m.title, COUNT(t.ticket_id), COALESCE(SUM(t.price), 0)
        FROM movies m
        LEFT JOIN screenings s ON s.movie_id = m.movie_id
        LEFT JOIN tickets t    ON t.screening_id = s.screening_id AND t.status = 'sold'
        GROUP BY m.movie_id, m.title
        ORDER BY 3 DESC
    """)
    print_table(["Фільм", "Продано квитків", "Виручка, грн"], rows)


def report_occupancy():
    rows = db.fetch_all("""
        SELECT s.screening_id, m.title, h.name,
               to_char(s.start_time, 'YYYY-MM-DD HH24:MI'),
               COUNT(t.ticket_id), hs.total_seats,
               ROUND(100.0 * COUNT(t.ticket_id) / hs.total_seats, 1)
        FROM screenings s
        JOIN movies m ON m.movie_id = s.movie_id
        JOIN halls  h ON h.hall_id  = s.hall_id
        JOIN (SELECT hall_id, COUNT(*) AS total_seats FROM seats GROUP BY hall_id) hs
             ON hs.hall_id = s.hall_id
        LEFT JOIN tickets t ON t.screening_id = s.screening_id AND t.status = 'sold'
        GROUP BY s.screening_id, m.title, h.name, s.start_time, hs.total_seats
        ORDER BY s.start_time
    """)
    print_table(["Сеанс", "Фільм", "Зал", "Початок", "Продано", "Місць", "Заповн., %"], rows)


# ---------------------------------------------------------------------
# Меню
# ---------------------------------------------------------------------
def safe_call(action):
    """Виконує дію і не дає застосунку впасти через помилку бази."""
    try:
        action()
    except psycopg2.Error as e:
        print(db_error_message(e))


def run_menu(title, items):
    while True:
        print(f"\n=== {title} ===")
        for number, (label, _) in enumerate(items, 1):
            print(f"{number}. {label}")
        print("0. Назад")
        choice = input("Оберіть опцію: ").strip()
        if choice == "0":
            return
        if choice.isdigit() and 1 <= int(choice) <= len(items):
            safe_call(items[int(choice) - 1][1])
        else:
            print("Невірна опція, спробуйте ще раз.")


MOVIES_MENU = [("Список фільмів", list_movies), ("Додати фільм", add_movie),
               ("Змінити фільм", update_movie), ("Видалити фільм", delete_movie)]
CUSTOMERS_MENU = [("Список клієнтів", list_customers), ("Додати клієнта", add_customer),
                  ("Змінити клієнта", update_customer), ("Видалити клієнта", delete_customer)]
SCREENINGS_MENU = [("Розклад (від сьогодні)", list_screenings), ("Додати сеанс", add_screening),
                   ("Видалити сеанс", delete_screening), ("Вільні місця на сеанс", free_seats)]
TICKETS_MENU = [("Продати квиток", sell_ticket), ("Скасувати квиток", cancel_ticket),
                ("Історія покупок клієнта", customer_history)]
REPORTS_MENU = [("Розклад на сьогодні", report_today), ("Виручка по фільмах", report_revenue),
                ("Заповненість сеансів", report_occupancy)]
MAIN_MENU = [("Фільми", MOVIES_MENU), ("Клієнти", CUSTOMERS_MENU),
             ("Сеанси", SCREENINGS_MENU), ("Квитки", TICKETS_MENU), ("Звіти", REPORTS_MENU)]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        db.connect()
    except psycopg2.Error as e:
        print("Не вдалося підключитися до бази даних.")
        print("Перевірте, що контейнер запущено (docker compose ps) і параметри підключення.")
        print(f"Деталі: {str(e).strip()}")
        return
    print("Успішне підключення до бази даних.")

    try:
        while True:
            print("\n" + "=" * 40)
            print("   КІНОТЕАТР: УПРАВЛІННЯ БАЗОЮ ДАНИХ")
            print("=" * 40)
            for number, (label, _) in enumerate(MAIN_MENU, 1):
                print(f"{number}. {label}")
            print("0. Вихід")
            choice = input("Оберіть розділ: ").strip()
            if choice == "0":
                print("До побачення!")
                break
            if choice.isdigit() and 1 <= int(choice) <= len(MAIN_MENU):
                label, submenu = MAIN_MENU[int(choice) - 1]
                run_menu(label, submenu)
            else:
                print("Невірна опція, спробуйте ще раз.")
    except (KeyboardInterrupt, EOFError):
        print("\nЗавершення роботи.")
    finally:
        db.disconnect()


if __name__ == "__main__":
    main()