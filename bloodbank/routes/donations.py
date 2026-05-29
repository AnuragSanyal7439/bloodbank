from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify

from ..auth_utils import ADMIN_ROLES, clean_text, current_user, json_error, login_required, request_json, roles_required
from ..db import dict_from_row, get_db
from ..services.eligibility import donor_eligibility
from ..services.notifications import create_notification


bp = Blueprint("donations", __name__, url_prefix="/api/donations")


@bp.get("")
@login_required
def list_donations():
    user = current_user()
    db = get_db()
    params = []
    where_sql = ""
    if user["role"] not in ADMIN_ROLES:
        donor = dict_from_row(db.execute("SELECT id FROM donor_profiles WHERE user_id = ?", (user["id"],)).fetchone())
        if not donor:
            return jsonify({"items": []})
        where_sql = "WHERE blood_donations.donor_id = ?"
        params.append(donor["id"])

    rows = db.execute(
        f"""
        SELECT blood_donations.*, users.name AS donor_name, users.phone AS donor_phone, users.city AS donor_city
        FROM blood_donations
        JOIN donor_profiles ON donor_profiles.id = blood_donations.donor_id
        JOIN users ON users.id = donor_profiles.user_id
        {where_sql}
        ORDER BY donation_date DESC
        """,
        params,
    ).fetchall()
    return jsonify({"items": [dict(row) for row in rows]})


@bp.post("")
@roles_required("donor")
def create_donation():
    user = current_user()
    data = request_json()
    db = get_db()
    donor = dict_from_row(db.execute("SELECT * FROM donor_profiles WHERE user_id = ?", (user["id"],)).fetchone())
    if not donor:
        return json_error("Donor profile not found.", 404)

    eligibility = donor_eligibility(donor["last_donation_date"], donor["age"], donor["availability_status"])
    if not eligibility["eligible"]:
        return json_error(eligibility["reason"], 422)

    center = clean_text(data.get("center"), 160)
    donation_date = clean_text(data.get("donation_date") or date.today().isoformat(), 20)
    if not center:
        return json_error("Donation center is required.", 422)

    now = datetime.utcnow().isoformat(timespec="seconds")
    cursor = db.execute(
        """
        INSERT INTO blood_donations (donor_id, blood_group, units, donation_date, center, status, notes, created_at)
        VALUES (?, ?, 1, ?, ?, 'Pending', ?, ?)
        """,
        (donor["id"], donor["blood_group"], donation_date, center, clean_text(data.get("notes"), 500), now),
    )
    donation_id = int(cursor.lastrowid)
    db.execute(
        """
        INSERT INTO audit_logs (actor_id, action, entity_type, entity_id, details, created_at)
        VALUES (?, 'donation_submitted', 'blood_donation', ?, 'Donor submitted donation for verification.', ?)
        """,
        (user["id"], donation_id, now),
    )
    db.commit()
    return jsonify({"message": "Donation submitted for admin verification.", "donation_id": donation_id}), 201


@bp.patch("/<int:donation_id>/verify")
@roles_required("blood_bank_admin")
def verify_donation(donation_id: int):
    user = current_user()
    data = request_json()
    status = clean_text(data.get("status", "Accepted"), 20).title()
    if status not in {"Accepted", "Rejected"}:
        return json_error("Donation status must be Accepted or Rejected.", 422)

    db = get_db()
    donation = dict_from_row(
        db.execute(
            """
            SELECT blood_donations.*, donor_profiles.user_id
            FROM blood_donations
            JOIN donor_profiles ON donor_profiles.id = blood_donations.donor_id
            WHERE blood_donations.id = ?
            """,
            (donation_id,),
        ).fetchone()
    )
    if not donation:
        return json_error("Donation not found.", 404)
    if donation["status"] != "Pending":
        return json_error("Only pending donations can be verified.", 422)

    now = datetime.utcnow().isoformat(timespec="seconds")
    db.execute(
        """
        UPDATE blood_donations
        SET status = ?, verified_by = ?, verified_at = ?, notes = ?
        WHERE id = ?
        """,
        (status, user["id"], now, clean_text(data.get("notes"), 500), donation_id),
    )

    if status == "Accepted":
        db.execute(
            """
            UPDATE blood_inventory
            SET available_units = available_units + ?, last_updated_at = ?
            WHERE blood_group = ?
            """,
            (int(donation["units"]), now, donation["blood_group"]),
        )
        db.execute(
            "UPDATE donor_profiles SET last_donation_date = ?, updated_at = ? WHERE id = ?",
            (donation["donation_date"], now, donation["donor_id"]),
        )
        collection = date.fromisoformat(donation["donation_date"][:10])
        for _ in range(int(donation["units"])):
            db.execute(
                """
                INSERT INTO blood_units (donation_id, donor_id, blood_group, collection_date, expiry_date, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'available', ?)
                """,
                (
                    donation_id,
                    donation["donor_id"],
                    donation["blood_group"],
                    collection.isoformat(),
                    (collection + timedelta(days=42)).isoformat(),
                    now,
                ),
            )

    db.execute(
        """
        INSERT INTO audit_logs (actor_id, action, entity_type, entity_id, details, created_at)
        VALUES (?, 'donor_verified', 'blood_donation', ?, ?, ?)
        """,
        (user["id"], donation_id, f"Donation {status.lower()}.", now),
    )
    create_notification(
        db,
        donation["user_id"],
        f"Donation {status}",
        "Thank you. Your donation has been accepted into inventory." if status == "Accepted" else "Your donation could not be accepted this time.",
        "success" if status == "Accepted" else "warning",
        "in_app",
        "blood_donation",
        donation_id,
    )
    db.commit()
    return jsonify({"message": f"Donation {status.lower()}."})

