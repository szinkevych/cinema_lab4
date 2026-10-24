"""Допоміжні засоби автентифікації та розмежування прав доступу."""
from functools import wraps

from flask import abort, g, redirect, request, url_for

STAFF = ("admin", "cashier")          # співробітники
ROLE_LABELS = {"admin": "адміністратор", "cashier": "касир", "customer": "глядач"}


def safe_next(url):
    """Дозволяє перенаправлення лише на адреси всередині сайту (захист від open redirect)."""
    if url and url.startswith("/") and not url.startswith("//") and "\\" not in url:
        return url
    return None


def roles_required(*roles):
    """Декоратор: сторінка доступна лише вказаним ролям. Інші отримують 403."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = g.get("user")
            if user is None:
                return redirect(url_for("auth.login", next=request.path))
            if user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapper
    return decorator