"""Перевірка даних форм на стороні сервера.

Кожна функція читає поле з форми, перевіряє його і, якщо щось не так,
записує текст помилки в словник errors[ім'я_поля]. Повертає очищене значення або None.
Перевірки в HTML (required, min, max) - лише зручність для користувача,
їх можна обійти, тому остаточна перевірка завжди тут.
"""


def get_text(form, name, label, errors, required=True, max_len=None):
    value = (form.get(name) or "").strip()
    if not value:
        if required:
            errors[name] = f"Поле «{label}» обов'язкове."
        return None
    if max_len and len(value) > max_len:
        errors[name] = f"Поле «{label}» не може бути довшим за {max_len} символів."
        return None
    return value


def get_int(form, name, label, errors, min_value=None, max_value=None, required=True):
    raw = (form.get(name) or "").strip()
    if not raw:
        if required:
            errors[name] = f"Поле «{label}» обов'язкове."
        return None
    try:
        number = int(raw)
    except ValueError:
        errors[name] = f"Поле «{label}» має бути цілим числом."
        return None
    if min_value is not None and number < min_value:
        errors[name] = f"Поле «{label}» не може бути менше {min_value}."
        return None
    if max_value is not None and number > max_value:
        errors[name] = f"Поле «{label}» не може бути більше {max_value}."
        return None
    return number


def get_choice(form, name, label, errors, allowed, cast=str):
    """Значення має бути одним із allowed (після приведення типу cast)."""
    raw = (form.get(name) or "").strip()
    try:
        value = cast(raw)
    except (TypeError, ValueError):
        value = None
    if value not in allowed:
        errors[name] = f"Оберіть коректне значення поля «{label}»."
        return None
    return value


# ---------------------------------------------------------------------
# Додаткові перевірки: email, телефон, гроші, дата й час
# ---------------------------------------------------------------------
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9]{10,15}$")


def get_email(form, name, label, errors, required=True, max_len=100):
    value = (form.get(name) or "").strip().lower()
    if not value:
        if required:
            errors[name] = f"Поле «{label}» обов'язкове."
        return None
    if len(value) > max_len or not EMAIL_RE.match(value):
        errors[name] = "Введіть коректну адресу електронної пошти, наприклад name@example.com."
        return None
    return value


def get_phone(form, name, label, errors, required=False):
    """Пробіли, дефіси й дужки прибираються: '+380 (50) 123-45-67' -> '+380501234567'."""
    raw = (form.get(name) or "").strip()
    if not raw:
        if required:
            errors[name] = f"Поле «{label}» обов'язкове."
        return None
    cleaned = re.sub(r"[\s\-()]", "", raw)
    if not PHONE_RE.match(cleaned):
        errors[name] = "Телефон у форматі +380501234567 (від 10 до 15 цифр)."
        return None
    return cleaned


def get_decimal(form, name, label, errors, min_value=0, max_value=None, required=True):
    raw = (form.get(name) or "").strip().replace(",", ".")
    if not raw:
        if required:
            errors[name] = f"Поле «{label}» обов'язкове."
        return None
    try:
        number = Decimal(raw)
    except InvalidOperation:
        number = None
    if number is None or not number.is_finite():
        errors[name] = f"Поле «{label}» має бути числом, наприклад 150 або 150.50."
        return None
    if number.as_tuple().exponent < -2:
        errors[name] = f"Поле «{label}»: не більше двох знаків після коми."
        return None
    if min_value is not None and number < min_value:
        errors[name] = f"Поле «{label}» не може бути менше {min_value}."
        return None
    if max_value is not None and number > max_value:
        errors[name] = f"Поле «{label}» не може бути більше {max_value}."
        return None
    return number


def get_datetime(form, name, label, errors, required=True):
    """Приймає значення поля datetime-local (2026-10-25T18:30) або '2026-10-25 18:30'."""
    raw = (form.get(name) or "").strip()
    if not raw:
        if required:
            errors[name] = f"Поле «{label}» обов'язкове."
        return None
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    errors[name] = f"Поле «{label}»: вкажіть дату й час, наприклад 2026-10-25 18:30."
    return None


def get_date(form, name, label, errors, required=True):
    """Дата у форматі РРРР-ММ-ДД (так її надсилає поле type="date")."""
    raw = (form.get(name) or "").strip()
    if not raw:
        if required:
            errors[name] = f"Поле «{label}» обов'язкове."
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        errors[name] = f"Поле «{label}»: вкажіть дату у форматі РРРР-ММ-ДД."
        return None