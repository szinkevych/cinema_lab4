"""Робота з PostgreSQL у вебзастосунку.

Для кожного HTTP-запиту відкривається власне з'єднання (зберігається у flask.g)
і закривається після відповіді. Так різні запити не заважають одне одному.
"""
import os
from contextlib import contextmanager

import psycopg2
from flask import g, has_request_context
from psycopg2 import errors
from psycopg2.extras import RealDictCursor

# Параметри підключення. Порт 5434 - якщо ви змінювали його в docker-compose.yml.
# Якщо у вас стандартний порт, змініть DEFAULT_PORT на 5432 або задайте змінну DB_PORT.
DEFAULT_PORT = "5434"

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", DEFAULT_PORT)),
    "dbname": os.getenv("DB_NAME", "cinema"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "connect_timeout": 5,
}


def get_db():
    """Повертає з'єднання для поточного запиту (створює, якщо його ще немає)."""
    if "db" not in g:
        g.db = psycopg2.connect(cursor_factory=RealDictCursor, **DB_CONFIG)
        g.db.set_client_encoding("UTF8")
    return g.db


def close_db(exception=None):
    """Закриває з'єднання після завершення запиту."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _apply_context(cur, app_user=None):
    """Передає базі, хто виконує операцію (змінні діють лише в поточній транзакції).

    app.user_id      - номер користувача, його записують тригери журналу дій;
    app.current_user - ім'я, його записує тригер аудиту квитків.
    """
    if not has_request_context():
        return
    user = g.get("user")
    if user:
        cur.execute("SELECT set_config('app.user_id', %s, true)", (str(user["user_id"]),))
    name = app_user or (user["username"] if user else None)
    if name:
        cur.execute("SELECT set_config('app.current_user', %s, true)", (name,))


def query_all(sql, params=None):
    """SELECT: повертає список рядків. Кожен рядок - словник {стовпець: значення}."""
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def query_one(sql, params=None):
    """SELECT: повертає один рядок (словник) або None."""
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute(sql, params=None, returning=False):
    """INSERT/UPDATE/DELETE у транзакції.

    Успіх -> commit, помилка -> rollback і повторний виклик винятку.
    Якщо returning=True, повертає перший рядок з RETURNING; інакше кількість змінених рядків.
    """
    conn = get_db()
    try:
        with conn.cursor() as cur:
            _apply_context(cur)
            cur.execute(sql, params)
            result = cur.fetchone() if returning else cur.rowcount
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise


@contextmanager
def transaction(app_user=None):
    """Кілька команд в одній транзакції: або виконаються всі, або жодна.

        with transaction() as cur:
            cur.execute("INSERT ...")
            cur.execute("INSERT ...")

    Користувач із сесії автоматично передається в базу (див. _apply_context), тож
    тригери журналу й аудиту знають, хто виконав операцію. app_user дозволяє підмінити ім'я.
    """
    conn = get_db()
    cur = conn.cursor()
    try:
        _apply_context(cur, app_user)
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def log_action(action, table_name=None, record_id=None, details=None, user_id=None):
    """Записує подію (вхід, вихід, реєстрація...) через функцію бази log_activity.

    Збій журналу не повинен ламати основну дію, тому помилки тут гасяться.
    """
    if user_id is None and has_request_context() and g.get("user"):
        user_id = g.user["user_id"]
    try:
        execute("SELECT log_activity(%s, %s, %s, %s, %s)",
                (user_id, action, table_name, record_id, details))
    except psycopg2.Error:
        pass


def db_error_message(e):
    """Перекладає помилку бази на зрозумілий текст для користувача."""
    if isinstance(e, errors.RaiseException):
        # Наші власні повідомлення з процедур і тригерів (RAISE EXCEPTION)
        return e.diag.message_primary or str(e)
    if isinstance(e, errors.UniqueViolation):
        return "Такий запис уже існує (порушено унікальність)."
    if isinstance(e, errors.ForeignKeyViolation):
        return ("Операція неможлива: запис пов'язаний з іншими даними, "
                "або посилається на неіснуючий запис.")
    if isinstance(e, errors.CheckViolation):
        return "Значення не відповідає обмеженням бази даних."
    if isinstance(e, errors.NotNullViolation):
        return "Не заповнено обов'язкове поле."
    return "Помилка бази даних. Спробуйте ще раз."