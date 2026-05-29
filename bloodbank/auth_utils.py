from functools import wraps
import re

from flask import jsonify, request, session
from werkzeug.security import check_password_hash

from .db import dict_from_row, get_db


VALID_ROLES = {"donor", "recipient", "hospital", "blood_bank_admin", "super_admin"}
ADMIN_ROLES = {"blood_bank_admin", "super_admin"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def current_user() -> dict | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    row = get_db().execute("SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,)).fetchone()
    return dict_from_row(row)


def authenticate(email: str, password: str) -> dict | None:
    user = dict_from_row(
        get_db().execute("SELECT * FROM users WHERE email = ? AND is_active = 1", (email.strip(),)).fetchone()
    )
    if user and check_password_hash(user["password_hash"], password):
        return user
    return None


def json_error(message: str, status: int = 400, details: dict | None = None):
    payload = {"error": message}
    if details:
        payload["details"] = details
    return jsonify(payload), status


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return json_error("Authentication required", 401)
        return view(*args, **kwargs)

    return wrapped


def roles_required(*roles: str):
    allowed = set(roles)

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                return json_error("Authentication required", 401)
            if user["role"] == "super_admin" or user["role"] in allowed:
                return view(*args, **kwargs)
            return json_error("You do not have permission to perform this action", 403)

        return wrapped

    return decorator


def request_json() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def clean_text(value, max_length: int = 255) -> str:
    cleaned = str(value or "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:max_length]


def validate_required(data: dict, required: list[str]) -> dict:
    errors = {}
    for field in required:
        if data.get(field) in (None, ""):
            errors[field] = "This field is required."
    return errors


def validate_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email or ""))

