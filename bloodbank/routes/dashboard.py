import json
import time

from flask import Blueprint, Response, current_app, jsonify, stream_with_context

from ..auth_utils import current_user, login_required
from ..db import get_db
from ..services.analytics import dashboard_overview
from ..services.notifications import notification_providers


bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


def public_snapshot(db) -> dict:
    overview = dashboard_overview(db)
    critical = [
        dict(row)
        for row in db.execute(
            """
            SELECT id, patient_name, blood_group, units_required, hospital_name, city, urgency, required_at, status
            FROM blood_requests
            WHERE urgency = 'Critical' AND status IN ('Pending', 'Matched')
            ORDER BY required_at ASC
            LIMIT 8
            """
        ).fetchall()
    ]
    return {
        "counts": overview["counts"],
        "inventory": overview["inventory"],
        "low_stock": overview["low_stock"],
        "critical_requests": critical,
        "providers": notification_providers(),
    }


@bp.get("/public")
def public_overview():
    return jsonify(public_snapshot(get_db()))


@bp.get("/overview")
@login_required
def overview():
    db = get_db()
    user = current_user()
    payload = dashboard_overview(db)
    payload["current_user_role"] = user["role"]
    payload["providers"] = notification_providers()
    payload["critical_requests"] = [
        dict(row)
        for row in db.execute(
            """
            SELECT *
            FROM blood_requests
            WHERE urgency = 'Critical' AND status IN ('Pending', 'Matched')
            ORDER BY required_at ASC
            """
        ).fetchall()
    ]
    payload["recent_activity"] = [
        dict(row)
        for row in db.execute(
            """
            SELECT audit_logs.*, users.name AS actor_name
            FROM audit_logs
            LEFT JOIN users ON users.id = audit_logs.actor_id
            ORDER BY audit_logs.created_at DESC
            LIMIT 12
            """
        ).fetchall()
    ]
    return jsonify(payload)


@bp.get("/events")
def events():
    interval = max(2, int(current_app.config.get("SSE_INTERVAL_SECONDS", 5)))

    @stream_with_context
    def generate():
        while True:
            snapshot = public_snapshot(get_db())
            yield f"event: dashboard\ndata: {json.dumps(snapshot)}\n\n"
            time.sleep(interval)

    return Response(generate(), mimetype="text/event-stream")

