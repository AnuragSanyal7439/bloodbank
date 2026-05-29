from datetime import datetime

from flask import Blueprint, jsonify

from ..auth_utils import clean_text, current_user, json_error, request_json, roles_required
from ..db import dict_from_row, get_db


bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@bp.get("/users")
@roles_required("blood_bank_admin")
def list_users():
    rows = get_db().execute(
        """
        SELECT id, name, email, role, phone, city, is_active, created_at, last_login_at
        FROM users
        ORDER BY created_at DESC
        """
    ).fetchall()
    return jsonify({"items": [dict(row) for row in rows]})


@bp.patch("/users/<int:user_id>")
@roles_required("super_admin")
def update_user(user_id: int):
    actor = current_user()
    data = request_json()
    db = get_db()
    user = dict_from_row(db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())
    if not user:
        return json_error("User not found.", 404)

    is_active = 1 if data.get("is_active", user["is_active"]) in (1, True, "1", "true", "True") else 0
    role = clean_text(data.get("role") or user["role"], 40)
    if role not in {"donor", "recipient", "hospital", "blood_bank_admin", "super_admin"}:
        return json_error("Invalid role.", 422)

    now = datetime.utcnow().isoformat(timespec="seconds")
    db.execute("UPDATE users SET is_active = ?, role = ? WHERE id = ?", (is_active, role, user_id))
    db.execute(
        """
        INSERT INTO audit_logs (actor_id, action, entity_type, entity_id, details, created_at)
        VALUES (?, 'user_management_updated', 'user', ?, ?, ?)
        """,
        (actor["id"], user_id, f"Role set to {role}, active={bool(is_active)}.", now),
    )
    db.commit()
    return jsonify({"message": "User updated."})


@bp.get("/audit-logs")
@roles_required("blood_bank_admin")
def audit_logs():
    rows = get_db().execute(
        """
        SELECT audit_logs.*, users.name AS actor_name
        FROM audit_logs
        LEFT JOIN users ON users.id = audit_logs.actor_id
        ORDER BY audit_logs.created_at DESC
        LIMIT 100
        """
    ).fetchall()
    return jsonify({"items": [dict(row) for row in rows]})

