from datetime import datetime

from flask import Blueprint, jsonify, request

from ..auth_utils import ADMIN_ROLES, clean_text, current_user, json_error, login_required, request_json, roles_required
from ..db import dict_from_row, get_db
from ..services.notifications import create_notification


bp = Blueprint("appointments", __name__, url_prefix="/api/appointments")
APPOINTMENT_STATUSES = {"Pending", "Approved", "Rescheduled", "Cancelled", "Completed"}


def current_donor_profile(db, user_id: int) -> dict | None:
    return dict_from_row(db.execute("SELECT * FROM donor_profiles WHERE user_id = ?", (user_id,)).fetchone())


@bp.get("")
@login_required
def list_appointments():
    user = current_user()
    status = clean_text(request.args.get("status", ""), 30)
    db = get_db()
    conditions = []
    params = []
    if user["role"] not in ADMIN_ROLES:
        donor = current_donor_profile(db, user["id"])
        if not donor:
            return jsonify({"items": []})
        conditions.append("appointments.donor_id = ?")
        params.append(donor["id"])
    if status:
        conditions.append("appointments.status = ?")
        params.append(status)
    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = db.execute(
        f"""
        SELECT appointments.*, users.name AS donor_name, users.email AS donor_email, users.phone AS donor_phone,
               donor_profiles.blood_group
        FROM appointments
        JOIN donor_profiles ON donor_profiles.id = appointments.donor_id
        JOIN users ON users.id = donor_profiles.user_id
        {where_sql}
        ORDER BY appointment_at ASC
        """,
        params,
    ).fetchall()
    return jsonify({"items": [dict(row) for row in rows]})


@bp.post("")
@roles_required("donor")
def create_appointment():
    user = current_user()
    data = request_json()
    if not data.get("center") or not data.get("appointment_at"):
        return json_error("Center and appointment date/time are required.", 422)

    db = get_db()
    donor = current_donor_profile(db, user["id"])
    if not donor:
        return json_error("Create a donor profile before booking an appointment.", 422)

    now = datetime.utcnow().isoformat(timespec="seconds")
    cursor = db.execute(
        """
        INSERT INTO appointments (donor_id, center, appointment_at, status, admin_notes, created_at, updated_at)
        VALUES (?, ?, ?, 'Pending', ?, ?, ?)
        """,
        (
            donor["id"],
            clean_text(data["center"], 160),
            clean_text(data["appointment_at"], 40),
            clean_text(data.get("notes"), 500),
            now,
            now,
        ),
    )
    appointment_id = int(cursor.lastrowid)
    db.execute(
        """
        INSERT INTO audit_logs (actor_id, action, entity_type, entity_id, details, created_at)
        VALUES (?, 'appointment_booked', 'appointment', ?, 'Donor booked appointment.', ?)
        """,
        (user["id"], appointment_id, now),
    )
    db.commit()
    return jsonify({"message": "Appointment requested.", "appointment_id": appointment_id}), 201


@bp.patch("/<int:appointment_id>/status")
@roles_required("blood_bank_admin")
def update_appointment_status(appointment_id: int):
    user = current_user()
    data = request_json()
    status = clean_text(data.get("status"), 30).title()
    if status not in APPOINTMENT_STATUSES:
        return json_error("Unsupported appointment status.", 422)

    db = get_db()
    appointment = dict_from_row(
        db.execute(
            """
            SELECT appointments.*, donor_profiles.user_id
            FROM appointments
            JOIN donor_profiles ON donor_profiles.id = appointments.donor_id
            WHERE appointments.id = ?
            """,
            (appointment_id,),
        ).fetchone()
    )
    if not appointment:
        return json_error("Appointment not found.", 404)

    appointment_at = clean_text(data.get("appointment_at") or appointment["appointment_at"], 40)
    notes = clean_text(data.get("admin_notes"), 500)
    now = datetime.utcnow().isoformat(timespec="seconds")
    db.execute(
        """
        UPDATE appointments
        SET status = ?, appointment_at = ?, admin_notes = ?, updated_at = ?
        WHERE id = ?
        """,
        (status, appointment_at, notes, now, appointment_id),
    )
    db.execute(
        """
        INSERT INTO audit_logs (actor_id, action, entity_type, entity_id, details, created_at)
        VALUES (?, 'appointment_status_changed', 'appointment', ?, ?, ?)
        """,
        (user["id"], appointment_id, f"Appointment set to {status}.", now),
    )
    create_notification(
        db,
        appointment["user_id"],
        f"Appointment {status}",
        f"Your appointment at {appointment['center']} is {status}.",
        "info",
        "in_app",
        "appointment",
        appointment_id,
    )
    db.commit()
    return jsonify({"message": f"Appointment {status.lower()}."})

