from flask import Blueprint, jsonify

from ..auth_utils import current_user, json_error, login_required
from ..db import get_db


bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@bp.get("")
@login_required
def list_notifications():
    user = current_user()
    rows = get_db().execute(
        """
        SELECT *
        FROM notifications
        WHERE user_id = ? OR user_id IS NULL
        ORDER BY created_at DESC
        LIMIT 40
        """,
        (user["id"],),
    ).fetchall()
    return jsonify({"items": [dict(row) for row in rows]})


@bp.patch("/<int:notification_id>/read")
@login_required
def mark_read(notification_id: int):
    user = current_user()
    db = get_db()
    cursor = db.execute(
        """
        UPDATE notifications
        SET is_read = 1
        WHERE id = ? AND (user_id = ? OR user_id IS NULL)
        """,
        (notification_id, user["id"]),
    )
    db.commit()
    if cursor.rowcount == 0:
        return json_error("Notification not found.", 404)
    return jsonify({"message": "Notification marked as read."})

