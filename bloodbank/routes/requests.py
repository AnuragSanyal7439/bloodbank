from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from ..auth_utils import ADMIN_ROLES, clean_text, current_user, json_error, login_required, request_json, roles_required
from ..db import dict_from_row, get_db
from ..services.compatibility import normalize_blood_group
from ..services.inventory import fulfill_reserved_units, release_reserved_units, reserve_units
from ..services.matching import find_matching_donors, persist_matches
from ..services.notifications import create_notification, queue_external_notification
from ..services.request_status import next_status_for_action, validate_status_transition


bp = Blueprint("requests", __name__, url_prefix="/api/requests")
URGENCY_ORDER = "CASE urgency WHEN 'Critical' THEN 1 WHEN 'Urgent' THEN 2 ELSE 3 END"


def serialize_request(row) -> dict:
    return dict(row)


def fetch_request(db, request_id: int) -> dict | None:
    return dict_from_row(
        db.execute(
            """
            SELECT blood_requests.*, users.name AS requester_name, users.role AS requester_role
            FROM blood_requests
            JOIN users ON users.id = blood_requests.requester_id
            WHERE blood_requests.id = ?
            """,
            (request_id,),
        ).fetchone()
    )


@bp.get("")
@login_required
def list_requests():
    user = current_user()
    status = clean_text(request.args.get("status", ""), 30)
    urgency = clean_text(request.args.get("urgency", ""), 30)
    blood_group = clean_text(request.args.get("blood_group", ""), 5)
    city = clean_text(request.args.get("city", ""), 80)
    sort = clean_text(request.args.get("sort", "newest"), 30)
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(50, max(5, int(request.args.get("per_page", 12))))

    conditions = []
    params = []
    if user["role"] not in ADMIN_ROLES and user["role"] != "hospital":
        conditions.append("blood_requests.requester_id = ?")
        params.append(user["id"])
    if status:
        conditions.append("blood_requests.status = ?")
        params.append(status)
    if urgency:
        conditions.append("blood_requests.urgency = ?")
        params.append(urgency)
    if blood_group:
        conditions.append("blood_requests.blood_group = ?")
        params.append(blood_group)
    if city:
        conditions.append("blood_requests.city = ?")
        params.append(city)

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    order_by = {
        "urgency": f"{URGENCY_ORDER}, required_at ASC",
        "location": "city ASC, created_at DESC",
        "status": "status ASC, created_at DESC",
        "newest": "created_at DESC",
    }.get(sort, "created_at DESC")

    db = get_db()
    total = db.execute(f"SELECT COUNT(*) AS count FROM blood_requests {where_sql}", params).fetchone()["count"]
    rows = db.execute(
        f"""
        SELECT blood_requests.*, users.name AS requester_name, users.role AS requester_role
        FROM blood_requests
        JOIN users ON users.id = blood_requests.requester_id
        {where_sql}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
        """,
        (*params, per_page, (page - 1) * per_page),
    ).fetchall()
    return jsonify(
        {
            "items": [serialize_request(row) for row in rows],
            "pagination": {"page": page, "per_page": per_page, "total": total},
        }
    )


@bp.post("")
@roles_required("recipient", "hospital", "blood_bank_admin")
def create_request():
    user = current_user()
    data = request_json()
    required = ["patient_name", "blood_group", "units_required", "hospital_name", "city", "urgency", "required_at", "contact_details"]
    missing = [field for field in required if data.get(field) in (None, "")]
    if missing:
        return json_error("Please complete all required request fields.", 422, {field: "Required" for field in missing})

    try:
        blood_group = normalize_blood_group(data["blood_group"])
        units_required = int(data["units_required"])
        if units_required <= 0:
            raise ValueError("Units required must be greater than zero")
    except (TypeError, ValueError) as exc:
        return json_error(str(exc), 422)

    urgency = clean_text(data["urgency"], 30).title()
    if urgency not in {"Normal", "Urgent", "Critical"}:
        return json_error("Urgency must be Normal, Urgent, or Critical.", 422)

    now = datetime.utcnow().isoformat(timespec="seconds")
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO blood_requests
            (requester_id, patient_name, blood_group, units_required, hospital_name, city,
             urgency, required_at, contact_details, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?)
        """,
        (
            user["id"],
            clean_text(data["patient_name"], 120),
            blood_group,
            units_required,
            clean_text(data["hospital_name"], 160),
            clean_text(data["city"], 80),
            urgency,
            clean_text(data["required_at"], 40),
            clean_text(data["contact_details"], 180),
            now,
            now,
        ),
    )
    request_id = int(cursor.lastrowid)
    created = fetch_request(db, request_id)
    matches = find_matching_donors(db, created, current_app.config["DONATION_COOLDOWN_DAYS"])
    persist_matches(db, request_id, matches)

    if urgency == "Critical":
        create_notification(
            db,
            None,
            f"Critical {blood_group} blood request",
            f"{units_required} unit(s) needed at {created['hospital_name']} in {created['city']}.",
            "critical",
            "in_app",
            "blood_request",
            request_id,
        )
        queue_external_notification(
            "email",
            "configured-admin-list",
            {"request_id": request_id, "urgency": urgency, "blood_group": blood_group},
        )

    db.execute(
        """
        INSERT INTO audit_logs (actor_id, action, entity_type, entity_id, details, created_at)
        VALUES (?, 'created_blood_request', 'blood_request', ?, ?, ?)
        """,
        (user["id"], request_id, f"{urgency} request for {units_required} unit(s) of {blood_group}.", now),
    )
    db.commit()
    return jsonify({"request": created, "matches": matches[:8], "message": "Blood request created."}), 201


@bp.get("/<int:request_id>/matches")
@login_required
def request_matches(request_id: int):
    db = get_db()
    blood_request = fetch_request(db, request_id)
    if not blood_request:
        return json_error("Request not found.", 404)

    rows = db.execute(
        """
        SELECT request_matches.score, request_matches.reason, request_matches.created_at AS matched_at,
               donor_profiles.*, users.name, users.email, users.phone, users.city
        FROM request_matches
        JOIN donor_profiles ON donor_profiles.id = request_matches.donor_id
        JOIN users ON users.id = donor_profiles.user_id
        WHERE request_matches.request_id = ?
        ORDER BY request_matches.score DESC
        """,
        (request_id,),
    ).fetchall()
    if rows:
        return jsonify({"request": blood_request, "matches": [dict(row) for row in rows]})

    matches = find_matching_donors(db, blood_request, current_app.config["DONATION_COOLDOWN_DAYS"])
    persist_matches(db, request_id, matches)
    db.commit()
    return jsonify({"request": blood_request, "matches": matches})


@bp.patch("/<int:request_id>/status")
@roles_required("blood_bank_admin")
def update_request_status(request_id: int):
    user = current_user()
    data = request_json()
    action = clean_text(data.get("action"), 30)
    admin_notes = clean_text(data.get("admin_notes"), 500)

    db = get_db()
    blood_request = fetch_request(db, request_id)
    if not blood_request:
        return json_error("Request not found.", 404)

    try:
        target_status = next_status_for_action(action)
        validate_status_transition(blood_request["status"], target_status)
        inventory = dict_from_row(db.execute("SELECT * FROM blood_inventory WHERE blood_group = ?", (blood_request["blood_group"],)).fetchone())
        units = int(blood_request["units_required"])
        if target_status == "Matched":
            inventory = reserve_units(inventory, units)
        elif target_status == "Fulfilled":
            inventory = fulfill_reserved_units(inventory, units)
        elif target_status == "Cancelled" and blood_request["status"] == "Matched":
            inventory = release_reserved_units(inventory, units)
    except ValueError as exc:
        return json_error(str(exc), 422)

    now = datetime.utcnow().isoformat(timespec="seconds")
    db.execute(
        """
        UPDATE blood_inventory
        SET available_units = ?, reserved_units = ?, expired_units = ?, last_updated_at = ?
        WHERE blood_group = ?
        """,
        (
            inventory["available_units"],
            inventory["reserved_units"],
            inventory["expired_units"],
            now,
            blood_request["blood_group"],
        ),
    )
    db.execute(
        """
        UPDATE blood_requests
        SET status = ?, admin_notes = ?, updated_at = ?
        WHERE id = ?
        """,
        (target_status, admin_notes, now, request_id),
    )
    db.execute(
        """
        INSERT INTO audit_logs (actor_id, action, entity_type, entity_id, details, created_at)
        VALUES (?, ?, 'blood_request', ?, ?, ?)
        """,
        (user["id"], f"request_{target_status.lower()}", request_id, admin_notes or f"Request moved to {target_status}.", now),
    )
    create_notification(
        db,
        blood_request["requester_id"],
        f"Request {target_status}",
        f"Your {blood_request['blood_group']} request for {blood_request['patient_name']} is now {target_status}.",
        "success" if target_status == "Fulfilled" else "info",
        "in_app",
        "blood_request",
        request_id,
    )
    db.commit()
    return jsonify({"request": fetch_request(db, request_id), "message": f"Request {target_status.lower()}."})
