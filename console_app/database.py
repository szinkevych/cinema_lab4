"""Підключення до PostgreSQL. Параметри можна змінити через змінні середовища."""
import os
from contextlib import contextmanager

import psycopg2


class Database:
    def __init__(self):
        self.params = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", "5434")),
            "dbname": os.getenv("DB_NAME", "cinema"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "password"),
            "connect_timeout": 5,
        }
        self.conn = None

    def connect(self):
        """Підключається до БД. Якщо не вдалось, кидає виняток psycopg2.OperationalError."""
        self.conn = psycopg2.connect(**self.params)
        self.conn.set_client_encoding("UTF8")

    def disconnect(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    @contextmanager
    def cursor(self):
        """Курсор з транзакцією: успіх -> commit, помилка -> rollback."""
        cur = self.conn.cursor()
        try:
            yield cur
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        finally:
            cur.close()

    def fetch_all(self, sql, params=None):
        with self.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def fetch_one(self, sql, params=None):
        with self.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    def execute(self, sql, params=None):
        """Виконує INSERT/UPDATE/DELETE, повертає кількість змінених рядків."""
        with self.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount